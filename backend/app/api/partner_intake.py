"""F3.03: server-to-server API for a separate candidate website (partner site).

The candidate website lists HRA's published positions (with the JD and the
candidate-facing posting text), collects the CV and a mandatory data-use consent,
and forwards both here from its own server with an API key (header
``X-Intake-Key``). The browser never sees the key.

A received CV goes through the same checks and queue as the public /apply portal
(file type, size, malware scan, duplicate check, consent records, CV processing
and automatic assessment). Consent is stored with channel PARTNER_SITE and the
notice version the site reports, plus the site's own reference.
"""
import hashlib
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text

from app.api.public_intake import OPEN_POSITION_SQL, _admit, _commit_application, read_checked_upload
from app.core.config import settings
from app.db.database import SessionLocal

router = APIRouter()

NOTICE_VERSION = re.compile(r"^[A-Za-z0-9._-]{1,40}$")
EXTERNAL_REF = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


def key_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8", "ignore")).hexdigest()


def require_client(x_intake_key: str | None = Header(default=None)) -> dict:
    if not settings.INTAKE_API_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    if not x_intake_key or len(x_intake_key) > 200:
        raise HTTPException(status_code=401, detail="Thiếu hoặc sai khóa API")
    db = SessionLocal()
    try:
        row = db.execute(text("""
            SELECT client_id, name, last_used_at FROM app_private.intake_clients
            WHERE key_hash = :h AND revoked_at IS NULL
        """), {"h": key_hash(x_intake_key)}).mappings().first()
        if not row:
            raise HTTPException(status_code=401, detail="Thiếu hoặc sai khóa API")
        last_used = row["last_used_at"]
        # Debounce last_used_at updates so frequent GET /positions calls do not contend on a row lock.
        if last_used is None or last_used < datetime.now(timezone.utc) - timedelta(minutes=5):
            db.execute(text("UPDATE app_private.intake_clients SET last_used_at = NOW() WHERE client_id = :id"),
                       {"id": row["client_id"]})
            db.commit()
    finally:
        db.close()
    return {"client_id": str(row["client_id"]), "name": row["name"]}


POSITION_FIELDS_SQL = """
    SELECT q.position_code, q.title, q.org_unit, q.work_location, q.employment_type, p.level, p.work_mode,
           p.posting_content, p.opened_at,
           (SELECT content_text FROM app_private.jd_versions j WHERE j.position_id = q.position_id
            ORDER BY version_number DESC LIMIT 1) AS jd_content,
           (SELECT language_code FROM app_private.jd_versions j WHERE j.position_id = q.position_id
            ORDER BY version_number DESC LIMIT 1) AS jd_language
    FROM (""" + OPEN_POSITION_SQL + """) q
    JOIN app_private.positions p ON p.position_id = q.position_id
"""


def _position_out(row, *, with_text: bool) -> dict:
    out = {"code": row["position_code"], "title": row["title"], "unit": row["org_unit"],
           "location": row["work_location"], "employment_type": row["employment_type"],
           "level": row["level"], "work_mode": row["work_mode"], "opened_at": row["opened_at"]}
    if with_text:
        out.update({"jd": row["jd_content"], "jd_language": row["jd_language"],
                    "posting_content": row["posting_content"]})
    return out


@router.get("/positions")
def list_positions(client: dict = Depends(require_client)):
    """Positions HR published, newest first, with the JD and the posting text."""
    db = SessionLocal()
    try:
        rows = db.execute(text(POSITION_FIELDS_SQL + " ORDER BY p.opened_at DESC NULLS LAST LIMIT 200")).mappings().all()
        return {"positions": [_position_out(r, with_text=True) for r in rows]}
    finally:
        db.close()


@router.get("/positions/{position_code}")
def get_position(position_code: str, client: dict = Depends(require_client)):
    db = SessionLocal()
    try:
        row = db.execute(text(POSITION_FIELDS_SQL + " WHERE q.position_code = :code"),
                         {"code": position_code}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Vị trí không còn nhận hồ sơ.")
        return _position_out(row, with_text=True)
    finally:
        db.close()


@router.post("/positions/{position_code}/applications", status_code=status.HTTP_202_ACCEPTED)
async def submit_application(position_code: str, file: UploadFile = File(...),
                             consent_accepted: bool = Form(False), consent_notice_version: str = Form(...),
                             consented_at: str | None = Form(None), external_ref: str | None = Form(None),
                             client: dict = Depends(require_client)):
    if not consent_accepted:
        raise HTTPException(status_code=400, detail="Ứng viên chưa đồng ý cho phép sử dụng thông tin hồ sơ.")
    if not NOTICE_VERSION.match(consent_notice_version or ""):
        raise HTTPException(status_code=422, detail="consent_notice_version không hợp lệ")
    if external_ref and not EXTERNAL_REF.match(external_ref):
        raise HTTPException(status_code=422, detail="external_ref không hợp lệ")
    if consented_at:
        try:
            consented_at = datetime.fromisoformat(consented_at.replace("Z", "+00:00")).isoformat()
        except ValueError:
            raise HTTPException(status_code=422, detail="consented_at phải theo định dạng ISO 8601") from None
    # Per-site limit, on its own counter (the bucket is the client id, not an address).
    pos = await run_in_threadpool(_admit, position_code, f"partner:{client['client_id']}",
                                  settings.INTAKE_MAX_PER_CLIENT_HOUR)
    if pos is None:
        raise HTTPException(status_code=404, detail="Vị trí không còn nhận hồ sơ.")
    filename, content, mime, size = await read_checked_upload(file)
    return await run_in_threadpool(
        _commit_application, pos, filename=filename, content=content, mime=mime, declared_type=file.content_type,
        size=size, sha=hashlib.sha256(content).hexdigest(),
        # The site's mandatory consent covers this position, AI-assisted assessment,
        # 5-year storage and reuse for other positions (same scope as the /apply portal).
        consent_talent_pool=True, ip_hash=f"partner:{client['client_id']}",
        channel="PARTNER_SITE", source_code="PARTNER_SITE", notice_version=consent_notice_version,
        evidence_extra={"client_id": client["client_id"], "external_ref": external_ref, "consented_at_site": consented_at},
        audit_action="RECEIVE_PARTNER_CV", audit_extra={"client_id": client["client_id"]}, receipt_extra=True)
