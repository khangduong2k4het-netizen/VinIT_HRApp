import hashlib
import hmac
import time

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, SecretStr
from sqlalchemy import text
from supabase import create_client

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import ensure_token_is_current, get_active_user
from app.db.database import SessionLocal
from app.schemas.accounts import (BootstrapRequest, ForgotPasswordRequest, PasswordChange, RegisterRequest,
                                  ResetPasswordRequest)
from app.services import local_auth, password_reset
from app.services.mailer import MailError, email_enabled, send_email
from app.services.accounts import provision_user

router = APIRouter()
logger = get_logger(__name__)


class LoginRequest(BaseModel):
    email: str
    password: SecretStr


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


def _bootstrap_configured() -> bool:
    token = settings.ADMIN_BOOTSTRAP_TOKEN
    auth_ready = settings.AUTH_BACKEND == "local" or bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)
    return 32 <= len(token) <= 256 and auth_ready


@router.get("/bootstrap-status")
def bootstrap_status():
    """Expose only whether setup is available, never the setup token or identity."""
    if not _bootstrap_configured():
        return {"available": False}
    db = SessionLocal()
    try:
        available = db.execute(text("""
            SELECT initialized_at IS NULL AND NOT EXISTS (
                SELECT 1 FROM app_private.user_role_assignments WHERE role_code = 'ADMIN'
            ) FROM app_private.account_initialization WHERE singleton = TRUE
        """)).scalar_one()
        return {"available": bool(available)}
    finally:
        db.close()


@router.post("/bootstrap", status_code=201)
def bootstrap_admin(request: BootstrapRequest):
    """Create the first administrator once, with an operator-provided secret."""
    if not _bootstrap_configured():
        raise HTTPException(status_code=403, detail="Khởi tạo Admin hiện không được mở.")
    expected = hashlib.sha256(settings.ADMIN_BOOTSTRAP_TOKEN.encode("utf-8")).digest()
    try:
        provided = hashlib.sha256(request.setup_token.get_secret_value().encode("utf-8")).digest()
    except UnicodeError:
        raise HTTPException(status_code=403, detail="Mã khởi tạo không hợp lệ.") from None
    if not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=403, detail="Mã khởi tạo không hợp lệ.")
    db = SessionLocal()
    try:
        marker = db.execute(text("""
            SELECT initialized_at FROM app_private.account_initialization
            WHERE singleton = TRUE FOR UPDATE
        """)).mappings().one()
        already_has_admin = db.execute(text("""
            SELECT EXISTS (SELECT 1 FROM app_private.user_role_assignments WHERE role_code = 'ADMIN')
        """)).scalar_one()
        if marker["initialized_at"] is not None or already_has_admin:
            raise HTTPException(status_code=409, detail="Hệ thống đã được khởi tạo Admin; không thể khởi tạo lại.")
        user_id = provision_user(db, email=str(request.email), password=request.password.get_secret_value(),
                                 display_name=request.display_name, roles=["ADMIN"], actor_id=None, bootstrap=True)
        return {"user_id": user_id, "message": "Đã tạo Admin. Hãy đăng nhập bằng tài khoản vừa tạo."}
    finally:
        db.close()


def _local_login(credentials: LoginRequest) -> LoginResponse:
    """AUTH_BACKEND=local: verify the scrypt hash and issue the app's own token."""
    db = SessionLocal()
    try:
        try:
            identity = local_auth.authenticate(db, credentials.email, credentials.password.get_secret_value())
        except local_auth.LocalAuthLocked:
            raise HTTPException(status_code=429, detail="Tài khoản tạm khóa do nhập sai mật khẩu nhiều lần. Vui lòng thử lại sau.") from None
        if not identity:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email hoặc mật khẩu không đúng")
        profile = db.execute(text("""
            SELECT account_status, must_change_password, tokens_valid_after FROM app_private.user_profiles WHERE user_id = :id
        """), {"id": identity["user_id"]}).mappings().first()
        if not profile or profile["account_status"] != "ACTIVE":
            raise HTTPException(status_code=403, detail="Tài khoản chưa được kích hoạt (đang chờ Admin duyệt) hoặc đã bị khóa")
        token, expires_in = local_auth.issue_token(identity["user_id"], identity["email"])
        if profile["tokens_valid_after"] is not None:
            # A token issued in the same second as an approval / password reset is refused by design.
            # Wait out that second here instead of making the user retry by hand.
            for attempt in (0, 1):
                try:
                    ensure_token_is_current(jwt.decode(token, options={"verify_signature": False}), profile["tokens_valid_after"])
                    break
                except Exception:
                    if attempt:
                        raise HTTPException(status_code=409, detail="Vui lòng chờ vài giây rồi đăng nhập lại.") from None
                    time.sleep(1.1)
                    token, expires_in = local_auth.issue_token(identity["user_id"], identity["email"])
        return LoginResponse(access_token=token, expires_in=expires_in,
                             user={"id": identity["user_id"], "email": identity["email"],
                                   "must_change_password": bool(profile["must_change_password"])})
    finally:
        db.close()


