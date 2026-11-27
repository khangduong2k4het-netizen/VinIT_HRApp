"""Interview Coordination, Conflict Detection, RFC 5545 .ics Export & AI Prep Brief.

Key design guarantees:
- Strict SQL-level access control: callers only ever see interviews on positions they
  handle (HR/HR_LEAD/ADMIN) or sessions they are explicitly assigned to as panelists.
- Panelist overlap check before scheduling/rescheduling, with structured conflict info
  (never leaking another candidate's personal data).
- Evidence-grounded AI Interview Prep Brief synthesized from the latest assessment.
- One-click bridge to F3.05 Candidate Emails (formatted GMT+7 slot & location).
- Audit records store IDs and session metadata only (no candidate PII).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.services.interview_calendar import (
    build_ics,
    build_prep_brief,
    format_vn_slot,
    safe_ics_filename,
)

router = APIRouter()

InterviewFormat = Literal["ONLINE", "ONSITE", "PHONE"]
SessionStatus = Literal["SCHEDULED", "COMPLETED", "CANCELLED", "NO_SHOW"]
PanelRole = Literal["LEAD_INTERVIEWER", "INTERVIEWER", "OBSERVER"]


class PanelistInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    panel_role: PanelRole = "INTERVIEWER"


class InterviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    round_no: int = Field(default=1, ge=1, le=10)
    title: str = Field(default="Phỏng vấn chuyên môn", min_length=1, max_length=160)
    starts_at: datetime
    ends_at: datetime
    format: InterviewFormat = "ONLINE"
    location_or_link: Optional[str] = Field(default=None, max_length=500)
    prep_notes: Optional[str] = Field(default=None, max_length=2000)
    panelists: list[PanelistInput] = Field(default_factory=list, max_length=15)
    allow_conflict: bool = False

    @field_validator("starts_at", "ends_at")
    @classmethod
    def _require_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Thời gian phải có múi giờ (ISO 8601)")
        return v

    @field_validator("title", "location_or_link")
    @classmethod
    def _no_newlines(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and ("\r" in v or "\n" in v):
            raise ValueError("Không được chứa ký tự xuống dòng")
        return v.strip() if isinstance(v, str) else v


class InterviewUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Optional[str] = Field(default=None, min_length=1, max_length=160)
    session_status: Optional[SessionStatus] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    format: Optional[InterviewFormat] = None
    location_or_link: Optional[str] = Field(default=None, max_length=500)
    prep_notes: Optional[str] = Field(default=None, max_length=2000)
    panelists: Optional[list[PanelistInput]] = Field(default=None, max_length=15)
    allow_conflict: bool = False

    @field_validator("starts_at", "ends_at")
    @classmethod
    def _require_tz(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None and v.tzinfo is None:
            raise ValueError("Thời gian phải có múi giờ (ISO 8601)")
        return v

    @field_validator("title", "location_or_link")
    @classmethod
    def _no_newlines(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and ("\r" in v or "\n" in v):
            raise ValueError("Không được chứa ký tự xuống dòng")
        return v.strip() if isinstance(v, str) else v


# ---- access & helpers ---------------------------------------------------------------

def _active_user(db, user_id: str) -> dict:
    row = db.execute(text("""
        SELECT p.user_id, p.display_name, p.account_status,
               EXISTS (SELECT 1 FROM app_private.user_role_assignments r
                       WHERE r.user_id = :u AND r.revoked_at IS NULL
                         AND r.role_code IN ('ADMIN', 'HR_LEAD')) AS is_lead_or_admin
        FROM app_private.user_profiles p
        WHERE p.user_id = :u
    """), {"u": user_id}).mappings().first()
    if not row or row["account_status"] != "ACTIVE":
        raise HTTPException(status_code=403, detail="Tài khoản chưa được kích hoạt hoặc đã bị khóa")
    return dict(row)


def _can_manage_position(db, user_id: str, position_id: str) -> bool:
    return bool(db.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM app_private.user_role_assignments r
            WHERE r.user_id = :u AND r.revoked_at IS NULL AND r.role_code IN ('ADMIN', 'HR_LEAD')
        ) OR EXISTS (
            SELECT 1 FROM app_private.position_assignments pa
            WHERE pa.user_id = :u AND pa.position_id = :p AND pa.revoked_at IS NULL
              AND pa.position_role IN ('HR_RECRUITER', 'HR_LEAD')
        )
    """), {"u": user_id, "p": position_id}).scalar())


