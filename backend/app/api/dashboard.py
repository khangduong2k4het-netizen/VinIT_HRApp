from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.services.workspace import build_work_queue_items, build_workflow, summarize_applications

router = APIRouter()

APPLICATION_STATUSES = (
    "NEW", "IN_REVIEW", "SHORTLIST", "REJECTED_SCREENING",
    "INTERVIEW", "REJECTED_INTERVIEW", "OFFERED", "ACCEPTED",
)
MATCHING_STATUSES = ("NOT_ASSESSED", "NEEDS_HR_VERIFICATION", "POSSIBLE_MISMATCH", "MEETS_MANDATORY")

# Service-role/PostgREST requests bypass RLS. Explicitly scope both position and
# application aggregates here: HR sees assigned positions, while an HM only
# sees applications actually shared with them. Revoked roles/shares never count.
_SCOPE_CTE = """
    WITH privileges AS (
        SELECT EXISTS (
            SELECT 1 FROM app_private.user_role_assignments
            WHERE user_id = :user_id AND revoked_at IS NULL
              AND role_code IN ('ADMIN', 'HR_LEAD')
        ) AS global_access
    ), visible_positions AS (
        SELECT p.position_id, p.status
        FROM app_private.positions p, privileges priv
        WHERE (CAST(:position_id AS uuid) IS NULL OR p.position_id = CAST(:position_id AS uuid))
          AND (priv.global_access OR EXISTS (
              SELECT 1 FROM app_private.position_assignments pa
              WHERE pa.position_id = p.position_id AND pa.user_id = :user_id AND pa.revoked_at IS NULL
          ))
    )
"""

_APPLICATIONS_QUERY = _SCOPE_CTE + """
    SELECT a.application_id, a.position_id, a.application_status,
        EXISTS (SELECT 1 FROM app_private.application_documents d
                WHERE d.application_id = a.application_id
                  AND d.file_processing_status IN ('RECEIVED', 'PROCESSING')) AS processing,
        EXISTS (SELECT 1 FROM app_private.application_documents d
                WHERE d.application_id = a.application_id
                  AND (d.file_processing_status IN ('NEEDS_HR_REVIEW', 'ERROR_UNSUPPORTED')
                       OR d.processing_error IS NOT NULL)) AS needs_review,
        EXISTS (SELECT 1 FROM app_private.duplicate_signals ds
                WHERE ds.position_id = a.position_id AND ds.review_status = 'PENDING'
                  AND (ds.application_id_1 = a.application_id OR ds.application_id_2 = a.application_id)) AS duplicate,
        latest.matching_status, latest.evidence_coverage
    FROM app_private.applications a
    JOIN visible_positions p ON p.position_id = a.position_id
    CROSS JOIN privileges priv
    LEFT JOIN LATERAL (
        SELECT ar.matching_status, ar.evidence_coverage
        FROM app_private.assessment_runs ar
        WHERE ar.application_id = a.application_id AND ar.status = 'COMPLETED'
                  AND ar.profile_version_id = (SELECT profile_version_id FROM app_private.profile_versions
                      WHERE application_id = a.application_id AND status = 'COMPLETED' ORDER BY version_number DESC LIMIT 1)
                  AND ar.criteria_version_id = (SELECT c.criteria_version_id FROM app_private.criteria_versions c
                      WHERE c.position_id = a.position_id AND c.status = 'APPROVED'
                        AND c.jd_version_id = (SELECT jd_version_id FROM app_private.jd_versions
                            WHERE position_id = a.position_id ORDER BY version_number DESC LIMIT 1)
                      ORDER BY c.version_number DESC LIMIT 1)
        ORDER BY ar.created_at DESC, ar.assessment_id DESC LIMIT 1
    ) latest ON TRUE
    WHERE priv.global_access OR EXISTS (
        SELECT 1 FROM app_private.position_assignments pa
        WHERE pa.position_id = a.position_id AND pa.user_id = :user_id
          AND pa.position_role IN ('HR_RECRUITER', 'HR_LEAD') AND pa.revoked_at IS NULL
    ) OR EXISTS (
        SELECT 1 FROM app_private.shortlist_shares s
        JOIN app_private.shortlist_share_items si ON si.share_id = s.share_id
        WHERE s.position_id = a.position_id AND s.shared_with = :user_id
          AND s.status = 'ACTIVE' AND si.application_id = a.application_id
          AND EXISTS (SELECT 1 FROM app_private.position_assignments hm
                      WHERE hm.position_id = s.position_id AND hm.user_id = :user_id
                        AND hm.position_role = 'HIRING_MANAGER' AND hm.revoked_at IS NULL)
    )
"""


