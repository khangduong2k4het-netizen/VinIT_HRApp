"""P3-1 Talent Pool, phase 1: marking and eligibility. Scanning comes later."""
import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from app.core.permissions import check_position_access
from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.services.talent_pool import MARK_REASONS, application_pool_state

router = APIRouter()

REASON_TEXT = {
    "NO_CONSENT": "Ứng viên chưa đồng ý cho dùng hồ sơ ở vị trí khác",
    "CONSENT_WITHDRAWN": "Ứng viên đã rút đồng ý",
    "RETENTION_EXPIRED": "Hồ sơ đã quá thời hạn lưu",
    "DELETION_PENDING": "Hồ sơ đang chờ xóa hoặc bị tạm hoãn",
    "STATUS_NOT_ELIGIBLE": "Trạng thái hồ sơ chưa đủ điều kiện",
}


class MarkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason_code: str


class WithdrawInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference: Optional[str] = None  # tham chiếu văn bản yêu cầu, không chứa dữ liệu cá nhân


def _audit(db, user_id, action, application_id, position_id, metadata):
    db.execute(text("""INSERT INTO app_private.audit_events(actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
        VALUES (:u, :a, 'APPLICATION', :o, :p, 'SUCCESS', CAST(:m AS jsonb))"""),
               {"u": user_id, "a": action, "o": application_id, "p": position_id, "m": json.dumps(metadata)})


async def _state_with_access(db, application_id, current_user):
    state = application_pool_state(db, str(application_id))
    if state is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ")
    await check_position_access(UUID(state["position_id"]), current_user, required_roles=["HR_RECRUITER"])
    return state


