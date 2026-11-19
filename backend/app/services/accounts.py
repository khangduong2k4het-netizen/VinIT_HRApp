"""Provisioning across Auth and PostgreSQL; never log credentials or request bodies."""
import json
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger
from app.db.supabase import get_supabase_client
from app.services import local_auth

logger = get_logger(__name__)


def _insert_profile_and_roles(db, *, user_id: str, display_name: str, roles: list[str],
                              actor_id: str | None, bootstrap: bool) -> None:
    db.execute(text("""
        INSERT INTO app_private.user_profiles (user_id, display_name, account_status, must_change_password)
        VALUES (:user_id, :display_name, 'ACTIVE', :must_change)
    """), {"user_id": user_id, "display_name": display_name, "must_change": not bootstrap})
    for role in roles:
        db.execute(text("""
            INSERT INTO app_private.user_role_assignments (user_id, role_code, granted_by)
            VALUES (:user_id, :role, :actor)
        """), {"user_id": user_id, "role": role, "actor": actor_id})
    db.execute(text("""
        INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome, metadata)
        VALUES (:actor, :action, 'USER', :user_id, 'ACTIVE', CAST(:metadata AS jsonb))
    """), {"actor": actor_id or user_id, "action": "BOOTSTRAP_ADMIN" if bootstrap else "CREATE_USER",
            "user_id": user_id, "metadata": json.dumps({"roles": sorted(roles), "must_change_password": not bootstrap,
                                                        "auth_backend": settings.AUTH_BACKEND})})


def _provision_local_user(db, *, email: str, password: str, display_name: str,
                          roles: list[str], actor_id: str | None, bootstrap: bool) -> str:
    """AUTH_BACKEND=local: identity, credentials, profile and roles commit atomically."""
    user_id = str(uuid4())
    try:
        local_auth.create_identity(db, user_id, email, password)
        _insert_profile_and_roles(db, user_id=user_id, display_name=display_name, roles=roles,
                                  actor_id=actor_id, bootstrap=bootstrap)
        db.commit()
        return user_id
    except local_auth.LocalIdentityExists:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email đã tồn tại hoặc không thể dùng để tạo tài khoản.") from None
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Local account provisioning failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=503, detail="Không tạo được tài khoản. Vui lòng thử lại.") from None


