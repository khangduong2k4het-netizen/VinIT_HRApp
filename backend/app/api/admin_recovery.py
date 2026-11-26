"""Admin recovery by a server-held recovery key (AUTH_BACKEND=local, no email needed).

Whoever holds ADMIN_RECOVERY_KEY (set once in the server configuration, kept like a system password) can list the
Admin accounts and set a new password for one of them in the web page /admin-recovery. Wrong keys are rate limited
per address and overall; every use is audited without the key or any password."""
import hashlib
import hmac
import json
import time
from collections import defaultdict, deque
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy import text

from app.api.public_intake import _ip_hash, client_address
from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import SessionLocal
from app.schemas.accounts import validate_password
from app.services import local_auth

router = APIRouter()
logger = get_logger(__name__)

MIN_KEY_LENGTH = 32
WINDOW_SECONDS = 15 * 60
MAX_FAILURES_PER_IP = 5
MAX_FAILURES_OVERALL = 20
_failures_by_ip: dict[str, deque] = defaultdict(deque)
_failures_overall: deque = deque()


def recovery_enabled() -> bool:
    return settings.AUTH_BACKEND == "local" and len((settings.ADMIN_RECOVERY_KEY or "").strip()) >= MIN_KEY_LENGTH


class RecoveryKey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: SecretStr = Field(min_length=1, max_length=256)


class RecoveryReset(RecoveryKey):
    user_id: UUID
    new_password: SecretStr

    _password = field_validator("new_password")(validate_password)


def _prune(window: deque, now: float) -> None:
    while window and window[0] < now - WINDOW_SECONDS:
        window.popleft()


def _check_key(http_request: Request, key: SecretStr) -> None:
    if not recovery_enabled():
        raise HTTPException(status_code=404, detail="Không tìm thấy.")
    ip, now = client_address(http_request), time.time()
    mine = _failures_by_ip[ip]
    _prune(mine, now)
    _prune(_failures_overall, now)
    if len(mine) >= MAX_FAILURES_PER_IP or len(_failures_overall) >= MAX_FAILURES_OVERALL:
        raise HTTPException(status_code=429, detail="Đã nhập sai mã quá nhiều lần. Vui lòng thử lại sau 15 phút.")
    given = hashlib.sha256(key.get_secret_value().strip().encode("utf-8")).digest()
    expected = hashlib.sha256(settings.ADMIN_RECOVERY_KEY.strip().encode("utf-8")).digest()
    if not hmac.compare_digest(given, expected):
        mine.append(now)
        _failures_overall.append(now)
        logger.warning("Admin recovery key rejected")
        raise HTTPException(status_code=401, detail="Mã khôi phục không đúng.")
    _failures_by_ip.pop(ip, None)


def _audit(db, action: str, user_id: str | None, http_request: Request, extra: dict | None = None) -> None:
    meta = {"via": "recovery_page", "ip_hash": _ip_hash(http_request), **(extra or {})}
    db.execute(text("""
        INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome, metadata)
        VALUES (NULL, :action, 'USER', :user_id, 'SUCCESS', CAST(:meta AS jsonb))
    """), {"action": action, "user_id": user_id, "meta": json.dumps(meta)})


@router.post("/admins")
def list_admins(body: RecoveryKey, http_request: Request):
    """The Admin accounts (so nobody has to remember an email). Requires the recovery key."""
    _check_key(http_request, body.key)
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT u.id AS user_id, u.email, p.display_name, p.account_status FROM auth.users u
            JOIN app_private.user_profiles p ON p.user_id = u.id
            WHERE EXISTS (SELECT 1 FROM app_private.user_role_assignments r
                          WHERE r.user_id = u.id AND r.role_code = 'ADMIN' AND r.revoked_at IS NULL)
            ORDER BY p.account_status, u.email
        """)).mappings().all()
        _audit(db, "ADMIN_RECOVERY_LIST_VIEWED", None, http_request, {"count": len(rows)})
        db.commit()
        return {"items": [{**dict(r), "user_id": str(r["user_id"])} for r in rows]}
    finally:
        db.close()


@router.post("/reset")
def reset_admin(body: RecoveryReset, http_request: Request):
    """Set a new password for one ACTIVE Admin, revoke their sessions and clear a temporary lock."""
    _check_key(http_request, body.key)
    target = str(body.user_id)
    db = SessionLocal()
    try:
        row = db.execute(text("""
            SELECT p.account_status,
                   EXISTS (SELECT 1 FROM app_private.user_role_assignments r
                           WHERE r.user_id = p.user_id AND r.role_code = 'ADMIN' AND r.revoked_at IS NULL) AS is_admin
            FROM app_private.user_profiles p WHERE p.user_id = :id FOR UPDATE
        """), {"id": target}).mappings().first()
        if not row or not row["is_admin"]:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản Admin này.")
        if row["account_status"] != "ACTIVE":
            raise HTTPException(status_code=409, detail="Chỉ đặt lại mật khẩu cho Admin đang hoạt động.")
        local_auth.set_password(db, target, body.new_password.get_secret_value())
        db.execute(text("""
            UPDATE app_private.user_profiles SET must_change_password = FALSE,
                tokens_valid_after = clock_timestamp(), updated_at = NOW() WHERE user_id = :id
        """), {"id": target})
        _audit(db, "ADMIN_RECOVERY_RESET_PASSWORD", target, http_request)
        db.commit()
        return {"changed": True}
    except HTTPException:
        db.rollback()
        raise
    finally:
        db.close()