@router.post("/login", response_model=LoginResponse)
def login(credentials: LoginRequest):
    """Login with email/password via an isolated Supabase client, or locally."""
    if settings.AUTH_BACKEND == "local":
        return _local_login(credentials)
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        raise HTTPException(status_code=503, detail="Authentication service is not configured")
    try:
        # Never sign in on the cached service-role client: this could replace
        # its session and affect unrelated requests.
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
        response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password.get_secret_value(),
        })
        if not response.user or not response.session:
            raise RuntimeError("Auth returned an incomplete response")
    except Exception as exc:
        if getattr(exc, "status", None) in (400, 401, 403):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email hoặc mật khẩu không đúng") from None
        logger.warning("Supabase login failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Dịch vụ đăng nhập tạm thời không khả dụng. Vui lòng thử lại sau.") from None
    db = SessionLocal()
    try:
        profile = db.execute(text("""
            SELECT account_status, must_change_password, tokens_valid_after FROM app_private.user_profiles WHERE user_id = :id
        """), {"id": str(response.user.id)}).mappings().first()
        if not profile or profile["account_status"] != "ACTIVE":
            raise HTTPException(status_code=403, detail="Tài khoản chưa được kích hoạt (đang chờ Admin duyệt) hoặc đã bị khóa")
        if profile["tokens_valid_after"] is not None:
            try:
                # The response came directly from Auth; full signature checking
                # still occurs on every subsequent request. Avoid returning a
                # same-second token that our reset cutoff would reject.
                payload = jwt.decode(response.session.access_token, options={"verify_signature": False})
                ensure_token_is_current(payload, profile["tokens_valid_after"])
            except Exception:
                raise HTTPException(status_code=409, detail="Vui lòng chờ vài giây rồi đăng nhập lại.") from None
        return LoginResponse(access_token=response.session.access_token, expires_in=response.session.expires_in,
                             user={"id": str(response.user.id), "email": response.user.email,
                                   "must_change_password": bool(profile["must_change_password"])})
    finally:
        db.close()


@router.get("/me")
def get_current_user_info(current_user: dict = Depends(get_active_user)):
    """Get own profile/roles, including whether a temporary password must change."""
    user_id = current_user["user_id"]
    db = SessionLocal()
    try:
        row = db.execute(text("""
            SELECT user_id, display_name, preferred_locale, account_status, must_change_password
            FROM app_private.user_profiles WHERE user_id = :id
        """), {"id": user_id}).mappings().first()
        if not row or row["account_status"] != "ACTIVE":
            raise HTTPException(status_code=403, detail="Tài khoản chưa được kích hoạt hoặc đã bị khóa")
        profile = dict(row)
        roles = db.execute(text("SELECT role_code FROM app_private.user_role_assignments WHERE user_id = :id AND revoked_at IS NULL"), {"id": user_id}).scalars().all()
        assignments = db.execute(text("""
            SELECT position_id, position_role FROM app_private.position_assignments WHERE user_id = :id AND revoked_at IS NULL
        """), {"id": user_id}).mappings().all()
        return {"user_id": user_id, "email": current_user.get("email"), "profile": profile,
                "display_name": profile["display_name"], "must_change_password": profile["must_change_password"],
                "system_roles": list(roles), "position_assignments": [dict(item) for item in assignments]}
    finally:
        db.close()