def build_dashboard(positions: list[Mapping[str, Any]], applications: list[Mapping[str, Any]]) -> dict:
    """Aggregate one row per visible application, with its latest completed assessment."""
    statuses = {key: 0 for key in APPLICATION_STATUSES}
    matching = {key: 0 for key in MATCHING_STATUSES}
    coverages: list[float] = []
    assessed = processing = needs_review = duplicates = 0

    for app in applications:
        status = app.get("application_status")
        if status in statuses:
            statuses[status] += 1
        processing += bool(app.get("processing"))
        needs_review += bool(app.get("needs_review"))
        duplicates += bool(app.get("duplicate"))
        match = app.get("matching_status")
        if match:
            assessed += 1
        matching[match if match in matching else "NOT_ASSESSED"] += 1
        if app.get("evidence_coverage") is not None:
            coverages.append(float(app["evidence_coverage"]))

    total = len(applications)
    return {
        "open_positions": sum(p.get("status") == "OPEN" for p in positions),
        "total_applications": total,
        "applications_by_status": statuses,
        "applications_processing": processing,
        "files_needing_hr_review": needs_review,
        "files_needing_review": needs_review,  # backward-compatible position endpoint
        "files_needing_review_rate": needs_review / total if total else None,
        "duplicate_alerts": duplicates,  # applications with at least one pending signal
        "assessments_completed": assessed,
        "matching_status_counts": matching,
        "average_coverage": sum(coverages) / len(coverages) if coverages else None,
        "coverage_sample_size": len(coverages),
        "coverage_under_threshold": sum(value < 0.7 for value in coverages),
        # No reliable baseline/override events are stored yet. Do not invent a zero.
        "hr_override_rate": None,
        "average_processing_time_seconds": None,
    }


def _load_dashboard(user_id: str, position_id: UUID | None = None) -> dict:
    params = {"user_id": user_id, "position_id": str(position_id) if position_id else None}
    db = SessionLocal()
    try:
        positions = db.execute(text(_SCOPE_CTE + " SELECT * FROM visible_positions"), params).mappings().all()
        if position_id and not positions:
            raise HTTPException(status_code=403, detail="Bạn không có quyền xem thống kê vị trí này")
        applications = db.execute(text(_APPLICATIONS_QUERY), params).mappings().all()
        result = build_dashboard(positions, applications)
        if position_id:
            result["position_id"] = str(position_id)
        return result
    finally:
        db.close()


