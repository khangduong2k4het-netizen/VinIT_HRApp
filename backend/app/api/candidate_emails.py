"""F3.05 phase 1: emails to candidates, always reviewed and sent by HR.

A template is filled with the candidate's name, the position and HR's details; HR
sees the sender, the recipient, the subject and the body, edits them and presses
send. Nothing is sent automatically. With CANDIDATE_EMAIL_SEND_MODE=record (the
default) "send" only records the message (status RECORDED) so the flow can be used
before a mail server is connected.

Audit events carry ids, template code and status only - never the address, subject
or body.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.core.config import settings
from app.core.security import get_current_user
from app.core.logging import get_logger
from app.db.database import SessionLocal
from app.services.mailer import MailError, email_enabled, send_email
from app.services.talent_pool import ELIGIBLE_POOL_SQL, application_pool_state

router = APIRouter()
logger = get_logger(__name__)

# A letter stuck in SENDING (worker died after claiming it) is treated as FAILED after this long and can be retried.
STALE_SENDING_MINUTES = 10

TemplateCode = Literal["ACK_RECEIVED", "REQUEST_INFO", "INTERVIEW_INVITE", "REJECTION", "POOL_INVITE"]
VARIABLES = ("ho_ten", "vi_tri", "ma_vi_tri", "ngay_nop", "ten_hr", "email_hr", "thoi_gian_pv", "dia_diem_pv")
# Placeholders HR must replace by hand (the interview details), left in the draft on purpose.
MANUAL_VARIABLES = ("thoi_gian_pv", "dia_diem_pv")
_PLACEHOLDER = re.compile(r"\{(" + "|".join(VARIABLES) + r")\}")
_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


class TemplateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_template: str = Field(min_length=1, max_length=300)
    body_template: str = Field(min_length=1, max_length=10000)


class ComposeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_code: TemplateCode
    # POOL_INVITE only: the Talent Pool scan (of the position being filled) the contact was revealed in.
    scan_id: Optional[UUID] = None


class EmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_code: Optional[TemplateCode] = None
    trigger_source: Literal["MANUAL", "STATUS_CHANGE"] = "MANUAL"
    to_address: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=20000)
    send: bool = False
    # Rejection letters need an explicit second confirmation from HR.
    confirmed: bool = False
    scan_id: Optional[UUID] = None


class EmailUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to_address: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=20000)


class SendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: bool = False


# ---- access -------------------------------------------------------------------------

def _hr_user(db, user_id: str) -> dict:
    """Active HR account (system role or HR on some position) with its name and email."""
    row = db.execute(text("""
        SELECT p.display_name, p.account_status, u.email,
               EXISTS (SELECT 1 FROM app_private.user_role_assignments r WHERE r.user_id = :u
                       AND r.revoked_at IS NULL AND r.role_code IN ('ADMIN', 'HR_LEAD', 'HR_RECRUITER')) AS hr_role,
               EXISTS (SELECT 1 FROM app_private.user_role_assignments r WHERE r.user_id = :u
                       AND r.revoked_at IS NULL AND r.role_code IN ('ADMIN', 'HR_LEAD')) AS lead_role
        FROM app_private.user_profiles p JOIN auth.users u ON u.id = p.user_id
        WHERE p.user_id = :u
    """), {"u": user_id}).mappings().first()
    if not row or row["account_status"] != "ACTIVE":
        raise HTTPException(status_code=403, detail="Tài khoản chưa được kích hoạt hoặc đã bị khóa")
    return dict(row)


def _handles_position(db, user_id: str, position_id: str) -> bool:
    return bool(db.execute(text("""
        SELECT EXISTS (SELECT 1 FROM app_private.user_role_assignments r WHERE r.user_id = :u
                       AND r.revoked_at IS NULL AND r.role_code IN ('ADMIN', 'HR_LEAD'))
            OR EXISTS (SELECT 1 FROM app_private.position_assignments pa WHERE pa.user_id = :u
                       AND pa.position_id = :p AND pa.revoked_at IS NULL
                       AND pa.position_role IN ('HR_RECRUITER', 'HR_LEAD'))
    """), {"u": user_id, "p": str(position_id)}).scalar())


POOL_ONLY = ("Thư mời Talent Pool chỉ soạn và gửi được từ kết quả quét Talent Pool, sau khi HR đã chọn Liên hệ "
             "và xem thông tin liên hệ.")


def _pool_guard(db, application_id: str, user_id: str, scan_id: Optional[str]) -> dict:
    """A Talent Pool invitation needs: a finished scan of a position this HR handles, the candidate marked CONTACT in
    it, consent still valid (not withdrawn, inside the window counted from the CV date, not queued for deletion), and
    the audited contact reveal done by this same user. Errors never repeat candidate data."""
    if not scan_id:
        raise HTTPException(status_code=409, detail=POOL_ONLY)
    scan = db.execute(text("""SELECT s.scan_id, s.status, s.position_id, p.title, p.position_code
        FROM app_private.talent_pool_scans s JOIN app_private.positions p ON p.position_id = s.position_id
        WHERE s.scan_id = :s"""), {"s": scan_id}).mappings().first()
    if not scan:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt quét Talent Pool")
    if not _handles_position(db, user_id, str(scan["position_id"])):
        raise HTTPException(status_code=403, detail="Chỉ HR phụ trách vị trí đang tuyển mới gửi thư mời Talent Pool")
    if scan["status"] != "COMPLETED":
        raise HTTPException(status_code=409, detail="Lượt quét chưa hoàn tất")
    decision = db.execute(text("""SELECT hr_decision FROM app_private.talent_pool_scan_results
        WHERE scan_id = :s AND application_id = :a"""), {"s": scan_id, "a": application_id}).scalar()
    if decision != "CONTACT":
        raise HTTPException(status_code=409, detail="Cần chọn quyết định Liên hệ cho hồ sơ này trong lượt quét trước")
    eligible = db.execute(text(ELIGIBLE_POOL_SQL + " AND a.application_id = :app"),
                          {"now": datetime.now(timezone.utc),
                           "months": settings.TALENT_POOL_RETENTION_MONTHS, "app": application_id}).first()
    if eligible is None:
        state = application_pool_state(db, application_id) or {}
        code = state.get("reason") or "NOT_IN_POOL"
        raise HTTPException(status_code=409, detail=f"Hồ sơ không còn đủ điều kiện Talent Pool nên không thể soạn hoặc gửi "
                                                    f"thư mời (POOL_{code}).")
    revealed = db.execute(text("""SELECT 1 FROM app_private.audit_events WHERE action_type = 'REVEAL_TALENT_POOL_CONTACT'
        AND actor_user_id = :u AND object_id = :a AND metadata ->> 'scan_id' = :s LIMIT 1"""),
                          {"u": user_id, "a": application_id, "s": scan_id}).first()
    if not revealed:
        raise HTTPException(status_code=409, detail="Cần xem thông tin liên hệ trong kết quả quét Talent Pool trước khi soạn thư mời")
    return {"scan_id": str(scan["scan_id"]), "target_position_id": str(scan["position_id"]),
            "target_title": scan["title"], "target_code": scan["position_code"]}


def _application_row(db, application_id: str) -> dict:
    row = db.execute(text("""
        SELECT a.application_id, a.position_id, a.created_at AS applied_at, a.application_status,
               p.title, p.position_code, i.display_name, i.email
        FROM app_private.applications a
        JOIN app_private.positions p ON p.position_id = a.position_id
        LEFT JOIN app_private.application_identities i ON i.application_id = a.application_id
        WHERE a.application_id = :a
    """), {"a": application_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ")
    return dict(row)


def _application(db, application_id: str, user_id: str, *, template_code: Optional[str] = None,
                 scan_id: Optional[str] = None) -> dict:
    """The application with what a letter needs. Normal letters: only HR handling its position. A Talent Pool
    invitation: only through its scan (see _pool_guard), by HR of the position being filled."""
    row = _application_row(db, application_id)
    out = dict(row)
    if template_code == "POOL_INVITE":
        out["pool"] = _pool_guard(db, application_id, user_id, scan_id)
        return out
    if not _handles_position(db, user_id, str(row["position_id"])):
        raise HTTPException(status_code=403, detail="Chỉ HR phụ trách vị trí mới gửi thư cho ứng viên")
    return out


# ---- helpers ------------------------------------------------------------------------

def _sender(hr: dict) -> dict:
    from_address = settings.CANDIDATE_EMAIL_FROM or settings.SMTP_FROM or hr["email"] or ""
    return {"from_address": from_address, "reply_to_address": hr["email"] or None, "send_mode": settings.CANDIDATE_EMAIL_SEND_MODE,
            "smtp_configured": email_enabled()}


def _fill(template: str, values: dict) -> str:
    return _PLACEHOLDER.sub(lambda m: values[m.group(1)] if values.get(m.group(1)) else m.group(0), template)


def _unresolved(*parts: str) -> list[str]:
    return sorted({m.group(1) for part in parts for m in _PLACEHOLDER.finditer(part or "")})


def _email_out(row) -> dict:
    out = dict(row)
    for key in ("email_id", "application_id", "position_id", "created_by", "sent_by"):
        if out.get(key) is not None:
            out[key] = str(out[key])
    return out


def _audit(db, user_id: str, action: str, application: dict, metadata: dict) -> None:
    if application.get("pool"):
        metadata = {**metadata, "pool_invite": True, "scan_id": application["pool"]["scan_id"],
                    "target_position_id": application["pool"]["target_position_id"]}
    db.execute(text("""
        INSERT INTO app_private.audit_events(actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
        VALUES (:u, :action, 'APPLICATION', :a, :p, 'SUCCESS', CAST(:m AS jsonb))
    """), {"u": user_id, "action": action, "a": str(application["application_id"]),
           "p": str(application["position_id"]), "m": json.dumps(metadata)})


def _check_sendable(to_address: str, subject: str, body: str) -> None:
    if "\r" in to_address or "\n" in to_address or not _EMAIL.match(to_address.strip()):
        raise HTTPException(status_code=400, detail="Địa chỉ email người nhận không hợp lệ")
    if "\r" in subject or "\n" in subject:
        raise HTTPException(status_code=400, detail="Tiêu đề thư không được chứa ký tự xuống dòng")
    missing = _unresolved(subject, body)
    if missing:
        raise HTTPException(status_code=400, detail="Thư còn chỗ chưa điền: " + ", ".join("{" + m + "}" for m in missing))


def _check_rate_limit(db, user_id: str) -> None:
    """Every send attempt is audited and counted, failed ones included, so a broken address cannot be retried without limit."""
    recent = db.execute(text("""SELECT COUNT(*) FROM app_private.audit_events
        WHERE actor_user_id = :u AND action_type = 'SEND_CANDIDATE_EMAIL' AND created_at > NOW() - INTERVAL '1 hour'"""),
                        {"u": user_id}).scalar_one()
    if recent >= settings.CANDIDATE_EMAIL_MAX_PER_HOUR:
        raise HTTPException(status_code=429, detail="Bạn đã gửi quá nhiều thư trong một giờ. Vui lòng thử lại sau.")


def _fail_stale_sending(db, *, email_id: Optional[str] = None, application_id: Optional[str] = None) -> None:
    """A letter stuck in SENDING is not known to have gone out: show it as FAILED so HR can look and retry."""
    db.execute(text("""UPDATE app_private.candidate_emails SET status = 'FAILED', error_code = 'SEND_TIMEOUT', updated_at = NOW()
        WHERE status = 'SENDING' AND sending_started_at < NOW() - make_interval(mins => :m)
          AND (CAST(:id AS uuid) IS NULL OR email_id = CAST(:id AS uuid))
          AND (CAST(:app AS uuid) IS NULL OR application_id = CAST(:app AS uuid))"""),
               {"m": STALE_SENDING_MINUTES, "id": email_id, "app": application_id})


def _send_via_transport(email_row: dict) -> tuple[str, Optional[str]]:
    """Perform the SMTP call outside any DB transaction/lock."""
    if settings.CANDIDATE_EMAIL_SEND_MODE != "smtp":
        return "RECORDED", None
    try:
        send_email(email_row["to_address"].strip(), email_row["subject"], email_row["body"],
                   from_address=email_row["from_address"], reply_to=email_row.get("reply_to_address"))
        return "SENT", None
    except MailError as exc:
        return "FAILED", str(exc)[:100]


def _deliver_out_of_tx(email_id: str, user_id: str, confirmed: bool, *, allowed_statuses: tuple[str, ...]) -> dict:
    """Claim the letter (DRAFT/FAILED -> SENDING, one conditional UPDATE under a row lock, so any number of workers or
    processes can race and only one wins), release the connection, call SMTP, then record SENT/FAILED only if the
    letter is still SENDING."""
    db = SessionLocal()
    try:
        _fail_stale_sending(db, email_id=email_id)
        db.commit()
        row, _hr, app = _own_email(db, email_id, user_id, allowed_statuses=allowed_statuses)
        if row["template_code"] == "REJECTION" and not confirmed:
            raise HTTPException(status_code=400, detail="Thư từ chối cần HR xác nhận lần nữa trước khi gửi")
        if row["template_code"] == "POOL_INVITE" and not confirmed:
            raise HTTPException(status_code=400, detail="Thư mời Talent Pool cần HR xác nhận lần nữa trước khi gửi")
        _check_sendable(row["to_address"], row["subject"], row["body"])
        _check_rate_limit(db, user_id)
        claimed = db.execute(text("""UPDATE app_private.candidate_emails
            SET status = 'SENDING', sending_started_at = NOW(), sent_by = :u, error_code = NULL, updated_at = NOW()
            WHERE email_id = :id AND status = ANY(:allowed) RETURNING *"""),
                             {"u": user_id, "id": email_id, "allowed": list(allowed_statuses)}).mappings().first()
        if claimed is None:
            raise HTTPException(status_code=409, detail="Thư này đã được gửi hoặc đang được gửi")
        db.commit()
        snapshot = dict(claimed)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    status, error_code = _send_via_transport(snapshot)

    db = SessionLocal()
    try:
        done = db.execute(text("""UPDATE app_private.candidate_emails
            SET status = :s, error_code = :e, sent_at = CASE WHEN :s = 'FAILED' THEN NULL ELSE NOW() END, updated_at = NOW()
            WHERE email_id = :id AND status = 'SENDING' RETURNING *"""),
                          {"s": status, "e": error_code, "id": email_id}).mappings().first()
        if done is None:
            logger.error("Candidate email left SENDING by someone else", email_id=email_id, outcome=status)
            raise HTTPException(status_code=409, detail="Trạng thái thư đã thay đổi trong lúc gửi; hãy kiểm tra lịch sử thư")
        done = dict(done)
        _audit(db, user_id, "SEND_CANDIDATE_EMAIL", app,
               {"email_id": email_id, "template_code": done["template_code"], "status": done["status"],
                "trigger": done["trigger_source"]})
        db.commit()
        return _email_out(done)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.error("Candidate email outcome could not be saved", email_id=email_id, outcome=status)
        raise
    finally:
        db.close()


def _discard_unsent_draft(email_id: str) -> None:
    """create_email(send=true) saves the draft first; if sending is refused before it starts, do not leave it behind."""
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM app_private.candidate_emails WHERE email_id = :id AND status = 'DRAFT'"), {"id": email_id})
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# ---- templates ----------------------------------------------------------------------

@router.get("/templates")
async def list_templates(current_user: dict = Depends(get_current_user)):
    def run():
        db = SessionLocal()
        try:
            hr = _hr_user(db, current_user["user_id"])
            if not hr["hr_role"] and not db.execute(text("""SELECT 1 FROM app_private.position_assignments
                    WHERE user_id = :u AND revoked_at IS NULL AND position_role IN ('HR_RECRUITER', 'HR_LEAD') LIMIT 1"""),
                    {"u": current_user["user_id"]}).first():
                raise HTTPException(status_code=403, detail="Chỉ HR mới xem được mẫu thư")
            rows = db.execute(text("""SELECT template_code, name, subject_template, body_template, updated_at
                FROM app_private.email_templates ORDER BY CASE template_code WHEN 'ACK_RECEIVED' THEN 1
                WHEN 'REQUEST_INFO' THEN 2 WHEN 'INTERVIEW_INVITE' THEN 3 WHEN 'REJECTION' THEN 4 ELSE 5 END""")).mappings().all()
            return {"templates": [dict(r) for r in rows], "variables": list(VARIABLES), "can_edit": bool(hr["lead_role"])}
        finally:
            db.close()
    return await run_in_threadpool(run)


@router.put("/templates/{template_code}")
async def update_template(template_code: TemplateCode, body: TemplateUpdate, current_user: dict = Depends(get_current_user)):
    def run():
        db = SessionLocal()
        try:
            hr = _hr_user(db, current_user["user_id"])
            if not hr["lead_role"]:
                raise HTTPException(status_code=403, detail="Chỉ HR Lead hoặc Admin mới sửa được mẫu thư")
            row = db.execute(text("""UPDATE app_private.email_templates
                SET subject_template = :s, body_template = :b, updated_by = :u, updated_at = NOW()
                WHERE template_code = :c RETURNING template_code, name, subject_template, body_template, updated_at"""),
                             {"s": body.subject_template.strip(), "b": body.body_template.strip(),
                              "u": current_user["user_id"], "c": template_code}).mappings().first()
            if not row:
                raise HTTPException(status_code=404, detail="Không tìm thấy mẫu thư")
            db.execute(text("""INSERT INTO app_private.audit_events(actor_user_id, action_type, object_type, outcome, metadata)
                VALUES (:u, 'UPDATE_EMAIL_TEMPLATE', 'EMAIL_TEMPLATE', 'SUCCESS', CAST(:m AS jsonb))"""),
                       {"u": current_user["user_id"], "m": json.dumps({"template_code": template_code})})
            db.commit()
            return dict(row)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    return await run_in_threadpool(run)


# ---- per application ----------------------------------------------------------------

@router.get("/applications/{application_id}")
async def application_emails(application_id: UUID, current_user: dict = Depends(get_current_user)):
    """Sender details and the message history of one application (HR of the position)."""
    def run():
        db = SessionLocal()
        try:
            hr = _hr_user(db, current_user["user_id"])
            app = _application(db, str(application_id), current_user["user_id"])
            _fail_stale_sending(db, application_id=str(application_id))
            db.commit()
            rows = db.execute(text("""
                SELECT e.*, p.display_name AS created_by_name, s.display_name AS sent_by_name
                FROM app_private.candidate_emails e
                LEFT JOIN app_private.user_profiles p ON p.user_id = e.created_by
                LEFT JOIN app_private.user_profiles s ON s.user_id = e.sent_by
                WHERE e.application_id = :a ORDER BY e.created_at DESC
            """), {"a": str(application_id)}).mappings().all()
            return {**_sender(hr), "candidate_email": app["email"], "emails": [_email_out(r) for r in rows]}
        finally:
            db.close()
    return await run_in_threadpool(run)


@router.post("/applications/{application_id}/compose")
async def compose(application_id: UUID, body: ComposeRequest, current_user: dict = Depends(get_current_user)):
    """A prefilled message for HR to review. Nothing is saved or sent."""
    def run():
        db = SessionLocal()
        try:
            hr = _hr_user(db, current_user["user_id"])
            scan_id = str(body.scan_id) if body.scan_id else None
            app = _application(db, str(application_id), current_user["user_id"], template_code=body.template_code, scan_id=scan_id)
            pool = app.get("pool")
            template = db.execute(text("SELECT * FROM app_private.email_templates WHERE template_code = :c"),
                                  {"c": body.template_code}).mappings().first()
            if not template:
                raise HTTPException(status_code=404, detail="Không tìm thấy mẫu thư")
            name = (app["display_name"] or "").strip()
            if pool:  # a file name is not a name: greet "Anh/Chị" unless the CV gave a real one
                from app.services.talent_pool_scan import usable_candidate_name
                cv_file = db.execute(text("""SELECT d.original_filename FROM app_private.application_documents d
                    WHERE d.application_id = :a AND d.document_type = 'CV' ORDER BY d.created_at LIMIT 1"""),
                                     {"a": str(application_id)}).scalar()
                name = usable_candidate_name(name, cv_file) or ""
            values = {"ho_ten": name or "Anh/Chị", "vi_tri": (pool["target_title"] if pool else app["title"]) or "",
                      "ma_vi_tri": (pool["target_code"] if pool else app["position_code"]) or "",
                      "ngay_nop": app["applied_at"].strftime("%d/%m/%Y") if app["applied_at"] else "",
                      "ten_hr": hr["display_name"] or "", "email_hr": hr["email"] or ""}
            previous = db.execute(text("""SELECT status, sent_at, created_at FROM app_private.candidate_emails
                WHERE application_id = :a AND template_code = :c AND status IN ('RECORDED', 'SENT', 'DRAFT')
                ORDER BY created_at DESC LIMIT 1"""), {"a": str(application_id), "c": body.template_code}).mappings().first()
            warnings = []
            if not app["email"]:
                warnings.append("NO_CANDIDATE_EMAIL")
            if previous and previous["status"] in ("RECORDED", "SENT"):
                warnings.append("ALREADY_SENT")
            elif previous:
                warnings.append("DRAFT_EXISTS")
            subject, text_body = _fill(template["subject_template"], values), _fill(template["body_template"], values)
            if pool:  # the invitation is being written: leave a trace (ids only)
                _audit(db, current_user["user_id"], "COMPOSE_POOL_INVITE", app, {"template_code": body.template_code})
                db.commit()
            return {**_sender(hr), "template_code": body.template_code, "template_name": template["name"],
                    "to_address": app["email"] or "", "to_source": "PROFILE" if app["email"] else "NONE",
                    "subject": subject, "body": text_body,
                    "unresolved": _unresolved(subject, text_body), "manual_variables": list(MANUAL_VARIABLES),
                    "warnings": warnings, "previous_sent_at": previous["sent_at"] if previous else None}
        finally:
            db.close()
    return await run_in_threadpool(run)


@router.post("/applications/{application_id}/emails", status_code=201)
async def create_email(application_id: UUID, body: EmailInput, current_user: dict = Depends(get_current_user)):
    """Save HR's reviewed message as a draft, or record/send it right away."""
    def run():
        db = SessionLocal()
        try:
            hr = _hr_user(db, current_user["user_id"])
            scan_id = str(body.scan_id) if body.scan_id else None
            app = _application(db, str(application_id), current_user["user_id"], template_code=body.template_code, scan_id=scan_id)
            sender = _sender(hr)
            if body.send:
                if body.template_code in ("REJECTION", "POOL_INVITE") and not body.confirmed:
                    raise HTTPException(status_code=400, detail="Thư này cần HR xác nhận lần nữa trước khi gửi")
                _check_sendable(body.to_address, body.subject, body.body)
                _check_rate_limit(db, current_user["user_id"])
            row = db.execute(text("""
                INSERT INTO app_private.candidate_emails (application_id, position_id, template_code, trigger_source,
                    from_address, reply_to_address, to_address, subject, body, created_by, pool_scan_id)
                VALUES (:a, :p, :c, :t, :f, :r, :to, :s, :b, :u, :ps) RETURNING *
            """), {"a": str(application_id), "p": str(app["position_id"]), "c": body.template_code, "t": body.trigger_source,
                   "f": sender["from_address"], "r": sender["reply_to_address"], "to": body.to_address.strip(),
                   "s": body.subject.strip(), "b": body.body, "u": current_user["user_id"],
                   "ps": app["pool"]["scan_id"] if app.get("pool") else None}).mappings().one()
            row = dict(row)
            if not body.send:
                _audit(db, current_user["user_id"], "DRAFT_CANDIDATE_EMAIL", app,
                       {"email_id": str(row["email_id"]), "template_code": body.template_code, "status": row["status"],
                        "trigger": body.trigger_source})
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        if body.send:
            try:
                return _deliver_out_of_tx(str(row["email_id"]), current_user["user_id"], body.confirmed, allowed_statuses=("DRAFT",))
            except HTTPException:
                _discard_unsent_draft(str(row["email_id"]))  # refused before sending started: no orphan draft
                raise
        return _email_out(row)
    return await run_in_threadpool(run)


def _own_email(db, email_id: str, user_id: str, *, allowed_statuses: tuple[str, ...] = ("DRAFT",),
               for_cancel: bool = False) -> tuple[dict, dict, dict]:
    row = db.execute(text("SELECT * FROM app_private.candidate_emails WHERE email_id = :id FOR UPDATE"),
                     {"id": email_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy thư")
    hr = _hr_user(db, user_id)
    scan_id = str(row["pool_scan_id"]) if row["pool_scan_id"] else None
    if row["template_code"] == "POOL_INVITE" and for_cancel:
        # Throwing a Talent Pool draft away must stay possible after the candidate left the pool.
        target = db.execute(text("SELECT position_id FROM app_private.talent_pool_scans WHERE scan_id = :s"), {"s": scan_id}).scalar() if scan_id else None
        if not (_handles_position(db, user_id, str(row["position_id"])) or (target and _handles_position(db, user_id, str(target)))):
            raise HTTPException(status_code=403, detail="Chỉ HR phụ trách mới hủy được thư này")
        app = _application_row(db, str(row["application_id"]))
    else:
        app = _application(db, str(row["application_id"]), user_id, template_code=row["template_code"], scan_id=scan_id)
    if row["status"] not in allowed_statuses:
        raise HTTPException(status_code=409, detail="Thư này đã được gửi hoặc đã hủy")
    return dict(row), hr, app


@router.put("/emails/{email_id}")
async def update_draft(email_id: UUID, body: EmailUpdate, current_user: dict = Depends(get_current_user)):
    def run():
        db = SessionLocal()
        try:
            _own_email(db, str(email_id), current_user["user_id"], allowed_statuses=("DRAFT", "FAILED"))
            row = db.execute(text("""UPDATE app_private.candidate_emails SET to_address = :to, subject = :s, body = :b,
                updated_at = NOW() WHERE email_id = :id RETURNING *"""),
                             {"to": body.to_address.strip(), "s": body.subject.strip(), "b": body.body,
                              "id": str(email_id)}).mappings().one()
            db.commit()
            return _email_out(row)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    return await run_in_threadpool(run)


@router.post("/emails/{email_id}/send")
async def send_draft(email_id: UUID, body: SendRequest, current_user: dict = Depends(get_current_user)):
    return await run_in_threadpool(
        _deliver_out_of_tx, str(email_id), current_user["user_id"], body.confirmed, allowed_statuses=("DRAFT",))


@router.post("/emails/{email_id}/retry")
async def retry_failed_email(email_id: UUID, body: SendRequest, current_user: dict = Depends(get_current_user)):
    """Retry sending an email whose previous SMTP delivery failed."""
    return await run_in_threadpool(
        _deliver_out_of_tx, str(email_id), current_user["user_id"], body.confirmed, allowed_statuses=("FAILED",))


@router.post("/emails/{email_id}/cancel")
async def cancel_draft(email_id: UUID, current_user: dict = Depends(get_current_user)):
    def run():
        db = SessionLocal()
        try:
            _, _, app = _own_email(db, str(email_id), current_user["user_id"], allowed_statuses=("DRAFT", "FAILED"), for_cancel=True)
            row = db.execute(text("""UPDATE app_private.candidate_emails SET status = 'CANCELLED', updated_at = NOW()
                WHERE email_id = :id RETURNING *"""), {"id": str(email_id)}).mappings().one()
            _audit(db, current_user["user_id"], "CANCEL_CANDIDATE_EMAIL", app,
                   {"email_id": str(email_id), "template_code": row["template_code"]})
            db.commit()
            return _email_out(row)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    return await run_in_threadpool(run)