def provision_user(db, *, email: str, password: str, display_name: str,
                   roles: list[str], actor_id: str | None, bootstrap: bool) -> str:
    """Create Auth identity and app profile/roles while caller holds authorization locks.

    Auth and PostgreSQL cannot participate in one transaction. Before DB commit,
    a definite failure is compensated by deleting only the new Auth identity.
    A failed/unknown commit is NOT compensated automatically: doing so might
    delete an identity whose DB commit actually succeeded. Operators must inspect
    Auth and app records before retrying an ambiguous failure.
    """
    if settings.AUTH_BACKEND == "local":
        return _provision_local_user(db, email=email, password=password, display_name=display_name,
                                     roles=roles, actor_id=actor_id, bootstrap=bootstrap)
    client = get_supabase_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Dịch vụ tạo tài khoản chưa được cấu hình.")
    user_id = str(uuid4())
    created = False
    commit_started = False
    try:
        try:
            response = client.auth.admin.create_user({
                "id": user_id,
                "email": email,
                "password": password,
                # Email ownership must be verified out of band by the admin.
                "email_confirm": True,
            })
        except Exception as exc:
            code = getattr(exc, "code", None)
            status = getattr(exc, "status", None)
            if code in ("email_exists", "user_already_exists"):
                raise HTTPException(status_code=409, detail="Email đã tồn tại hoặc không thể dùng để tạo tài khoản.") from None
            if status in (400, 422):
                raise HTTPException(status_code=400, detail="Email hoặc mật khẩu không đáp ứng chính sách của dịch vụ xác thực.") from None
            # An Auth timeout can occur after creation: do not delete an
            # identity whose existence/ownership has not been confirmed.
            logger.warning("Auth user creation failed or has an unknown outcome", error_type=type(exc).__name__, user_id=user_id)
            raise HTTPException(status_code=503, detail="Không xác nhận được việc tạo tài khoản. Kiểm tra Supabase Auth trước khi thử lại.") from None
        try:
            returned_id = str(UUID(str(response.user.id)))
        except (AttributeError, ValueError, TypeError):
            logger.error("Auth returned an invalid new user identifier", requested_user_id=user_id)
            raise HTTPException(status_code=503, detail="Không xác nhận được việc tạo tài khoản. Kiểm tra Supabase Auth trước khi thử lại.") from None
        if returned_id != user_id:
            logger.error("Auth returned a different user identifier", requested_user_id=user_id, returned_user_id=returned_id)
            raise HTTPException(status_code=503, detail="Không xác nhận được việc tạo tài khoản. Kiểm tra Supabase Auth trước khi thử lại.")
        created = True
        db.execute(text("""
            INSERT INTO app_private.user_profiles (user_id, display_name, account_status, must_change_password)
            VALUES (:user_id, :display_name, 'ACTIVE', :must_change)
        """), {"user_id": user_id, "display_name": display_name, "must_change": not bootstrap})
        for role in roles:
            db.execute(text("""
                INSERT INTO app_private.user_role_assignments (user_id, role_code, granted_by)
                VALUES (:user_id, :role, :actor)
            """), {"user_id": user_id, "role": role, "actor": actor_id})
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome, metadata)
            VALUES (:actor, :action, 'USER', :user_id, 'ACTIVE', CAST(:metadata AS jsonb))
        """), {"actor": actor_id or user_id, "action": "BOOTSTRAP_ADMIN" if bootstrap else "CREATE_USER",
                "user_id": user_id, "metadata": json.dumps({"roles": sorted(roles), "must_change_password": not bootstrap})})
        commit_started = True
        db.commit()
        return user_id
    except Exception as exc:
        try:
            db.rollback()
        except Exception as rollback_exc:
            logger.error("Account transaction rollback failed", error_type=type(rollback_exc).__name__, user_id=user_id)
        if created and not commit_started:
            try:
                client.auth.admin.delete_user(user_id)
            except Exception as cleanup_exc:
                logger.error("Unable to compensate new Auth identity", error_type=type(cleanup_exc).__name__, user_id=user_id)
        elif created and commit_started:
            logger.error("Account DB commit outcome is unknown; manual reconciliation required", user_id=user_id)
        if isinstance(exc, HTTPException):
            raise
        logger.error("Account provisioning failed", error_type=type(exc).__name__, user_id=user_id)
        raise HTTPException(status_code=503, detail="Không xác nhận được việc tạo tài khoản. Kiểm tra Supabase Auth trước khi thử lại.") from None


def reset_user_password(db, *, target_user_id: str, new_password: str, actor_id: str) -> None:
    """Reset a member password through the Supabase Auth Admin API.

    The target profile is marked as requiring a change and every access token
    issued earlier is rejected by ``tokens_valid_after``. The password itself
    is never logged or written into audit metadata. If the DB finalize fails
    after Auth has accepted the password, the caller must not retry blindly:
    the new temporary password may already be effective while the account was
    not marked for a forced change.
    """
    client = get_supabase_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Dịch vụ đặt lại mật khẩu chưa được cấu hình.")
    target = db.execute(text("""
        SELECT account_status FROM app_private.user_profiles
        WHERE user_id = :id FOR UPDATE
    """), {"id": target_user_id}).mappings().first()
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
    if target["account_status"] != "ACTIVE":
        raise HTTPException(status_code=400, detail="Chỉ đặt lại mật khẩu cho tài khoản đang hoạt động.")
    try:
        client.auth.admin.update_user_by_id(target_user_id, {"password": new_password})
    except Exception as exc:
        if getattr(exc, "code", None) == "weak_password" or getattr(exc, "status", None) in (400, 422):
            raise HTTPException(status_code=400, detail="Mật khẩu tạm thời không đáp ứng chính sách của dịch vụ xác thực.") from None
        logger.warning("Admin password reset failed or has an unknown outcome", error_type=type(exc).__name__, user_id=target_user_id)
        raise HTTPException(status_code=503, detail="Không xác nhận được việc đặt lại mật khẩu. Kiểm tra Supabase Auth trước khi thử lại.") from None
    db.execute(text("""
        UPDATE app_private.user_profiles
        SET must_change_password = TRUE,
            tokens_valid_after = clock_timestamp(), updated_at = NOW()
        WHERE user_id = :id
    """), {"id": target_user_id})
    db.execute(text("""
        INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome)
        VALUES (:actor, 'RESET_USER_PASSWORD', 'USER', :target, 'SUCCESS')
    """), {"actor": actor_id, "target": target_user_id})
    db.commit()
