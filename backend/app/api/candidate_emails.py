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
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.core.config import settings
from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.services.mailer import MailError, email_enabled, send_email

router = APIRouter()

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


def _application(db, application_id: str, user_id: str) -> dict:
    """The application with what a letter needs; only HR handling its position may use it."""
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
    allowed = db.execute(text("""
        SELECT EXISTS (SELECT 1 FROM app_private.user_role_assignments r WHERE r.user_id = :u
                       AND r.revoked_at IS NULL AND r.role_code IN ('ADMIN', 'HR_LEAD'))
            OR EXISTS (SELECT 1 FROM app_private.position_assignments pa WHERE pa.user_id = :u
                       AND pa.position_id = :p AND pa.revoked_at IS NULL
                       AND pa.position_role IN ('HR_RECRUITER', 'HR_LEAD'))
    """), {"u": user_id, "p": str(row["position_id"])}).scalar()
    if not allowed:
        raise HTTPException(status_code=403, detail="Chỉ HR phụ trách vị trí mới gửi thư cho ứng viên")
    return dict(row)


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
    db.execute(text("""
        INSERT INTO app_private.audit_events(actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
        VALUES (:u, :action, 'APPLICATION', :a, :p, 'SUCCESS', CAST(:m AS jsonb))
    """), {"u": user_id, "action": action, "a": str(application["application_id"]),
           "p": str(application["position_id"]), "m": json.dumps(metadata)})


def _check_sendable(to_address: str, subject: str, body: str) -> None:
    if not _EMAIL.match(to_address.strip()):
        raise HTTPException(status_code=400, detail="Địa chỉ email người nhận không hợp lệ")
    missing = _unresolved(subject, body)
    if missing:
        raise HTTPException(status_code=400, detail="Thư còn chỗ chưa điền: " + ", ".join("{" + m + "}" for m in missing))


def _deliver(db, email_row: dict, hr: dict, user_id: str, confirmed: bool) -> dict:
    """Record or send one message HR has reviewed. Caller commits."""
    if email_row["template_code"] == "REJECTION" and not confirmed:
        raise HTTPException(status_code=400, detail="Thư từ chối cần HR xác nhận lần nữa trước khi gửi")
    _check_sendable(email_row["to_address"], email_row["subject"], email_row["body"])
    recent = db.execute(text("""SELECT COUNT(*) FROM app_private.candidate_emails
        WHERE sent_by = :u AND status IN ('RECORDED', 'SENT') AND sent_at > NOW() - INTERVAL '1 hour'"""),
                        {"u": user_id}).scalar_one()
    if recent >= settings.CANDIDATE_EMAIL_MAX_PER_HOUR:
        raise HTTPException(status_code=429, detail="Bạn đã gửi quá nhiều thư trong một giờ. Vui lòng thử lại sau.")
    status, error_code = "RECORDED", None
    if settings.CANDIDATE_EMAIL_SEND_MODE == "smtp":
        try:
            send_email(email_row["to_address"].strip(), email_row["subject"], email_row["body"],
                       from_address=email_row["from_address"], reply_to=email_row.get("reply_to_address"))
            status = "SENT"
        except MailError as exc:
            status, error_code = "FAILED", str(exc)[:100]
    row = db.execute(text("""
        UPDATE app_private.candidate_emails
        SET status = :s, error_code = :e, sent_by = :u, sent_at = CASE WHEN :s = 'FAILED' THEN NULL ELSE NOW() END,
            updated_at = NOW()
        WHERE email_id = :id RETURNING *
    """), {"s": status, "e": error_code, "u": user_id, "id": str(email_row["email_id"])}).mappings().one()
    return dict(row)


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
            app = _application(db, str(application_id), current_user["user_id"])
            template = db.execute(text("SELECT * FROM app_private.email_templates WHERE template_code = :c"),
                                  {"c": body.template_code}).mappings().first()
            if not template:
                raise HTTPException(status_code=404, detail="Không tìm thấy mẫu thư")
            values = {"ho_ten": (app["display_name"] or "").strip() or "Anh/Chị", "vi_tri": app["title"] or "", "ma_vi_tri": app["position_code"] or "",
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
            app = _application(db, str(application_id), current_user["user_id"])
            sender = _sender(hr)
            if body.send:
                _check_sendable(body.to_address, body.subject, body.body)
            row = db.execute(text("""
                INSERT INTO app_private.candidate_emails (application_id, position_id, template_code, trigger_source,
                    from_address, reply_to_address, to_address, subject, body, created_by)
                VALUES (:a, :p, :c, :t, :f, :r, :to, :s, :b, :u) RETURNING *
            """), {"a": str(application_id), "p": str(app["position_id"]), "c": body.template_code, "t": body.trigger_source,
                   "f": sender["from_address"], "r": sender["reply_to_address"], "to": body.to_address.strip(),
                   "s": body.subject.strip(), "b": body.body, "u": current_user["user_id"]}).mappings().one()
            row = dict(row)
            if body.send:
                row = _deliver(db, row, hr, current_user["user_id"], body.confirmed)
            _audit(db, current_user["user_id"], "SEND_CANDIDATE_EMAIL" if body.send else "DRAFT_CANDIDATE_EMAIL", app,
                   {"email_id": str(row["email_id"]), "template_code": body.template_code, "status": row["status"],
                    "trigger": body.trigger_source})
            db.commit()
            return _email_out(row)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    return await run_in_threadpool(run)


def _own_draft(db, email_id: str, user_id: str) -> tuple[dict, dict, dict]:
    row = db.execute(text("SELECT * FROM app_private.candidate_emails WHERE email_id = :id FOR UPDATE"),
                     {"id": email_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy thư")
    hr = _hr_user(db, user_id)
    app = _application(db, str(row["application_id"]), user_id)
    if row["status"] != "DRAFT":
        raise HTTPException(status_code=409, detail="Thư này đã được gửi hoặc đã hủy")
    return dict(row), hr, app


@router.put("/emails/{email_id}")
async def update_draft(email_id: UUID, body: EmailUpdate, current_user: dict = Depends(get_current_user)):
    def run():
        db = SessionLocal()
        try:
            _own_draft(db, str(email_id), current_user["user_id"])
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
    def run():
        db = SessionLocal()
        try:
            row, hr, app = _own_draft(db, str(email_id), current_user["user_id"])
            row = _deliver(db, row, hr, current_user["user_id"], body.confirmed)
            _audit(db, current_user["user_id"], "SEND_CANDIDATE_EMAIL", app,
                   {"email_id": str(email_id), "template_code": row["template_code"], "status": row["status"],
                    "trigger": row["trigger_source"]})
            db.commit()
            return _email_out(row)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    return await run_in_threadpool(run)


@router.post("/emails/{email_id}/cancel")
async def cancel_draft(email_id: UUID, current_user: dict = Depends(get_current_user)):
    def run():
        db = SessionLocal()
        try:
            _, _, app = _own_draft(db, str(email_id), current_user["user_id"])
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
