"""Pure workflow aggregation for the recruitment workspace UI.

The UI must not infer business state independently in several screens.  These
helpers turn already-scoped database aggregates into one stepper/next-action
contract and one work-queue contract.  They intentionally do not create an
overall assessment "confidence" value: matching score, evidence coverage and
per-criterion evidence strength remain separate concepts.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

COVERAGE_THRESHOLD = 0.7

# Defaults only. HR can change both through the Settings screen
# (app_private.app_settings); these values are what the app uses when a stored
# setting is missing or out of range.
DEADLINE_SOON_DAYS = 7
WAITING_ATTENTION_DAYS = 7

# The one place that decides which applications a *work* queue may count.
# Applications outside the screening stage (rejected, interviewed, offered) are
# still part of the position history and still appear in the status breakdown,
# but they are not "work left to do": counting them made the dashboard promise
# more items than the ranking page could list. Keep in step with
# frontend/src/lib/applicantReview.ts and the ranking endpoint
# (backend/app/api/assessments.py).
SCREENING_APPLICATION_STATUSES = ("NEW", "IN_REVIEW", "SHORTLIST")

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
    """Summarize scoped application rows using the ranking queue definitions.

    Only screening-stage rows are counted: these figures drive the work queue and
    its deep links, so they must describe applications the ranking page can
    actually show. Rows without ``application_status`` are kept (unit fixtures
    omit it) rather than silently dropped.
    """
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
        # Applications a reviewer has finished checking: every criterion the
        # machine flagged now carries a review. Kept visible so the dashboard can
        # say "12 need you, 3 you already checked" instead of silently shrinking.
        "verification_complete": 0,
    }
    for app in applications:
        status = app.get("application_status")
        if status and status not in SCREENING_APPLICATION_STATUSES:
            continue
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
        # A row that was never assessed has no score to verify: it belongs to the
        # "not assessed" queue only. Counting it here as well made the same
        # application appear in two queues and inflated the dashboard figure the
        # reviewer had to reconcile by hand.
        if not matching_status or matching_status == "NOT_ASSESSED":
            counts["not_assessed"] += 1
            continue
        # A criterion the machine flagged is only still "waiting for HR" while no
        # reviewer has looked at it. When every flagged criterion of this
        # assessment has a review, the application belongs to "assessed and
        # confirmed" instead — that is what lets the queue close without anyone
        # being pushed into a hiring decision just to clear a to-do list.
        # `pending_reviews` is 0 when the assessment had nothing flagged at all,
        # so this is a no-op for those rows.
        pending_reviews = _as_int(app.get("pending_reviews"))
        reviewed_criteria = _as_int(app.get("reviewed_criteria"))
        needs_verification = (matching_status == "NEEDS_HR_VERIFICATION") or (
            coverage_value is not None and coverage_value < COVERAGE_THRESHOLD
        )
        if needs_verification and pending_reviews == 0 and reviewed_criteria > 0:
            needs_verification = False
            counts["verification_complete"] = counts.get("verification_complete", 0) + 1
        counts["assessed"] += 1
        counts["needs_verification"] += needs_verification
        if matching_status == "POSSIBLE_MISMATCH":
            counts["possible_mismatch"] += 1
        elif matching_status == "MEETS_MANDATORY" and not needs_verification:
            counts["meets_mandatory"] += 1
    return counts


def summarize_waiting(
    applications: Iterable[Mapping[str, Any]],
    now: datetime | None = None,
    *,
    threshold_days: int = WAITING_ATTENTION_DAYS,
) -> dict[str, int | None]:
    """How long screening work has been waiting.

    Kept apart from ``summarize_applications`` on purpose: that function returns
    plain counts, whereas these can legitimately be unknown. Age is descriptive
    only -- it never changes ``rank_number`` or the order of a ranking run.

    ``threshold_days`` comes from Settings; it decides what counts as "waiting too
    long", never the order things are shown in.
    """
    waiting_days: list[int] = []
    for app in applications:
        status = app.get("application_status")
        if status and status not in SCREENING_APPLICATION_STATUSES:
            continue
        age = _age_days(app.get("created_at"), now)
        if age is not None:
            waiting_days.append(age)
    ordered = sorted(waiting_days)
    return {
        # Key keeps its original name for clients already reading it; the threshold
        # it compares against is the configurable one.
        "waiting_over_7d": sum(age > threshold_days for age in waiting_days),
        # None, not 0: a position with no timestamped files has no "oldest" file.
        "oldest_waiting_days": ordered[-1] if ordered else None,
        "median_waiting_days": ordered[len(ordered) // 2] if ordered else None,
    }


def _age_days(created_at: Any, now: datetime | None = None) -> int | None:
    if not created_at:
        return None
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(created_at, datetime):
        return None
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    elapsed = (reference - created_at).days
    return elapsed if elapsed >= 0 else None


def _target(position_id: str, pathname: str, search: str = "") -> dict[str, str]:
    return {"pathname": pathname, "search": search}


def _position_target(position_id: str, tab: str) -> dict[str, str]:
    return _target(position_id, f"/positions/{position_id}", f"tab={tab}")


def _iso_datetime(value: Any) -> str | None:
    """Serialise a deadline for the client, defaulting naive values to UTC."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return None


