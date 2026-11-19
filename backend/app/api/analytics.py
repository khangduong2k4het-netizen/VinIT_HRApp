"""F2.03 — operational analytics API (pilot report)."""
import json
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.core.permissions import require_admin_role
from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.services.ai_quality import (MARKER_NOTE_MAX, MARKER_TITLE_MAX, QualityError, quality_breakdown,
                                     quality_trends, resolve_period, version_markers)
from app.services.analytics import AnalyticsError, has_any_hr_scope, operational_report, resolve_range

router = APIRouter()


@router.get("/operations")
async def operations_report(date_from: Optional[str] = None, date_to: Optional[str] = None,
                            position_id: Optional[UUID] = None, department_id: Optional[UUID] = None,
                            current_user: dict = Depends(get_current_user)):
    """HR Lead/Admin see every position; HR recruiters only positions they handle.
    Hiring Managers have no access. Nothing is reported per recruiter."""
    try:
        start, end = resolve_range(date_from, date_to)
    except AnalyticsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    db = SessionLocal()
    try:
        if not has_any_hr_scope(db, current_user["user_id"]):
            raise HTTPException(status_code=403, detail="Chỉ HR, HR Lead hoặc Admin được xem báo cáo vận hành")
        return operational_report(db, user_id=current_user["user_id"], start=start, end=end,
                                  position_id=str(position_id) if position_id else None,
                                  department_id=str(department_id) if department_id else None)
    finally:
        db.close()


# ----------------------------------------------------------------------------
# P3-2 — AI quality dashboard (read-only aggregates; never per recruiter)

def _quality_scope(db, user: dict) -> None:
    if not has_any_hr_scope(db, user["user_id"]):
        raise HTTPException(status_code=403, detail="Chỉ HR, HR Lead hoặc Admin được xem chất lượng AI")


def _period(date_from, date_to, grain):
    try:
        return resolve_period(date_from, date_to, grain)
    except QualityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.get("/quality/trends")
async def quality_trends_report(date_from: Optional[str] = None, date_to: Optional[str] = None, grain: str = "week",
                                position_id: Optional[UUID] = None, department_id: Optional[UUID] = None,
                                job_family_id: Optional[UUID] = None, current_user: dict = Depends(get_current_user)):
    start, end, grain = _period(date_from, date_to, grain)

    def _run():
        db = SessionLocal()
        try:
            _quality_scope(db, current_user)
            return quality_trends(db, user_id=current_user["user_id"], start=start, end=end, grain=grain,
                                  position_id=str(position_id) if position_id else None,
                                  department_id=str(department_id) if department_id else None,
                                  job_family_id=str(job_family_id) if job_family_id else None)
        finally:
            db.close()

    return await run_in_threadpool(_run)


@router.get("/quality/breakdown")
async def quality_breakdown_report(dimension: str, date_from: Optional[str] = None, date_to: Optional[str] = None,
                                   position_id: Optional[UUID] = None, department_id: Optional[UUID] = None,
                                   job_family_id: Optional[UUID] = None, current_user: dict = Depends(get_current_user)):
    start, end, _ = _period(date_from, date_to, "week")

    def _run():
        db = SessionLocal()
        try:
            _quality_scope(db, current_user)
            try:
                return quality_breakdown(db, user_id=current_user["user_id"], start=start, end=end, dimension=dimension,
                                         position_id=str(position_id) if position_id else None,
                                         department_id=str(department_id) if department_id else None,
                                         job_family_id=str(job_family_id) if job_family_id else None)
            except QualityError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from None
        finally:
            db.close()

    return await run_in_threadpool(_run)


@router.get("/quality/markers")
async def quality_markers(date_from: Optional[str] = None, date_to: Optional[str] = None,
                          current_user: dict = Depends(get_current_user)):
    start, end, _ = _period(date_from, date_to, "week")

    def _run():
        db = SessionLocal()
        try:
            _quality_scope(db, current_user)
            return {"markers": version_markers(db, user_id=current_user["user_id"], start=start, end=end)}
        finally:
            db.close()

    return await run_in_threadpool(_run)


class MarkerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    occurred_on: date
    title: str = Field(min_length=1, max_length=MARKER_TITLE_MAX)
    note: Optional[str] = Field(default=None, max_length=MARKER_NOTE_MAX)


@router.post("/quality/markers", status_code=201)
async def create_quality_marker(body: MarkerInput, current_user: dict = Depends(require_admin_role)):
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Tiêu đề không được để trống")

    def _run():
        db = SessionLocal()
        try:
            marker_id = db.execute(text("""
                INSERT INTO app_private.quality_markers(occurred_on, title, note, created_by)
                VALUES (:d, :t, :n, :u) RETURNING marker_id::text
            """), {"d": body.occurred_on, "t": title, "n": (body.note or "").strip() or None,
                   "u": current_user["user_id"]}).scalar_one()
            # The audit record keeps ids and sizes only, never the marker text.
            db.execute(text("""
                INSERT INTO app_private.audit_events(actor_user_id, action_type, object_type, object_id, outcome, metadata)
                VALUES (:u, 'CREATE_QUALITY_MARKER', 'QUALITY_MARKER', :id, 'SUCCESS', CAST(:m AS jsonb))
            """), {"u": current_user["user_id"], "id": marker_id,
                   "m": json.dumps({"occurred_on": body.occurred_on.isoformat(), "title_length": len(title)})})
            db.commit()
            return {"marker_id": marker_id, "occurred_on": body.occurred_on.isoformat(), "title": title,
                    "note": (body.note or "").strip() or None}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    return await run_in_threadpool(_run)