@router.get("/applications/{application_id}")
async def pool_state(application_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        state = await _state_with_access(db, application_id, current_user)
        marked = db.execute(text("SELECT 1 FROM app_private.talent_pool_marks WHERE application_id = :a AND removed_at IS NULL"),
                            {"a": str(application_id)}).first() is not None
        return {"marked": marked, "can_mark": state["eligible"], "reason": state["reason"],
                "reason_text": REASON_TEXT.get(state["reason"]), "expires_on": state["expires_on"]}
    finally:
        db.close()


@router.post("/applications/{application_id}/mark", status_code=201)
async def mark(application_id: UUID, body: MarkInput, current_user: dict = Depends(get_current_user)):
    if body.reason_code not in MARK_REASONS:
        raise HTTPException(status_code=400, detail="Lý do không hợp lệ")
    db = SessionLocal()
    try:
        state = await _state_with_access(db, application_id, current_user)
        if not state["eligible"]:
            raise HTTPException(status_code=409, detail=REASON_TEXT[state["reason"]])
        existing = db.execute(text("SELECT 1 FROM app_private.talent_pool_marks WHERE application_id = :a AND removed_at IS NULL"),
                              {"a": str(application_id)}).first()
        if existing:
            raise HTTPException(status_code=409, detail="Hồ sơ đã nằm trong Talent Pool")
        db.execute(text("INSERT INTO app_private.talent_pool_marks(application_id, marked_by, reason_code) VALUES (:a, :u, :r)"),
                   {"a": str(application_id), "u": current_user["user_id"], "r": body.reason_code})
        _audit(db, current_user["user_id"], "MARK_TALENT_POOL", str(application_id), state["position_id"], {"reason_code": body.reason_code})
        db.commit()
        return {"marked": True}
    finally:
        db.close()


@router.delete("/applications/{application_id}/mark")
async def unmark(application_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        state = await _state_with_access(db, application_id, current_user)
        done = db.execute(text("UPDATE app_private.talent_pool_marks SET removed_at = NOW() WHERE application_id = :a AND removed_at IS NULL"),
                          {"a": str(application_id)}).rowcount
        if not done:
            raise HTTPException(status_code=404, detail="Hồ sơ không nằm trong Talent Pool")
        _audit(db, current_user["user_id"], "UNMARK_TALENT_POOL", str(application_id), state["position_id"], {})
        db.commit()
        return {"marked": False}
    finally:
        db.close()


@router.post("/applications/{application_id}/withdraw-consent")
async def withdraw_consent(application_id: UUID, body: WithdrawInput, current_user: dict = Depends(get_current_user)):
    """HR records a candidate's written request. Scanning stops at once; deletion follows the retention queue."""
    db = SessionLocal()
    try:
        state = await _state_with_access(db, application_id, current_user)
        done = db.execute(text("""UPDATE app_private.application_data_consents SET withdrawn_at = NOW(), withdrawn_by = :u
            WHERE application_id = :a AND purpose = 'TALENT_POOL' AND withdrawn_at IS NULL"""),
                          {"a": str(application_id), "u": current_user["user_id"]}).rowcount
        if not done:
            raise HTTPException(status_code=404, detail="Không có đồng ý đang hiệu lực để rút")
        db.execute(text("UPDATE app_private.talent_pool_marks SET removed_at = NOW() WHERE application_id = :a AND removed_at IS NULL"),
                   {"a": str(application_id)})
        _audit(db, current_user["user_id"], "WITHDRAW_TALENT_POOL_CONSENT", str(application_id), state["position_id"],
               {"has_reference": bool(body.reference)})
        db.commit()
        return {"withdrawn": True}
    finally:
        db.close()


# ---- List the pool and scan it for a new position (P3-1 phase 2) ---------------------

from app.services.talent_pool import (eligible_application_ids, eligible_pool,  # noqa: E402
                                      pool_expiry, scan_candidates)

HR_ROLES = ("ADMIN", "HR_LEAD", "HR_RECRUITER")


def _require_hr(db, user_id: str) -> None:
    """HR by system role, or HR assigned to at least one position."""
    roles = set(db.execute(text("""
        SELECT role_code FROM app_private.user_role_assignments
        WHERE user_id = :u AND revoked_at IS NULL AND role_code = ANY(:roles)
        UNION
        SELECT position_role FROM app_private.position_assignments
        WHERE user_id = :u AND revoked_at IS NULL AND position_role IN ('HR_RECRUITER', 'HR_LEAD')
    """), {"u": user_id, "roles": list(HR_ROLES)}).scalars())
    account = db.execute(text("SELECT account_status FROM app_private.user_profiles WHERE user_id = :u"),
                         {"u": user_id}).scalar_one_or_none()
    if not roles or account != "ACTIVE":
        raise HTTPException(status_code=403, detail="Chỉ HR mới xem được Talent Pool")


@router.get("")
async def list_pool(current_user: dict = Depends(get_current_user)):
    """Applications that may be reused now. Name and source position only, no contact details."""
    db = SessionLocal()
    try:
        _require_hr(db, current_user["user_id"])
        ids = [str(row["application_id"]) for row in eligible_pool(db)]
        if not ids:
            return {"items": []}
        rows = db.execute(text("""
            SELECT a.application_id, a.application_status, p.position_id, p.position_code, p.title AS position_title,
                   i.display_name, m.reason_code, m.marked_at, c.granted_at
            FROM app_private.applications a
            JOIN app_private.positions p ON p.position_id = a.position_id
            JOIN app_private.talent_pool_marks m ON m.application_id = a.application_id AND m.removed_at IS NULL
            JOIN app_private.application_data_consents c
              ON c.application_id = a.application_id AND c.purpose = 'TALENT_POOL' AND c.withdrawn_at IS NULL
            LEFT JOIN app_private.application_identities i ON i.application_id = a.application_id
            WHERE a.application_id = ANY(CAST(:ids AS uuid[]))
            ORDER BY m.marked_at DESC
        """), {"ids": ids}).mappings().all()
        return {"items": [{
            "application_id": str(r["application_id"]), "candidate_name": r["display_name"],
            "application_status": r["application_status"], "position_id": str(r["position_id"]),
            "position_code": r["position_code"], "position_title": r["position_title"],
            "reason_code": r["reason_code"], "marked_at": r["marked_at"],
            "expires_on": pool_expiry(r["granted_at"]).date().isoformat(),
        } for r in rows]}
    finally:
        db.close()


def _scan_out(row) -> dict:
    return {"scan_id": str(row["scan_id"]), "status": row["status"], "criteria_version_id": str(row["criteria_version_id"]),
            "candidate_count": row["candidate_count"], "scored_count": row["scored_count"],
            "failed_count": row["failed_count"], "error_message": row["error_message"],
            "created_at": row["created_at"], "completed_at": row["completed_at"]}


@router.post("/positions/{position_id}/scans", status_code=202)
async def start_scan(position_id: UUID, current_user: dict = Depends(get_current_user)):
    """Queue a scan of the pool against this position's approved criteria (HR of the position)."""
    await check_position_access(position_id, current_user, required_roles=["HR_RECRUITER"])
    db = SessionLocal()
    try:
        pid = str(position_id)
        position_status = db.execute(text("SELECT status FROM app_private.positions WHERE position_id = :p FOR UPDATE"),
                                     {"p": pid}).scalar_one_or_none()
        if position_status is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy vị trí")
        if position_status != "OPEN":
            raise HTTPException(status_code=409, detail="Chỉ quét Talent Pool cho vị trí đang mở")
        cv_id = db.execute(text("""
            SELECT criteria_version_id FROM app_private.criteria_versions
            WHERE position_id = :p AND status = 'APPROVED'
              AND jd_version_id = (SELECT jd_version_id FROM app_private.jd_versions WHERE position_id = :p
                                   ORDER BY version_number DESC LIMIT 1)
            ORDER BY version_number DESC LIMIT 1
        """), {"p": pid}).scalar_one_or_none()
        if not cv_id:
            raise HTTPException(status_code=409, detail="Cần duyệt bộ tiêu chí cho JD mới nhất trước khi quét Talent Pool")
        if db.execute(text("""SELECT 1 FROM app_private.talent_pool_scans
                WHERE position_id = :p AND status IN ('PENDING', 'PROCESSING') LIMIT 1"""), {"p": pid}).first():
            raise HTTPException(status_code=409, detail="Đang có một lượt quét Talent Pool cho vị trí này")
        candidate_count = len(scan_candidates(db, pid))
        operation_id = db.execute(text("""
            INSERT INTO app_private.operations (position_id, capability, status, requested_by)
            VALUES (:p, 'TALENT_POOL_SCAN', 'PENDING', :u) RETURNING operation_id
        """), {"p": pid, "u": current_user["user_id"]}).scalar_one()
        row = db.execute(text("""
            INSERT INTO app_private.talent_pool_scans (position_id, criteria_version_id, operation_id, requested_by)
            VALUES (:p, :cv, :o, :u) RETURNING *
        """), {"p": pid, "cv": str(cv_id), "o": str(operation_id), "u": current_user["user_id"]}).mappings().one()
        db.execute(text("""INSERT INTO app_private.audit_events(actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
            VALUES (:u, 'START_TALENT_POOL_SCAN', 'POSITION', :p, :p, 'SUCCESS', CAST(:m AS jsonb))"""),
                   {"u": current_user["user_id"], "p": pid,
                    "m": json.dumps({"scan_id": str(row["scan_id"]), "candidate_count": candidate_count})})
        db.commit()
        return {**_scan_out(row), "candidate_count": candidate_count}
    finally:
        db.close()


@router.get("/positions/{position_id}/scans/latest")
async def latest_scan(position_id: UUID, current_user: dict = Depends(get_current_user)):
    """Latest scan and its ranked results. Results whose pool eligibility ended since are hidden."""
    await check_position_access(position_id, current_user, required_roles=["HR_RECRUITER"])
    db = SessionLocal()
    try:
        row = db.execute(text("""SELECT * FROM app_private.talent_pool_scans WHERE position_id = :p
            ORDER BY created_at DESC LIMIT 1"""), {"p": str(position_id)}).mappings().first()
        if not row:
            return {"scan": None, "results": [], "hidden_count": 0}
        results = db.execute(text("""
            SELECT r.application_id, r.status, r.matching_status, r.matching_score, r.evidence_coverage, r.rank_number,
                   r.criteria, a.application_status, p.position_code, p.title AS position_title,
                   i.display_name, i.email, i.phone, m.reason_code
            FROM app_private.talent_pool_scan_results r
            JOIN app_private.applications a ON a.application_id = r.application_id
            JOIN app_private.positions p ON p.position_id = a.position_id
            LEFT JOIN app_private.application_identities i ON i.application_id = r.application_id
            LEFT JOIN app_private.talent_pool_marks m ON m.application_id = r.application_id AND m.removed_at IS NULL
            WHERE r.scan_id = :s
            ORDER BY r.rank_number NULLS LAST, r.created_at
        """), {"s": str(row["scan_id"])}).mappings().all()
        still_eligible = eligible_application_ids(db)
        visible = [r for r in results if str(r["application_id"]) in still_eligible]
        if visible:
            db.execute(text("""INSERT INTO app_private.audit_events(actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
                VALUES (:u, 'VIEW_TALENT_POOL_RESULTS', 'POSITION', :p, :p, 'SUCCESS', CAST(:m AS jsonb))"""),
                       {"u": current_user["user_id"], "p": str(position_id),
                        "m": json.dumps({"scan_id": str(row["scan_id"]), "result_count": len(visible)})})
            db.commit()
        return {"scan": _scan_out(row), "hidden_count": len(results) - len(visible), "results": [{
            "application_id": str(r["application_id"]), "status": r["status"], "rank_number": r["rank_number"],
            "matching_status": r["matching_status"],
            "matching_score": float(r["matching_score"]) if r["matching_score"] is not None else None,
            "evidence_coverage": float(r["evidence_coverage"]) if r["evidence_coverage"] is not None else None,
            "criteria": r["criteria"] or [], "candidate_name": r["display_name"],
            # Consent covers reuse for other positions, so the HR of this position may contact the candidate.
            "email": r["email"], "phone": r["phone"], "reason_code": r["reason_code"],
            "source_position_code": r["position_code"], "source_position_title": r["position_title"],
            "source_application_status": r["application_status"],
        } for r in visible]}
    finally:
        db.close()
