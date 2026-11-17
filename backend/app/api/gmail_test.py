"""Manual read-only Gmail test ingestion. No automatic polling or mailbox mutation."""
import asyncio
from email import policy
from email.parser import BytesParser
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text

from app.api.careers_intake import _commit_intake, _fingerprint
from app.core.config import settings
from app.core.exceptions import FileValidationError
from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.services import gmail_test_client
from app.services.careers_storage import destination
from app.services.document_processor import document_processor
from app.services.email_demo import extract_synthetic_attachment
from app.services.malware_scan import ScanVerdict, scan_bytes
from app.services.spam_scan import SpamVerdict, scan_message

router = APIRouter()


def _ready():
    if not settings.GMAIL_TEST_INGEST_ENABLED:
        raise HTTPException(404, 'Không khả dụng')
    if (not settings.CLAMAV_UNIX_SOCKET.startswith('/')
            or (not settings.GMAIL_TEST_GMAIL_SPAM_ONLY and not settings.SPAMD_UNIX_SOCKET.startswith('/'))):
        raise HTTPException(503, 'Dịch vụ kiểm tra email chưa sẵn sàng')


def _spam_mode():
    return 'GMAIL_LABELS_ONLY_TEST' if settings.GMAIL_TEST_GMAIL_SPAM_ONLY else 'SPAMD'


def _require_lead(db, user_id: str):
    active = db.execute(text("SELECT account_status FROM app_private.user_profiles WHERE user_id=:id FOR SHARE"), {'id': user_id}).scalar_one_or_none()
    roles = db.execute(text("""SELECT role_code FROM app_private.user_role_assignments
        WHERE user_id=:id AND revoked_at IS NULL AND role_code IN ('HR_LEAD','ADMIN') FOR SHARE"""), {'id': user_id}).all()
    if active != 'ACTIVE' or not roles:
        raise HTTPException(403, 'Chỉ HR Lead hoặc quản trị viên được xử lý Gmail thử nghiệm')


def _process_message(db, session, mailbox: str, message_id: str) -> tuple[str, str | None, str | None]:
    """Return safe status, reason and optional app ID. Caller owns row lock."""
    labels, raw = gmail_test_client.fetch_message(session, message_id)
    if {'SPAM', 'TRASH'} & set(labels):
        return 'SPAM', 'GMAIL_SPAM_OR_TRASH', None
    if raw is None:
        return 'REVIEW', 'MESSAGE_TOO_LARGE', None
    virus = scan_bytes(raw, socket_path=settings.CLAMAV_UNIX_SOCKET, max_bytes=gmail_test_client.MAX_RAW_BYTES)
    if virus == ScanVerdict.INFECTED:
        return 'MALWARE', 'MALWARE', None
    if virus != ScanVerdict.CLEAN:
        return 'REVIEW', 'ANTIVIRUS_UNAVAILABLE', None
    if not settings.GMAIL_TEST_GMAIL_SPAM_ONLY:
        spam = scan_message(raw, socket_path=settings.SPAMD_UNIX_SOCKET, max_bytes=gmail_test_client.MAX_RAW_BYTES)
        if spam == SpamVerdict.SPAM:
            return 'SPAM', 'SPAM_FILTER', None
        if spam != SpamVerdict.HAM:
            return 'REVIEW', 'SPAM_FILTER_UNAVAILABLE', None
    # No MIME parsing before antivirus and the configured spam gate. The marker is merely an
    # accidental-ingestion guard, NOT proof that a message contains fake data.
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
        subject = str(message.get('Subject', '')).strip()
        if message.defects or not subject.startswith('[HRA-TEST] '):
            return 'REVIEW', 'SYNTHETIC_MARKER_REQUIRED', None
        codes = {r[0] for r in db.execute(text('SELECT position_code FROM app_private.positions')) if r[0]}
        result, filename, content = extract_synthetic_attachment(raw, codes)
        if result['status'] != 'CANDIDATE' or not filename or not content:
            return 'REVIEW', result.get('reason', 'ATTACHMENT_INVALID'), None
        attachment_verdict = scan_bytes(content, socket_path=settings.CLAMAV_UNIX_SOCKET, max_bytes=settings.MAX_FILE_SIZE_BYTES)
        if attachment_verdict == ScanVerdict.INFECTED:
            return 'MALWARE', 'MALWARE', None
        if attachment_verdict != ScanVerdict.CLEAN:
            return 'REVIEW', 'ANTIVIRUS_UNAVAILABLE', None
        filename = filename.replace('\\', '/').split('/')[-1][:200]
        try:
            mime = asyncio.run(document_processor.validate_file(content, filename, 'application/octet-stream'))
        except FileValidationError:
            return 'REVIEW', 'ATTACHMENT_INVALID', None
        pos = db.execute(text('SELECT position_id FROM app_private.positions WHERE position_code=:code'), {'code': result['position_code']}).scalar_one_or_none()
        if not pos:
            return 'REVIEW', 'POSITION_UNAVAILABLE', None
        request_id = uuid5(NAMESPACE_URL, f'hra-gmail-synthetic:{mailbox}:{message_id}')
        synthetic_name, synthetic_email = 'Gmail thử nghiệm', 'gmail-test@example.test'
        digest = _fingerprint(request_id, pos, synthetic_name, synthetic_email, '', filename, content, '')
        ext = '.pdf' if mime == 'application/pdf' else '.docx'
        path = f'careers/{pos}/{uuid4()}{ext}'
        backend, bucket, identity = destination()
        try:
            _commit_intake(str(pos), str(request_id), digest, path, synthetic_name, synthetic_email,
                           '', filename, content, mime, 'application/octet-stream', False, '',
                           backend, bucket, identity, source='EMAIL_TEST')
        except HTTPException as exc:
            return 'REVIEW', 'POSITION_NOT_READY' if exc.status_code in (404, 409) else 'INTAKE_UNAVAILABLE', None
        application = db.execute(text("SELECT application_id FROM app_private.careers_intake_receipts WHERE request_id=:id AND state='COMMITTED'"), {'id': str(request_id)}).scalar_one_or_none()
        if not application:
            return 'REVIEW', 'INTAKE_UNAVAILABLE', None
        return 'ACCEPTED', None, str(application)
    except (ValueError, TypeError, LookupError, RecursionError):
        return 'REVIEW', 'MESSAGE_INVALID', None