_WORK_QUEUE_POSITIONS_QUERY = _SCOPE_CTE + """
    SELECT p.position_id, p.position_code, p.title, p.status, d.name AS department_name,
        jd.jd_version_id AS latest_jd_version_id, jd.version_number AS latest_jd_version,
        crit.criteria_version_id AS current_criteria_version_id,
        crit.status AS current_criteria_status, crit.version_number AS current_criteria_version,
        crit.jd_version_id AS current_criteria_jd_version_id,
        EXISTS (SELECT 1 FROM app_private.criteria_versions approved
                WHERE approved.position_id = p.position_id AND approved.status = 'APPROVED'
                  AND approved.jd_version_id = jd.jd_version_id) AS criteria_approved,
        COALESCE((SELECT array_remove(array_agg(pa.position_role), NULL)
                  FROM app_private.position_assignments pa
                  WHERE pa.position_id = p.position_id AND pa.user_id = :user_id
                    AND pa.revoked_at IS NULL), ARRAY[]::text[]) AS position_roles,
        COALESCE((SELECT array_remove(array_agg(ur.role_code), NULL)
                  FROM app_private.user_role_assignments ur
                  WHERE ur.user_id = :user_id AND ur.revoked_at IS NULL), ARRAY[]::text[]) AS system_roles,
        op.operation_id AS active_operation_id, op.status AS active_operation_status,
        op.capability AS active_operation_stage,
        (SELECT COUNT(*) FROM app_private.shortlist_shares s
         WHERE s.position_id = p.position_id AND s.status = 'ACTIVE'
           AND (s.created_by = :user_id OR s.shared_with = :user_id)
           AND NOT EXISTS (SELECT 1 FROM app_private.shortlist_feedback f WHERE f.share_id = s.share_id)
        ) AS shares_without_feedback,
        (SELECT COUNT(DISTINCT si.application_id) FROM app_private.shortlist_shares s
         JOIN app_private.shortlist_share_items si ON si.share_id = s.share_id
         WHERE s.position_id = p.position_id AND s.status = 'ACTIVE') AS shared_shortlisted_any,
        (SELECT COUNT(DISTINCT si.application_id) FROM app_private.shortlist_shares s
         JOIN app_private.shortlist_share_items si ON si.share_id = s.share_id
         WHERE s.position_id = p.position_id AND s.status = 'ACTIVE'
           AND (s.created_by = :user_id OR s.shared_with = :user_id)) AS shared_shortlisted_own
    FROM visible_positions vp
    JOIN app_private.positions p ON p.position_id = vp.position_id
    LEFT JOIN app_private.departments d ON d.department_id = p.department_id
    LEFT JOIN LATERAL (
        SELECT jd_version_id, version_number FROM app_private.jd_versions
        WHERE position_id = p.position_id ORDER BY version_number DESC LIMIT 1
    ) jd ON TRUE
    LEFT JOIN LATERAL (
        SELECT criteria_version_id, status, version_number, jd_version_id FROM app_private.criteria_versions
        WHERE position_id = p.position_id ORDER BY version_number DESC LIMIT 1
    ) crit ON TRUE
    LEFT JOIN LATERAL (
        SELECT operation_id, status, capability FROM app_private.operations
        WHERE position_id = p.position_id AND capability IN ('CV_PROCESSING', 'ASSESSMENT', 'RANKING')
          AND status IN ('PENDING', 'PROCESSING')
        ORDER BY created_at ASC LIMIT 1
    ) op ON TRUE
    ORDER BY p.created_at DESC, p.position_id DESC
"""


def _viewer_flags(row: Mapping[str, Any]) -> tuple[bool, bool]:
    position_roles = {str(role) for role in (row.get("position_roles") or []) if role}
    system_roles = {str(role) for role in (row.get("system_roles") or []) if role}
    is_hr = bool(position_roles & {"HR_RECRUITER", "HR_LEAD"} or system_roles & {"ADMIN", "HR_LEAD"})
    is_hm = "HIRING_MANAGER" in position_roles
    return is_hr, is_hm


def load_position_application_counts(user_id: str, position_id: UUID) -> dict[str, int]:
    """Queue counts for one visible position, scoped exactly like the dashboard."""
    params = {"user_id": user_id, "position_id": str(position_id)}
    db = SessionLocal()
    try:
        positions = db.execute(text(_SCOPE_CTE + " SELECT * FROM visible_positions"), params).mappings().all()
        if not positions:
            raise HTTPException(status_code=403, detail="Bạn không có quyền xem thống kê vị trí này")
        applications = db.execute(text(_APPLICATIONS_QUERY), params).mappings().all()
        return summarize_applications(applications)
    finally:
        db.close()


