"""F2.04: HR Lead only. Inspection never changes AI or recruitment decisions."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.core.config import settings
from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.services.quality import generate_samples, read_storage
from app.services.review_access import audit, require_scope

router = APIRouter()


class FlagInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    category: Literal['INCORRECT_EVIDENCE', 'MISSING_CONTENT', 'INCORRECT_FACT', 'OCR_ERROR', 'INCORRECT_MATCH']
    criterion_result_id: UUID | None = None
    note: str = Field(min_length=1, max_length=2000)


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=0)
    verdict: Literal['CORRECT', 'ISSUES_FOUND']
    flags: list[FlagInput] = Field(default_factory=list, max_length=100)


class ClaimInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=0)


def _case(db, inspection_id: UUID, user_id: str, lock=False):
    row = db.execute(text('SELECT * FROM app_private.quality_inspections WHERE inspection_id=:id' +
                          (' FOR UPDATE' if lock else '')), {'id': str(inspection_id)}).mappings().first()
    if not row:
        raise HTTPException(404, 'Không tìm thấy kiểm định')
    require_scope(db, user_id, str(row['position_id']), quality=True)
    return dict(row)


@router.post('/positions/{position_id}/sample')
def sample(position_id: UUID, user: dict = Depends(get_current_user)):
    with SessionLocal.begin() as db:
        require_scope(db, user['user_id'], str(position_id), quality=True)
        if not db.execute(text('SELECT 1 FROM app_private.positions WHERE position_id=:p'), {'p': str(position_id)}).first():
            raise HTTPException(404, 'Không tìm thấy vị trí')
        count = generate_samples(db, str(position_id))
        audit(db, user['user_id'], 'GENERATE_QA_SAMPLES', 'POSITION', str(position_id), str(position_id))
        return {'created_count': count}


@router.get('/inspections')
def queue(position_id: UUID | None = None, status: Literal['PENDING', 'IN_REVIEW', 'COMPLETED'] | None = None,
          limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), user: dict = Depends(get_current_user)):
    with SessionLocal() as db:
        # Reject HM/recruiters/admin-only rather than returning a misleading empty queue.
        if not db.execute(text("""
            SELECT 1 FROM app_private.user_role_assignments WHERE user_id=:u AND role_code='HR_LEAD' AND revoked_at IS NULL
            UNION ALL SELECT 1 FROM app_private.position_assignments WHERE user_id=:u AND position_role='HR_LEAD' AND revoked_at IS NULL
        """), {'u': user['user_id']}).first():
            raise HTTPException(403, 'Chỉ HR Lead có quyền kiểm định')
        rows = db.execute(text("""
            SELECT q.*,p.title AS position_title,a.application_id,i.display_name AS candidate_name,
                   a.evidence_coverage,up.display_name AS reviewer_name
            FROM app_private.quality_inspections q
            JOIN app_private.positions p ON p.position_id=q.position_id
            JOIN app_private.assessment_runs a ON a.assessment_id=q.assessment_id
            LEFT JOIN app_private.application_identities i ON i.application_id=a.application_id
            LEFT JOIN app_private.user_profiles up ON up.user_id=q.assigned_to
            WHERE (CAST(:p AS uuid) IS NULL OR q.position_id=CAST(:p AS uuid)) AND (:s IS NULL OR q.status=:s)
              AND (EXISTS (SELECT 1 FROM app_private.user_role_assignments WHERE user_id=:u AND role_code='HR_LEAD' AND revoked_at IS NULL)
                OR EXISTS (SELECT 1 FROM app_private.position_assignments WHERE user_id=:u AND position_role='HR_LEAD'
                           AND revoked_at IS NULL AND position_id=q.position_id))
            ORDER BY q.created_at DESC,q.inspection_id LIMIT :limit OFFSET :offset
        """), {'u': user['user_id'], 'p': str(position_id) if position_id else None, 's': status,
                'limit': limit, 'offset': offset}).mappings().all()
        return [dict(r) for r in rows]


@router.get('/inspections/{inspection_id}')
def detail(inspection_id: UUID, user: dict = Depends(get_current_user)):
    with SessionLocal.begin() as db:
        case = _case(db, inspection_id, user['user_id'])
        assessment = dict(db.execute(text('SELECT * FROM app_private.assessment_runs WHERE assessment_id=:id'),
                                     {'id': case['assessment_id']}).mappings().one())
        findings = [dict(r) for r in db.execute(text("""
            SELECT r.*,c.name,c.category,
                COALESCE((SELECT jsonb_agg(jsonb_build_object('evidence_id',e.evidence_id,'quote',e.verbatim_quote,
                    'page_number',e.page_number,'verification_status',e.verification_status))
                  FROM app_private.evidence_items e WHERE e.criterion_result_id=r.result_id),'[]'::jsonb) AS evidence
            FROM app_private.criterion_assessment_results r JOIN app_private.criteria_items c ON c.criterion_id=r.criterion_id
            WHERE r.assessment_id=:id ORDER BY c.display_order,c.criterion_id
        """), {'id': case['assessment_id']}).mappings()]
        profile = [dict(r) for r in db.execute(text('SELECT fact_type,fact_value,source_page_number FROM app_private.profile_facts WHERE profile_version_id=:id'),
                                              {'id': assessment['profile_version_id']}).mappings()]
        flags = [dict(r) for r in db.execute(text('SELECT * FROM app_private.quality_flags WHERE inspection_id=:id'), {'id': str(inspection_id)}).mappings()]
        events = [dict(r) for r in db.execute(text('SELECT * FROM app_private.quality_inspection_events WHERE inspection_id=:id ORDER BY created_at,event_id'),
                                             {'id': str(inspection_id)}).mappings()]
        audit(db, user['user_id'], 'VIEW_QA_INSPECTION', 'QUALITY_INSPECTION', str(inspection_id), str(case['position_id']))
        return {'case': case, 'assessment': assessment, 'findings': findings, 'facts': profile, 'flags': flags, 'events': events}


def _document(db, case):
    return db.execute(text("""
        SELECT d.* FROM app_private.assessment_runs a JOIN app_private.profile_versions p ON p.profile_version_id=a.profile_version_id
        JOIN app_private.application_documents d ON d.document_id=p.source_document_id WHERE a.assessment_id=:a
    """), {'a': case['assessment_id']}).mappings().one()


@router.get('/inspections/{inspection_id}/source')
def source(inspection_id: UUID, user: dict = Depends(get_current_user)):
    with SessionLocal.begin() as db:
        case = _case(db, inspection_id, user['user_id'])
        document = _document(db, case)
        content = read_storage(document['bucket'], document['storage_path'])
        audit(db, user['user_id'], 'VIEW_QA_CV', 'QUALITY_INSPECTION', str(inspection_id), str(case['position_id']))
        # Proxy bytes, never issue an irrevocable signed URL to a reviewer.
        return Response(content, media_type=document['mime_type'], headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


@router.get('/inspections/{inspection_id}/feedback')
def feedback(inspection_id: UUID, user: dict = Depends(get_current_user)):
    """Explicit, audited handoff to engineering; never sends feedback externally."""
    with SessionLocal.begin() as db:
        case = _case(db, inspection_id, user['user_id'])
        rows = db.execute(text('SELECT category,criterion_result_id,note FROM app_private.quality_flags WHERE inspection_id=:id ORDER BY created_at,flag_id'),
                          {'id': str(inspection_id)}).mappings().all()
        audit(db, user['user_id'], 'EXPORT_QA_FEEDBACK', 'QUALITY_INSPECTION', str(inspection_id), str(case['position_id']))
        return {'inspection_id': inspection_id, 'assessment_id': case['assessment_id'], 'policy_version': case['policy_version'],
                'status': case['status'], 'verdict': case['verdict'], 'flags': [dict(r) for r in rows]}


@router.get('/inspections/{inspection_id}/text')
def extracted_text(inspection_id: UUID, user: dict = Depends(get_current_user)):
    with SessionLocal.begin() as db:
        case = _case(db, inspection_id, user['user_id'])
        document = _document(db, case)
        # The extraction run is pinned at selection time by the assessment's creation time.
        run = db.execute(text("""
            SELECT COALESCE(a.source_extracted_text_path,d.extracted_text_storage_path) AS path,
                   a.source_extracted_text_path IS NOT NULL AS exact_snapshot,d.ocr_mean_confidence
            FROM app_private.document_processing_runs d
            JOIN app_private.assessment_runs a ON a.assessment_id=:a
            WHERE d.document_id=:d AND d.status='COMPLETED' AND d.created_at<=a.created_at
              AND (a.source_extracted_text_path IS NULL OR d.extracted_text_storage_path=a.source_extracted_text_path)
              AND d.extracted_text_storage_path IS NOT NULL ORDER BY d.created_at DESC LIMIT 1
        """), {'a': case['assessment_id'], 'd': document['document_id']}).mappings().first()
        if not run:
            raise HTTPException(404, 'Chưa có văn bản trích xuất cho bản đánh giá này')
        content = read_storage(settings.SUPABASE_STORAGE_BUCKET_EXTRACTED, run['path']).decode('utf-8', errors='replace')
        audit(db, user['user_id'], 'VIEW_QA_TEXT', 'QUALITY_INSPECTION', str(inspection_id), str(case['position_id']))
        return {'text': content, 'exact_snapshot': run['exact_snapshot'], 'ocr_mean_confidence': run['ocr_mean_confidence']}


@router.post('/inspections/{inspection_id}/claim')
def claim(inspection_id: UUID, request: ClaimInput, user: dict = Depends(get_current_user)):
    with SessionLocal.begin() as db:
        case = _case(db, inspection_id, user['user_id'], lock=True)
        if case['status'] != 'PENDING' or case['revision'] != request.expected_revision:
            raise HTTPException(409, 'Kiểm định đã được nhận hoặc thay đổi. Vui lòng tải lại.')
        db.execute(text("UPDATE app_private.quality_inspections SET assigned_to=:u,status='IN_REVIEW',revision=revision+1 WHERE inspection_id=:id"),
                   {'u': user['user_id'], 'id': str(inspection_id)})
        db.execute(text("INSERT INTO app_private.quality_inspection_events(inspection_id,actor_id,action) VALUES (:id,:u,'CLAIM')"),
                   {'id': str(inspection_id), 'u': user['user_id']})
        audit(db, user['user_id'], 'CLAIM_QA_INSPECTION', 'QUALITY_INSPECTION', str(inspection_id), str(case['position_id']))
        return {'revision': case['revision'] + 1}


@router.post('/inspections/{inspection_id}/submit')
def submit(inspection_id: UUID, request: ReviewInput, user: dict = Depends(get_current_user)):
    if (request.verdict == 'ISSUES_FOUND') != bool(request.flags) or any(not f.note.strip() for f in request.flags):
        raise HTTPException(400, 'Kết luận có lỗi cần ít nhất một phản hồi; kết luận đúng không kèm lỗi')
    with SessionLocal.begin() as db:
        case = _case(db, inspection_id, user['user_id'], lock=True)
        if case['status'] != 'IN_REVIEW' or str(case['assigned_to']) != user['user_id'] or case['revision'] != request.expected_revision:
            raise HTTPException(409, 'Kiểm định không thuộc bạn hoặc đã thay đổi. Vui lòng tải lại.')
        for flag in request.flags:
            if flag.criterion_result_id and not db.execute(text('SELECT 1 FROM app_private.criterion_assessment_results WHERE result_id=:r AND assessment_id=:a'),
                                                          {'r': str(flag.criterion_result_id), 'a': case['assessment_id']}).first():
                raise HTTPException(400, 'Tiêu chí không thuộc bản đánh giá đang kiểm định')
            db.execute(text("""INSERT INTO app_private.quality_flags(inspection_id,category,criterion_result_id,note)
                               VALUES (:id,:c,:r,:n)"""), {'id': str(inspection_id), 'c': flag.category,
                               'r': str(flag.criterion_result_id) if flag.criterion_result_id else None, 'n': flag.note.strip()})
        db.execute(text("UPDATE app_private.quality_inspections SET status='COMPLETED',verdict=:v,completed_at=NOW(),revision=revision+1 WHERE inspection_id=:id"),
                   {'id': str(inspection_id), 'v': request.verdict})
        db.execute(text("INSERT INTO app_private.quality_inspection_events(inspection_id,actor_id,action) VALUES (:id,:u,'SUBMIT')"),
                   {'id': str(inspection_id), 'u': user['user_id']})
        audit(db, user['user_id'], 'SUBMIT_QA_INSPECTION', 'QUALITY_INSPECTION', str(inspection_id), str(case['position_id']))
        return {'status': 'COMPLETED', 'revision': case['revision'] + 1}
