"""Retention/deletion workflow API.

These endpoints expose the per-application retention queue.  They do not
implement bulk auto-deletion: a case must be confirmed after its due date by
an authorised user and then executed explicitly with a one-time code.

F2.07 adds the exception hold, reminders, the purge one-time code and a
manual trigger of the scheduled cycle (which never deletes data).
"""
from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.core.config import settings
from app.services.retention import (
    CASE_COLUMNS,
    CASE_JOINS,
    RetentionError,
    _has_global_role,
    can_confirm_retention,
    can_view_retention,
    cancel_retention_case,
    confirm_retention_case,
    execute_retention_case,
    generate_retention_cases,
    get_case,
    notice_window_days,
    place_hold,
    public_case,
    release_hold,
)
from app.services.retention_automation import (
    create_purge_challenge,
    notification_rows,
    run_retention_cycle,
    verify_purge_challenge,
)

router = APIRouter()


class RetentionActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Deprecated compatibility field. It is accepted so older clients do not
    # break, but it is intentionally ignored and never stored: free-text
    # reasons can accidentally contain candidate identifiers.
    reason: str | None = Field(
        default=None,
        max_length=500,
        deprecated=True,
        description=(
            "Deprecated compatibility field; accepted but intentionally "
            "ignored and never stored. Do not include candidate identifiers."
        ),
    )


class HoldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason_code: Literal["COMPLAINT", "INSPECTION", "LEGAL_REQUEST", "OTHER_LEGAL_BASIS"]
    # Number/code of the Legal & Privacy approval document. A strict pattern
    # keeps free text (and candidate identifiers) out of this field.
    legal_approval_reference: str = Field(min_length=2, max_length=80,
                                          pattern=r"^[A-Za-z0-9][A-Za-z0-9 ./_:-]{1,79}$")
    hold_until: date | None = None


class ExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge_id: UUID | None = None
    otp: str | None = Field(default=None, min_length=6, max_length=6, pattern=r"^[0-9]{6}$")


