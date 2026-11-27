"""ADMIN review of password-reset requests. Approving emails a one-time reset link to the account's own address;
the link is never returned to the Admin or to the person who asked."""
import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger
from app.core.permissions import require_admin_role
from app.db.database import SessionLocal
from app.services import password_reset
from app.services.mailer import MailError, email_enabled, send_email

router = APIRouter()
logger = get_logger(__name__)
EXPIRE_AFTER_DAYS = 7


class RejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: Optional[str] = Field(default=None, max_length=500)


def expire_old_requests(db) -> None:
    db.execute(text("""
        UPDATE app_private.password_reset_requests SET status = 'EXPIRED', decided_at = NOW()
        WHERE status = 'PENDING' AND requested_at < NOW() - make_interval(days => :d)
    """), {"d": EXPIRE_AFTER_DAYS})


def _audit(db, actor_id: str, action: str, request_id: str, user_id: str, outcome: str) -> None:
    db.execute(text("""
        INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome, metadata)
        VALUES (:actor, :action, 'USER', :user_id, :outcome, CAST(:metadata AS jsonb))
    """), {"actor": actor_id, "action": action, "user_id": user_id, "outcome": outcome,
            "metadata": json.dumps({"request_id": request_id})})


@router.get("")
def list_requests(status: Optional[str] = Query("PENDING", pattern="^(PENDING|APPROVED|REJECTED|EXPIRED|ALL)$"),
                  current_user: dict = Depends(require_admin_role)):
    db = SessionLocal()
    try:
        expire_old_requests(db)
        db.commit()
        rows = db.execute(text("""
            SELECT r.request_id, r.user_id, r.email, p.display_name, r.reason, r.status, r.requested_at, r.decided_at, r.decision_note
            FROM app_private.password_reset_requests r JOIN app_private.user_profiles p ON p.user_id = r.user_id
            WHERE (:status = 'ALL' OR r.status = :status)
            ORDER BY r.requested_at DESC LIMIT 100
        """), {"status": status}).mappings().all()
        return {"items": [dict(row) for row in rows], "email_configured": email_enabled()}
    finally:
        db.close()


def _lock_pending(db, request_id: str) -> dict:
    row = db.execute(text("""
        SELECT r.request_id, r.user_id, r.email, r.status, p.account_status
        FROM app_private.password_reset_requests r JOIN app_private.user_profiles p ON p.user_id = r.user_id
        WHERE r.request_id = :id FOR UPDATE OF r
    """), {"id": request_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu.")
    if row["status"] != "PENDING":
        raise HTTPException(status_code=409, detail="Yêu cầu này đã được xử lý hoặc đã hết hạn.")
    return dict(row)


@router.post("/{request_id}/approve")
def approve_request(request_id: UUID, current_user: dict = Depends(require_admin_role)):
    actor_id, rid = current_user["user_id"], str(request_id)
    if not email_enabled():
        raise HTTPException(status_code=409, detail="Chưa cấu hình email nên không gửi được link. Hãy dùng nút "
                            "'Đặt lại mật khẩu' (mật khẩu tạm) ở Quản lý tài khoản.")
    db = SessionLocal()
    try:
        expire_old_requests(db)
        req = _lock_pending(db, rid)
        target = str(req["user_id"])
        if req["account_status"] != "ACTIVE":
            raise HTTPException(status_code=409, detail="Tài khoản này không còn hoạt động.")
        if target == actor_id:
            other_admins = db.execute(text("""
                SELECT COUNT(*) FROM app_private.user_role_assignments r JOIN app_private.user_profiles p ON p.user_id = r.user_id
                WHERE r.role_code = 'ADMIN' AND r.revoked_at IS NULL AND p.account_status = 'ACTIVE' AND r.user_id <> :me
            """), {"me": actor_id}).scalar_one()
            raise HTTPException(status_code=403 if other_admins else 409,
                                detail="Bạn không thể tự duyệt yêu cầu của chính mình; nhờ Admin khác duyệt." if other_admins
                                else "Chỉ có một Admin: hãy dùng lệnh khẩn cấp scripts/reset_admin_password.py trên máy chủ.")
        token = password_reset.issue_token(db, target, "RESET")
        if token is None:
            raise HTTPException(status_code=429, detail="Tài khoản này đã nhận quá nhiều link trong giờ qua. Thử lại sau.")
        link = f"{settings.APP_PUBLIC_URL.rstrip('/')}/reset-password?token={token}"
        try:
            send_email(req["email"], "Đặt lại mật khẩu VinUni HRA",
                       f"Admin đã duyệt yêu cầu đặt lại mật khẩu của bạn. Mở liên kết sau (hết hạn sau "
                       f"{settings.PASSWORD_RESET_TTL_MINUTES} phút, dùng một lần):\n\n{link}\n\n"
                       "Nếu bạn không gửi yêu cầu này, hãy báo cho Admin.")
        except MailError as exc:
            db.rollback()
            logger.warning("Approved reset link could not be emailed", error_type=str(exc))
            raise HTTPException(status_code=502, detail="Không gửi được email. Kiểm tra cấu hình email rồi thử lại.") from None
        db.execute(text("""
            UPDATE app_private.password_reset_requests SET status = 'APPROVED', decided_by = :actor, decided_at = NOW()
            WHERE request_id = :id
        """), {"actor": actor_id, "id": rid})
        _audit(db, actor_id, "APPROVE_PASSWORD_RESET_REQUEST", rid, target, "APPROVED")
        db.commit()
        return {"request_id": rid, "status": "APPROVED", "sent_to": req["email"]}
    except HTTPException:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/{request_id}/reject")
def reject_request(request_id: UUID, body: RejectRequest, current_user: dict = Depends(require_admin_role)):
    actor_id, rid = current_user["user_id"], str(request_id)
    db = SessionLocal()
    try:
        req = _lock_pending(db, rid)
        db.execute(text("""
            UPDATE app_private.password_reset_requests
            SET status = 'REJECTED', decided_by = :actor, decided_at = NOW(), decision_note = :note WHERE request_id = :id
        """), {"actor": actor_id, "id": rid, "note": (body.note or "").strip() or None})
        _audit(db, actor_id, "REJECT_PASSWORD_RESET_REQUEST", rid, str(req["user_id"]), "REJECTED")
        db.commit()
        return {"request_id": rid, "status": "REJECTED"}
    except HTTPException:
        db.rollback()
        raise
    finally:
        db.close()