def _deadline_moment(deadline_at: Any) -> datetime | None:
    """Parse a deadline into an aware datetime, or None when there is not one."""
    if not deadline_at:
        return None
    if isinstance(deadline_at, str):
        try:
            deadline_at = datetime.fromisoformat(deadline_at.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(deadline_at, datetime):
        return None
    if deadline_at.tzinfo is None:
        deadline_at = deadline_at.replace(tzinfo=timezone.utc)
    return deadline_at


def _reference_now(now: datetime | None) -> datetime:
    reference = now or datetime.now(timezone.utc)
    return reference if reference.tzinfo else reference.replace(tzinfo=timezone.utc)


def deadline_is_passed(deadline_at: Any, now: datetime | None = None) -> bool:
    """Whether the intake gate has closed; used where the answer must be exact."""
    moment = _deadline_moment(deadline_at)
    return moment is not None and moment <= _reference_now(now)


def deadline_days_left(deadline_at: Any, now: datetime | None = None) -> int | None:
    """Whole days until the intake deadline; negative once it has passed.

    Returns None when there is no deadline (no deadline is not "0 days left").
    0 means "today": either still open later today, or it closed earlier today.
    Use ``deadline_is_passed`` when an exact answer matters.
    """
    moment = _deadline_moment(deadline_at)
    if moment is None:
        return None
    remaining = moment - _reference_now(now)
    # timedelta.days floors, so -2 days minus a second would report -3. Count the
    # elapsed whole days instead and put the sign back.
    if remaining.total_seconds() >= 0:
        return remaining.days
    return -((-remaining).days)


def _applicants_target(position_id: str, queue: str | None = None) -> dict[str, str]:
    # Queue codes travel in the URL exactly as the ranking page names them
    # (UPPER_SNAKE). They used to be emitted lower-case here, which the page did
    # not recognise, so every "review the files" deep link opened an unfiltered
    # list. Keep the two sides in step; tests/test_workspace.py checks the codes.
    return _target(
        position_id,
        f"/positions/{position_id}/applicants",
        f"queue={queue.upper()}" if queue else "",
    )


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
    deadline_at: datetime | str | None = None,
    now: datetime | None = None,
    deadline_soon_days: int = DEADLINE_SOON_DAYS,
) -> list[dict[str, Any]]:
    """Build role-appropriate work items for one visible position.

    ``deadline_at`` is the position's application deadline. It is reported, never
    used to change what the position is: a passed deadline means intake is closed
    (see careers_intake.py), so HR deserves an item instead of a silent wall.
    """
    position_id = str(position["position_id"])
    base = {
        "position_id": position_id,
        "position_code": position.get("position_code"),
        "position_title": position.get("title"),
        "position_status": position.get("status"),
    }
    items: list[dict[str, Any]] = []

    def add(
        item_type: str,
        priority: str,
        count: int,
        target: Mapping[str, str],
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        if count <= 0:
            return
        items.append({
            **base,
            "item_id": f"{item_type}:{position_id}",
            "type": item_type,
            "priority": priority,
            "count": int(count),
            "target": dict(target),
            **(extra or {}),
        })

    if position.get("status") == "OPEN":
        if criteria_status in ("DRAFT", "PENDING_HR_REVIEW") and is_hr:
            add("CRITERIA_PENDING_HR", "HIGH", 1, _position_target(position_id, "criteria"))
        elif criteria_status == "PENDING_HM_APPROVAL" and (is_hr or is_hm):
            add("CRITERIA_PENDING_HM", "HIGH" if is_hm else "MEDIUM", 1, _position_target(position_id, "criteria"))
        elif not jd_exists or not criteria_status or criteria_stale or criteria_status == "REJECTED":
            if is_hr:
                add("POSITION_SETUP", "HIGH", 1, workflow["next_action"]["target"])

    days_left = deadline_days_left(deadline_at, now)
    # Gated on approved criteria, not merely on status: a position still in setup
    # already has POSITION_SETUP, and a second row would double-count one piece of
    # work. HR is the role that owns the intake gate, so only HR sees these.
    if is_hr and criteria_approved and position.get("status") == "OPEN" and days_left is not None:
        deadline_extra = {
            "due_at": _iso_datetime(deadline_at),
            "days_left": days_left,
        }
        # Closed is decided by the clock, not by the rounded day count: a deadline
        # that passed this morning is already closed even though it is "today".
        if deadline_is_passed(deadline_at, now):
            add("POSITION_DEADLINE_PASSED", "HIGH", 1, _position_target(position_id, "overview"), deadline_extra)
        elif days_left <= deadline_soon_days:
            add("POSITION_DEADLINE_SOON", "MEDIUM", 1, _position_target(position_id, "overview"), deadline_extra)

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
