"""Admin recovery by a server-held recovery key (AUTH_BACKEND=local, no email needed).

Whoever holds ADMIN_RECOVERY_KEY (set once in the server configuration, kept like a system password) can list the
Admin accounts and set a new password for one of them in the web page /admin-recovery. Wrong keys are rate limited
per address and overall; every use is audited without the key or any password."""
import hashlib
import hmac
import json
import secrets
import time
from collections import defaultdict, deque
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator
from sqlalchemy import text

from app.api.public_intake import _ip_hash, client_address
from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import SessionLocal
from app.schemas.accounts import validate_password
from app.services import local_auth
from app.services.mailer import MailError, email_enabled, send_email

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


class RecoveryEmail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class RecoveryCodeReset(RecoveryEmail):
    code: SecretStr = Field(min_length=1, max_length=64)
    new_password: SecretStr

    _password = field_validator("new_password")(validate_password)


# No look-alike characters (0/O, 1/I/L). 12 characters of 31 = about 59 bits, shown as XXXX-XXXX-XXXX.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 12
CODE_TTL_MINUTES = 15
MAX_CODE_ATTEMPTS = 5
MAX_CODES_PER_HOUR = 3
GENERIC_EMAIL = ("Nếu email thuộc một tài khoản Admin đang hoạt động, hệ thống đã gửi mã tới email đó. "
                 "Nhập mã vào ô đầu tiên bên dưới cùng mật khẩu mới.")
GENERIC_CODE_ERROR = "Email hoặc mã không đúng, hoặc mã đã hết hạn. Hãy kiểm tra hoặc gửi lại mã."


def generate_code() -> str:
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
    return "-".join(raw[i:i + 4] for i in range(0, CODE_LENGTH, 4))


def normalize_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch in CODE_ALPHABET)


def _hash_code(code: str) -> str:
    return hashlib.sha256(normalize_code(code).encode("utf-8")).hexdigest()


def _active_admin(db, email: str):
    return db.execute(text("""
        SELECT u.id FROM auth.users u JOIN app_private.user_profiles p ON p.user_id = u.id
        WHERE lower(u.email) = :email AND p.account_status = 'ACTIVE'
          AND EXISTS (SELECT 1 FROM app_private.user_role_assignments r
                      WHERE r.user_id = u.id AND r.role_code = 'ADMIN' AND r.revoked_at IS NULL)
    """), {"email": email}).first()


@router.post("/email-code", status_code=202)
def send_email_code(body: RecoveryEmail, http_request: Request):
    """Step 1 of the email path: the Admin types their email. The answer is the same for every email; only an
    ACTIVE Admin gets a mail, with a one-time code that plays the part of the old password in step 2."""
    from app.api.auth import _limit_public_calls
    _limit_public_calls(http_request)
    if not email_enabled():
        raise HTTPException(status_code=409, detail="Chưa cấu hình email. Hãy dùng mã khôi phục, hoặc nhờ Admin khác / "
                            "người quản trị máy chủ.")
    email = str(body.email).strip().lower()
    db = SessionLocal()
    try:
        row = _active_admin(db, email)
        if not row:
            return {"message": GENERIC_EMAIL}
        user_id = str(row[0])
        recent = db.execute(text("""
            SELECT COUNT(*) FROM app_private.admin_recovery_codes WHERE user_id = :id AND created_at > NOW() - INTERVAL '1 hour'
        """), {"id": user_id}).scalar_one()
        if recent >= MAX_CODES_PER_HOUR:
            return {"message": GENERIC_EMAIL}
        db.execute(text("""
            UPDATE app_private.admin_recovery_codes SET used_at = NOW(), cancelled = TRUE WHERE user_id = :id AND used_at IS NULL
        """), {"id": user_id})
        code = generate_code()
        db.execute(text("""
            INSERT INTO app_private.admin_recovery_codes (user_id, code_hash, expires_at)
            VALUES (:id, :hash, NOW() + make_interval(mins => :ttl))
        """), {"id": user_id, "hash": _hash_code(code), "ttl": CODE_TTL_MINUTES})
        _audit(db, "ADMIN_RECOVERY_EMAIL_CODE_SENT", user_id, http_request)
        db.commit()
        try:
            send_email(email, "Mã khôi phục tài khoản Admin VinUni HRA",
                       "Có yêu cầu khôi phục tài khoản Admin của bạn. Mã dưới đây đóng vai mật khẩu cũ: nhập nó vào ô đầu tiên "
                       f"trên trang khôi phục cùng mật khẩu mới.\n\n    {code}\n\n"
                       f"Mã hết hạn sau {CODE_TTL_MINUTES} phút, dùng được một lần và bị hủy nếu nhập sai {MAX_CODE_ATTEMPTS} lần. "
                       "Không chuyển tiếp thư này. Nếu bạn không yêu cầu, hãy bỏ qua thư và báo cho người quản trị hệ thống.")
        except MailError as exc:
            logger.warning("Admin recovery code email failed", error_type=str(exc))
        return {"message": GENERIC_EMAIL}
    finally:
        db.close()