def _raise(error: RetentionError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from None


def _get_case_or_404(db, case_id: UUID) -> dict:
    try:
        return get_case(db, str(case_id))
    except RetentionError as exc:
        _raise(exc)


def _require_view(db, current_user: dict, position_id: str | None) -> None:
    if not position_id or not can_view_retention(db, current_user["user_id"], position_id):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem retention của vị trí này")


def _require_confirm(db, current_user: dict, position_id: str | None) -> None:
    if not position_id or not can_confirm_retention(db, current_user["user_id"], position_id):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xác nhận xóa dữ liệu của vị trí này")


@router.get("/queue")
async def retention_queue(status: str | None = None, current_user: dict = Depends(get_current_user)):
    """S-19: retention cases across every position the caller may view.

    Global ADMIN/HR_LEAD see all positions; HR assigned to a position sees
    that position. Each row says whether the caller may confirm/execute it.
    Closed positions are listed so HR can scan them for newly due cases.
    """
    if status is not None and status not in ("PENDING", "SCHEDULED_FOR_DELETION", "ON_HOLD", "DELETED", "CANCELLED"):
        raise HTTPException(status_code=400, detail="Trạng thái retention không hợp lệ")
    user_id = current_user["user_id"]
    db = SessionLocal()
    try:
        visible = """
            (EXISTS (SELECT 1 FROM app_private.user_role_assignments ur WHERE ur.user_id = :user_id
                     AND ur.revoked_at IS NULL AND ur.role_code IN ('ADMIN', 'HR_LEAD'))
             OR EXISTS (SELECT 1 FROM app_private.position_assignments pa WHERE pa.position_id = p.position_id
                        AND pa.user_id = :user_id AND pa.revoked_at IS NULL AND pa.position_role IN ('HR_RECRUITER', 'HR_LEAD')))
        """
        rows = db.execute(text(f"""
            SELECT {CASE_COLUMNS},
                   p.title AS position_title, p.position_code
            FROM app_private.application_retention_cases c
            JOIN app_private.positions p ON p.position_id = c.position_id
            {CASE_JOINS}
            WHERE {visible} AND (CAST(:status AS text) IS NULL OR c.status = :status)
            ORDER BY c.due_date, c.created_at, c.retention_case_id
            LIMIT 500
        """), {"user_id": user_id, "status": status}).mappings().all()
        confirm_cache: dict[str, bool] = {}
        cases = []
        for row in rows:
            position_id = str(row["position_id"])
            if position_id not in confirm_cache:
                confirm_cache[position_id] = can_confirm_retention(db, user_id, position_id)
            cases.append({**public_case(dict(row)), "position_title": row["position_title"],
                          "position_code": row["position_code"], "can_confirm": confirm_cache[position_id]})
        positions = db.execute(text(f"""
            SELECT p.position_id, p.title, p.position_code, p.closed_at
            FROM app_private.positions p
            WHERE p.status = 'CLOSED' AND {visible}
            ORDER BY p.closed_at NULLS LAST, p.title
        """), {"user_id": user_id}).mappings().all()
        return {"cases": cases, "closed_positions": [dict(row) for row in positions],
                "settings": {"notice_days": sorted(settings.RETENTION_NOTICE_DAYS, reverse=True),
                             "notice_window_days": notice_window_days(),
                             "purge_requires_otp": settings.RETENTION_PURGE_REQUIRE_OTP,
                             "scheduler_enabled": settings.RETENTION_SCHEDULER_ENABLED}}
    finally:
        db.close()


@router.get("/positions/{position_id}/cases")
async def list_retention_cases(position_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        _require_view(db, current_user, str(position_id))
        rows = db.execute(text(f"""
            SELECT {CASE_COLUMNS}
            FROM app_private.application_retention_cases c
            {CASE_JOINS}
            WHERE c.position_id = :position_id
            ORDER BY c.due_date, c.created_at, c.retention_case_id
        """), {"position_id": str(position_id)}).mappings().all()
        return [public_case(dict(row)) for row in rows]
    finally:
        db.close()


@router.post("/positions/{position_id}/cases/generate")
async def generate_cases(position_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        _require_view(db, current_user, str(position_id))
        result = generate_retention_cases(
            db, position_id=str(position_id), actor_user_id=current_user["user_id"]
        )
        db.commit()
        return result
    except RetentionError as exc:
        db.rollback()
        _raise(exc)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/cases/{case_id}/confirm")
async def confirm_case(
    case_id: UUID,
    request: RetentionActionRequest | None = None,
    current_user: dict = Depends(get_current_user),
):
    db = SessionLocal()
    try:
        case = _get_case_or_404(db, case_id)
        _require_confirm(db, current_user, case.get("position_id"))
        result = confirm_retention_case(db, case_id=str(case_id), actor_user_id=current_user["user_id"])
        db.commit()
        return result
    except RetentionError as exc:
        db.rollback()
        _raise(exc)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/cases/{case_id}/cancel")
async def cancel_case(
    case_id: UUID,
    request: RetentionActionRequest | None = None,
    current_user: dict = Depends(get_current_user),
):
    db = SessionLocal()
    try:
        case = _get_case_or_404(db, case_id)
        _require_confirm(db, current_user, case.get("position_id"))
        result = cancel_retention_case(db, case_id=str(case_id), actor_user_id=current_user["user_id"])
        db.commit()
        return result
    except RetentionError as exc:
        db.rollback()
        _raise(exc)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/cases/{case_id}/purge-otp")
async def request_purge_otp(case_id: UUID, current_user: dict = Depends(get_current_user)):
    """F2.07: send a one-time code before the physical purge of one case."""
    db = SessionLocal()
    try:
        case = _get_case_or_404(db, case_id)
        _require_confirm(db, current_user, case.get("position_id"))
        result = create_purge_challenge(db, case_id=str(case_id), user_id=current_user["user_id"])
        db.commit()
        return result
    except RetentionError as exc:
        db.rollback()
        _raise(exc)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/cases/{case_id}/execute")
async def execute_case(case_id: UUID, request: ExecuteRequest | None = None,
                       current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        case = _get_case_or_404(db, case_id)
        _require_confirm(db, current_user, case.get("position_id"))
        if settings.RETENTION_PURGE_REQUIRE_OTP:
            if not request or not request.challenge_id or not request.otp:
                raise HTTPException(status_code=428, detail="Cần nhập mã OTP để thực hiện xóa vật lý")
            try:
                verify_purge_challenge(db, case_id=str(case_id), user_id=current_user["user_id"],
                                       challenge_id=str(request.challenge_id), code=request.otp)
            except RetentionError as exc:
                db.commit()  # persist the failed-attempt counter
                _raise(exc)
            db.commit()
    finally:
        db.close()
    try:
        return execute_retention_case(case_id=str(case_id), actor_user_id=current_user["user_id"])
    except RetentionError as exc:
        _raise(exc)


@router.post("/cases/{case_id}/hold")
async def hold_case(case_id: UUID, request: HoldRequest, current_user: dict = Depends(get_current_user)):
    """Retention Exception Hold with a Legal & Privacy approval reference."""
    db = SessionLocal()
    try:
        case = _get_case_or_404(db, case_id)
        _require_confirm(db, current_user, case.get("position_id"))
        result = place_hold(db, case_id=str(case_id), actor_user_id=current_user["user_id"],
                            reason_code=request.reason_code,
                            legal_approval_reference=request.legal_approval_reference.strip(),
                            hold_until=request.hold_until)
        db.commit()
        return result
    except RetentionError as exc:
        db.rollback()
        _raise(exc)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/cases/{case_id}/release-hold")
async def release_case_hold(case_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        case = _get_case_or_404(db, case_id)
        _require_confirm(db, current_user, case.get("position_id"))
        result = release_hold(db, case_id=str(case_id), actor_user_id=current_user["user_id"])
        db.commit()
        return result
    except RetentionError as exc:
        db.rollback()
        _raise(exc)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/notifications")
async def list_notifications(unread_only: bool = False, current_user: dict = Depends(get_current_user)):
    """In-app reminders (30/15/7 days before due) addressed to the caller."""
    db = SessionLocal()
    try:
        return notification_rows(db, user_id=current_user["user_id"], unread_only=unread_only)
    finally:
        db.close()


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        updated = db.execute(text("""
            UPDATE app_private.retention_notifications SET read_at = COALESCE(read_at, NOW())
            WHERE notification_id = :id AND recipient_user_id = :user_id AND channel = 'IN_APP'
            RETURNING notification_id
        """), {"id": str(notification_id), "user_id": current_user["user_id"]}).scalar_one_or_none()
        if not updated:
            raise HTTPException(status_code=404, detail="Không tìm thấy thông báo")
        db.commit()
        return {"notification_id": str(updated), "read": True}
    finally:
        db.close()


@router.post("/cycle/run")
async def run_cycle(current_user: dict = Depends(get_current_user)):
    """Run the retention cycle now (Admin/HR Lead). It never deletes data."""
    db = SessionLocal()
    try:
        if not _has_global_role(db, current_user["user_id"], ("ADMIN", "HR_LEAD")):
            raise HTTPException(status_code=403, detail="Chỉ Admin hoặc HR Lead được chạy chu kỳ retention")
    finally:
        db.close()
    return run_retention_cycle()
