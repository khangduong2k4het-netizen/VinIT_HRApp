"""Pure workflow aggregation for the recruitment workspace UI.

The UI must not infer business state independently in several screens.  These
helpers turn already-scoped database aggregates into one stepper/next-action
contract and one work-queue contract.  They intentionally do not create an
overall assessment "confidence" value: matching score, evidence coverage and
per-criterion evidence strength remain separate concepts.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

COVERAGE_THRESHOLD = 0.7

WORKFLOW_STEPS = ("JD", "CRITERIA", "CV_INTAKE", "HR_REVIEW", "SHORTLIST")
_PRIORITY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _as_bool(value: Any) -> bool:
    return bool(value)


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def summarize_applications(applications: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Summarize scoped application rows using the ranking queue definitions."""
    counts = {
        "total": 0,
        "assessed": 0,
        "processing": 0,
        "file_review": 0,
        "not_assessed": 0,
        "needs_verification": 0,
        "possible_mismatch": 0,
        "meets_mandatory": 0,
        "duplicate_pending": 0,
        "shortlisted": 0,
    }
    for app in applications:
        counts["total"] += 1
        counts["processing"] += _as_bool(app.get("processing"))
        counts["file_review"] += _as_bool(app.get("needs_review"))
        counts["duplicate_pending"] += _as_bool(app.get("duplicate"))
        counts["shortlisted"] += app.get("application_status") == "SHORTLIST"

        matching_status = app.get("matching_status")
        coverage = app.get("evidence_coverage")
        try:
            coverage_value = float(coverage) if coverage is not None else None
        except (TypeError, ValueError):
            coverage_value = None
        needs_verification = matching_status == "NEEDS_HR_VERIFICATION" or (
            coverage_value is not None and coverage_value < COVERAGE_THRESHOLD
        )
        if not matching_status or matching_status == "NOT_ASSESSED":
            counts["not_assessed"] += 1
            continue
        counts["assessed"] += 1
        counts["needs_verification"] += needs_verification
        if matching_status == "POSSIBLE_MISMATCH":
            counts["possible_mismatch"] += 1
        elif matching_status == "MEETS_MANDATORY" and not needs_verification:
            counts["meets_mandatory"] += 1
    return counts


def _target(position_id: str, pathname: str, search: str = "") -> dict[str, str]:
    return {"pathname": pathname, "search": search}


def _position_target(position_id: str, tab: str) -> dict[str, str]:
    return _target(position_id, f"/positions/{position_id}", f"tab={tab}")


def _applicants_target(position_id: str, queue: str | None = None) -> dict[str, str]:
    return _target(
        position_id,
        f"/positions/{position_id}/applicants",
        f"queue={queue}" if queue else "",
    )


# Steps only HR can carry out. A Hiring Manager (or any non-HR viewer) must never be sent to them:
# the target pages are HR-only and would just show permission errors.
HR_ONLY_ACTIONS = frozenset({
    "CREATE_JD", "GENERATE_CRITERIA", "REGENERATE_CRITERIA", "UPLOAD_CV", "VIEW_PROCESSING", "REVIEW_FILES",
    "REVIEW_DUPLICATES", "REVIEW_EVIDENCE", "REVIEW_MISMATCH", "RUN_ASSESSMENT", "SHARE_SHORTLIST", "VIEW_RANKING",
})


def _viewer_next_action(
    position_id: str,
    action: dict[str, Any],
    criteria_approved: bool,
    shared_shortlisted: int,
) -> dict[str, Any]:
    """Replace an HR-only next action with what a non-HR viewer can actually do."""
    code = action["code"]
    if code not in HR_ONLY_ACTIONS and not (code == "VIEW_SHORTLIST" and not shared_shortlisted):
        return action
    if criteria_approved and shared_shortlisted:
        return {"code": "VIEW_SHORTLIST", "blocked_reason_code": None, "target": _target(position_id, "/shortlist")}
    return {
        "code": "WAIT_HR_SHORTLIST" if criteria_approved else "WAIT_HR_REVIEW",
        "blocked_reason_code": "WAITING_FOR_HR",
        "target": _position_target(position_id, "criteria"),
    }


