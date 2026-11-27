"""Closed-loop HR Evidence Sign-Off API.

Lets HR confirm or dispute individual AI criterion assessment results in 1 click.
Every sign-off is append-only; the latest verdict per criterion result feeds
directly into P3-2 AI Quality calibration metrics (aggregates only).
"""
from __future__ import annotations

import json
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text

from app.core.exceptions import NotFoundError
from app.core.permissions import application_access, can_update_application_status
from app.core.security import get_current_user
from app.db.database import SessionLocal

router = APIRouter()

SIGN_OFF_REASON_CODES = (
    "WRONG_QUOTE",
    "WRONG_LEVEL",
    "MISSING_CONTEXT",
    "OCR_NOISE",
    "RUBRIC_AMBIGUOUS",
    "OTHER",
)


class EvidenceSignoffInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal["CONFIRMED", "DISPUTED"]
    reason_code: Optional[Literal[
        "WRONG_QUOTE",
        "WRONG_LEVEL",
        "MISSING_CONTEXT",
        "OCR_NOISE",
        "RUBRIC_AMBIGUOUS",
        "OTHER",
    ]] = None
    note: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _validate_dispute_reason(self):
        if self.verdict == "DISPUTED" and not self.reason_code:
            raise ValueError("Vui lòng chọn lý do khi báo bằng chứng sai.")
        if self.verdict == "CONFIRMED":
            self.reason_code = None
        if self.note is not None:
            self.note = self.note.strip() or None
        return self


@router.get("/applications/{application_id}/signoffs")
async def list_application_evidence_signoffs(
    application_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    """Return latest HR evidence sign-off per criterion result_id for an application."""
    app_id = str(application_id)

    def _run():
        db = SessionLocal()
        try:
            pos_id = db.execute(
                text("SELECT position_id FROM app_private.applications WHERE application_id = :id"),
                {"id": app_id},
            ).scalar_one_or_none()
            if not pos_id:
                raise NotFoundError("Application")
            access = application_access(current_user["user_id"], str(pos_id), app_id)
            if not access["can_view_cv"] and not access["can_update_status"]:
                raise HTTPException(status_code=403, detail="Bạn không có quyền xem xác nhận bằng chứng của hồ sơ này")

            rows = db.execute(
                text("""
                    SELECT DISTINCT ON (es.result_id)
                           es.signoff_id::text AS signoff_id,
                           es.result_id::text AS result_id,
                           es.criterion_id::text AS criterion_id,
                           es.verdict,
                           es.reason_code,
                           es.note,
                           es.created_at,
                           COALESCE(up.display_name, 'HR') AS reviewed_by_name
                    FROM app_private.evidence_signoffs es
                    LEFT JOIN app_private.user_profiles up ON up.user_id = es.reviewed_by
                    WHERE es.application_id = :app_id
                    ORDER BY es.result_id, es.created_at DESC, es.signoff_id DESC
                """),
                {"app_id": app_id},
            ).mappings().all()

            signoffs = {}
            for row in rows:
                item = dict(row)
                item["created_at"] = item["created_at"].isoformat() if item["created_at"] else None
                # Summary-only viewers never see free-text notes (could reference CV details).
                if not access["can_update_status"]:
                    item["note"] = None
                signoffs[item["result_id"]] = item
            return {"application_id": app_id, "signoffs": signoffs}
        finally:
            db.close()

    return await run_in_threadpool(_run)


@router.post("/results/{result_id}/signoff", status_code=status.HTTP_201_CREATED)
async def create_evidence_signoff(
    result_id: UUID,
    body: EvidenceSignoffInput,
    current_user: dict = Depends(get_current_user),
):
    """Record an append-only HR verdict (CONFIRMED / DISPUTED) on one criterion result."""
    res_id = str(result_id)
    user_id = current_user["user_id"]

    def _run():
        db = SessionLocal()
        try:
            target = db.execute(
                text("""
                    SELECT car.result_id::text AS result_id,
                           car.criterion_id::text AS criterion_id,
                           ar.application_id::text AS application_id,
                           ar.position_id::text AS position_id
                    FROM app_private.criterion_assessment_results car
                    JOIN app_private.assessment_runs ar ON ar.assessment_id = car.assessment_id
                    WHERE car.result_id = :result_id
                """),
                {"result_id": res_id},
            ).mappings().first()
            if not target:
                raise NotFoundError("Criterion result")

            if not can_update_application_status(user_id, target["position_id"]):
                raise HTTPException(
                    status_code=403,
                    detail="Chỉ HR phụ trách vị trí mới được xác nhận hoặc báo sai bằng chứng AI",
                )

            row = db.execute(
                text("""
                    INSERT INTO app_private.evidence_signoffs (
                        result_id, application_id, position_id, criterion_id,
                        verdict, reason_code, note, reviewed_by
                    )
                    VALUES (
                        :result_id, :application_id, :position_id, :criterion_id,
                        :verdict, :reason_code, :note, :reviewed_by
                    )
                    RETURNING signoff_id::text AS signoff_id, result_id::text AS result_id,
                              criterion_id::text AS criterion_id, verdict, reason_code, note, created_at
                """),
                {
                    "result_id": target["result_id"],
                    "application_id": target["application_id"],
                    "position_id": target["position_id"],
                    "criterion_id": target["criterion_id"],
                    "verdict": body.verdict,
                    "reason_code": body.reason_code,
                    "note": body.note,
                    "reviewed_by": user_id,
                },
            ).mappings().first()

            # PII-free audit trail: never store candidate info or free-text note in audit metadata.
            db.execute(
                text("""
                    INSERT INTO app_private.audit_events (
                        actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata
                    )
                    VALUES (
                        :actor, 'REVIEW_CRITERION_EVIDENCE', 'CRITERION_RESULT', :result_id, :position_id,
                        'SUCCESS', CAST(:metadata AS jsonb)
                    )
                """),
                {
                    "actor": user_id,
                    "result_id": target["result_id"],
                    "position_id": target["position_id"],
                    "metadata": json.dumps({
                        "verdict": body.verdict,
                        "reason_code": body.reason_code,
                        "has_note": bool(body.note),
                    }),
                },
            )
            reviewer_name = db.execute(
                text("SELECT COALESCE(display_name, 'HR') FROM app_private.user_profiles WHERE user_id = :u"),
                {"u": user_id},
            ).scalar_one_or_none() or "HR"
            db.commit()

            item = dict(row)
            item["created_at"] = item["created_at"].isoformat() if item["created_at"] else None
            item["reviewed_by_name"] = reviewer_name
            return item
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    return await run_in_threadpool(_run)
