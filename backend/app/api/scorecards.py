"""F2.02 — Structured HR–HM scorecards on shortlist shares.

Access (plan D-10): the reviewing Hiring Manager, HR responsible for the
position, and HR Lead/Admin. Another HM never sees a scorecard. A revoked share
or a revoked HM assignment removes the reviewer's access immediately. HR private
notes are never read here.

Mounted under /shortlist *before* the shortlist router so that literal paths
such as /shortlist/my-scorecards are not captured by /shortlist/{share_id}.
"""
import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from app.core.exceptions import NotFoundError
from app.core.permissions import can_update_application_status
from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.schemas.rubric import ScorecardReopenRequest, ScorecardUpdate
from app.services.workflow_rules import INSUFFICIENT_EVIDENCE, scorecard_completion_errors

router = APIRouter()

_SCORECARD_SELECT = """
    SELECT sc.*, s.status AS share_status, s.allow_cv_view, p.title AS position_title, p.position_code,
           COALESCE(i.display_name, 'Chưa có tên') AS candidate_name,
           reviewer.display_name AS reviewer_name, reopener.display_name AS reopened_by_name,
           cv.version_number AS criteria_version_number,
           ar.matching_status, ar.matching_score, ar.evidence_coverage,
           (sc.status <> 'SUBMITTED' AND sc.due_at < NOW()) AS is_overdue
    FROM app_private.shortlist_scorecards sc
    JOIN app_private.shortlist_shares s ON s.share_id = sc.share_id
    JOIN app_private.positions p ON p.position_id = sc.position_id
    LEFT JOIN app_private.application_identities i ON i.application_id = sc.application_id
    LEFT JOIN app_private.user_profiles reviewer ON reviewer.user_id = sc.reviewer_user_id
    LEFT JOIN app_private.user_profiles reopener ON reopener.user_id = sc.reopened_by
    LEFT JOIN app_private.criteria_versions cv ON cv.criteria_version_id = sc.criteria_version_id
    LEFT JOIN app_private.assessment_runs ar ON ar.assessment_id = sc.assessment_id
"""


def _is_active_reviewer(db, scorecard: dict, user_id: str) -> bool:
    if str(scorecard["reviewer_user_id"]) != user_id or scorecard["share_status"] != "ACTIVE":
        return False
    return bool(db.execute(text("""
        SELECT 1 FROM app_private.position_assignments WHERE position_id = :position AND user_id = :user_id
          AND position_role = 'HIRING_MANAGER' AND revoked_at IS NULL
    """), {"position": str(scorecard["position_id"]), "user_id": user_id}).first())


def _load_scorecard(db, scorecard_id, user_id: str, *, lock: bool = False) -> tuple[dict, bool, bool]:
    """Return (scorecard, is_reviewer, is_hr) after an access check."""
    if lock:
        if not db.execute(text("SELECT 1 FROM app_private.shortlist_scorecards WHERE scorecard_id = :id FOR UPDATE"),
                          {"id": str(scorecard_id)}).first():
            raise NotFoundError("Scorecard")
    row = db.execute(text(_SCORECARD_SELECT + " WHERE sc.scorecard_id = :id"), {"id": str(scorecard_id)}).mappings().first()
    if not row:
        raise NotFoundError("Scorecard")
    scorecard = dict(row)
    is_reviewer = _is_active_reviewer(db, scorecard, user_id)
    is_hr = can_update_application_status(user_id, str(scorecard["position_id"]))
    if not is_reviewer and not is_hr:
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem scorecard này")
    return scorecard, is_reviewer, is_hr


def _criteria(db, scorecard_id) -> list[dict]:
    return [dict(row) for row in db.execute(text("""
        SELECT scc.criterion_id, ci.name, ci.description, ci.category, ci.weight_in_group, ci.display_order,
               scc.rating, scc.evidence_assessment, scc.comment, scc.updated_at
        FROM app_private.shortlist_scorecard_criteria scc
        JOIN app_private.criteria_items ci ON ci.criterion_id = scc.criterion_id
        WHERE scc.scorecard_id = :id
        ORDER BY CASE ci.category WHEN 'MUST_HAVE' THEN 0 ELSE 1 END, ci.display_order, ci.criterion_id
    """), {"id": str(scorecard_id)}).mappings().all()]


def _response(db, scorecard: dict, is_reviewer: bool, is_hr: bool) -> dict:
    criteria = _criteria(db, scorecard["scorecard_id"])
    editable = is_reviewer and scorecard["status"] != "SUBMITTED" and scorecard["criteria_version_id"] is not None
    return {
        **scorecard,
        "criteria": criteria,
        "can_edit": editable,
        "can_reopen": is_hr and scorecard["status"] == "SUBMITTED",
        "completion_errors": scorecard_completion_errors(criteria, scorecard["overall_recommendation"]),
    }


def _audit(db, user_id, action: str, scorecard: dict, metadata: Optional[dict] = None):
    db.execute(text("""
        INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
        VALUES (:user_id, :action, 'SCORECARD', :id, :position, 'SUCCESS', CAST(:metadata AS jsonb))
    """), {"user_id": user_id, "action": action, "id": str(scorecard["scorecard_id"]),
            "position": str(scorecard["position_id"]), "metadata": json.dumps(metadata) if metadata else None})