def _can_view_application(db, user_id: str, application_id: str, position_id: str) -> bool:
    if _can_manage_position(db, user_id, position_id):
        return True
    return bool(db.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM app_private.position_assignments pa
            WHERE pa.user_id = :u AND pa.position_id = :p AND pa.revoked_at IS NULL
        ) OR EXISTS (
            SELECT 1 FROM app_private.interview_panelists ip
            JOIN app_private.interview_sessions s ON s.session_id = ip.session_id
            WHERE ip.user_id = :u AND s.application_id = :a
        )
    """), {"u": user_id, "p": position_id, "a": application_id}).scalar())


def _find_panelist_conflicts(
    db,
    panelist_ids: list[str],
    starts_at: datetime,
    ends_at: datetime,
    *,
    exclude_session_id: Optional[str] = None,
) -> list[dict]:
    if not panelist_ids:
        return []
    rows = db.execute(text("""
        SELECT ip.user_id, up.display_name, s.session_id, s.starts_at, s.ends_at,
               s.round_no, p.position_code
        FROM app_private.interview_panelists ip
        JOIN app_private.interview_sessions s ON s.session_id = ip.session_id
        JOIN app_private.positions p ON p.position_id = s.position_id
        LEFT JOIN app_private.user_profiles up ON up.user_id = ip.user_id
        WHERE ip.user_id = ANY(CAST(:uids AS uuid[]))
          AND s.session_status = 'SCHEDULED'
          AND s.starts_at < :ends_at
          AND s.ends_at > :starts_at
          AND (:excl IS NULL OR s.session_id <> CAST(:excl AS uuid))
        ORDER BY s.starts_at
    """), {
        "uids": panelist_ids,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "excl": exclude_session_id,
    }).mappings().all()
    return [
        {
            "user_id": str(r["user_id"]),
            "display_name": r["display_name"] or "",
            "session_id": str(r["session_id"]),
            "position_code": r["position_code"],
            "round_no": r["round_no"],
            "starts_at": r["starts_at"].isoformat(),
            "ends_at": r["ends_at"].isoformat(),
            "slot_vn": format_vn_slot(r["starts_at"], r["ends_at"]),
        }
        for r in rows
    ]


def _load_panelists_map(db, session_ids: list[str]) -> dict[str, list[dict]]:
    if not session_ids:
        return {}
    rows = db.execute(text("""
        SELECT ip.session_id, ip.user_id, ip.panel_role, up.display_name, u.email
        FROM app_private.interview_panelists ip
        LEFT JOIN app_private.user_profiles up ON up.user_id = ip.user_id
        LEFT JOIN auth.users u ON u.id = ip.user_id
        WHERE ip.session_id = ANY(CAST(:ids AS uuid[]))
        ORDER BY CASE ip.panel_role WHEN 'LEAD_INTERVIEWER' THEN 1 WHEN 'INTERVIEWER' THEN 2 ELSE 3 END,
                 up.display_name
    """), {"ids": session_ids}).mappings().all()
    out: dict[str, list[dict]] = {}
    for r in rows:
        sid = str(r["session_id"])
        out.setdefault(sid, []).append({
            "user_id": str(r["user_id"]),
            "display_name": r["display_name"] or r["email"] or "",
            "email": r["email"],
            "panel_role": r["panel_role"],
        })
    return out


def _serialize_session(row: dict, panelists: list[dict], *, can_manage: bool) -> dict:
    return {
        "session_id": str(row["session_id"]),
        "application_id": str(row["application_id"]),
        "position_id": str(row["position_id"]),
        "position_code": row.get("position_code"),
        "position_title": row.get("position_title"),
        "candidate_name": row.get("candidate_name"),
        "round_no": row["round_no"],
        "title": row["title"],
        "session_status": row["session_status"],
        "starts_at": row["starts_at"].isoformat(),
        "ends_at": row["ends_at"].isoformat(),
        "slot_vn": format_vn_slot(row["starts_at"], row["ends_at"]),
        "format": row["format"],
        "location_or_link": row["location_or_link"],
        "prep_notes": row["prep_notes"],
        "panelists": panelists,
        "can_manage": can_manage,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def _load_prep_brief(db, application_id: str) -> dict:
    run_row = db.execute(text("""
        SELECT assessment_id FROM app_private.assessment_runs
        WHERE application_id = :a
        ORDER BY created_at DESC LIMIT 1
    """), {"a": application_id}).first()
    if not run_row:
        return {"probe_points": [], "strengths": [], "probe_count": 0, "strength_count": 0}
    rows = db.execute(text("""
        SELECT car.criterion_id, ci.name AS criterion_name, ci.category,
               car.outcome, car.requires_hr_verification AS requires_verification,
               (SELECT ei.verbatim_quote FROM app_private.evidence_items ei
                WHERE ei.criterion_result_id = car.result_id
                ORDER BY (ei.verification_status = 'VERIFIED') DESC, ei.evidence_id LIMIT 1) AS quote,
               (SELECT ei.page_number FROM app_private.evidence_items ei
                WHERE ei.criterion_result_id = car.result_id
                ORDER BY (ei.verification_status = 'VERIFIED') DESC, ei.evidence_id LIMIT 1) AS page_number
        FROM app_private.criterion_assessment_results car
        JOIN app_private.criteria_items ci ON ci.criterion_id = car.criterion_id
        WHERE car.assessment_id = :aid
        ORDER BY CASE ci.category WHEN 'MUST_HAVE' THEN 0 ELSE 1 END, ci.display_order
    """), {"aid": str(run_row[0])}).mappings().all()
    return build_prep_brief([dict(r) for r in rows])


def _validate_eligible_panelists(db, position_id: str, panelist_ids: list[str]) -> None:
    """Every panelist must be an ACTIVE user assigned to this position (or HR Lead / Admin)."""
    if not panelist_ids:
        return
    valid_rows = db.execute(text("""
        SELECT up.user_id::text AS user_id
        FROM app_private.user_profiles up
        WHERE up.user_id = ANY(CAST(:uids AS uuid[]))
          AND up.account_status = 'ACTIVE'
          AND (
              EXISTS (SELECT 1 FROM app_private.position_assignments pa
                      WHERE pa.position_id = :p AND pa.user_id = up.user_id AND pa.revoked_at IS NULL)
              OR EXISTS (SELECT 1 FROM app_private.user_role_assignments r
                         WHERE r.user_id = up.user_id AND r.revoked_at IS NULL
                           AND r.role_code IN ('HR_LEAD', 'ADMIN'))
          )
    """), {"uids": panelist_ids, "p": position_id}).scalars().all()
    valid_set = set(valid_rows)
    if any(uid not in valid_set for uid in panelist_ids):
        raise HTTPException(
            status_code=400,
            detail="Thành viên hội đồng phải là tài khoản đang hoạt động và có quyền trên vị trí này.",
        )


def _audit(db, user_id: str, action: str, session_id: str, position_id: str, metadata: dict) -> None:
    db.execute(text("""
        INSERT INTO app_private.audit_events
            (actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
        VALUES (:u, :a, 'INTERVIEW_SESSION', :o, :p, 'SUCCESS', CAST(:m AS jsonb))
    """), {"u": user_id, "a": action, "o": session_id, "p": position_id, "m": json.dumps(metadata)})


def _validate_slot_and_location(starts_at: datetime, ends_at: datetime, fmt: str, location_or_link: Optional[str]) -> None:
    if ends_at <= starts_at:
        raise HTTPException(status_code=400, detail="Giờ kết thúc phải sau giờ bắt đầu")
    if (ends_at - starts_at) > timedelta(hours=8):
        raise HTTPException(status_code=400, detail="Thời lượng buổi phỏng vấn tối đa 8 giờ")
    if fmt != "ONSITE" and not (location_or_link or "").strip():
        raise HTTPException(status_code=400, detail="Phỏng vấn Online hoặc Điện thoại cần nhập đường dẫn hoặc số liên hệ")


# ---- routes -------------------------------------------------------------------------

@router.get("/my-schedule")
async def my_schedule(
    from_date: Optional[datetime] = Query(default=None),
    to_date: Optional[datetime] = Query(default=None),
    include_cancelled: bool = Query(default=False),
    current_user: dict = Depends(get_current_user),
):
    """Weekly interview schedule scoped strictly to sessions the user participates in or manages."""
    def run():
        db = SessionLocal()
        try:
            user = _active_user(db, current_user["user_id"])
            uid = current_user["user_id"]
            start = from_date or (datetime.now(timezone.utc) - timedelta(days=1))
            end = to_date or (start + timedelta(days=14))
            rows = db.execute(text("""
                SELECT s.*, p.position_code, p.title AS position_title,
                       COALESCE(i.display_name, 'Ứng viên') AS candidate_name
                FROM app_private.interview_sessions s
                JOIN app_private.positions p ON p.position_id = s.position_id
                LEFT JOIN app_private.application_identities i ON i.application_id = s.application_id
                WHERE s.starts_at >= :start AND s.starts_at < :end
                  AND (:inc_cancel OR s.session_status <> 'CANCELLED')
                  AND (
                      :is_lead
                      OR EXISTS (SELECT 1 FROM app_private.interview_panelists ip
                                 WHERE ip.session_id = s.session_id AND ip.user_id = :u)
                      OR EXISTS (SELECT 1 FROM app_private.position_assignments pa
                                 WHERE pa.position_id = s.position_id AND pa.user_id = :u
                                   AND pa.revoked_at IS NULL AND pa.position_role IN ('HR_RECRUITER', 'HR_LEAD'))
                  )
                ORDER BY s.starts_at ASC
                LIMIT 200
            """), {"start": start, "end": end, "inc_cancel": include_cancelled,
                   "is_lead": bool(user["is_lead_or_admin"]), "u": uid}).mappings().all()
            sids = [str(r["session_id"]) for r in rows]
            pmap = _load_panelists_map(db, sids)
            items = []
            for r in rows:
                sid = str(r["session_id"])
                pid = str(r["position_id"])
                brief = _load_prep_brief(db, str(r["application_id"]))
                items.append({
                    **_serialize_session(dict(r), pmap.get(sid, []), can_manage=_can_manage_position(db, uid, pid)),
                    "probe_count": brief["probe_count"],
                })
            return {"items": items}
        finally:
            db.close()
    return await run_in_threadpool(run)


@router.get("/applications/{application_id}")
async def list_for_application(application_id: UUID, current_user: dict = Depends(get_current_user)):
    """All interview rounds for one application, plus the AI Interview Prep Brief and panelist options."""
    def run():
        db = SessionLocal()
        try:
            _active_user(db, current_user["user_id"])
            app = db.execute(text("""
                SELECT a.application_id, a.position_id, p.position_code, p.title AS position_title,
                       COALESCE(i.display_name, 'Ứng viên') AS candidate_name
                FROM app_private.applications a
                JOIN app_private.positions p ON p.position_id = a.position_id
                LEFT JOIN app_private.application_identities i ON i.application_id = a.application_id
                WHERE a.application_id = :a
            """), {"a": str(application_id)}).mappings().first()
            if not app:
                raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ")
            pid = str(app["position_id"])
            uid = current_user["user_id"]
            if not _can_view_application(db, uid, str(application_id), pid):
                raise HTTPException(status_code=403, detail="Bạn không có quyền xem lịch phỏng vấn của hồ sơ này")
            can_manage = _can_manage_position(db, uid, pid)
            rows = db.execute(text("""
                SELECT s.*, :pcode AS position_code, :ptitle AS position_title, :cname AS candidate_name
                FROM app_private.interview_sessions s
                WHERE s.application_id = :a
                ORDER BY s.round_no ASC, s.starts_at ASC
            """), {"a": str(application_id), "pcode": app["position_code"],
                   "ptitle": app["position_title"], "cname": app["candidate_name"]}).mappings().all()
            sids = [str(r["session_id"]) for r in rows]
            pmap = _load_panelists_map(db, sids)
            panel_options = []
            if can_manage:
                opt_rows = db.execute(text("""
                    SELECT DISTINCT up.user_id, up.display_name, u.email
                    FROM app_private.user_profiles up
                    JOIN auth.users u ON u.id = up.user_id
                    WHERE up.account_status = 'ACTIVE' AND (
                        EXISTS (SELECT 1 FROM app_private.position_assignments pa
                                WHERE pa.position_id = :p AND pa.user_id = up.user_id AND pa.revoked_at IS NULL)
                        OR EXISTS (SELECT 1 FROM app_private.user_role_assignments r
                                   WHERE r.user_id = up.user_id AND r.revoked_at IS NULL
                                     AND r.role_code IN ('HR_LEAD', 'ADMIN'))
                    )
                    ORDER BY up.display_name
                    LIMIT 100
                """), {"p": pid}).mappings().all()
                panel_options = [
                    {"user_id": str(o["user_id"]), "display_name": o["display_name"] or o["email"] or "", "email": o["email"]}
                    for o in opt_rows
                ]
            return {
                "can_manage": can_manage,
                "sessions": [_serialize_session(dict(r), pmap.get(str(r["session_id"]), []), can_manage=can_manage) for r in rows],
                "prep_brief": _load_prep_brief(db, str(application_id)),
                "panel_options": panel_options,
            }
        finally:
            db.close()
    return await run_in_threadpool(run)


@router.post("/applications/{application_id}", status_code=201)
async def schedule_interview(application_id: UUID, body: InterviewCreate, current_user: dict = Depends(get_current_user)):
    """Schedule an interview round with automatic panelist conflict checking."""
    _validate_slot_and_location(body.starts_at, body.ends_at, body.format, body.location_or_link)

    def run():
        db = SessionLocal()
        try:
            _active_user(db, current_user["user_id"])
            app = db.execute(text("""
                SELECT a.application_id, a.position_id, p.position_code, p.title AS position_title,
                       COALESCE(i.display_name, 'Ứng viên') AS candidate_name
                FROM app_private.applications a
                JOIN app_private.positions p ON p.position_id = a.position_id
                LEFT JOIN app_private.application_identities i ON i.application_id = a.application_id
                WHERE a.application_id = :a
            """), {"a": str(application_id)}).mappings().first()
            if not app:
                raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ")
            pid = str(app["position_id"])
            uid = current_user["user_id"]
            if not _can_manage_position(db, uid, pid):
                raise HTTPException(status_code=403, detail="Chỉ HR phụ trách vị trí mới đặt được lịch phỏng vấn")

            unique_panelists = {str(p.user_id): p.panel_role for p in body.panelists}
            panelist_ids = list(unique_panelists.keys())
            _validate_eligible_panelists(db, pid, panelist_ids)
            conflicts = _find_panelist_conflicts(db, panelist_ids, body.starts_at, body.ends_at)
            if conflicts and not body.allow_conflict:
                raise HTTPException(
                    status_code=409,
                    detail={"message": "Một hoặc nhiều thành viên hội đồng đang trùng lịch phỏng vấn khác.", "conflicts": conflicts},
                )
            try:
                row = db.execute(text("""
                    INSERT INTO app_private.interview_sessions
                        (application_id, position_id, round_no, title, starts_at, ends_at, format, location_or_link, prep_notes, created_by)
                    VALUES (:a, :p, :r, :t, :s, :e, :f, :loc, :notes, :u)
                    RETURNING *
                """), {
                    "a": str(application_id), "p": pid, "r": body.round_no, "t": body.title,
                    "s": body.starts_at, "e": body.ends_at, "f": body.format,
                    "loc": body.location_or_link or None, "notes": (body.prep_notes or "").strip() or None, "u": uid,
                }).mappings().one()
            except IntegrityError as exc:
                db.rollback()
                if getattr(exc.orig, "pgcode", None) == "23505":
                    raise HTTPException(status_code=409, detail=f"Hồ sơ đã có buổi phỏng vấn vòng {body.round_no} đang hiệu lực") from None
                raise
            sid = str(row["session_id"])
            for p_uid, p_role in unique_panelists.items():
                db.execute(text("""
                    INSERT INTO app_private.interview_panelists (session_id, user_id, panel_role, added_by)
                    VALUES (:sid, :uid, :role, :actor)
                """), {"sid": sid, "uid": p_uid, "role": p_role, "actor": uid})
            _audit(db, uid, "SCHEDULE_INTERVIEW", sid, pid, {
                "round_no": body.round_no, "format": body.format,
                "panelist_count": len(panelist_ids), "had_conflict": bool(conflicts),
            })
            db.commit()
            pmap = _load_panelists_map(db, [sid])
            full = {**dict(row), "position_code": app["position_code"], "position_title": app["position_title"],
                    "candidate_name": app["candidate_name"]}
            return {**_serialize_session(full, pmap.get(sid, []), can_manage=True), "conflicts": conflicts}
        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    return await run_in_threadpool(run)


@router.patch("/{session_id}")
async def update_interview(session_id: UUID, body: InterviewUpdate, current_user: dict = Depends(get_current_user)):
    """Reschedule, update status (COMPLETED/CANCELLED/NO_SHOW), or change panelists."""
    def run():
        db = SessionLocal()
        try:
            _active_user(db, current_user["user_id"])
            existing = db.execute(text("""
                SELECT s.*, p.position_code, p.title AS position_title,
                       COALESCE(i.display_name, 'Ứng viên') AS candidate_name
                FROM app_private.interview_sessions s
                JOIN app_private.positions p ON p.position_id = s.position_id
                LEFT JOIN app_private.application_identities i ON i.application_id = s.application_id
                WHERE s.session_id = :sid FOR UPDATE OF s
            """), {"sid": str(session_id)}).mappings().first()
            if not existing:
                raise HTTPException(status_code=404, detail="Không tìm thấy buổi phỏng vấn")
            pid = str(existing["position_id"])
            uid = current_user["user_id"]
            if not _can_manage_position(db, uid, pid):
                raise HTTPException(status_code=403, detail="Chỉ HR phụ trách vị trí mới cập nhật được lịch phỏng vấn")

            new_starts = body.starts_at or existing["starts_at"]
            new_ends = body.ends_at or existing["ends_at"]
            new_format = body.format or existing["format"]
            new_loc = existing["location_or_link"] if body.location_or_link is None else (body.location_or_link or None)
            new_status = body.session_status or existing["session_status"]
            _validate_slot_and_location(new_starts, new_ends, new_format, new_loc)

            if body.panelists is not None:
                unique_panelists = {str(p.user_id): p.panel_role for p in body.panelists}
                panelist_ids = list(unique_panelists.keys())
                _validate_eligible_panelists(db, pid, panelist_ids)
            else:
                panelist_ids = [str(r[0]) for r in db.execute(
                    text("SELECT user_id FROM app_private.interview_panelists WHERE session_id = :sid"),
                    {"sid": str(session_id)}).all()]
                unique_panelists = None

            conflicts: list[dict] = []
            if new_status == "SCHEDULED":
                conflicts = _find_panelist_conflicts(db, panelist_ids, new_starts, new_ends, exclude_session_id=str(session_id))
                if conflicts and not body.allow_conflict:
                    raise HTTPException(
                        status_code=409,
                        detail={"message": "Một hoặc nhiều thành viên hội đồng đang trùng lịch phỏng vấn khác.", "conflicts": conflicts},
                    )

            try:
                updated = db.execute(text("""
                    UPDATE app_private.interview_sessions
                    SET title = COALESCE(:t, title),
                        session_status = :st,
                        starts_at = :s,
                        ends_at = :e,
                        format = :f,
                        location_or_link = :loc,
                        prep_notes = CASE WHEN :has_notes THEN :notes ELSE prep_notes END,
                        updated_at = NOW()
                    WHERE session_id = :sid
                    RETURNING *
                """), {
                    "t": body.title, "st": new_status, "s": new_starts, "e": new_ends,
                    "f": new_format, "loc": new_loc,
                    "has_notes": body.prep_notes is not None,
                    "notes": (body.prep_notes or "").strip() or None if body.prep_notes is not None else None,
                    "sid": str(session_id),
                }).mappings().one()
            except IntegrityError as exc:
                db.rollback()
                if getattr(exc.orig, "pgcode", None) == "23505":
                    raise HTTPException(status_code=409, detail="Đã có buổi phỏng vấn khác cùng vòng đang hiệu lực") from None
                raise

            if unique_panelists is not None:
                db.execute(text("DELETE FROM app_private.interview_panelists WHERE session_id = :sid"), {"sid": str(session_id)})
                for p_uid, p_role in unique_panelists.items():
                    db.execute(text("""
                        INSERT INTO app_private.interview_panelists (session_id, user_id, panel_role, added_by)
                        VALUES (:sid, :uid, :role, :actor)
                    """), {"sid": str(session_id), "uid": p_uid, "role": p_role, "actor": uid})

            _audit(db, uid, "UPDATE_INTERVIEW", str(session_id), pid, {
                "status": new_status, "format": new_format, "had_conflict": bool(conflicts),
            })
            db.commit()
            pmap = _load_panelists_map(db, [str(session_id)])
            full = {**dict(updated), "position_code": existing["position_code"],
                    "position_title": existing["position_title"], "candidate_name": existing["candidate_name"]}
            return {**_serialize_session(full, pmap.get(str(session_id), []), can_manage=True), "conflicts": conflicts}
        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    return await run_in_threadpool(run)


@router.get("/{session_id}/calendar.ics")
async def download_ics(session_id: UUID, current_user: dict = Depends(get_current_user)):
    """Download an RFC 5545 .ics calendar file for Outlook / Google Calendar import."""
    def run():
        db = SessionLocal()
        try:
            _active_user(db, current_user["user_id"])
            row = db.execute(text("""
                SELECT s.*, p.position_code, p.title AS position_title
                FROM app_private.interview_sessions s
                JOIN app_private.positions p ON p.position_id = s.position_id
                WHERE s.session_id = :sid
            """), {"sid": str(session_id)}).mappings().first()
            if not row:
                raise HTTPException(status_code=404, detail="Không tìm thấy buổi phỏng vấn")
            if not _can_view_application(db, current_user["user_id"], str(row["application_id"]), str(row["position_id"])):
                raise HTTPException(status_code=403, detail="Bạn không có quyền tải lịch buổi phỏng vấn này")
            payload = build_ics(
                session_id=str(row["session_id"]),
                position_code=row["position_code"],
                position_title=row["position_title"],
                round_no=row["round_no"],
                title=row["title"],
                starts_at=row["starts_at"],
                ends_at=row["ends_at"],
                fmt=row["format"],
                location_or_link=row["location_or_link"],
                prep_notes=row["prep_notes"],
            )
            filename = safe_ics_filename(row["position_code"], row["round_no"])
            return payload, filename
        finally:
            db.close()
    payload, filename = await run_in_threadpool(run)
    return Response(
        content=payload,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
