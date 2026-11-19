"""ADMIN-only user provisioning and account/role administration."""
import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from app.api.admin import _lock_active_admin
from app.core.permissions import require_admin_role
from app.db.database import SessionLocal
from app.schemas.accounts import AccountStatus, AdminPasswordReset, AdminUserCreate, AdminUserUpdate, Role
from app.services.accounts import provision_user, reset_user_password

router = APIRouter()


def _lock_management(db, actor_id: str) -> None:
    # Serialize all role/status changes made through this API so two admins
    # cannot remove the last active ADMIN concurrently. Then hold the actor's
    # profile and ADMIN assignment until the write/provisioning finishes.
    db.execute(text("SELECT pg_advisory_xact_lock(708195211)"))
    _lock_active_admin(db, actor_id)


@router.get("")
def list_managed_users(
    search: Optional[str] = Query(None, max_length=120),
    role: Optional[Role] = None,
    account_status: Optional[AccountStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: dict = Depends(require_admin_role),
):
    """List account profiles and Auth emails; never return password or tokens."""
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT p.user_id, p.display_name, p.preferred_locale, p.account_status,
                   p.must_change_password, p.created_at, u.email,
                   COALESCE(array_agg(DISTINCT r.role_code ORDER BY r.role_code)
                       FILTER (WHERE r.role_code IS NOT NULL), ARRAY[]::text[]) AS roles
            FROM app_private.user_profiles p
            JOIN auth.users u ON u.id = p.user_id
            LEFT JOIN app_private.user_role_assignments r ON r.user_id = p.user_id AND r.revoked_at IS NULL
            WHERE (CAST(:search AS text) IS NULL OR p.display_name ILIKE :pattern OR u.email ILIKE :pattern)
              AND (CAST(:status AS text) IS NULL OR p.account_status = :status)
              AND (CAST(:role AS text) IS NULL OR EXISTS (
                    SELECT 1 FROM app_private.user_role_assignments chosen
                    WHERE chosen.user_id = p.user_id AND chosen.role_code = :role AND chosen.revoked_at IS NULL
              ))
            GROUP BY p.user_id, u.email
            ORDER BY lower(p.display_name), p.user_id
            LIMIT :limit OFFSET :offset
        """), {"search": search.strip() if search and search.strip() else None,
                "pattern": f"%{search.strip()}%" if search and search.strip() else None,
                "status": account_status, "role": role, "limit": page_size + 1,
                "offset": (page - 1) * page_size}).mappings().all()
        return {"items": [dict(row) for row in rows[:page_size]], "page": page,
                "page_size": page_size, "has_more": len(rows) > page_size}
    finally:
        db.close()


@router.post("", status_code=201)
def create_managed_user(request: AdminUserCreate, current_user: dict = Depends(require_admin_role)):
    """Create an Auth identity; the owner must change its temporary password."""
    db = SessionLocal()
    try:
        _lock_management(db, current_user["user_id"])
        user_id = provision_user(db, email=str(request.email), password=request.password.get_secret_value(),
                                 display_name=request.display_name, roles=list(request.roles),
                                 actor_id=current_user["user_id"], bootstrap=False)
        return {"user_id": user_id, "must_change_password": True}
    finally:
        db.close()


@router.post("/{user_id}/reset-password")
def reset_managed_user_password(user_id: UUID, request: AdminPasswordReset,
                                current_user: dict = Depends(require_admin_role)):
    """Give a member a new temporary password and revoke earlier sessions."""
    db = SessionLocal()
    try:
        _lock_management(db, current_user["user_id"])
        reset_user_password(db, target_user_id=str(user_id),
                            new_password=request.new_password.get_secret_value(),
                            actor_id=current_user["user_id"])
        return {"user_id": str(user_id), "must_change_password": True}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.patch("/{user_id}")
def update_managed_user(user_id: UUID, request: AdminUserUpdate, current_user: dict = Depends(require_admin_role)):
    """Update profile/status/roles, and revoke matching position assignments."""
    actor_id, target_id = current_user["user_id"], str(user_id)
    requested_roles = set(request.roles)
    db = SessionLocal()
    try:
        _lock_management(db, actor_id)
        target = db.execute(text("""
            SELECT display_name, account_status FROM app_private.user_profiles
            WHERE user_id = :id FOR UPDATE
        """), {"id": target_id}).mappings().first()
        if not target:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
        current_roles = set(db.execute(text("""
            SELECT role_code FROM app_private.user_role_assignments
            WHERE user_id = :id AND revoked_at IS NULL FOR UPDATE
        """), {"id": target_id}).scalars().all())
        if actor_id == target_id and (request.account_status != "ACTIVE" or "ADMIN" not in requested_roles):
            raise HTTPException(status_code=409, detail="Bạn không thể tự khóa tài khoản hoặc tự bỏ quyền Admin.")
        if (target["account_status"] == "ACTIVE" and "ADMIN" in current_roles
                and (request.account_status != "ACTIVE" or "ADMIN" not in requested_roles)):
            active_admins = db.execute(text("""
                SELECT COUNT(*) FROM app_private.user_profiles p
                JOIN app_private.user_role_assignments r ON r.user_id = p.user_id
                WHERE p.account_status = 'ACTIVE' AND r.role_code = 'ADMIN' AND r.revoked_at IS NULL
            """)).scalar_one()
            if active_admins <= 1:
                raise HTTPException(status_code=409, detail="Hệ thống phải còn ít nhất một Admin đang hoạt động.")
        db.execute(text("""
            UPDATE app_private.user_profiles
            SET display_name = :name,
                tokens_valid_after = CASE WHEN account_status <> :status THEN clock_timestamp() ELSE tokens_valid_after END,
                account_status = :status, updated_at = NOW()
            WHERE user_id = :id
        """), {"name": request.display_name, "status": request.account_status, "id": target_id})
        removed = sorted(current_roles - requested_roles)
        position_roles = {role for role in removed if role in ("HR_RECRUITER", "HR_LEAD", "HIRING_MANAGER")}
        hr_authorizing_roles = {"ADMIN", "HR_LEAD", "HR_RECRUITER"}
        if set(removed) & hr_authorizing_roles and not requested_roles & hr_authorizing_roles:
            # ADMIN/HR_LEAD can create positions as HR_RECRUITER even without
            # that system role. Removing their final HR-capable system role
            # must not leave those assignments granting recruiter access (or
            # the ability to create more positions).
            position_roles.update({"HR_RECRUITER", "HR_LEAD"})
        if removed:
            db.execute(text("""
                UPDATE app_private.user_role_assignments SET revoked_at = NOW()
                WHERE user_id = :id AND revoked_at IS NULL AND role_code = ANY(:roles)
            """), {"id": target_id, "roles": removed})
            if position_roles:
                db.execute(text("""
                    UPDATE app_private.position_assignments SET revoked_at = NOW()
                    WHERE user_id = :id AND revoked_at IS NULL AND position_role = ANY(:roles)
                """), {"id": target_id, "roles": sorted(position_roles)})
        for role in sorted(requested_roles - current_roles):
            db.execute(text("""
                INSERT INTO app_private.user_role_assignments (user_id, role_code, granted_by)
                VALUES (:id, :role, :actor)
                ON CONFLICT (user_id, role_code) DO UPDATE
                    SET revoked_at = NULL, granted_by = EXCLUDED.granted_by, granted_at = NOW()
            """), {"id": target_id, "role": role, "actor": actor_id})
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome, metadata)
            VALUES (:actor, 'UPDATE_USER', 'USER', :target, :outcome, CAST(:metadata AS jsonb))
        """), {"actor": actor_id, "target": target_id, "outcome": request.account_status,
                "metadata": json.dumps({"previous_status": target["account_status"],
                                        "previous_roles": sorted(current_roles), "roles": sorted(requested_roles),
                                        "removed_position_role_assignments": bool(position_roles),
                                        "revoked_position_roles": sorted(position_roles)})})
        db.commit()
        return {"user_id": target_id, "display_name": request.display_name,
                "account_status": request.account_status, "roles": sorted(requested_roles)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