def build_workflow(
    *,
    position_id: str,
    position_status: str | None,
    jd_exists: bool,
    criteria_status: str | None,
    criteria_stale: bool,
    criteria_approved: bool,
    counts: Mapping[str, int],
    active_operation: Mapping[str, Any] | None,
    is_hr: bool,
    is_hm: bool,
    shared_shortlisted: int = 0,
) -> dict[str, Any]:
    """Build the stepper and the single next action for one position."""
    total = _as_int(counts.get("total"))
    processing = _as_int(counts.get("processing"))
    file_review = _as_int(counts.get("file_review"))
    duplicate = _as_int(counts.get("duplicate_pending"))
    needs_verification = _as_int(counts.get("needs_verification"))
    possible_mismatch = _as_int(counts.get("possible_mismatch"))
    not_assessed = _as_int(counts.get("not_assessed"))
    shortlisted = _as_int(counts.get("shortlisted"))
    operation_active = bool(active_operation)

    if position_status != "OPEN":
        next_action = {
            "code": "VIEW_ONLY_CLOSED",
            "blocked_reason_code": "POSITION_NOT_OPEN",
            "target": _position_target(position_id, "criteria"),
        }
        current_step = "CRITERIA"
    elif not jd_exists:
        next_action = {
            "code": "CREATE_JD",
            "blocked_reason_code": None,
            "target": _position_target(position_id, "jd"),
        }
        current_step = "JD"
    elif criteria_stale:
        next_action = {
            "code": "REGENERATE_CRITERIA",
            "blocked_reason_code": "CRITERIA_STALE_FOR_LATEST_JD",
            "target": _position_target(position_id, "criteria"),
        }
        current_step = "CRITERIA"
    elif not criteria_status:
        next_action = {
            "code": "GENERATE_CRITERIA",
            "blocked_reason_code": None,
            "target": _position_target(position_id, "criteria"),
        }
        current_step = "CRITERIA"
    elif criteria_status == "REJECTED":
        next_action = {
            "code": "REGENERATE_CRITERIA",
            "blocked_reason_code": "CRITERIA_REJECTED",
            "target": _position_target(position_id, "criteria"),
        }
        current_step = "CRITERIA"
    elif criteria_status in ("DRAFT", "PENDING_HR_REVIEW"):
        next_action = {
            "code": "REVIEW_CRITERIA_HR" if is_hr else "WAIT_HR_REVIEW",
            "blocked_reason_code": None if is_hr else "WAITING_FOR_HR",
            "target": _position_target(position_id, "criteria"),
        }
        current_step = "CRITERIA"
    elif criteria_status == "PENDING_HM_APPROVAL":
        next_action = {
            "code": "APPROVE_CRITERIA_HM" if is_hm else "WAIT_HM_APPROVAL",
            "blocked_reason_code": None if is_hm else "WAITING_FOR_HM",
            "target": _position_target(position_id, "criteria"),
        }
        current_step = "CRITERIA"
    elif not criteria_approved:
        next_action = {
            "code": "VIEW_CRITERIA",
            "blocked_reason_code": "CRITERIA_NOT_APPROVED",
            "target": _position_target(position_id, "criteria"),
        }
        current_step = "CRITERIA"
    elif total == 0:
        next_action = {
            "code": "UPLOAD_CV",
            "blocked_reason_code": None,
            "target": _target(position_id, f"/positions/{position_id}", "tab=applications&intake=1"),
        }
        current_step = "CV_INTAKE"
    elif operation_active or processing:
        next_action = {
            "code": "VIEW_PROCESSING",
            "blocked_reason_code": None,
            "target": _position_target(position_id, "applications"),
        }
        current_step = "CV_INTAKE" if (active_operation or {}).get("stage") == "CV_PROCESSING" else "HR_REVIEW"
    elif file_review:
        next_action = {
            "code": "REVIEW_FILES",
            "blocked_reason_code": None,
            "target": _applicants_target(position_id, "file_review"),
        }
        current_step = "HR_REVIEW"
    elif duplicate:
        next_action = {
            "code": "REVIEW_DUPLICATES",
            "blocked_reason_code": None,
            "target": _applicants_target(position_id, "duplicate"),
        }
        current_step = "HR_REVIEW"
    elif needs_verification:
        next_action = {
            "code": "REVIEW_EVIDENCE",
            "blocked_reason_code": None,
            "target": _applicants_target(position_id, "needs_verification"),
        }
        current_step = "HR_REVIEW"
    elif possible_mismatch:
        next_action = {
            "code": "REVIEW_MISMATCH",
            "blocked_reason_code": None,
            "target": _applicants_target(position_id, "possible_mismatch"),
        }
        current_step = "HR_REVIEW"
    elif not_assessed:
        next_action = {
            "code": "RUN_ASSESSMENT",
            "blocked_reason_code": None,
            "target": _applicants_target(position_id),
        }
        current_step = "HR_REVIEW"
    elif shortlisted and is_hr and shared_shortlisted < shortlisted:
        next_action = {
            "code": "SHARE_SHORTLIST",
            "blocked_reason_code": None,
            "target": _applicants_target(position_id),
        }
        current_step = "SHORTLIST"
    elif shortlisted:
        next_action = {
            "code": "VIEW_SHORTLIST",
            "blocked_reason_code": None,
            "target": _target(position_id, "/shortlist"),
        }
        current_step = "SHORTLIST"
    else:
        next_action = {
            "code": "VIEW_RANKING",
            "blocked_reason_code": None,
            "target": _applicants_target(position_id),
        }
        current_step = "HR_REVIEW"

    if not is_hr:
        next_action = _viewer_next_action(position_id, next_action, criteria_approved, shared_shortlisted)

    criteria_step_status = "NOT_STARTED"
    if not jd_exists:
        criteria_step_status = "NOT_STARTED"
    elif criteria_stale or criteria_status == "REJECTED":
        criteria_step_status = "BLOCKED"
    elif criteria_approved:
        criteria_step_status = "COMPLETED"
    else:
        criteria_step_status = "CURRENT"

    if not criteria_approved:
        intake_status = "NOT_STARTED"
    elif operation_active or processing:
        intake_status = "CURRENT"
    elif total == 0:
        intake_status = "CURRENT"
    else:
        intake_status = "COMPLETED"

    if not criteria_approved or total == 0:
        review_status = "NOT_STARTED"
    elif file_review or duplicate or needs_verification or possible_mismatch or not_assessed:
        review_status = "CURRENT"
    else:
        review_status = "COMPLETED"

    if shortlisted == 0:
        shortlist_status = "NOT_STARTED"
    elif shared_shortlisted >= shortlisted:
        shortlist_status = "COMPLETED"
    else:
        shortlist_status = "CURRENT"

    statuses = {
        "JD": "COMPLETED" if jd_exists else "CURRENT",
        "CRITERIA": criteria_step_status,
        "CV_INTAKE": intake_status,
        "HR_REVIEW": review_status,
        "SHORTLIST": shortlist_status,
    }
    steps = [{"code": code, "status": statuses[code]} for code in WORKFLOW_STEPS]
    return {"current_step": current_step, "steps": steps, "next_action": next_action}


