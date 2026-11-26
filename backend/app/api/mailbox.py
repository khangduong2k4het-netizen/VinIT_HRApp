"""F3.03 email channel: connect the Gmail recruiting mailbox (Admin) and sort the
CVs HRA could not place (HR triage).

Addresses, subjects and file names are shown to HR in the app but are never
written to audit metadata or logs.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from app.core.config import settings
from app.core.permissions import check_position_access, require_admin_role
from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.services import gmail_client as gmail
from app.services import mail_intake

router = APIRouter()
HR_ROLES = ("ADMIN", "HR_LEAD", "HR_RECRUITER")


# ---- helpers -------------------------------------------------------------------------

def _state_secret() -> bytes:
    secret = settings.SUPABASE_JWT_SECRET or settings.MAILBOX_ENCRYPTION_KEY or settings.AI_CONFIG_ENCRYPTION_KEY or ""
    if not secret:
        raise HTTPException(status_code=503, detail="Server chưa có khóa bí mật để ký yêu cầu kết nối")
    return secret.encode()


def make_state(user_id: str) -> str:
    payload = f"{user_id}.{int(time.time()) + 600}.{secrets.token_hex(8)}"
    sig = hmac.new(_state_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}.{sig}".encode()).decode().rstrip("=")


def read_state(state: str) -> Optional[str]:
    """The admin user id in a state we issued in the last 10 minutes, else None."""
    try:
        raw = base64.urlsafe_b64decode(state + "=" * (-len(state) % 4)).decode()
        user_id, expires, nonce, sig = raw.split(".")
    except (ValueError, UnicodeDecodeError):
        return None
    expected = hmac.new(_state_secret(), f"{user_id}.{expires}.{nonce}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected) or int(expires) < time.time():
        return None
    return user_id


def _is_admin(db, user_id: str) -> bool:
    return db.execute(text("""SELECT 1 FROM app_private.user_role_assignments r
        JOIN app_private.user_profiles p ON p.user_id = r.user_id
        WHERE r.user_id = :u AND r.revoked_at IS NULL AND r.role_code = 'ADMIN' AND p.account_status = 'ACTIVE'"""),
                      {"u": user_id}).first() is not None


def _require_hr(current_user: dict) -> None:
    db = SessionLocal()
    try:
        ok = db.execute(text("""SELECT 1 FROM app_private.user_role_assignments r
            JOIN app_private.user_profiles p ON p.user_id = r.user_id
            WHERE r.user_id = :u AND r.revoked_at IS NULL AND r.role_code = ANY(:roles) AND p.account_status = 'ACTIVE'
            LIMIT 1"""), {"u": current_user["user_id"], "roles": list(HR_ROLES)}).first()
    finally:
        db.close()
    if not ok:
        raise HTTPException(status_code=403, detail="Chỉ HR mới xem được hộp thư CV")


def _audit(db, user_id: Optional[str], action: str, object_id: Optional[str], metadata: dict, position_id: Optional[str] = None) -> None:
    db.execute(text("""INSERT INTO app_private.audit_events(actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
        VALUES (:u, :a, 'MAILBOX', :o, :p, 'SUCCESS', CAST(:m AS jsonb))"""),
               {"u": user_id, "a": action, "o": object_id, "p": position_id, "m": json.dumps(metadata)})


def intake_address(account_email: Optional[str], position_code: str) -> Optional[str]:
    if not account_email or "@" not in account_email:
        return None
    local, domain = account_email.split("@", 1)
    return f"{local.split('+')[0]}+{position_code}@{domain}"


# ---- Admin: connection --------------------------------------------------------------

@router.get("/status")
async def mailbox_status(_: dict = Depends(require_admin_role)):
    def run():
        db = SessionLocal()
        try:
            account = mail_intake.active_account(db)
            counts = dict(db.execute(text("""SELECT status, COUNT(*) FROM app_private.mailbox_messages
                WHERE created_at > NOW() - INTERVAL '30 days' GROUP BY status""")).all())
            return {
                "enabled": settings.GMAIL_INTAKE_ENABLED,
                "client_configured": bool(settings.GMAIL_CLIENT_ID and settings.GMAIL_CLIENT_SECRET),
                "pubsub_topic": settings.GMAIL_PUBSUB_TOPIC, "pubsub_subscription": settings.GMAIL_PUBSUB_SUBSCRIPTION,
                "redirect_uri": settings.GMAIL_REDIRECT_URI, "encryption_ready": _encryption_ready(),
                "account": None if not account else {
                    "email_address": account["email_address"], "status": account["status"],
                    "last_error": account["last_error"], "last_sync_at": account["last_sync_at"],
                    "watch_expires_at": account["watch_expires_at"], "connected_at": account["connected_at"],
                    "address_example": intake_address(account["email_address"], "REQ-IT-043"),
                },
                "last_30_days": {k: int(v) for k, v in counts.items()},
            }
        finally:
            db.close()
    return await run_in_threadpool(run)


def _encryption_ready() -> bool:
    try:
        gmail.encrypt_token("check")
        return True
    except gmail.GmailError:
        return False


@router.post("/gmail/connect")
async def gmail_connect(current_user: dict = Depends(require_admin_role)):
    """Google sign-in link for the Admin to connect the recruiting Gmail account."""
    if not gmail.configured():
        raise HTTPException(status_code=409, detail="Chưa bật GMAIL_INTAKE_ENABLED hoặc thiếu GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET")
    if not _encryption_ready():
        raise HTTPException(status_code=409, detail="Chưa cấu hình MAILBOX_ENCRYPTION_KEY để lưu khóa truy cập Gmail")
    return {"auth_url": gmail.auth_url(make_state(current_user["user_id"]))}


@router.get("/gmail/callback")
async def gmail_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """Google sends the browser back here after sign-in; we finish and return to the admin page."""
    back = settings.FRONTEND_BASE_URL.rstrip("/") + "/admin/mailbox"
    user_id = read_state(state or "")
    if not user_id:
        return RedirectResponse(back + "?error=STATE_INVALID", status_code=302)
    if error or not code:
        return RedirectResponse(back + "?error=" + ("ACCESS_DENIED" if error == "access_denied" else "NO_CODE"), status_code=302)

    def run() -> str:
        db = SessionLocal()
        try:
            if not _is_admin(db, user_id):
                return "NOT_ADMIN"
            try:
                tokens = gmail.exchange_code(code)
                profile = gmail.get_profile(tokens["access_token"])
                ciphertext = gmail.encrypt_token(tokens["refresh_token"])
            except gmail.GmailError as exc:
                return exc.code
            address = profile["emailAddress"].lower()
            # One mailbox at a time: connecting replaces the previous one.
            db.execute(text("""UPDATE app_private.mailbox_accounts SET status = 'DISCONNECTED', updated_at = NOW()
                WHERE status <> 'DISCONNECTED'"""))
            account_id = db.execute(text("""INSERT INTO app_private.mailbox_accounts(provider, email_address,
                    refresh_token_ciphertext, history_id, connected_by) VALUES ('GMAIL', :e, :t, :h, :u) RETURNING account_id"""),
                                    {"e": address, "t": ciphertext, "h": str(profile.get("historyId")), "u": user_id}).scalar_one()
            _audit(db, user_id, "CONNECT_MAILBOX", str(account_id), {"provider": "GMAIL"})
            db.commit()
            return "OK"
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    result = await run_in_threadpool(run)
    if result == "OK":
        await run_in_threadpool(mail_intake.sync_mailbox)  # starts the watch and reads today's mail
        return RedirectResponse(back + "?connected=1", status_code=302)
    return RedirectResponse(back + "?error=" + result, status_code=302)


@router.post("/disconnect")
async def disconnect(current_user: dict = Depends(require_admin_role)):
    def run():
        db = SessionLocal()
        try:
            account = mail_intake.active_account(db)
            if not account:
                raise HTTPException(status_code=404, detail="Chưa kết nối hộp thư nào")
            try:
                refresh = gmail.decrypt_token(account["refresh_token_ciphertext"])
                gmail.stop_watch(gmail.access_token(refresh))
                gmail.forget_token(refresh)
            except gmail.GmailError:
                pass  # disconnect locally even if Google cannot be reached
            db.execute(text("""UPDATE app_private.mailbox_accounts SET status = 'DISCONNECTED', refresh_token_ciphertext = '',
                watch_expires_at = NULL, updated_at = NOW() WHERE account_id = :id"""), {"id": account["account_id"]})
            _audit(db, current_user["user_id"], "DISCONNECT_MAILBOX", str(account["account_id"]), {"provider": "GMAIL"})
            db.commit()
            return {"status": "DISCONNECTED"}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    return await run_in_threadpool(run)


@router.post("/sync")
async def sync_now(_: dict = Depends(require_admin_role)):
    """Read new mail now instead of waiting for the next notification."""
    return await run_in_threadpool(mail_intake.sync_mailbox)


# ---- HR: intake address and triage ----------------------------------------------------

@router.get("/intake-address")
async def get_intake_address(position_code: str = Query(min_length=3, max_length=40), current_user: dict = Depends(get_current_user)):
    """The address candidates can send a CV to for this position, if a mailbox is connected."""
    _require_hr(current_user)

    def run():
        db = SessionLocal()
        try:
            account = mail_intake.active_account(db)
            ok = account and account["status"] == "ACTIVE"
            return {"address": intake_address(account["email_address"], position_code.upper()) if ok else None}
        finally:
            db.close()
    return await run_in_threadpool(run)


@router.get("/messages")
async def list_messages(status: Literal["NEEDS_TRIAGE", "MATCHED", "IGNORED", "FAILED"] = "NEEDS_TRIAGE",
                        limit: int = Query(default=50, ge=1, le=200), current_user: dict = Depends(get_current_user)):
    _require_hr(current_user)

    def run():
        db = SessionLocal()
        try:
            rows = db.execute(text("""
                SELECT m.message_id, m.from_address, m.from_name, m.subject, m.received_at, m.created_at, m.status,
                       m.reason, m.match_method, m.suggestions, m.position_id, p.position_code, p.title AS position_title,
                       (SELECT a.application_id FROM app_private.mailbox_attachments a
                        WHERE a.message_id = m.message_id AND a.application_id IS NOT NULL LIMIT 1) AS application_id
                FROM app_private.mailbox_messages m
                LEFT JOIN app_private.positions p ON p.position_id = m.position_id
                WHERE m.status = :s ORDER BY COALESCE(m.received_at, m.created_at) DESC LIMIT :n
            """), {"s": status, "n": limit}).mappings().all()
            ids = [r["message_id"] for r in rows]
            files = {}
            if ids:
                for f in db.execute(text("""SELECT attachment_id, message_id, filename, mime_type, size_bytes, status, reject_reason
                        FROM app_private.mailbox_attachments WHERE message_id = ANY(:ids) ORDER BY created_at"""),
                                    {"ids": ids}).mappings().all():
                    files.setdefault(f["message_id"], []).append({
                        "attachment_id": str(f["attachment_id"]), "filename": f["filename"], "mime_type": f["mime_type"],
                        "size_bytes": f["size_bytes"], "status": f["status"], "reject_reason": f["reject_reason"]})
            return {"items": [{
                **{k: (str(v) if k in ("message_id", "position_id", "application_id") and v else v) for k, v in r.items()},
                "attachments": files.get(r["message_id"], []),
            } for r in rows]}
        finally:
            db.close()
    return await run_in_threadpool(run)


@router.get("/attachments/{attachment_id}/file")
async def attachment_file(attachment_id: UUID, current_user: dict = Depends(get_current_user)):
    """A file waiting for triage, for HR to open before choosing the position."""
    _require_hr(current_user)

    def run():
        db = SessionLocal()
        try:
            row = db.execute(text("""SELECT a.storage_path, a.mime_type, a.filename, m.status FROM app_private.mailbox_attachments a
                JOIN app_private.mailbox_messages m USING (message_id) WHERE a.attachment_id = :id"""),
                             {"id": str(attachment_id)}).mappings().first()
            if not row or not row["storage_path"] or row["status"] != "NEEDS_TRIAGE":
                raise HTTPException(status_code=404, detail="Không tìm thấy tệp")
            return mail_intake.read_stored(row["storage_path"]), row["mime_type"]
        finally:
            db.close()
    content, mime = await run_in_threadpool(run)
    return Response(content=content, media_type=mime or "application/octet-stream",
                    headers={"Content-Disposition": "inline", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


class AssignInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    position_id: UUID
    attachment_id: Optional[UUID] = None


def _triage_message(db, message_id: str) -> dict:
    row = db.execute(text("SELECT * FROM app_private.mailbox_messages WHERE message_id = :id FOR UPDATE"),
                     {"id": message_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy thư")
    if row["status"] != "NEEDS_TRIAGE":
        raise HTTPException(status_code=409, detail="Thư này đã được xử lý")
    return dict(row)


@router.post("/messages/{message_id}/assign")
async def assign(message_id: UUID, body: AssignInput, current_user: dict = Depends(get_current_user)):
    """HR picks the position for a CV HRA could not place; the application is created like any email CV."""
    _require_hr(current_user)
    await check_position_access(body.position_id, current_user, required_roles=["HR_RECRUITER"])

    def run():
        db = SessionLocal()
        try:
            msg = _triage_message(db, str(message_id))
            pos = db.execute(text(mail_intake.EMAIL_OPEN_POSITION_SQL + " AND p.position_id = :p"),
                             {"p": str(body.position_id)}).first()
            if not pos:
                raise HTTPException(status_code=409, detail="Vị trí chưa mở hoặc chưa có bộ tiêu chí được duyệt")
            files = db.execute(text("""SELECT * FROM app_private.mailbox_attachments
                WHERE message_id = :m AND status = 'STORED' ORDER BY created_at"""), {"m": str(message_id)}).mappings().all()
            if body.attachment_id:
                files = [f for f in files if str(f["attachment_id"]) == str(body.attachment_id)]
            if not files:
                raise HTTPException(status_code=409, detail="Thư không còn tệp CV để dùng")
            chosen = mail_intake._pick_cv([{"filename": f["filename"], "mime": f["mime_type"] or "", "size": f["size_bytes"] or 0,
                                            "row": f} for f in files])["row"]
            content = mail_intake.read_stored(chosen["storage_path"])
            app_id = mail_intake.create_application(
                db, pos, {"filename": chosen["filename"], "mime": chosen["mime_type"], "declared": chosen["mime_type"],
                          "content": content},
                message_id=str(message_id), method="HR",
                sender={"address": msg["from_address"], "name": msg["from_name"]})
            for f in db.execute(text("SELECT * FROM app_private.mailbox_attachments WHERE message_id = :m AND status = 'STORED'"),
                                {"m": str(message_id)}).mappings().all():
                used = f["attachment_id"] == chosen["attachment_id"] and app_id is not None
                db.execute(text("""UPDATE app_private.mailbox_attachments SET status = :s, application_id = :a, storage_path = NULL
                    WHERE attachment_id = :id"""), {"s": "USED" if used else "DISCARDED", "a": app_id if used else None,
                                                     "id": f["attachment_id"]})
                mail_intake.remove_stored(f["storage_path"])
            db.execute(text("""UPDATE app_private.mailbox_messages SET status = :s, position_id = :p, match_method = 'HR',
                reason = :r, decided_by = :u, decided_at = NOW() WHERE message_id = :id"""),
                       {"s": "MATCHED" if app_id else "IGNORED", "p": str(body.position_id), "u": current_user["user_id"],
                        "r": None if app_id else "DUPLICATE_CV", "id": str(message_id)})
            _audit(db, current_user["user_id"], "ASSIGN_EMAIL_CV", str(message_id), {"duplicate": app_id is None},
                   position_id=str(body.position_id))
            db.commit()
            return {"status": "MATCHED" if app_id else "DUPLICATE", "application_id": app_id}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    return await run_in_threadpool(run)


@router.post("/messages/{message_id}/ignore")
async def ignore(message_id: UUID, current_user: dict = Depends(get_current_user)):
    """Not a CV, spam, or not for any open position: delete the kept files."""
    _require_hr(current_user)

    def run():
        db = SessionLocal()
        try:
            _triage_message(db, str(message_id))
            for f in db.execute(text("""SELECT attachment_id, storage_path FROM app_private.mailbox_attachments
                    WHERE message_id = :m AND status = 'STORED'"""), {"m": str(message_id)}).mappings().all():
                mail_intake.remove_stored(f["storage_path"])
                db.execute(text("UPDATE app_private.mailbox_attachments SET status = 'DISCARDED', storage_path = NULL WHERE attachment_id = :id"),
                           {"id": f["attachment_id"]})
            db.execute(text("""UPDATE app_private.mailbox_messages SET status = 'IGNORED', reason = 'HR_IGNORED',
                decided_by = :u, decided_at = NOW() WHERE message_id = :id"""), {"u": current_user["user_id"], "id": str(message_id)})
            _audit(db, current_user["user_id"], "IGNORE_EMAIL_CV", str(message_id), {})
            db.commit()
            return {"status": "IGNORED"}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    return await run_in_threadpool(run)
