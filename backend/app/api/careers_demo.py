"""Synthetic-only careers prototype. Not a public production intake endpoint."""
import os
import io
import hashlib
from datetime import datetime, timezone
import re
from uuid import UUID, uuid4

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text
from psycopg2.extensions import parse_dsn

from app.core.config import settings
from app.core.exceptions import FileValidationError
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.api.candidate_details import _require_hr_locked
from app.db.database import SessionLocal
from app.db.supabase import get_supabase_client
from app.services.document_processor import document_processor
from app.services.email_demo import MAX_MESSAGE_BYTES, extract_synthetic_attachment

router = APIRouter()
logger = get_logger(__name__)


def require_demo():
    try:
        dsn = parse_dsn(settings.DATABASE_URL)
        host = dsn.get('host', '')
        local = host in ('localhost', '127.0.0.1', '::1') or (host.startswith('/') and ',' not in host)
        safe_dsn = local and dsn.get('dbname', '').endswith('_test') and not any(dsn.get(key) for key in ('hostaddr', 'service', 'servicefile', 'options'))
        safe_environment = not any(os.environ.get(key) for key in ('PGHOSTADDR', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS'))
    except Exception:
        safe_dsn = safe_environment = False
    if (not settings.CAREERS_DEMO_ENABLED or settings.APP_ENV not in ('development', 'testing')
            or not safe_dsn or not safe_environment or settings.STORAGE_BACKEND != 'local'):
        raise HTTPException(404, 'Không khả dụng')


@router.get('/jobs')
def jobs():
    require_demo()
    db = SessionLocal()
    try:
        return [dict(row) for row in db.execute(text("""
            SELECT p.position_id, p.position_code, p.title, p.org_unit, p.work_location,
                   p.work_mode, p.employment_type, p.application_deadline_at,
                   jd.content_text AS description,
                   EXISTS (SELECT 1 FROM app_private.criteria_versions c
                       WHERE c.position_id=p.position_id AND c.jd_version_id=jd.jd_version_id
                         AND c.status='APPROVED') AS can_apply
            FROM app_private.positions p
            JOIN LATERAL (SELECT jd_version_id, content_text FROM app_private.jd_versions
                WHERE position_id=p.position_id ORDER BY version_number DESC LIMIT 1) jd ON TRUE
            WHERE p.status='OPEN' AND p.application_deadline_at > now()
            ORDER BY p.application_deadline_at, p.position_id LIMIT 100
        """)).mappings()]
    finally:
        db.close()


@router.post('/jobs/{position_id}/apply', status_code=202)
async def apply(position_id: UUID, request_id: UUID = Form(...), name: str = Form(...),
                email: str = Form(...), phone: str = Form(''), cv: UploadFile = File(...),
                pool_opt_in: bool = Form(False), pool_token: str = Form('')):
    return await _ingest_demo(position_id, request_id, name, email, phone, cv, pool_opt_in, pool_token, 'CAREERS_DEMO', None)


async def _ingest_demo(position_id: UUID, request_id: UUID, name: str, email: str, phone: str,
                       cv: UploadFile, pool_opt_in: bool, pool_token: str, source: str, actor: str | None):
    require_demo()
    name, email, phone = name.strip(), email.strip(), phone.strip()
    if not 1 <= len(name) <= 200 or len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(phone) > 50:
        raise HTTPException(400, 'Thông tin ứng viên không hợp lệ')
    if pool_opt_in and not re.fullmatch(r'[0-9a-f]{64}', pool_token):
        raise HTTPException(400, 'Mã rút đồng ý demo không hợp lệ')
    filename = os.path.basename((cv.filename or '').replace('\\', '/'))[:200]
    data = await cv.read(settings.MAX_FILE_SIZE_BYTES + 1)
    try:
        mime = await document_processor.validate_file(data, filename, cv.content_type or '')
    except FileValidationError:
        raise HTTPException(400, 'CV không hợp lệ hoặc quá lớn') from None
    if settings.STORAGE_BACKEND not in ('local', 'supabase'):
        raise HTTPException(503, 'Storage không khả dụng')
    storage = get_supabase_client() if settings.STORAGE_BACKEND == 'supabase' else None
    if settings.STORAGE_BACKEND == 'supabase' and not storage:
        raise HTTPException(503, 'Storage không khả dụng')
    db = SessionLocal()
    saved = None
    try:
        pos = str(position_id)
        locked = db.execute(text("SELECT 1 FROM app_private.positions WHERE position_id=:pos FOR UPDATE"), {'pos': pos}).first()
        # Re-read after acquiring the lock, using wall-clock time rather than
        # transaction-start time: the deadline can pass while waiting for it.
        row = db.execute(text("""SELECT status, application_deadline_at > clock_timestamp() AS within_deadline
            FROM app_private.positions WHERE position_id=:pos"""), {'pos': pos}).mappings().first() if locked else None
        if not row or row['status'] != 'OPEN' or not row['within_deadline']:
            raise HTTPException(404, 'Vị trí không còn nhận hồ sơ')
        if source == 'EMAIL_DEMO':
            _require_hr_locked(db, actor, pos, include_admin=True)
        key = f'{source.lower()}:{pos}:{request_id}'
        previous = db.execute(text('SELECT 1 FROM app_private.operations WHERE idempotency_key=:key'), {'key': key}).first()
        if previous:
            return {'message': 'Hồ sơ demo đã được tiếp nhận.'}
        approved = db.execute(text("""SELECT 1 FROM app_private.criteria_versions c
            WHERE c.position_id=:pos AND c.status='APPROVED' AND c.jd_version_id=
              (SELECT jd_version_id FROM app_private.jd_versions WHERE position_id=:pos ORDER BY version_number DESC LIMIT 1)"""), {'pos': pos}).first()
        if not approved:
            raise HTTPException(409, 'Vị trí chưa sẵn sàng nhận hồ sơ demo')
        if db.execute(text("""SELECT 1 FROM app_private.operations WHERE position_id=:pos
            AND capability IN ('CV_PROCESSING','ASSESSMENT','RANKING') AND status IN ('PENDING','PROCESSING')"""), {'pos': pos}).first():
            raise HTTPException(409, 'Vị trí đang xử lý, vui lòng thử lại sau')
        operation = db.execute(text("""INSERT INTO app_private.operations(position_id, capability, status, idempotency_key, requested_by)
            VALUES (:pos,'CV_PROCESSING','PENDING',:key,:actor) RETURNING operation_id"""), {'pos': pos, 'key': key, 'actor': actor}).scalar_one()
        batch = db.execute(text("""INSERT INTO app_private.cv_batches(position_id, operation_id, intake_source, status, total_files,total_size_bytes,uploaded_by)
            VALUES (:pos,:operation,:source,'PROCESSING',1,:size,:actor) RETURNING batch_id"""), {'pos': pos, 'operation': operation, 'source': source, 'size': len(data), 'actor': actor}).scalar_one()
        application = db.execute(text("""INSERT INTO app_private.applications(position_id,source_code,created_by)
            VALUES (:pos,:source,:actor) RETURNING application_id"""), {'pos': pos, 'source': source, 'actor': actor}).scalar_one()
        if pool_opt_in:
            db.execute(text("""INSERT INTO app_private.talent_pool_demo_consents(application_id,notice_version,token_hash,expires_at)
                VALUES (:app,'synthetic-demo-v1',:token_hash,now()+interval '7 days')"""),
                {'app': application, 'token_hash': hashlib.sha256(pool_token.encode('ascii')).hexdigest()})
        ext = '.pdf' if mime == 'application/pdf' else '.docx'
        saved = f'{pos}/{application}/{uuid4()}{ext}'
        if storage:
            storage.storage.from_(settings.SUPABASE_STORAGE_BUCKET_CV).upload(path=saved, file=data, file_options={'content-type': mime})
        else:
            path = os.path.join(settings.LOCAL_STORAGE_PATH, settings.SUPABASE_STORAGE_BUCKET_CV, saved)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            async with aiofiles.open(path, 'wb') as out:
                await out.write(data)
        doc = db.execute(text("""INSERT INTO app_private.application_documents(application_id,document_type,bucket,storage_path,original_filename,mime_type,size_bytes,file_processing_status)
            VALUES (:app,'CV',:bucket,:path,:filename,:mime,:size,'RECEIVED') RETURNING document_id"""),
            {'app': application, 'bucket': settings.SUPABASE_STORAGE_BUCKET_CV, 'path': saved, 'filename': filename, 'mime': mime, 'size': len(data)}).scalar_one()
        db.execute(text("INSERT INTO app_private.application_identities(application_id,display_name,email,phone) VALUES (:app,:name,:email,:phone)"), {'app': application, 'name': name, 'email': email, 'phone': phone or None})
        db.execute(text("INSERT INTO app_private.document_processing_runs(document_id,operation_id,extraction_type,status) VALUES (:doc,:operation,'INITIAL_EXTRACTION','PENDING')"), {'doc': doc, 'operation': operation})
        db.execute(text("""INSERT INTO app_private.cv_batch_items(batch_id,original_filename,declared_mime_type,detected_mime_type,size_bytes,validation_result,application_id)
            VALUES (:batch,:filename,:declared,:mime,:size,'ACCEPTED',:app)"""), {'batch': batch, 'filename': filename, 'declared': cv.content_type, 'mime': mime, 'size': len(data), 'app': application})
        db.execute(text("""INSERT INTO app_private.audit_events(actor_user_id,action_type,object_type,object_id,position_id,outcome,metadata)
            VALUES (:actor,'DEMO_INTAKE','APPLICATION',:app,:pos,'SUCCESS',jsonb_build_object('source',CAST(:source AS text)))"""), {'app': application, 'pos': pos, 'source': source, 'actor': actor})
        db.commit()
        return {'message': 'Hồ sơ demo đã được tiếp nhận.'}
    except Exception:
        db.rollback()
        if saved:
            try:
                if storage:
                    storage.storage.from_(settings.SUPABASE_STORAGE_BUCKET_CV).remove([saved])
                else:
                    os.remove(os.path.join(settings.LOCAL_STORAGE_PATH, settings.SUPABASE_STORAGE_BUCKET_CV, saved))
            except Exception as exc:
                # Cleanup failure must be reconciled by the operator; no PII in logs.
                logger.error('Demo upload cleanup failed', error_type=type(exc).__name__)
        raise
    finally:
        db.close()


class WithdrawDemo(BaseModel):
    token: str = Field(min_length=64, max_length=64, pattern=r'^[0-9a-f]{64}$')


@router.post('/pool/withdraw')
def withdraw_consent(request: WithdrawDemo):
    require_demo()
    db = SessionLocal()
    try:
        # Uniform response for unknown/already-withdrawn tokens. No token in URL/log/audit.
        row = db.execute(text("""UPDATE app_private.talent_pool_demo_consents SET withdrawn_at=clock_timestamp()
            WHERE token_hash=:token_hash AND withdrawn_at IS NULL RETURNING application_id"""),
            {'token_hash': hashlib.sha256(request.token.encode('ascii')).hexdigest()}).first()
        if row:
            db.execute(text("""INSERT INTO app_private.audit_events(action_type, object_type, object_id, outcome)
                VALUES ('TALENT_POOL_DEMO_WITHDRAW','APPLICATION',:id,'SUCCESS')"""), {'id': row[0]})
        db.commit()
        return {'message': 'Nếu mã hợp lệ, lựa chọn demo đã được rút.'}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get('/pool/scan')
def scan_demo_pool(target_position_id: UUID, source_position_id: UUID,
                   current_user: dict = Depends(get_current_user)):
    require_demo()
    target, source, actor = str(target_position_id), str(source_position_id), current_user['user_id']
    if target == source:
        raise HTTPException(400, 'Chọn hai vị trí khác nhau')
    db = SessionLocal()
    try:
        # Stable lock order shared with position edits. Hold permissions and
        # source/consent locks through selection and audit to serialize revoke.
        for position in sorted((target, source)):
            if not db.execute(text('SELECT 1 FROM app_private.positions WHERE position_id=:id FOR SHARE'), {'id': position}).first():
                raise HTTPException(404, 'Không tìm thấy vị trí')
            _require_hr_locked(db, actor, position, include_admin=True)
        ready = db.execute(text("""SELECT 1 FROM app_private.positions p WHERE p.position_id=:id AND p.status='OPEN'
            AND EXISTS(SELECT 1 FROM app_private.criteria_versions c WHERE c.position_id=p.position_id AND c.status='APPROVED'
              AND c.jd_version_id=(SELECT jd_version_id FROM app_private.jd_versions WHERE position_id=p.position_id ORDER BY version_number DESC LIMIT 1))"""), {'id': target}).first()
        if not ready:
            raise HTTPException(409, 'Vị trí đích chưa OPEN hoặc rubric chưa được duyệt')
        # Fail closed for closed source positions, any open deletion case,
        # unprocessed CVs, expired/withdrawn consent and non-demo applications.
        rows = db.execute(text("""SELECT a.application_id, a.position_id, i.display_name, c.expires_at
            FROM app_private.talent_pool_demo_consents c
            JOIN app_private.applications a ON a.application_id=c.application_id
            JOIN app_private.positions p ON p.position_id=a.position_id
            JOIN app_private.application_identities i ON i.application_id=a.application_id
            WHERE p.position_id=:source AND p.status IN ('OPEN','PAUSED') AND a.source_code='CAREERS_DEMO'
              AND c.withdrawn_at IS NULL AND c.expires_at > clock_timestamp()
              AND NOT EXISTS (SELECT 1 FROM app_private.application_retention_cases r
                  WHERE r.application_id=a.application_id AND r.status <> 'CANCELLED')
              AND EXISTS (SELECT 1 FROM app_private.application_documents d
                  WHERE d.application_id=a.application_id AND d.document_type='CV' AND d.file_processing_status='COMPLETED')
            ORDER BY a.application_id LIMIT 100 FOR SHARE OF c, a"""), {'source': source}).mappings().all()
        rows = [row for row in rows if row['expires_at'] > datetime.now(timezone.utc)]
        db.execute(text("""INSERT INTO app_private.audit_events(actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
            VALUES (:actor,'TALENT_POOL_DEMO_SCAN','POSITION',:target,:target,'SUCCESS',jsonb_build_object('source_position_id',CAST(:source AS text),'count',:count))"""),
            {'actor': actor, 'target': target, 'source': source, 'count': len(rows)})
        db.commit()
        return {'items': [dict(row) for row in rows], 'note': 'DEMO: chưa xếp hạng, chưa đánh giá độ phù hợp.'}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post('/email/ingest', status_code=202)
async def ingest_offline_email(request_id: UUID = Form(...), message: UploadFile = File(...),
                               current_user: dict = Depends(get_current_user)):
    require_demo()
    raw = await message.read(MAX_MESSAGE_BYTES + 1)
    db = SessionLocal()
    try:
        codes = {r[0] for r in db.execute(text('SELECT position_code FROM app_private.positions'))}
        result, filename, content = extract_synthetic_attachment(raw, codes)
        if result['status'] != 'CANDIDATE' or not filename or not content:
            return {'status': 'REVIEW', 'reason': result.get('reason', 'ATTACHMENT_INVALID')}
        position = db.execute(text('SELECT position_id FROM app_private.positions WHERE position_code=:code'),
                              {'code': result['position_code']}).scalar_one_or_none()
    finally:
        db.close()
    if not position:
        raise HTTPException(404, 'Vị trí không khả dụng')
    # From header is unverified and deliberately ignored. No pool consent is inferred.
    upload = UploadFile(file=io.BytesIO(content), filename=filename)
    result = await _ingest_demo(position, request_id, 'Email demo (chưa xác minh)',
                                'email-demo@example.invalid', '', upload, False, '',
                                'EMAIL_DEMO', current_user['user_id'])
    return {'status': 'ACCEPTED', 'message': result['message']}