def _load_work_queue(user_id: str) -> dict:
    params = {"user_id": user_id, "position_id": None}
    db = SessionLocal()
    try:
        positions = db.execute(text(_WORK_QUEUE_POSITIONS_QUERY), params).mappings().all()
        applications = db.execute(text(_APPLICATIONS_QUERY), params).mappings().all()
    finally:
        db.close()

    applications_by_position: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for application in applications:
        applications_by_position[str(application["position_id"])].append(application)

    items: list[dict[str, Any]] = []
    counts_by_position: dict[str, dict[str, int]] = {}
    criteria_pending_positions = 0
    shares_without_feedback = 0
    for row in positions:
        position_id = str(row["position_id"])
        counts = summarize_applications(applications_by_position[position_id])
        is_hr, is_hm = _viewer_flags(row)
        if is_hr:
            counts_by_position[position_id] = counts
        criteria_stale = bool(
            row.get("current_criteria_jd_version_id")
            and row.get("latest_jd_version_id")
            and str(row["current_criteria_jd_version_id"]) != str(row["latest_jd_version_id"])
        )
        active_operation = None
        if row.get("active_operation_id"):
            active_operation = {
                "operation_id": str(row["active_operation_id"]),
                "status": row.get("active_operation_status"),
                "stage": row.get("active_operation_stage"),
            }
        shared_shortlisted = int(row.get("shared_shortlisted_any") or 0) if is_hr else int(row.get("shared_shortlisted_own") or 0)
        workflow = build_workflow(
            position_id=position_id,
            position_status=row.get("status"),
            jd_exists=bool(row.get("latest_jd_version_id")),
            criteria_status=row.get("current_criteria_status"),
            criteria_stale=criteria_stale,
            criteria_approved=bool(row.get("criteria_approved")),
            counts=counts,
            active_operation=active_operation,
            is_hr=is_hr,
            is_hm=is_hm,
            shared_shortlisted=shared_shortlisted,
        )
        position_items = build_work_queue_items(
            position=row,
            counts=counts,
            workflow=workflow,
            criteria_status=row.get("current_criteria_status"),
            criteria_stale=criteria_stale,
            jd_exists=bool(row.get("latest_jd_version_id")),
            is_hr=is_hr,
            is_hm=is_hm,
            share_without_feedback=int(row.get("shares_without_feedback") or 0),
            criteria_approved=bool(row.get("criteria_approved")),
        )
        items.extend(position_items)
        criteria_pending_positions += any(item["type"] in ("CRITERIA_PENDING_HR", "CRITERIA_PENDING_HM", "POSITION_SETUP") for item in position_items)
        shares_without_feedback += int(row.get("shares_without_feedback") or 0)

    priority_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    items.sort(key=lambda item: (priority_rank[item["priority"]], -item["count"], item["position_title"] or ""))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "positions_needing_attention": len({item["position_id"] for item in items}),
            "files_needing_review": sum(counts["file_review"] for counts in counts_by_position.values()),
            "applications_needing_verification": sum(counts["needs_verification"] for counts in counts_by_position.values()),
            "duplicate_alerts": sum(counts["duplicate_pending"] for counts in counts_by_position.values()),
            "criteria_pending_action": criteria_pending_positions,
            "shares_without_feedback": shares_without_feedback,
        },
        "items": items,
    }


@router.get("/work-queue")
async def get_work_queue(current_user: dict = Depends(get_current_user)):
    """Role-scoped work items with deep links into each position workspace."""
    return _load_work_queue(current_user["user_id"])


@router.get("/summary")
async def get_dashboard_summary(current_user: dict = Depends(get_current_user)):
    """Dashboard for the current user's active position assignments and shares."""
    return _load_dashboard(current_user["user_id"])


@router.get("/position/{position_id}")
async def get_position_dashboard(position_id: UUID, current_user: dict = Depends(get_current_user)):
    """Statistics for one visible position, using the same application-level scope."""
    return _load_dashboard(current_user["user_id"], position_id)
