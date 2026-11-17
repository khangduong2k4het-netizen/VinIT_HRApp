"""Separate consent withdrawal and authorized, non-ranking rediscovery."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.api.candidate_details import _require_hr_locked
from app.core.config import settings
from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.services.talent_pool import hash_token

router = APIRouter()


def require_storage():
    if not settings.TALENT_POOL_STORAGE_READY:
        raise HTTPException(404, 'Không khả dụng', headers={'Cache-Control': 'no-store'})


class Withdrawal(BaseModel):
    model_config = ConfigDict(extra='forbid')
    token: str = Field(min_length=64, max_length=64, pattern=r'^[0-9a-f]{64}$')


@router.post('/withdraw')
def withdraw(request: Withdrawal, response: Response):
    # Remains available when rediscovery is disabled: withdrawal is a right,
    # not contingent on enabling search. Storage must be provisioned separately.
    require_storage()
    response.headers['Cache-Control'] = 'no-store'
    db = SessionLocal()
    try:
        row = db.execute(text("""UPDATE app_private.talent_pool_consents
            SET withdrawn_at=clock_timestamp()
            WHERE token_hash=:token AND withdrawn_at IS NULL RETURNING application_id"""),
            {'token': hash_token(request.token)}).first()
        if row:
            db.execute(text("""INSERT INTO app_private.audit_events(action_type, object_type, object_id, outcome)
                VALUES ('TALENT_POOL_WITHDRAW','APPLICATION',:id,'SUCCESS')"""), {'id': row[0]})
        db.commit()
        return {'message': 'Nếu mã hợp lệ, lựa chọn Talent Pool đã được rút.'}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get('/scan')
def scan(response: Response, target_position_id: UUID, source_position_id: UUID,
         cursor: UUID | None = None, limit: int = Query(25, ge=1, le=100),
         current_user: dict = Depends(get_current_user)):
    require_storage()
    if not settings.TALENT_POOL_REDISCOVERY_ENABLED:
        raise HTTPException(404, 'Không khả dụng', headers={'Cache-Control': 'no-store'})
    response.headers['Cache-Control'] = 'no-store'
    target, source, actor = str(target_position_id), str(source_position_id), current_user['user_id']
    if target == source:
        raise HTTPException(400, 'Chọn hai vị trí khác nhau')
    db = SessionLocal()
    try:
        # Locks match position/retention workflows; check both HR scopes while
        # holding locks, preventing concurrent revocation and retention creation.
        for position in sorted((target, source)):
            if not db.execute(text('SELECT 1 FROM app_private.positions WHERE position_id=:id FOR SHARE'), {'id': position}).first():
                raise HTTPException(404, 'Không tìm thấy vị trí')
            _require_hr_locked(db, actor, position, include_admin=True)
        ready = db.execute(text("""SELECT 1 FROM app_private.positions p WHERE p.position_id=:id AND p.status='OPEN'
            AND EXISTS(SELECT 1 FROM app_private.criteria_versions c WHERE c.position_id=p.position_id AND c.status='APPROVED'
              AND c.jd_version_id=(SELECT jd_version_id FROM app_private.jd_versions WHERE position_id=p.position_id ORDER BY version_number DESC LIMIT 1))"""), {'id': target}).first()
        if not ready:
            raise HTTPException(409, 'Vị trí đích chưa OPEN hoặc rubric chưa được duyệt')
        rows = db.execute(text("""SELECT a.application_id, a.position_id, i.display_name,
                   c.consent_expires_at, c.retention_expires_at
            FROM app_private.talent_pool_consents c
            JOIN app_private.applications a ON a.application_id=c.application_id
            JOIN app_private.positions p ON p.position_id=a.position_id
            JOIN app_private.application_identities i ON i.application_id=a.application_id
            WHERE p.position_id=:source AND p.status IN ('OPEN','PAUSED')
              AND c.withdrawn_at IS NULL AND c.consent_expires_at > clock_timestamp()
              AND c.retention_expires_at > clock_timestamp()
              AND (:cursor IS NULL OR a.application_id > CAST(:cursor AS uuid))
              AND NOT EXISTS (SELECT 1 FROM app_private.application_retention_cases r
                  WHERE r.application_id=a.application_id AND r.status <> 'CANCELLED')
              AND EXISTS (SELECT 1 FROM app_private.application_documents d
                  WHERE d.application_id=a.application_id AND d.document_type='CV' AND d.file_processing_status='COMPLETED')
            ORDER BY a.application_id LIMIT :limit FOR SHARE OF c, a"""),
            {'source': source, 'cursor': str(cursor) if cursor else None, 'limit': limit + 1}).mappings().all()
        now = datetime.now(timezone.utc)
        # Keep the cursor based on scanned rows even if a consent expires
        # while this request is running; otherwise eligible later rows vanish.
        scanned = rows[:limit]
        page = [r for r in scanned if r['consent_expires_at'] > now and r['retention_expires_at'] > now]
        db.execute(text("""INSERT INTO app_private.audit_events(actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
            VALUES (:actor,'TALENT_POOL_SCAN','POSITION',:target,:target,'SUCCESS',jsonb_build_object('source_position_id',CAST(:source AS text),'count',:count))"""),
            {'actor': actor, 'target': target, 'source': source, 'count': len(page)})
        db.commit()
        return {'items': [dict(row) for row in page],
                'next_cursor': str(scanned[-1]['application_id']) if len(rows) > limit else None,
                'note': 'Danh sách đủ điều kiện; không phải đánh giá hay xếp hạng.'}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