@router.post("/email-code/reset")
def reset_with_email_code(body: RecoveryCodeReset, http_request: Request):
    """Step 2: email + the code from the mail + new password. Every failure gives the same answer."""
    if not email_enabled():
        raise HTTPException(status_code=409, detail="Chưa cấu hình email. Hãy dùng mã khôi phục, hoặc nhờ Admin khác / "
                            "người quản trị máy chủ.")
    ip, now = client_address(http_request), time.time()
    mine = _failures_by_ip[ip]
    _prune(mine, now)
    if len(mine) >= MAX_FAILURES_PER_IP:
        raise HTTPException(status_code=429, detail="Đã nhập sai quá nhiều lần. Vui lòng thử lại sau 15 phút.")
    invalid = HTTPException(status_code=400, detail=GENERIC_CODE_ERROR)
    email = str(body.email).strip().lower()
    given = _hash_code(body.code.get_secret_value())
    db = SessionLocal()
    try:
        row = _active_admin(db, email)
        open_code = None
        if row:
            open_code = db.execute(text("""
                SELECT code_id, user_id, code_hash, failed_attempts FROM app_private.admin_recovery_codes
                WHERE user_id = :id AND used_at IS NULL AND expires_at > NOW() FOR UPDATE
            """), {"id": str(row[0])}).mappings().first()
        stored = open_code["code_hash"] if open_code else hashlib.sha256(b"no-open-code").hexdigest()
        matches = hmac.compare_digest(given, stored)
        if not open_code or not matches:
            mine.append(now)
            if open_code:
                attempts = open_code["failed_attempts"] + 1
                db.execute(text("""
                    UPDATE app_private.admin_recovery_codes SET failed_attempts = :n,
                        used_at = CASE WHEN :n >= :max THEN NOW() ELSE NULL END, cancelled = (:n >= :max)
                    WHERE code_id = :id
                """), {"n": attempts, "max": MAX_CODE_ATTEMPTS, "id": str(open_code["code_id"])})
                db.commit()
            else:
                db.rollback()
            raise invalid
        user_id = str(open_code["user_id"])
        db.execute(text("UPDATE app_private.admin_recovery_codes SET used_at = NOW() WHERE code_id = :id"), {"id": str(open_code["code_id"])})
        local_auth.set_password(db, user_id, body.new_password.get_secret_value())
        db.execute(text("""
            UPDATE app_private.user_profiles SET must_change_password = FALSE,
                tokens_valid_after = clock_timestamp(), updated_at = NOW() WHERE user_id = :id
        """), {"id": user_id})
        _audit(db, "ADMIN_RECOVERY_EMAIL_CODE_USED", user_id, http_request)
        db.commit()
        mine.clear()
        return {"changed": True}
    except HTTPException:
        raise
    finally:
        db.close()
