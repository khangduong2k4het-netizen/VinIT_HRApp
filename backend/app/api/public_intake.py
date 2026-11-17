"""P3-3 public application portal: no sign-in, so every guard is explicit.

Order of checks on a submission: feature flag, honeypot, per-address rate limit,
position is open and published by HR, required consent, size and file type,
malware scan (fail-closed), duplicate content. Nothing here returns candidate
data, and the audit record holds counts only.
"""
import hashlib
import json
import os
from uuid import uuid4

import aiofiles
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text

from app.core.config import settings
from app.core.exceptions import FileValidationError
from app.core.logging import get_logger
from app.db.database import SessionLocal
from app.db.supabase import get_supabase_client
from app.services.document_processor import MIME_EXTENSIONS, document_processor
from app.services.malware_scan import ScanRejected, ScanUnavailable, scan_upload

router = APIRouter()
logger = get_logger(__name__)

# Same message for every refused file so the endpoint is not a scanner oracle.
REFUSED = "Không thể nhận tệp này. Vui lòng kiểm tra định dạng (PDF, DOCX, JPG, PNG) và thử lại."


def client_address(request: Request) -> str:
    """Peer address, or the client entry of X-Forwarded-For behind a known number of proxies."""
    hops = settings.PUBLIC_INTAKE_TRUSTED_PROXY_HOPS
    if hops > 0:
        chain = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",") if part.strip()]
        if len(chain) >= hops:
            return chain[-hops]
    return request.client.host if request.client else "unknown"


def _ip_hash(request: Request) -> str:
    ip = client_address(request)
    return hashlib.sha256(f"{settings.PUBLIC_INTAKE_IP_SALT}|{ip}".encode()).hexdigest()


def _require_enabled():
    if not settings.PUBLIC_INTAKE_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")


OPEN_POSITION_SQL = """
    SELECT p.position_id, p.position_code, p.title, p.org_unit, p.work_location, p.employment_type
    FROM app_private.positions p
    WHERE p.status = 'OPEN' AND p.public_apply_enabled
      AND EXISTS (SELECT 1 FROM app_private.criteria_versions cv
                  WHERE cv.position_id = p.position_id AND cv.status = 'APPROVED'
                    AND cv.jd_version_id = (SELECT jd_version_id FROM app_private.jd_versions
                                            WHERE position_id = p.position_id ORDER BY version_number DESC LIMIT 1))
"""


@router.get("/positions")
def list_public_positions():
    _require_enabled()
    db = SessionLocal()
    try:
        rows = db.execute(text(OPEN_POSITION_SQL + " ORDER BY p.opened_at DESC NULLS LAST LIMIT 200")).fetchall()
        return {"positions": [{"code": r.position_code, "title": r.title, "unit": r.org_unit,
                               "location": r.work_location, "employment_type": r.employment_type} for r in rows]}
    finally:
        db.close()