@router.post('/sync')
def sync(response: Response, page_token: str | None = Query(None, max_length=1000),
         current_user: dict = Depends(get_current_user)):
    _ready()
    response.headers['Cache-Control'] = 'no-store'
    actor = current_user['user_id']
    with SessionLocal() as db:
        _require_lead(db, actor)
        db.commit()
    try:
        session = gmail_test_client.open_session()
        try:
            mailbox = gmail_test_client.mailbox_hash(session)
            ids, next_page = gmail_test_client.list_messages(session, page_token)
            processed = 0
            for message_id in ids:
                db = SessionLocal()
                try:
                    _require_lead(db, actor)
                    db.execute(text("""INSERT INTO app_private.gmail_test_messages(mailbox_hash,message_id,status)
                        VALUES (:mailbox,:message,'PENDING') ON CONFLICT (mailbox_hash,message_id) DO NOTHING"""), {'mailbox': mailbox, 'message': message_id})
                    row = db.execute(text("""SELECT receipt_id,status FROM app_private.gmail_test_messages
                        WHERE mailbox_hash=:mailbox AND message_id=:message FOR UPDATE"""), {'mailbox': mailbox, 'message': message_id}).mappings().one()
                    if row['status'] in ('ACCEPTED','SPAM','MALWARE'):
                        db.commit()
                        continue
                    try:
                        state, reason, app_id = _process_message(db, session, mailbox, message_id)
                    except Exception:
                        # Never leak Gmail responses, OAuth tokens, or raw content.
                        state, reason, app_id = 'REVIEW', 'PROCESSING_UNAVAILABLE', None
                    db.execute(text("""UPDATE app_private.gmail_test_messages SET status=:status,reason=:reason,application_id=:app,updated_at=clock_timestamp()
                        WHERE receipt_id=:id"""), {'status': state, 'reason': reason, 'app': app_id, 'id': row['receipt_id']})
                    db.execute(text("""INSERT INTO app_private.audit_events(actor_user_id,action_type,object_type,object_id,outcome,metadata)
                        VALUES (:actor,'GMAIL_TEST_PROCESS','GMAIL_TEST_RECEIPT',:id,'SUCCESS',jsonb_build_object('status',CAST(:status AS text),'spam_mode',CAST(:spam_mode AS text)))"""),
                        {'actor': actor, 'id': row['receipt_id'], 'status': state, 'spam_mode': _spam_mode()})
                    db.commit()
                    processed += 1
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.close()
            return {'processed': processed, 'next_page_token': next_page, 'spam_mode': _spam_mode()}
        finally:
            session.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Không thể kết nối hoặc xử lý Gmail thử nghiệm') from None


@router.get('/review')
def review(response: Response, current_user: dict = Depends(get_current_user)):
    _ready()
    response.headers['Cache-Control'] = 'no-store'
    with SessionLocal() as db:
        _require_lead(db, current_user['user_id'])
        rows = db.execute(text("""SELECT receipt_id,message_id,status,reason,application_id,updated_at
            FROM app_private.gmail_test_messages ORDER BY updated_at DESC,receipt_id DESC LIMIT 100""")).mappings().all()
        return {'items': [dict(row) for row in rows], 'spam_mode': _spam_mode()}
