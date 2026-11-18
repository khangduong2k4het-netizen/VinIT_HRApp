"""P3-3 public application portal: no sign-in, so every guard is explicit.

Order of checks on a submission: feature flag, honeypot, per-address rate limit,
position is open and published by HR, required consent, size and file type,
malware scan (fail-closed), duplicate content. Nothing here returns candidate
data, and the audit record holds counts only.
"""
import hashlib
import json
import os
import secrets
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.core.exceptions import FileValidationError
from app.core.logging import get_logger
from app.db.database import SessionLocal
from app.db.supabase import get_supabase_client
from app.services.document_processor import MIME_EXTENSIONS, document_processor
from app.services.malware_scan import ScanRejected, ScanUnavailable, scan_upload
from app.services.portal_dispatch import DEFERRED_WHILE_BUSY

router = APIRouter()
logger = get_logger(__name__)

# Same message for every refused file so the endpoint is not a scanner oracle.
REFUSED = "Không thể nhận tệp này. Vui lòng kiểm tra định dạng (PDF, DOCX, JPG, PNG) và thử lại."
# Shown to HR only (never to the candidate) on a portal CV that arrived while the
# position already had a job running; HR queues it with "Xử lý lại".
LOCK_TIMEOUT = "5s"  # how long a portal request may wait for a position that HR is changing


def client_address(request: Request) -> str:
    """Peer address, or the client entry of X-Forwarded-For behind a known number of proxies."""
    hops = settings.PUBLIC_INTAKE_TRUSTED_PROXY_HOPS
    if hops > 0:
        chain = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",") if part.strip()]
        if len(chain) >= hops:
            return chain[-hops]
    return request.client.host if request.client else "unknown"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii", "ignore")).hexdigest()


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


def _fake_token() -> str:
    """Answer shaped like a real receipt, so a repeat or bot submission learns nothing."""
    return secrets.token_hex(32)


def _received(consent_talent_pool: bool, token: str | None = None) -> dict:
    # The real token is shown once; only its hash is stored. Duplicates get a throwaway one.
    if not consent_talent_pool:
        return {"status": "received"}
    return {"status": "received", "withdrawal_token": token or _fake_token()}


