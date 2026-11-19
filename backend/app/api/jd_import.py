"""Authenticated, non-persistent previews for position creation."""
import asyncio

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
async def preview_file(file: UploadFile = File(...), _: dict = Depends(require_hr)):
    filename = (file.filename or '').replace('\\', '/').rsplit('/', 1)[-1]
    if not filename.lower().endswith(('.docx', '.txt')):
        raise HTTPException(400, 'Chỉ hỗ trợ .docx và .txt; hãy chuyển .doc sang .docx.')
    data = await file.read(MAX_FILE + 1)
    if not data or len(data) > MAX_FILE:
        raise HTTPException(400, 'Tệp rỗng hoặc lớn hơn 2 MB.')
    verdict = await run_in_threadpool(scan_bytes, data, socket_path=settings.CLAMAV_UNIX_SOCKET, max_bytes=MAX_FILE)
    if verdict != ScanVerdict.CLEAN:
        raise HTTPException(400 if verdict == ScanVerdict.INFECTED else 503,
                            'Không thể tiếp nhận tệp.' if verdict == ScanVerdict.INFECTED else 'Máy quét chưa sẵn sàng.')
    try:
        content = await run_in_threadpool(extract_file, data, filename)
        return {'content': content, 'warning': 'Hãy rà soát nội dung được trích xuất trước khi lưu.'}
    except ImportErrorDetail as exc:
        raise HTTPException(400, str(exc)) from None
