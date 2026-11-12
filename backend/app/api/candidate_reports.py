"""F2.09 API: side-by-side comparison and custom Excel/PDF export.

Access: HR recruiters/leads assigned to the position, and global HR Lead or
Admin (same rule as the ranking list). Hiring managers are not included.
Every export is written to the audit log with format, columns and row count
(never candidate data). Exports never contain email or phone numbers.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text

from app.core.permissions import check_position_access
from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.services.candidate_report import (COLUMNS, DEFAULT_COLUMNS, MAX_COMPARE, ReportError,
                                           build_comparison, build_export, to_pdf, to_xlsx)

router = APIRouter()

_MEDIA = {"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "pdf": "application/pdf"}


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["xlsx", "pdf"]
    columns: list[Literal[COLUMNS]] = Field(default_factory=lambda: list(DEFAULT_COLUMNS), min_length=1)  # type: ignore[valid-type]
    # None = every application assessed with the current criteria version.
    application_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=1000)
    language: Literal["vi", "en"] = "vi"

    @field_validator("columns")
    @classmethod
    def _dedupe(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


def _raise(error: ReportError):
    raise HTTPException(status_code=error.status_code, detail=error.message)


@router.get("/positions/{position_id}/comparison")
async def compare_candidates(position_id: UUID,
                             application_ids: list[UUID] = Query(..., min_length=2, max_length=MAX_COMPARE),
                             current_user: dict = Depends(get_current_user)):
    await check_position_access(position_id, current_user, required_roles=["HR_RECRUITER"])
    with SessionLocal() as db:
        try:
            return build_comparison(db, str(position_id), [str(i) for i in application_ids])
        except ReportError as error:
            _raise(error)


@router.post("/positions/{position_id}/export")
async def export_candidates(position_id: UUID, request: ExportRequest,
                            current_user: dict = Depends(get_current_user)):
    await check_position_access(position_id, current_user, required_roles=["HR_RECRUITER"])
    with SessionLocal() as db:
        try:
            report = build_export(db, str(position_id),
                                  [str(i) for i in request.application_ids] if request.application_ids else None,
                                  request.columns)
            content = to_xlsx(report, request.language) if request.format == "xlsx" else to_pdf(report, request.language)
        except ReportError as error:
            _raise(error)
        # Audit metadata names the shape of the export, never its content.
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, position_id,
                                                  outcome, metadata)
            VALUES (:user, 'EXPORT_CANDIDATE_REPORT', 'POSITION', :position, :position, 'SUCCESS', CAST(:meta AS jsonb))
        """), {"user": current_user["user_id"], "position": str(position_id), "meta": json.dumps({
            "format": request.format, "columns": report["columns"], "row_count": len(report["rows"]),
            "selected": request.application_ids is not None, "language": request.language,
            "criteria_version_id": report["criteria_version_id"]})})
        db.commit()
    code = re.sub(r"[^A-Za-z0-9_-]+", "-", report["position"]["position_code"] or "position").strip("-")
    filename = f"HRA_{code}_{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}.{request.format}"
    return Response(content, media_type=_MEDIA[request.format], headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