@router.get("/my-scorecards")
async def list_my_scorecards(status_filter: Optional[str] = Query(None, alias="status",
                                                                  pattern="^(NOT_STARTED|IN_PROGRESS|SUBMITTED|OVERDUE|OPEN)$"),
                             current_user: dict = Depends(get_current_user)):
    """Reviewer inbox: scorecards assigned to me on active shares I can still access."""
    db = SessionLocal()
    try:
        rows = db.execute(text(_SCORECARD_SELECT + """
            WHERE sc.reviewer_user_id = :user_id AND s.status = 'ACTIVE'
              AND EXISTS (SELECT 1 FROM app_private.position_assignments pa WHERE pa.position_id = sc.position_id
                          AND pa.user_id = :user_id AND pa.position_role = 'HIRING_MANAGER' AND pa.revoked_at IS NULL)
              AND (CAST(:status AS text) IS NULL
                   OR (:status = 'OVERDUE' AND sc.status <> 'SUBMITTED' AND sc.due_at < NOW())
                   OR (:status = 'OPEN' AND sc.status <> 'SUBMITTED')
                   OR sc.status = :status)
            ORDER BY (sc.status = 'SUBMITTED'), sc.due_at, sc.scorecard_id
        """), {"user_id": current_user["user_id"], "status": status_filter}).mappings().all()
        items = [dict(row) for row in rows]
        summary = {
            "total": len(items),
            "not_started": sum(1 for r in items if r["status"] == "NOT_STARTED"),
            "in_progress": sum(1 for r in items if r["status"] == "IN_PROGRESS"),
            "submitted": sum(1 for r in items if r["status"] == "SUBMITTED"),
            "overdue": sum(1 for r in items if r["is_overdue"]),
        }
        return {"summary": summary, "items": items}
    finally:
        db.close()


