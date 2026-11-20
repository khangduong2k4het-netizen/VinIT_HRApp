"""Authenticated, non-persistent previews for position creation."""
import asyncio
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.core.security import get_current_user
from app.core.config import settings
from app.db.database import SessionLocal
from app.services.jd_import import MAX_FILE, ImportErrorDetail, extract_file, fetch_job
from app.services.malware_scan import ScanVerdict, scan_bytes

router = APIRouter()
URL_RESPONSE_TIMEOUT = 20


def require_hr(current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        allowed = db.execute(text("""
            SELECT 1 FROM app_private.user_profiles p WHERE p.user_id=:id AND p.account_status='ACTIVE'
              AND (EXISTS (SELECT 1 FROM app_private.user_role_assignments r WHERE r.user_id=p.user_id
                  AND r.revoked_at IS NULL AND r.role_code IN ('ADMIN','HR_LEAD','HR_RECRUITER'))
              OR EXISTS (SELECT 1 FROM app_private.position_assignments a WHERE a.user_id=p.user_id
                  AND a.revoked_at IS NULL AND a.position_role IN ('HR_LEAD','HR_RECRUITER')))
        """), {'id': current_user['user_id']}).first()
        if not allowed:
            raise HTTPException(403, 'Chỉ HR được phép nhập JD.')
    finally:
        db.close()
    return current_user


class UrlInput(BaseModel):
    url: str = Field(min_length=1, max_length=500)


@router.post('/url')
async def preview_url(body: UrlInput, _: dict = Depends(require_hr)):
    try:
        content = await asyncio.wait_for(run_in_threadpool(fetch_job, body.url), timeout=URL_RESPONSE_TIMEOUT)
        return {'content': content, 'warning': 'Kiểm tra và chỉnh sửa nội dung, bao gồm hướng dẫn ứng tuyển, trước khi lưu.'}
    except TimeoutError:
        # The background worker may still be blocked in DNS or response headers.
        # fetch_job holds a bounded slot until it actually exits.
        raise HTTPException(504, 'Nguồn JD phản hồi quá lâu. Hãy thử lại hoặc dán thủ công.') from None
    except ImportErrorDetail as exc:
        raise HTTPException(400, str(exc)) from None


@router.post('/file')
async def preview_file(file: UploadFile = File(...), user: dict = Depends(require_hr)):
    filename = (file.filename or '').replace('\\', '/').rsplit('/', 1)[-1]
    if not filename.lower().endswith(('.docx', '.txt')):
        raise HTTPException(400, 'Chỉ hỗ trợ .docx và .txt; hãy chuyển .doc sang .docx.')
    data = await file.read(MAX_FILE + 1)
    if not data or len(data) > MAX_FILE:
        raise HTTPException(400, 'Tệp rỗng hoặc lớn hơn 2 MB.')
    verdict = await run_in_threadpool(scan_bytes, data, socket_path=settings.CLAMAV_UNIX_SOCKET, max_bytes=MAX_FILE)
    scanned = verdict == ScanVerdict.CLEAN
    if not scanned:
        if verdict == ScanVerdict.INFECTED:
            # Tệp bẩn thì luôn từ chối, kể cả ở chế độ thử nghiệm.
            raise HTTPException(400, 'Không thể tiếp nhận tệp.')
        # Máy quét chết/cấu hình sai. Đây là đường nhập JD: nội dung được trích
        # xuất ra để HR ĐỌC VÀ SỬA rồi mới lưu, tệp gốc không được giữ lại và
        # không bao giờ chạy. Nên chặn cứng ở đây chỉ làm hỏng việc, không thêm
        # an toàn. Bản CV tải lên thật thì khác — xem careers_intake.py, ở đó
        # tệp được lưu và xử lý nên vẫn fail-closed.
        #
        # Vẫn cần cờ rõ ràng, vẫn cảnh báo cho người dùng, vẫn ghi audit.
        if not settings.PUBLIC_CAREERS_UNSCANNED_FILES_ENABLED:
            raise HTTPException(503, 'Máy quét chưa sẵn sàng.')
    try:
        content = await run_in_threadpool(extract_file, data, filename)
        warning = 'Hãy rà soát nội dung được trích xuất trước khi lưu.'
        if not scanned:
            _audit_unscanned_preview(user['user_id'], filename, len(data))
            warning = (
                'Tệp được trích xuất nhưng CHƯA được quét virus vì máy quét chưa '
                'sẵn sàng. Tệp gốc không được lưu lại. ' + warning
            )
        return {'content': content, 'warning': warning, 'scanned': scanned}
    except ImportErrorDetail as exc:
        raise HTTPException(400, str(exc)) from None


def _audit_unscanned_preview(user_id: str, filename: str, size: int) -> None:
    """Ghi lại việc trích xuất tệp chưa quét. Lỗi ghi audit không chặn người dùng."""
    db = SessionLocal()
    try:
        db.execute(text("""
            INSERT INTO app_private.audit_events
                (actor_user_id, action_type, object_type, outcome, metadata)
            VALUES (:actor, 'JD_PREVIEW_UNSCANNED', 'SYSTEM', 'SUCCESS', CAST(:metadata AS jsonb))
        """), {'actor': user_id, 'metadata': json.dumps({
            'filename': filename, 'bytes': size, 'reason': 'SCANNER_UNAVAILABLE',
        }, ensure_ascii=False)})
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