@router.post("/change-password")
def change_own_password(request: PasswordChange, current_user: dict = Depends(get_active_user)):
    """Reauthenticate the owner before changing their own password.

    This serves both the forced temporary-password flow and voluntary
    password changes from the account menu. The current password is always
    verified (Supabase Auth, or the local scrypt hash with AUTH_BACKEND=local);
    a bearer token alone is not enough.
    """
    if settings.AUTH_BACKEND != "local" and (not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY):
        raise HTTPException(status_code=503, detail="Authentication service is not configured")
    old_password = request.current_password.get_secret_value()
    new_password = request.new_password.get_secret_value()
    if hmac.compare_digest(old_password.encode("utf-8"), new_password.encode("utf-8")):
        raise HTTPException(status_code=400, detail="Mật khẩu mới phải khác mật khẩu hiện tại.")
    if not current_user.get("email"):
        raise HTTPException(status_code=403, detail="Không thể xác minh email của tài khoản.")
    db = SessionLocal()
    try:
        profile = db.execute(text("""
            SELECT account_status, must_change_password, tokens_valid_after
            FROM app_private.user_profiles WHERE user_id = :id FOR UPDATE
        """), {"id": current_user["user_id"]}).mappings().first()
        if not profile or profile["account_status"] != "ACTIVE":
            raise HTTPException(status_code=403, detail="Tài khoản chưa được kích hoạt hoặc đã bị khóa")
        ensure_token_is_current(current_user["token_payload"], profile["tokens_valid_after"])
        was_forced_change = bool(profile["must_change_password"])
        if settings.AUTH_BACKEND == "local":
            if not local_auth.verify_user_password(db, current_user["user_id"], old_password):
                raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng.")
            local_auth.set_password(db, current_user["user_id"], new_password)
        else:
            _change_supabase_password(current_user, old_password, new_password)
        db.execute(text("""
            UPDATE app_private.user_profiles SET must_change_password = FALSE,
                tokens_valid_after = clock_timestamp(), updated_at = NOW() WHERE user_id = :id
        """), {"id": current_user["user_id"]})
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome)
            VALUES (:id, :action, 'USER', :id, 'SUCCESS')
        """), {"id": current_user["user_id"],
              "action": "CHANGE_TEMPORARY_PASSWORD" if was_forced_change else "CHANGE_OWN_PASSWORD"})
        db.commit()
        return {"changed": True}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Unable to finalize password change", error_type=type(exc).__name__, user_id=current_user["user_id"])
        raise HTTPException(status_code=503, detail="Không xác nhận được việc đổi mật khẩu. Hãy kiểm tra mật khẩu mới trước khi thử lại.") from None
    finally:
        db.close()


def _change_supabase_password(current_user: dict, old_password: str, new_password: str) -> None:
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    try:
        verified = client.auth.sign_in_with_password({"email": current_user["email"], "password": old_password})
        if not verified.user or str(verified.user.id) != str(current_user["user_id"]):
            raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng.")
    except HTTPException:
        raise
    except Exception as exc:
        if getattr(exc, "status", None) in (400, 401, 403):
            raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng.") from None
        logger.warning("Password reauthentication failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=503, detail="Không thể xác minh mật khẩu. Vui lòng thử lại.") from None
    try:
        client.auth.update_user({"password": new_password})
    except Exception as exc:
        if getattr(exc, "code", None) == "weak_password":
            raise HTTPException(status_code=400, detail="Mật khẩu mới không đáp ứng chính sách của dịch vụ xác thực.") from None
        logger.warning("Password update failed or has an unknown outcome", error_type=type(exc).__name__, user_id=current_user["user_id"])
        raise HTTPException(status_code=503, detail="Không xác nhận được việc đổi mật khẩu. Hãy kiểm tra mật khẩu mới trước khi thử lại.") from None


GENERIC_REGISTER = "Đã gửi đăng ký, chờ Admin duyệt."
GENERIC_FORGOT = "Nếu email thuộc một tài khoản đang hoạt động, hướng dẫn đặt lại mật khẩu đã được gửi."


@router.get("/public-config")
def public_config():
    """What the login page may offer. No secrets."""
    return {"self_registration": bool(settings.SELF_REGISTRATION_ENABLED),
            "password_reset": settings.AUTH_BACKEND == "local" or email_enabled(),
            "registration_domains": [d.strip() for d in settings.SELF_REGISTRATION_ALLOWED_DOMAINS.split(",") if d.strip()]}


@router.post("/register", status_code=201)
def register(request: RegisterRequest):
    """Self-registration: INACTIVE account without a role until an Admin approves it.

    Duplicate emails get the same answer as new ones, so the response never reveals
    whether an account exists.
    """
    if not settings.SELF_REGISTRATION_ENABLED:
        raise HTTPException(status_code=404, detail="Không tìm thấy.")
    email = str(request.email).strip().lower()
    if not password_reset.allowed_registration_domain(email):
        domains = ", ".join(d.strip() for d in settings.SELF_REGISTRATION_ALLOWED_DOMAINS.split(",") if d.strip())
        raise HTTPException(status_code=400, detail="Email phải thuộc tên miền được phép: " + domains)
    db = SessionLocal()
    try:
        provision_user(db, email=email, password=request.password.get_secret_value(),
                       display_name=request.display_name, roles=[], actor_id=None, bootstrap=False,
                       account_status="INACTIVE", self_registered=True)
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
    finally:
        db.close()
    return {"message": GENERIC_REGISTER}


@router.post("/forgot-password", status_code=202)
def forgot_password(request: ForgotPasswordRequest):
    """Always answers the same, whether or not the email has an active account."""
    result: dict = {"message": GENERIC_FORGOT}
    if settings.AUTH_BACKEND != "local" and not settings.SUPABASE_SERVICE_ROLE_KEY:
        return result
    email = str(request.email).strip().lower()
    db = SessionLocal()
    try:
        row = db.execute(text("""
            SELECT u.id FROM auth.users u JOIN app_private.user_profiles p ON p.user_id = u.id
            WHERE lower(u.email) = :email AND p.account_status = 'ACTIVE'
        """), {"email": email}).first()
        if not row:
            return result
        user_id = str(row[0])
        token = password_reset.issue_token(db, user_id)
        if token is None:
            db.rollback()
            return result
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome)
            VALUES (:id, 'REQUEST_PASSWORD_RESET', 'USER', :id, 'SUCCESS')
        """), {"id": user_id})
        db.commit()
        link = f"{settings.APP_PUBLIC_URL.rstrip('/')}/reset-password?token={token}"
        sent = False
        if email_enabled():
            try:
                send_email(email, "Đặt lại mật khẩu VinUni HRA",
                           f"Mở liên kết sau để đặt lại mật khẩu (hết hạn sau {settings.PASSWORD_RESET_TTL_MINUTES} phút, "
                           f"dùng một lần):\n\n{link}\n\nNếu bạn không yêu cầu, hãy bỏ qua email này.")
                sent = True
            except MailError as exc:
                logger.warning("Password reset email failed", error_type=str(exc))
        if not sent and settings.PASSWORD_RESET_DEV_ECHO:
            result["dev_reset_link"] = link
        return result
    finally:
        db.close()