@router.get("/scorecards/{scorecard_id}")
async def get_scorecard(scorecard_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        scorecard, is_reviewer, is_hr = _load_scorecard(db, scorecard_id, current_user["user_id"])
        return _response(db, scorecard, is_reviewer, is_hr)
    finally:
        db.close()


@router.patch("/scorecards/{scorecard_id}")
async def save_scorecard_draft(scorecard_id: UUID, request: ScorecardUpdate, current_user: dict = Depends(get_current_user)):
    """The reviewing HM saves ratings/comments; allowed until submission."""
    user_id = current_user["user_id"]
    fields = request.model_dump(exclude_unset=True)
    db = SessionLocal()
    try:
        scorecard, is_reviewer, is_hr = _load_scorecard(db, scorecard_id, user_id, lock=True)
        if not is_reviewer:
            raise HTTPException(status_code=403, detail="Chỉ Hiring Manager được giao mới điền được scorecard")
        if scorecard["status"] == "SUBMITTED":
            raise HTTPException(status_code=400, detail="Scorecard đã nộp. Cần HR mở lại trước khi chỉnh sửa.")
        if scorecard["criteria_version_id"] is None:
            raise HTTPException(status_code=400, detail="Hồ sơ chưa có kết quả đánh giá hợp lệ khi chia sẻ; chưa thể chấm scorecard.")
        allowed_ids = {str(c["criterion_id"]) for c in _criteria(db, scorecard_id)}
        for item in request.criteria:
            if str(item.criterion_id) not in allowed_ids:
                raise HTTPException(status_code=400, detail="Tiêu chí không thuộc bộ tiêu chí đã khóa của scorecard này")
        for item in request.criteria:
            comment = (item.comment or "").strip() or None
            db.execute(text("""
                UPDATE app_private.shortlist_scorecard_criteria
                SET rating = :rating, evidence_assessment = :evidence, comment = :comment, updated_at = NOW()
                WHERE scorecard_id = :scorecard AND criterion_id = :criterion
            """), {"rating": item.rating, "evidence": INSUFFICIENT_EVIDENCE if item.insufficient_evidence else None,
                    "comment": comment, "scorecard": str(scorecard_id), "criterion": str(item.criterion_id)})
        values = {}
        if "overall_recommendation" in fields:
            values["overall_recommendation"] = fields["overall_recommendation"]
        for key in ("strengths", "concerns"):
            if key in fields:
                values[key] = (fields[key] or "").strip() or None
        sets = "".join(f", {key} = :{key}" for key in values)
        db.execute(text(f"""
            UPDATE app_private.shortlist_scorecards SET status = 'IN_PROGRESS', updated_at = NOW(){sets}
            WHERE scorecard_id = :id
        """), {**values, "id": str(scorecard_id)})
        scorecard, is_reviewer, is_hr = _load_scorecard(db, scorecard_id, user_id)
        result = _response(db, scorecard, is_reviewer, is_hr)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/scorecards/{scorecard_id}/submit")
async def submit_scorecard(scorecard_id: UUID, current_user: dict = Depends(get_current_user)):
    """Validate completeness (D-07) and lock the scorecard."""
    user_id = current_user["user_id"]
    db = SessionLocal()
    try:
        scorecard, is_reviewer, _ = _load_scorecard(db, scorecard_id, user_id, lock=True)
        if not is_reviewer:
            raise HTTPException(status_code=403, detail="Chỉ Hiring Manager được giao mới nộp được scorecard")
        if scorecard["status"] == "SUBMITTED":
            raise HTTPException(status_code=400, detail="Scorecard đã được nộp")
        if scorecard["criteria_version_id"] is None:
            raise HTTPException(status_code=400, detail="Hồ sơ chưa có kết quả đánh giá hợp lệ khi chia sẻ; chưa thể nộp scorecard.")
        errors = scorecard_completion_errors(_criteria(db, scorecard_id), scorecard["overall_recommendation"])
        if errors:
            raise HTTPException(status_code=400, detail=" ".join(errors))
        db.execute(text("""
            UPDATE app_private.shortlist_scorecards SET status = 'SUBMITTED', submitted_at = NOW(), updated_at = NOW()
            WHERE scorecard_id = :id
        """), {"id": str(scorecard_id)})
        _audit(db, user_id, "SUBMIT_SCORECARD", scorecard, {"overall_recommendation": scorecard["overall_recommendation"]})
        scorecard, is_reviewer, is_hr = _load_scorecard(db, scorecard_id, user_id)
        result = _response(db, scorecard, is_reviewer, is_hr)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/scorecards/{scorecard_id}/reopen")
async def reopen_scorecard(scorecard_id: UUID, request: ScorecardReopenRequest, current_user: dict = Depends(get_current_user)):
    """HR responsible for the position (or HR Lead/Admin) reopens a submitted scorecard with a reason."""
    user_id = current_user["user_id"]
    reason = request.reason.strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Vui lòng nhập lý do mở lại scorecard")
    db = SessionLocal()
    try:
        scorecard, _, is_hr = _load_scorecard(db, scorecard_id, user_id, lock=True)
        if not is_hr:
            raise HTTPException(status_code=403, detail="Chỉ HR phụ trách mới mở lại được scorecard")
        if scorecard["status"] != "SUBMITTED":
            raise HTTPException(status_code=400, detail="Chỉ mở lại được scorecard đã nộp")
        db.execute(text("""
            UPDATE app_private.shortlist_scorecards
            SET status = 'IN_PROGRESS', submitted_at = NULL, reopened_by = :user_id, reopened_at = NOW(),
                reopen_reason = :reason, updated_at = NOW()
            WHERE scorecard_id = :id
        """), {"user_id": user_id, "reason": reason, "id": str(scorecard_id)})
        # Audit metadata never carries the reason text or scorecard content.
        _audit(db, user_id, "REOPEN_SCORECARD", scorecard)
        scorecard, is_reviewer, is_hr = _load_scorecard(db, scorecard_id, user_id)
        result = _response(db, scorecard, is_reviewer, is_hr)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/{share_id}/scorecard-summary")
async def scorecard_summary(share_id: UUID, current_user: dict = Depends(get_current_user)):
    """Progress and recommendations for one share (HR responsible, HR Lead/Admin, or the reviewing HM)."""
    user_id = current_user["user_id"]
    db = SessionLocal()
    try:
        share = db.execute(text("SELECT position_id, shared_with, status FROM app_private.shortlist_shares WHERE share_id = :id"),
                           {"id": str(share_id)}).mappings().first()
        if not share:
            raise NotFoundError("Shortlist share")
        is_hr = can_update_application_status(user_id, str(share["position_id"]))
        is_reviewer = _is_active_reviewer(db, {"reviewer_user_id": share["shared_with"], "share_status": share["status"],
                                               "position_id": share["position_id"]}, user_id)
        if not is_hr and not is_reviewer:
            raise HTTPException(status_code=403, detail="Bạn không có quyền xem tổng hợp scorecard này")
        rows = [dict(row) for row in db.execute(text(_SCORECARD_SELECT + """
            WHERE sc.share_id = :id ORDER BY candidate_name, sc.scorecard_id
        """), {"id": str(share_id)}).mappings().all()]
        recommendations = {key: sum(1 for r in rows if r["status"] == "SUBMITTED" and r["overall_recommendation"] == key)
                           for key in ("STRONG_YES", "YES", "NO", "STRONG_NO")}
        return {
            "share_id": share_id,
            "total": len(rows),
            "not_started": sum(1 for r in rows if r["status"] == "NOT_STARTED"),
            "in_progress": sum(1 for r in rows if r["status"] == "IN_PROGRESS"),
            "submitted": sum(1 for r in rows if r["status"] == "SUBMITTED"),
            "overdue": sum(1 for r in rows if r["is_overdue"]),
            "recommendations": recommendations,
            "scorecards": [{key: r[key] for key in (
                "scorecard_id", "application_id", "candidate_name", "reviewer_name", "status", "due_at", "is_overdue",
                "submitted_at", "overall_recommendation", "reopened_at", "criteria_version_number")} for r in rows],
        }
    finally:
        db.close()
