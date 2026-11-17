"""Gated synthetic-only intake over real DB/Storage/clamd (not production)."""
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.exceptions import FileValidationError
from app.db.database import SessionLocal
from app.services.document_processor import document_processor
from app.services.careers_storage import destination, store as _store
from app.services.malware_scan import ScanVerdict, scan_bytes
from app.services.talent_pool import create_consent

router = APIRouter()
TEST_NOTICE = 'synthetic-intake-test-v1'


def _fingerprint(request_id, position_id, name, email, phone, filename, data, pool_token):
    payload = json.dumps([str(request_id), str(position_id), name, email, phone, filename,
                          hashlib.sha256(data).hexdigest(), pool_token], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


@router.post('/jobs/{position_id}/apply', status_code=202)
async def apply(position_id: UUID, request_id: UUID = Form(...), name: str = Form(...),
                email: str = Form(...), phone: str = Form(''), cv: UploadFile = File(...),
                pool_opt_in: bool = Form(False), pool_token: str = Form('')):
    if not settings.PUBLIC_CAREERS_ENABLED or not settings.PUBLIC_CAREERS_TEST_INTAKE_ENABLED:
        raise HTTPException(404, 'Không khả dụng')
    if not settings.CLAMAV_UNIX_SOCKET.startswith('/'):
        raise HTTPException(503, 'Dịch vụ kiểm tra tệp chưa sẵn sàng')
    if pool_opt_in and not settings.TALENT_POOL_STORAGE_READY:
        raise HTTPException(503, 'Talent Pool chưa sẵn sàng')
    name, phone = name.strip(), phone.strip()
    try:
        email = validate_email(email.strip(), check_deliverability=False, test_environment=True).normalized.lower()
    except EmailNotValidError:
        raise HTTPException(400, 'Thông tin ứng viên không hợp lệ') from None
    if (not name or len(name) > 200 or len(phone) > 50 or len(email) > 254
            or not email.endswith('@example.test')):
        raise HTTPException(400, 'Vòng thử nghiệm chỉ chấp nhận dữ liệu tổng hợp với email @example.test')
    if (pool_opt_in and not re.fullmatch(r'[0-9a-f]{64}', pool_token)) or (not pool_opt_in and pool_token):
        raise HTTPException(400, 'Mã rút lựa chọn không hợp lệ')
    filename = os.path.basename((cv.filename or '').replace('\\', '/'))[:200]
    data = await cv.read(settings.MAX_FILE_SIZE_BYTES + 1)
    # Antivirus always runs before ZIP/PDF validation or extraction. Scanner
    # errors/limits/timeouts fail closed, not clean.
    verdict = await run_in_threadpool(scan_bytes, data, socket_path=settings.CLAMAV_UNIX_SOCKET,
                                      max_bytes=settings.MAX_FILE_SIZE_BYTES)
    if verdict != ScanVerdict.CLEAN:
        raise HTTPException(400 if verdict == ScanVerdict.INFECTED else 503,
                            'Không thể tiếp nhận tệp' if verdict == ScanVerdict.INFECTED else 'Dịch vụ kiểm tra tệp chưa sẵn sàng')
    try:
        mime = await document_processor.validate_file(data, filename, cv.content_type or '')
    except FileValidationError:
        raise HTTPException(400, 'CV không hợp lệ hoặc quá lớn') from None
    digest = _fingerprint(request_id, position_id, name, email, phone, filename, data, pool_token)
    ext = '.pdf' if mime == 'application/pdf' else '.docx'
    path = f'careers/{position_id}/{uuid4()}{ext}'
    pos, req = str(position_id), str(request_id)
    try:
        backend, bucket, identity = destination()
    except ValueError:
        raise HTTPException(503, 'Storage chưa sẵn sàng') from None
    return await run_in_threadpool(_commit_intake, pos, req, digest, path, name, email, phone,
                                   filename, data, mime, cv.content_type, pool_opt_in, pool_token, backend, bucket, identity)


def _commit_intake(pos, req, digest, path, name, email, phone, filename, data, mime, declared_type, pool_opt_in, pool_token, backend, bucket, identity):
    # Persist the intended path before external I/O. Stale STAGING receipts are
    # a durable reconciliation queue, not proof that an object exists.
    db = SessionLocal()
    try:
        if not db.execute(text('SELECT 1 FROM app_private.positions WHERE position_id=:id'), {'id': pos}).first():
            raise HTTPException(404, 'Vị trí không còn nhận hồ sơ')
        db.execute(text("""INSERT INTO app_private.careers_intake_receipts(request_id,position_id,fingerprint,storage_path,state,storage_backend,storage_bucket,storage_identity)
            VALUES (:req,:pos,:digest,:path,'STAGING',:backend,:bucket,:identity) ON CONFLICT (request_id) DO NOTHING"""),
            {'req': req, 'pos': pos, 'digest': digest, 'path': path, 'backend': backend, 'bucket': bucket, 'identity': identity})
        db.commit()
        receipt = db.execute(text("""SELECT position_id,fingerprint,storage_path,state,storage_backend,storage_bucket,storage_identity FROM app_private.careers_intake_receipts
            WHERE request_id=:req FOR UPDATE"""), {'req': req}).mappings().one()
        if str(receipt['position_id']) != pos or receipt['fingerprint'] != digest:
            raise HTTPException(409, 'Mã yêu cầu đã được sử dụng cho nội dung khác')
        if receipt['state'] == 'COMMITTED':
            return {'message': 'Hồ sơ thử nghiệm đã được tiếp nhận.'}
        if receipt['state'] == 'ABANDONED':
            raise HTTPException(410, 'Yêu cầu thử nghiệm đã hết hạn, vui lòng tạo yêu cầu mới')
        if (receipt['storage_backend'], receipt['storage_bucket'], receipt['storage_identity']) != (backend, bucket, identity):
            raise HTTPException(503, 'Cấu hình Storage đã thay đổi; cần đối soát')
        locked = db.execute(text('SELECT 1 FROM app_private.positions WHERE position_id=:id FOR UPDATE'), {'id': pos}).first()
        current = db.execute(text("SELECT status, application_deadline_at > clock_timestamp() AS eligible FROM app_private.positions WHERE position_id=:id"), {'id': pos}).mappings().first() if locked else None
        if not current or current['status'] != 'OPEN' or not current['eligible']:
            raise HTTPException(404, 'Vị trí không còn nhận hồ sơ')
        approved = db.execute(text("""SELECT 1 FROM app_private.criteria_versions c WHERE c.position_id=:pos AND c.status='APPROVED'
            AND c.jd_version_id=(SELECT jd_version_id FROM app_private.jd_versions WHERE position_id=:pos ORDER BY version_number DESC LIMIT 1)"""), {'pos': pos}).first()
        if not approved:
            raise HTTPException(409, 'Vị trí chưa sẵn sàng nhận hồ sơ')
        if db.execute(text("""SELECT 1 FROM app_private.operations WHERE position_id=:pos AND capability IN
            ('CV_PROCESSING','ASSESSMENT','RANKING') AND status IN ('PENDING','PROCESSING')"""), {'pos': pos}).first():
            raise HTTPException(409, 'Vị trí đang xử lý, vui lòng thử lại sau')
        try:
            _store(backend, bucket, identity, receipt['storage_path'], data, mime)
        except Exception:
            # Do not delete on uncertain upload/commit outcome; the committed
            # receipt permits explicit reconciliation or identical retry.
            raise HTTPException(503, 'Storage chưa sẵn sàng, vui lòng thử lại') from None
        operation = db.execute(text("""INSERT INTO app_private.operations(position_id,capability,status,idempotency_key,requested_by)
            VALUES (:pos,'CV_PROCESSING','PENDING',:key,NULL) RETURNING operation_id"""), {'pos': pos, 'key': f'careers:{req}'}).scalar_one()
        batch = db.execute(text("""INSERT INTO app_private.cv_batches(position_id,operation_id,intake_source,status,total_files,total_size_bytes,uploaded_by)
            VALUES (:pos,:op,'CAREERS','PROCESSING',1,:size,NULL) RETURNING batch_id"""), {'pos': pos, 'op': operation, 'size': len(data)}).scalar_one()
        application = db.execute(text("""INSERT INTO app_private.applications(position_id,source_code,created_by)
            VALUES (:pos,'CAREERS',NULL) RETURNING application_id"""), {'pos': pos}).scalar_one()
        db.execute(text("INSERT INTO app_private.application_identities(application_id,display_name,email,phone) VALUES (:app,:name,:email,:phone)"),
                   {'app': application, 'name': name, 'email': email, 'phone': phone or None})
        document = db.execute(text("""INSERT INTO app_private.application_documents(application_id,document_type,bucket,storage_path,original_filename,mime_type,size_bytes,file_processing_status)
            VALUES (:app,'CV',:bucket,:path,:name,:mime,:size,'RECEIVED') RETURNING document_id"""),
            {'app': application, 'bucket': receipt['storage_bucket'], 'path': receipt['storage_path'], 'name': filename, 'mime': mime, 'size': len(data)}).scalar_one()
        db.execute(text("INSERT INTO app_private.document_processing_runs(document_id,operation_id,extraction_type,status) VALUES (:doc,:op,'INITIAL_EXTRACTION','PENDING')"), {'doc': document, 'op': operation})
        db.execute(text("""INSERT INTO app_private.cv_batch_items(batch_id,original_filename,declared_mime_type,detected_mime_type,size_bytes,validation_result,application_id)
            VALUES (:batch,:name,:declared,:mime,:size,'ACCEPTED',:app)"""), {'batch': batch, 'name': filename, 'declared': declared_type, 'mime': mime, 'size': len(data), 'app': application})
        if pool_opt_in:
            expiry = datetime.now(timezone.utc) + timedelta(days=7)
            create_consent(db, application_id=str(application), notice_version=TEST_NOTICE,
                           consent_expires_at=expiry, retention_expires_at=expiry, withdrawal_token=pool_token)
        db.execute(text("""UPDATE app_private.careers_intake_receipts SET state='COMMITTED',application_id=:app,updated_at=clock_timestamp() WHERE request_id=:req"""), {'app': application, 'req': req})
        db.execute(text("""INSERT INTO app_private.audit_events(action_type,object_type,object_id,position_id,outcome,metadata)
            VALUES ('CAREERS_TEST_APPLY','APPLICATION',:app,:pos,'SUCCESS',jsonb_build_object('source','CAREERS'))"""), {'app': application, 'pos': pos})
        db.commit()
        return {'message': 'Hồ sơ thử nghiệm đã được tiếp nhận.'}
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Yêu cầu hoặc mã rút lựa chọn đã được sử dụng') from None
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