@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest):
    """Set a new password with a one-time token from the reset link."""
    invalid = HTTPException(status_code=400, detail="Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.")
    db = SessionLocal()
    try:
        user_id = password_reset.consume_token(db, request.token)
        if not user_id:
            db.rollback()
            raise invalid
        status_row = db.execute(text("SELECT account_status FROM app_private.user_profiles WHERE user_id = :id FOR UPDATE"),
                                {"id": user_id}).first()
        if not status_row or status_row[0] != "ACTIVE":
            db.rollback()
            raise invalid
        new_password = request.new_password.get_secret_value()
        if settings.AUTH_BACKEND == "local":
            local_auth.set_password(db, user_id, new_password)
        else:
            from app.db.supabase import get_supabase_client
            client = get_supabase_client()
            if client is None:
                db.rollback()
                raise HTTPException(status_code=503, detail="Dịch vụ đặt lại mật khẩu chưa được cấu hình.")
            try:
                client.auth.admin.update_user_by_id(user_id, {"password": new_password})
            except Exception:
                db.rollback()
                raise HTTPException(status_code=400, detail="Mật khẩu mới không đáp ứng chính sách của dịch vụ xác thực.") from None
        db.execute(text("""
            UPDATE app_private.user_profiles SET must_change_password = FALSE,
                tokens_valid_after = clock_timestamp(), updated_at = NOW() WHERE user_id = :id
        """), {"id": user_id})
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome)
            VALUES (:id, 'RESET_PASSWORD_BY_TOKEN', 'USER', :id, 'SUCCESS')
        """), {"id": user_id})
        db.commit()
        return {"changed": True}
    finally:
        db.close()
