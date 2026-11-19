from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.schemas.departments import Department, DepartmentCreate, DepartmentUpdate
from app.services.departments import (
    DepartmentError,
    normalize_code_format,
    normalize_department_name,
)

router = APIRouter()


def _require_admin_write(db, user_id: str) -> None:
    """Recheck an active ADMIN account/role inside the write transaction."""
    account = db.execute(text("""
        SELECT account_status FROM app_private.user_profiles
        WHERE user_id = :user_id FOR SHARE
    """), {"user_id": user_id}).scalar_one_or_none()
    roles = db.execute(text("""
        SELECT role_code FROM app_private.user_role_assignments
        WHERE user_id = :user_id AND role_code = 'ADMIN' AND revoked_at IS NULL FOR SHARE
    """), {"user_id": user_id}).scalars().all()
    if account != "ACTIVE" or not roles:
        raise HTTPException(status_code=403, detail="Admin role required for this endpoint")


def _normalize_payload(values: dict) -> dict:
    normalized = dict(values)
    try:
        if "name" in normalized and normalized["name"] is not None:
            normalized["name"] = normalize_department_name(normalized["name"])
        if "code_format" in normalized and normalized["code_format"] is not None:
            normalized["code_format"] = normalize_code_format(normalized["code_format"])
    except DepartmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return normalized


@router.get("", response_model=list[Department])
async def list_departments(
    include_inactive: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    """List departments for dropdowns; inactive rows are Admin-only."""
    db = SessionLocal()
    try:
        if include_inactive:
            _require_admin_write(db, current_user["user_id"])
        rows = db.execute(text("""
            SELECT d.*, COUNT(p.position_id)::int AS position_count
            FROM app_private.departments d
            LEFT JOIN app_private.positions p ON p.department_id = d.department_id
            WHERE (:include_inactive OR d.is_active)
            GROUP BY d.department_id
            ORDER BY d.name, d.department_id
        """), {"include_inactive": include_inactive}).mappings().all()
        return [dict(row) for row in rows]
    finally:
        db.close()


@router.post("", response_model=Department, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate,
    current_user: dict = Depends(get_current_user),
):
    values = _normalize_payload(payload.model_dump())
    db = SessionLocal()
    try:
        _require_admin_write(db, current_user["user_id"])
        row = db.execute(text("""
            INSERT INTO app_private.departments (name, code_format, is_active, created_by)
            VALUES (:name, :code_format, :is_active, :created_by)
            RETURNING *
        """), {**values, "created_by": current_user["user_id"]}).mappings().one()
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome)
            VALUES (:user_id, 'CREATE_DEPARTMENT', 'DEPARTMENT', :id, 'SUCCESS')
        """), {"user_id": current_user["user_id"], "id": row["department_id"]})
        db.commit()
        return dict(row)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tên phòng ban hoặc mã định dạng đã tồn tại") from None
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.patch("/{department_id}", response_model=Department)
async def update_department(
    department_id: UUID,
    payload: DepartmentUpdate,
    current_user: dict = Depends(get_current_user),
):
    values = _normalize_payload(payload.model_dump(exclude_unset=True))
    values = {key: value for key, value in values.items() if value is not None or key == "is_active"}
    if not values:
        raise HTTPException(status_code=400, detail="Không có nội dung cần cập nhật")
    db = SessionLocal()
    try:
        _require_admin_write(db, current_user["user_id"])
        existing = db.execute(text("""
            SELECT department_id FROM app_private.departments
            WHERE department_id = :id FOR UPDATE
        """), {"id": str(department_id)}).first()
        if not existing:
            raise HTTPException(status_code=404, detail="Không tìm thấy phòng ban")
        sets = ", ".join(f"{key} = :{key}" for key in values)
        row = db.execute(text(f"""
            UPDATE app_private.departments
            SET {sets}, updated_at = NOW()
            WHERE department_id = :id
            RETURNING *
        """), {**values, "id": str(department_id)}).mappings().one()
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome)
            VALUES (:user_id, 'UPDATE_DEPARTMENT', 'DEPARTMENT', :id, 'SUCCESS')
        """), {"user_id": current_user["user_id"], "id": str(department_id)})
        db.commit()
        return dict(row)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tên phòng ban hoặc mã định dạng đã tồn tại") from None
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.delete("/{department_id}")
async def delete_department(
    department_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    db = SessionLocal()
    try:
        _require_admin_write(db, current_user["user_id"])
        existing = db.execute(text("""
            SELECT department_id FROM app_private.departments
            WHERE department_id = :id FOR UPDATE
        """), {"id": str(department_id)}).first()
        if not existing:
            raise HTTPException(status_code=404, detail="Không tìm thấy phòng ban")
        position_count = db.execute(text("""
            SELECT COUNT(*) FROM app_private.positions WHERE department_id = :id
        """), {"id": str(department_id)}).scalar_one()
        if position_count:
            raise HTTPException(
                status_code=409,
                detail="Không thể xóa phòng ban đã có vị trí tuyển dụng; hãy tắt trạng thái hoạt động thay vì xóa.",
            )
        db.execute(text("DELETE FROM app_private.departments WHERE department_id = :id"),
                   {"id": str(department_id)})
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome)
            VALUES (:user_id, 'DELETE_DEPARTMENT', 'DEPARTMENT', :id, 'SUCCESS')
        """), {"user_id": current_user["user_id"], "id": str(department_id)})
        db.commit()
        return {"department_id": str(department_id), "deleted": True}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