@router.post("/positions/{position_code}/apply", status_code=status.HTTP_202_ACCEPTED)
async def apply(position_code: str, request: Request, file: UploadFile = File(...),
                consent_processing: bool = Form(False), consent_talent_pool: bool = Form(False),
                website: str = Form("")):
    _require_enabled()
    ip_hash = _ip_hash(request)
    db = SessionLocal()
    saved_path = None
    storage = None
    try:
        db.execute(text("DELETE FROM app_private.public_intake_events WHERE created_at < NOW() - INTERVAL '7 days'"))
        recent = db.execute(text("""SELECT COUNT(*) FROM app_private.public_intake_events
            WHERE ip_hash = :h AND created_at > NOW() - INTERVAL '1 hour'"""), {"h": ip_hash}).scalar_one()
        if recent >= settings.PUBLIC_INTAKE_MAX_PER_IP_HOUR:
            raise HTTPException(status_code=429, detail="Bạn đã gửi quá nhiều lần. Vui lòng thử lại sau.")
        pos = db.execute(text(OPEN_POSITION_SQL + " AND p.position_code = :code"), {"code": position_code}).first()
        # The attempt counts against the limit even when it fails, which blunts probing.
        db.execute(text("INSERT INTO app_private.public_intake_events(ip_hash, position_id, outcome) VALUES (:h, :p, 'ATTEMPT')"),
                   {"h": ip_hash, "p": pos.position_id if pos else None})
        db.commit()
        if website.strip():
            # Honeypot: pretend success so a bot learns nothing.
            return {"status": "received"}
        if pos is None:
            raise HTTPException(status_code=404, detail="Vị trí không còn nhận hồ sơ.")
        if not consent_processing:
            raise HTTPException(status_code=400, detail="Cần đồng ý cho phép xử lý hồ sơ để ứng tuyển.")

        filename = os.path.basename(file.filename or "cv")
        file.file.seek(0, os.SEEK_END)
        size = file.file.tell()
        file.file.seek(0)
        if size > settings.MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=413, detail=REFUSED)
        content = await file.read()
        try:
            mime = await document_processor.validate_file(content, filename, file.content_type)
        except FileValidationError:
            raise HTTPException(status_code=400, detail=REFUSED) from None
        try:
            # clamd is a blocking socket call; keep it off the event loop.
            await run_in_threadpool(scan_upload, content)
        except ScanRejected:
            logger.warning("Public upload rejected by malware scan")
            raise HTTPException(status_code=400, detail=REFUSED) from None
        except ScanUnavailable as exc:
            logger.error("Malware scan unavailable; refusing upload", reason=str(exc))
            raise HTTPException(status_code=503, detail="Hệ thống tạm thời chưa nhận hồ sơ. Vui lòng thử lại sau.") from None

        sha = hashlib.sha256(content).hexdigest()
        duplicate = db.execute(text("""
            SELECT 1 FROM app_private.application_documents d JOIN app_private.applications a USING (application_id)
            WHERE a.position_id = :p AND d.content_sha256 = :sha LIMIT 1"""), {"p": pos.position_id, "sha": sha}).first()
        if duplicate:
            return {"status": "received"}  # idempotent: no second application, no signal to the sender

        if settings.STORAGE_BACKEND == "supabase":
            storage = get_supabase_client()
            if not storage:
                raise HTTPException(status_code=503, detail="Hệ thống tạm thời chưa nhận hồ sơ.")
        position_id = str(pos.position_id)
        operation_id = db.execute(text("INSERT INTO app_private.operations(capability, status) VALUES ('CV_PROCESSING', 'PENDING') RETURNING operation_id")).scalar_one()
        batch_id = db.execute(text("""INSERT INTO app_private.cv_batches(position_id, operation_id, status, total_files, total_size_bytes)
            VALUES (:p, :o, 'PROCESSING', 1, :s) RETURNING batch_id"""), {"p": position_id, "o": operation_id, "s": size}).scalar_one()
        app_id = db.execute(text("INSERT INTO app_private.applications(position_id, source_code) VALUES (:p, 'PORTAL') RETURNING application_id"),
                            {"p": position_id}).scalar_one()
        storage_path = f"{position_id}/{app_id}/{uuid4()}{MIME_EXTENSIONS[mime]}"
        saved_path = storage_path
        if settings.STORAGE_BACKEND == "local":
            full = os.path.join(settings.LOCAL_STORAGE_PATH, settings.SUPABASE_STORAGE_BUCKET_CV, storage_path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            async with aiofiles.open(full, "wb") as out:
                await out.write(content)
        else:
            storage.storage.from_(settings.SUPABASE_STORAGE_BUCKET_CV).upload(
                path=storage_path, file=content, file_options={"content-type": mime})
        doc_id = db.execute(text("""INSERT INTO app_private.application_documents(application_id, document_type, bucket, storage_path,
                original_filename, mime_type, size_bytes, file_processing_status, content_sha256)
            VALUES (:a, 'CV', :b, :sp, :fn, :m, :s, 'RECEIVED', :sha) RETURNING document_id"""),
                            {"a": app_id, "b": settings.SUPABASE_STORAGE_BUCKET_CV, "sp": storage_path, "fn": filename,
                             "m": mime, "s": size, "sha": sha}).scalar_one()
        db.execute(text("INSERT INTO app_private.application_identities(application_id) VALUES (:a)"), {"a": app_id})
        db.execute(text("""INSERT INTO app_private.document_processing_runs(document_id, operation_id, extraction_type, status)
            VALUES (:d, :o, 'INITIAL_EXTRACTION', 'PENDING')"""), {"d": doc_id, "o": operation_id})
        db.execute(text("""INSERT INTO app_private.cv_batch_items(batch_id, original_filename, declared_mime_type, detected_mime_type,
                size_bytes, validation_result, application_id) VALUES (:b, :fn, :dm, :m, :s, 'ACCEPTED', :a)"""),
                   {"b": batch_id, "fn": filename, "dm": file.content_type, "m": mime, "s": size, "a": app_id})
        evidence = json.dumps({"ip_hash": ip_hash[:16]})
        purposes = ["THIS_POSITION"] + (["TALENT_POOL"] if consent_talent_pool else [])
        for purpose in purposes:
            db.execute(text("""INSERT INTO app_private.application_data_consents(application_id, purpose, notice_version, channel, evidence)
                VALUES (:a, :p, :v, 'PORTAL', CAST(:e AS jsonb))"""),
                       {"a": app_id, "p": purpose, "v": settings.PUBLIC_INTAKE_NOTICE_VERSION, "e": evidence})
        db.execute(text("""INSERT INTO app_private.audit_events(action_type, object_type, object_id, position_id, outcome, metadata)
            VALUES ('RECEIVE_PUBLIC_CV', 'APPLICATION', :a, :p, 'SUCCESS', CAST(:m AS jsonb))"""),
                   {"a": app_id, "p": position_id, "m": json.dumps({"talent_pool_consent": consent_talent_pool, "size_bytes": size})})
        db.commit()
        return {"status": "received"}
    except Exception:
        db.rollback()
        if saved_path:
            try:
                if settings.STORAGE_BACKEND == "local":
                    full = os.path.join(settings.LOCAL_STORAGE_PATH, settings.SUPABASE_STORAGE_BUCKET_CV, saved_path)
                    if os.path.exists(full):
                        os.remove(full)
                elif storage:
                    storage.storage.from_(settings.SUPABASE_STORAGE_BUCKET_CV).remove([saved_path])
            except Exception as exc:
                logger.error("Could not remove orphaned public upload", error_type=type(exc).__name__)
        raise
    finally:
        db.close()


# ---- HR side: publish or unpublish a position on the public portal -------------------

from uuid import UUID  # noqa: E402

from fastapi import Depends  # noqa: E402
from pydantic import BaseModel, ConfigDict  # noqa: E402

from app.core.permissions import check_position_access  # noqa: E402
from app.core.security import get_current_user  # noqa: E402

manage_router = APIRouter()


class PublicApplyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


@manage_router.put("/{position_id}/public-apply")
async def set_public_apply(position_id: UUID, body: PublicApplyInput, current_user: dict = Depends(get_current_user)):
    await check_position_access(position_id, current_user, required_roles=["HR_RECRUITER"])
    db = SessionLocal()
    try:
        done = db.execute(text("UPDATE app_private.positions SET public_apply_enabled = :e WHERE position_id = :p"),
                          {"e": body.enabled, "p": str(position_id)}).rowcount
        if not done:
            raise HTTPException(status_code=404, detail="Không tìm thấy vị trí")
        db.execute(text("""INSERT INTO app_private.audit_events(actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
            VALUES (:u, 'SET_PUBLIC_APPLY', 'POSITION', :p, :p, 'SUCCESS', CAST(:m AS jsonb))"""),
                   {"u": current_user["user_id"], "p": str(position_id), "m": json.dumps({"enabled": body.enabled})})
        db.commit()
        return {"public_apply_enabled": body.enabled}
    finally:
        db.close()
