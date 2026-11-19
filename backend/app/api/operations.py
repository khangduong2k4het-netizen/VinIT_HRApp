from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.core.exceptions import NotFoundError
from app.core.permissions import can_update_application_status, check_position_access
from app.core.security import get_current_user
from app.db.database import SessionLocal

router = APIRouter()


@router.get("/{operation_id}")
async def get_operation_status(operation_id: UUID, current_user: dict = Depends(get_current_user)):
    """Return progress only while the caller retains HR access to the position."""
    db = SessionLocal()
    try:
        row = db.execute(text("""
            SELECT operation_id, capability, status, requested_by, position_id, error_code, error_message,
                   created_at, started_at, completed_at
            FROM app_private.operations WHERE operation_id = :operation_id
        """), {"operation_id": str(operation_id)}).mappings().first()
        if not row:
            raise NotFoundError("Operation")
        # A former requester must not retain access to filenames after their
        # assignment is revoked. Legacy unscoped operations fail closed.
        if not row["position_id"] or not can_update_application_status(current_user["user_id"], str(row["position_id"])):
            raise HTTPException(status_code=403, detail="Bạn không có quyền xem tiến trình này")
        op = dict(row)
        op.pop("requested_by", None)
        op["stage"] = op["capability"]
        if op["capability"] == "CV_PROCESSING":
            batch = db.execute(text("""
                SELECT total_files, processed_files, failed_files, status
                FROM app_private.cv_batches WHERE operation_id = :operation_id
            """), {"operation_id": str(operation_id)}).mappings().first()
            if batch:
                total = batch["total_files"] or 0
                processed = batch["processed_files"] or 0
                failed = batch["failed_files"] or 0
                # application_id is the point of this list: a rejected file with a
                # row behind it can be opened directly. Without it HR sees only a
                # filename and has to go hunting in the ranking page.
                invalid = db.execute(text("""
                    SELECT original_filename, error_code, application_id FROM app_private.cv_batch_items
                    WHERE batch_id = (SELECT batch_id FROM app_private.cv_batches WHERE operation_id = :operation_id LIMIT 1)
                      AND validation_result = 'ERROR' ORDER BY created_at
                """), {"operation_id": str(operation_id)}).mappings().all()
                op["progress"] = {"total": total, "processed": processed, "failed": failed,
                                  "percent_complete": min(100, round((processed + failed) / total * 100)) if total else 0,
                                  "invalid_files": [dict(item) for item in invalid]}
                if processed and batch["status"] in ("COMPLETED", "PARTIALLY_COMPLETED") and op["status"] == "PROCESSING":
                    op["stage"] = "ASSESSMENT"
        return op
    finally:
        db.close()


@router.get("/position/{position_id}/active")
async def get_active_position_operation(position_id: UUID, current_user: dict = Depends(get_current_user)):
    """Resume polling an operation after navigation or a page refresh."""
    await check_position_access(position_id, current_user, required_roles=["HR_RECRUITER"])
    db = SessionLocal()
    try:
        row = db.execute(text("""
            SELECT operation_id FROM app_private.operations
            WHERE position_id = :position_id AND capability IN ('CV_PROCESSING', 'ASSESSMENT', 'RANKING')
              AND status IN ('PENDING', 'PROCESSING')
            ORDER BY created_at ASC LIMIT 1
        """), {"position_id": str(position_id)}).mappings().first()
    finally:
        db.close()
    if not row:
        return None
    return await get_operation_status(row["operation_id"], current_user)
