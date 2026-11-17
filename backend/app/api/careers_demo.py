"""Synthetic-only careers prototype. Not a public production intake endpoint."""
import os
import re
from uuid import UUID, uuid4

import aiofiles
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import text
from psycopg2.extensions import parse_dsn

from app.core.config import settings
from app.core.exceptions import FileValidationError
from app.core.logging import get_logger
from app.db.database import SessionLocal
from app.db.supabase import get_supabase_client
from app.services.document_processor import document_processor

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
                email: str = Form(...), phone: str = Form(''), cv: UploadFile = File(...)):
    require_demo()
    name, email, phone = name.strip(), email.strip(), phone.strip()
    if not 1 <= len(name) <= 200 or len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(phone) > 50:
        raise HTTPException(400, 'Thông tin ứng viên không hợp lệ')
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
        key = f'careers-demo:{pos}:{request_id}'
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
        operation = db.execute(text("""INSERT INTO app_private.operations(position_id, capability, status, idempotency_key)
            VALUES (:pos,'CV_PROCESSING','PENDING',:key) RETURNING operation_id"""), {'pos': pos, 'key': key}).scalar_one()
        batch = db.execute(text("""INSERT INTO app_private.cv_batches(position_id, operation_id, intake_source, status, total_files,total_size_bytes)
            VALUES (:pos,:operation,'CAREERS_DEMO','PROCESSING',1,:size) RETURNING batch_id"""), {'pos': pos, 'operation': operation, 'size': len(data)}).scalar_one()
        application = db.execute(text("""INSERT INTO app_private.applications(position_id,source_code)
            VALUES (:pos,'CAREERS_DEMO') RETURNING application_id"""), {'pos': pos}).scalar_one()
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
        db.execute(text("""INSERT INTO app_private.audit_events(action_type,object_type,object_id,position_id,outcome,metadata)
            VALUES ('CAREERS_DEMO_APPLY','APPLICATION',:app,:pos,'SUCCESS','{"source":"CAREERS_DEMO"}'::jsonb)"""), {'app': application, 'pos': pos})
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