def build_work_queue_items(
    *,
    position: Mapping[str, Any],
    counts: Mapping[str, int],
    workflow: Mapping[str, Any],
    criteria_status: str | None,
    criteria_stale: bool,
    jd_exists: bool,
    is_hr: bool,
    is_hm: bool,
    share_without_feedback: int = 0,
    criteria_approved: bool = False,
) -> list[dict[str, Any]]:
    """Build role-appropriate work items for one visible position."""
    position_id = str(position["position_id"])
    base = {
        "position_id": position_id,
        "position_code": position.get("position_code"),
        "position_title": position.get("title"),
        "position_status": position.get("status"),
    }
    items: list[dict[str, Any]] = []

    def add(item_type: str, priority: str, count: int, target: Mapping[str, str]) -> None:
        if count <= 0:
            return
        items.append({
            **base,
            "item_id": f"{item_type}:{position_id}",
            "type": item_type,
            "priority": priority,
            "count": int(count),
            "target": dict(target),
        })

    if position.get("status") == "OPEN":
        if criteria_status in ("DRAFT", "PENDING_HR_REVIEW") and is_hr:
            add("CRITERIA_PENDING_HR", "HIGH", 1, _position_target(position_id, "criteria"))
        elif criteria_status == "PENDING_HM_APPROVAL" and (is_hr or is_hm):
            add("CRITERIA_PENDING_HM", "HIGH" if is_hm else "MEDIUM", 1, _position_target(position_id, "criteria"))
        elif not jd_exists or not criteria_status or criteria_stale or criteria_status == "REJECTED":
            if is_hr:
                add("POSITION_SETUP", "HIGH", 1, workflow["next_action"]["target"])

    can_review_applications = bool(
        jd_exists and not criteria_stale and criteria_status == "APPROVED" and criteria_approved
    )
    if is_hr and can_review_applications:
        add("FILE_REVIEW", "HIGH", _as_int(counts.get("file_review")), _applicants_target(position_id, "file_review"))
        add("NEEDS_VERIFICATION", "HIGH", _as_int(counts.get("needs_verification")), _applicants_target(position_id, "needs_verification"))
        add("DUPLICATE_PENDING", "MEDIUM", _as_int(counts.get("duplicate_pending")), _applicants_target(position_id, "duplicate"))
        add("POSSIBLE_MISMATCH", "MEDIUM", _as_int(counts.get("possible_mismatch")), _applicants_target(position_id, "possible_mismatch"))
        add("PROCESSING", "MEDIUM", _as_int(counts.get("processing")), _position_target(position_id, "applications"))
        add("NOT_ASSESSED", "MEDIUM", _as_int(counts.get("not_assessed")), _applicants_target(position_id, "not_assessed"))

    if is_hr or is_hm:
        add("SHARE_WITHOUT_FEEDBACK", "LOW", share_without_feedback, _target(position_id, "/shortlist"))

    items.sort(key=lambda item: (_PRIORITY_RANK[item["priority"]], -item["count"], item["position_title"] or ""))
    return items