def _admit(position_code: str, ip_hash: str):
    """Rate limit and look up the position. Blocking DB work: run in the threadpool."""
    db = SessionLocal()
    try:
        # The attempt row references the position, so it can wait for a lock HR holds on it.
        db.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
        # Serialise attempts from the same address so parallel requests cannot all read
        # a count under the limit before any of them is recorded. The lock is held until
        # the commit below, after this attempt has been inserted.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:h, 3303))"), {"h": ip_hash})
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
        return pos
    except OperationalError as exc:
        db.rollback()
        if getattr(exc.orig, "pgcode", None) == "55P03":  # lock_not_available
            raise HTTPException(status_code=503, detail="Hệ thống đang bận. Vui lòng thử lại sau ít phút.") from None
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _write_cv(storage, storage_path: str, content: bytes, mime: str) -> None:
    if settings.STORAGE_BACKEND == "local":
        full = os.path.join(settings.LOCAL_STORAGE_PATH, settings.SUPABASE_STORAGE_BUCKET_CV, storage_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as out:
            out.write(content)
    else:
        storage.storage.from_(settings.SUPABASE_STORAGE_BUCKET_CV).upload(
            path=storage_path, file=content, file_options={"content-type": mime})


def _remove_cv(storage, saved_path: str) -> None:
    try:
        if settings.STORAGE_BACKEND == "local":
            full = os.path.join(settings.LOCAL_STORAGE_PATH, settings.SUPABASE_STORAGE_BUCKET_CV, saved_path)
            if os.path.exists(full):
                os.remove(full)
        elif storage:
            storage.storage.from_(settings.SUPABASE_STORAGE_BUCKET_CV).remove([saved_path])
    except Exception as exc:
        logger.error("Could not remove orphaned public upload", error_type=type(exc).__name__)


def _commit_application(pos, *, filename: str, content: bytes, mime: str, declared_type, size: int, sha: str,
                        consent_talent_pool: bool, ip_hash: str) -> dict:
    """Store the CV and create the application. Blocking: runs in the threadpool, never on the event loop."""
    db = SessionLocal()
    saved_path = None
    storage = None
    try:
        if settings.STORAGE_BACKEND == "supabase":
            storage = get_supabase_client()
            if not storage:
                raise HTTPException(status_code=503, detail="Hệ thống tạm thời chưa nhận hồ sơ.")
        position_id = str(pos.position_id)
        # Do not queue behind an HR upload that holds this position: give up after a few seconds.
        db.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
        # Same order as the HR upload and the reprocess endpoint: lock the position,
        # then check for a running job. The worker needs operations.position_id to
        # assess and rank, and the one-job-per-position guard only sees jobs that carry it.
        # Re-check everything the portal promises (open, published, approved criteria) under the lock.
        still_open = db.execute(text(OPEN_POSITION_SQL + " AND p.position_id = :p FOR UPDATE OF p"), {"p": position_id}).first()
        if not still_open:
            raise HTTPException(status_code=404, detail="Vị trí không còn nhận hồ sơ.")
        # Checked under the position lock, so two simultaneous identical uploads cannot both pass.
        duplicate = db.execute(text("""
            SELECT 1 FROM app_private.application_documents d JOIN app_private.applications a USING (application_id)
            WHERE a.position_id = :p AND d.content_sha256 = :sha LIMIT 1"""), {"p": position_id, "sha": sha}).first()
        if duplicate:
            return _received(consent_talent_pool)  # idempotent: no second application, no signal to the sender
        busy = db.execute(text("""SELECT 1 FROM app_private.operations WHERE position_id = :p
              AND capability IN ('CV_PROCESSING', 'ASSESSMENT', 'RANKING') AND status IN ('PENDING', 'PROCESSING') LIMIT 1"""),
                          {"p": position_id}).first() is not None
        operation_id = batch_id = None
        if not busy:
            operation_id = db.execute(text("""INSERT INTO app_private.operations(position_id, capability, status)
                VALUES (:p, 'CV_PROCESSING', 'PENDING') RETURNING operation_id"""), {"p": position_id}).scalar_one()
            batch_id = db.execute(text("""INSERT INTO app_private.cv_batches(position_id, operation_id, status, total_files, total_size_bytes)
                VALUES (:p, :o, 'PROCESSING', 1, :s) RETURNING batch_id"""), {"p": position_id, "o": operation_id, "s": size}).scalar_one()
        app_id = db.execute(text("INSERT INTO app_private.applications(position_id, source_code) VALUES (:p, 'PORTAL') RETURNING application_id"),
                            {"p": position_id}).scalar_one()
        storage_path = f"{position_id}/{app_id}/{uuid4()}{MIME_EXTENSIONS[mime]}"
        saved_path = storage_path
        _write_cv(storage, storage_path, content, mime)
        doc_id = db.execute(text("""INSERT INTO app_private.application_documents(application_id, document_type, bucket, storage_path,
                original_filename, mime_type, size_bytes, file_processing_status, processing_error, content_sha256)
            VALUES (:a, 'CV', :b, :sp, :fn, :m, :s, :st, :err, :sha) RETURNING document_id"""),
                            {"a": app_id, "b": settings.SUPABASE_STORAGE_BUCKET_CV, "sp": storage_path, "fn": filename,
                             "m": mime, "s": size, "sha": sha,
                             # While another job runs on the position, the CV is kept but not queued;
                             # the worker queues all held CVs of the position as one job once it is free
                             # (services/portal_dispatch.py). HR can still use "reprocess" on one CV.
                             "st": "NEEDS_HR_REVIEW" if busy else "RECEIVED",
                             "err": DEFERRED_WHILE_BUSY if busy else None}).scalar_one()
        db.execute(text("INSERT INTO app_private.application_identities(application_id) VALUES (:a)"), {"a": app_id})
        if not busy:
            db.execute(text("""INSERT INTO app_private.document_processing_runs(document_id, operation_id, extraction_type, status)
                VALUES (:d, :o, 'INITIAL_EXTRACTION', 'PENDING')"""), {"d": doc_id, "o": operation_id})
            db.execute(text("""INSERT INTO app_private.cv_batch_items(batch_id, original_filename, declared_mime_type, detected_mime_type,
                    size_bytes, validation_result, application_id) VALUES (:b, :fn, :dm, :m, :s, 'ACCEPTED', :a)"""),
                       {"b": batch_id, "fn": filename, "dm": declared_type, "m": mime, "s": size, "a": app_id})
        evidence = json.dumps({"ip_hash": ip_hash[:16]})
        purposes = ["THIS_POSITION"] + (["TALENT_POOL"] if consent_talent_pool else [])
        withdrawal_token = secrets.token_hex(32) if consent_talent_pool else None
        for purpose in purposes:
            db.execute(text("""INSERT INTO app_private.application_data_consents(application_id, purpose, notice_version, channel, evidence, withdrawal_token_hash)
                VALUES (:a, :p, :v, 'PORTAL', CAST(:e AS jsonb), :th)"""),
                       {"a": app_id, "p": purpose, "v": settings.PUBLIC_INTAKE_NOTICE_VERSION, "e": evidence,
                        "th": hash_token(withdrawal_token) if withdrawal_token and purpose == "TALENT_POOL" else None})
        db.execute(text("""INSERT INTO app_private.audit_events(action_type, object_type, object_id, position_id, outcome, metadata)
            VALUES ('RECEIVE_PUBLIC_CV', 'APPLICATION', :a, :p, 'SUCCESS', CAST(:m AS jsonb))"""),
                   {"a": app_id, "p": position_id, "m": json.dumps({"talent_pool_consent": consent_talent_pool, "size_bytes": size})})
        db.commit()
        return _received(consent_talent_pool, withdrawal_token)
    except OperationalError as exc:
        db.rollback()
        if saved_path:
            _remove_cv(storage, saved_path)
        if getattr(exc.orig, "pgcode", None) == "55P03":  # lock_not_available
            raise HTTPException(status_code=503, detail="Hệ thống đang bận. Vui lòng thử lại sau ít phút.") from None
        raise
    except Exception:
        db.rollback()
        if saved_path:
            _remove_cv(storage, saved_path)
        raise
    finally:
        db.close()


@router.post("/positions/{position_code}/apply", status_code=status.HTTP_202_ACCEPTED)
async def apply(position_code: str, request: Request, file: UploadFile = File(...),
                consent_processing: bool = Form(False), consent_talent_pool: bool = Form(False),
                website: str = Form("")):
    _require_enabled()
    ip_hash = _ip_hash(request)
    pos = await run_in_threadpool(_admit, position_code, ip_hash)
    if website.strip():
        # Honeypot: pretend success so a bot learns nothing.
        return _received(True)
    if pos is None:
        raise HTTPException(status_code=404, detail="Vị trí không còn nhận hồ sơ.")
    if not consent_processing:
        raise HTTPException(status_code=400, detail="Cần đồng ý cho phép sử dụng thông tin hồ sơ để ứng tuyển.")
    # One mandatory consent (notice v2): processing for this position, AI-assisted
    # assessment, keeping the CV for 5 years and reuse for other suitable positions.
    # The separate optional Talent Pool box is gone; the old form field is ignored.
    # The candidate can still withdraw the reuse part with the token shown once.
    consent_talent_pool = True

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

    return await run_in_threadpool(
        _commit_application, pos, filename=filename, content=content, mime=mime, declared_type=file.content_type,
        size=size, sha=hashlib.sha256(content).hexdigest(), consent_talent_pool=consent_talent_pool, ip_hash=ip_hash)


class WithdrawInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


@router.post("/talent-pool/withdraw")
def withdraw_talent_pool(body: WithdrawInput):
    """Candidate withdraws the Talent Pool consent with the token shown at submission. Always answers alike.

    Stays available when the portal is switched off: withdrawing is a right, not part of intake.
    """
    db = SessionLocal()
    try:
        row = db.execute(text("""UPDATE app_private.application_data_consents SET withdrawn_at = NOW()
            WHERE withdrawal_token_hash = :h AND purpose = 'TALENT_POOL' AND withdrawn_at IS NULL RETURNING application_id"""),
                         {"h": hash_token(body.token)}).first()
        if row:
            db.execute(text("UPDATE app_private.talent_pool_marks SET removed_at = NOW() WHERE application_id = :a AND removed_at IS NULL"),
                       {"a": row[0]})
            db.execute(text("""INSERT INTO app_private.audit_events(action_type, object_type, object_id, outcome)
                VALUES ('WITHDRAW_TALENT_POOL_CONSENT_BY_CANDIDATE', 'APPLICATION', :a, 'SUCCESS')"""), {"a": row[0]})
        db.commit()
        return {"status": "ok"}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---- HR side: publish or unpublish a position on the public portal -------------------

from uuid import UUID  # noqa: E402

from fastapi import Depends  # noqa: E402

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
