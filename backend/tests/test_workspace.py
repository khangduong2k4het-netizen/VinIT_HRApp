import re

from app.services.workspace import build_work_queue_items, build_workflow, summarize_applications

# The ranking page only recognises these queue codes (frontend/src/lib/applicantReview.ts).
RANKING_QUEUE_CODES = {
    "ALL", "SHORTLIST", "FILE_REVIEW", "DUPLICATE",
    "NEEDS_VERIFICATION", "POSSIBLE_MISMATCH", "NOT_ASSESSED", "MEETS_MANDATORY",
}


def _counts(**overrides):
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
    counts.update(overrides)
    return counts


def test_summarize_applications_separates_review_queues():
    counts = summarize_applications([
        {"application_status": "NEW", "processing": True, "needs_review": False, "duplicate": False,
         "matching_status": None, "evidence_coverage": None},
        {"application_status": "IN_REVIEW", "processing": False, "needs_review": True, "duplicate": True,
         "matching_status": "MEETS_MANDATORY", "evidence_coverage": 0.5},
        {"application_status": "SHORTLIST", "processing": False, "needs_review": False, "duplicate": False,
         "matching_status": "POSSIBLE_MISMATCH", "evidence_coverage": 0.9},
        {"application_status": "IN_REVIEW", "processing": False, "needs_review": False, "duplicate": False,
         "matching_status": "MEETS_MANDATORY", "evidence_coverage": 0.9},
    ])

    assert counts == {
        "total": 4,
        "assessed": 3,
        "processing": 1,
        "file_review": 1,
        "not_assessed": 1,
        "needs_verification": 1,
        "possible_mismatch": 1,
        "meets_mandatory": 1,
        "duplicate_pending": 1,
        "shortlisted": 1,
    }


def test_workflow_prioritizes_file_review_before_matching_queues():
    workflow = build_workflow(
        position_id="pos-1",
        position_status="OPEN",
        jd_exists=True,
        criteria_status="APPROVED",
        criteria_stale=False,
        criteria_approved=True,
        counts=_counts(total=8, file_review=2, duplicate_pending=1, needs_verification=3, not_assessed=2),
        active_operation=None,
        is_hr=True,
        is_hm=False,
    )

    assert workflow["current_step"] == "HR_REVIEW"
    assert workflow["next_action"]["code"] == "REVIEW_FILES"
    assert workflow["next_action"]["target"]["search"] == "queue=FILE_REVIEW"
    assert workflow["steps"][2]["status"] == "COMPLETED"


def test_workflow_waits_for_hm_instead_of_offering_hr_the_hm_action():
    workflow = build_workflow(
        position_id="pos-1",
        position_status="OPEN",
        jd_exists=True,
        criteria_status="PENDING_HM_APPROVAL",
        criteria_stale=False,
        criteria_approved=False,
        counts=_counts(),
        active_operation=None,
        is_hr=True,
        is_hm=False,
    )

    assert workflow["next_action"] == {
        "code": "WAIT_HM_APPROVAL",
        "blocked_reason_code": "WAITING_FOR_HM",
        "target": {"pathname": "/positions/pos-1", "search": "tab=criteria"},
    }


def test_work_queue_does_not_assign_hr_review_work_to_hm():
    position = {"position_id": "pos-1", "position_code": "REQ-1", "title": "Engineer", "status": "OPEN"}
    counts = _counts(total=4, file_review=2, needs_verification=1)
    workflow = build_workflow(
        position_id="pos-1",
        position_status="OPEN",
        jd_exists=True,
        criteria_status="APPROVED",
        criteria_stale=False,
        criteria_approved=True,
        counts=counts,
        active_operation=None,
        is_hr=False,
        is_hm=True,
    )

    items = build_work_queue_items(
        position=position,
        counts=counts,
        workflow=workflow,
        criteria_status="APPROVED",
        criteria_stale=False,
        jd_exists=True,
        is_hr=False,
        is_hm=True,
        share_without_feedback=1,
    )

    assert [item["type"] for item in items] == ["SHARE_WITHOUT_FEEDBACK"]


def test_work_queue_waits_for_approved_criteria_before_applicant_review_items():
    position = {"position_id": "pos-1", "position_code": "REQ-1", "title": "Engineer", "status": "OPEN"}
    counts = _counts(total=3, not_assessed=3)
    workflow = build_workflow(
        position_id="pos-1",
        position_status="OPEN",
        jd_exists=True,
        criteria_status="DRAFT",
        criteria_stale=False,
        criteria_approved=False,
        counts=counts,
        active_operation=None,
        is_hr=True,
        is_hm=False,
    )

    items = build_work_queue_items(
        position=position,
        counts=counts,
        workflow=workflow,
        criteria_status="DRAFT",
        criteria_stale=False,
        jd_exists=True,
        is_hr=True,
        is_hm=False,
        criteria_approved=False,
    )

    assert [item["type"] for item in items] == ["CRITERIA_PENDING_HR"]


def _queue_from_search(search: str) -> str:
    match = re.search(r"(?:^|&)queue=([^&]*)", search or "")
    return match.group(1) if match else ""


def test_every_work_queue_link_targets_a_code_the_ranking_page_understands():
    """A deep link with an unknown queue silently opens the unfiltered list."""
    items = build_work_queue_items(
        position={"position_id": "pos-1", "position_code": "REQ-1", "title": "Backend", "status": "OPEN"},
        counts=_counts(total=9, file_review=2, duplicate_pending=1, needs_verification=3,
                      possible_mismatch=1, not_assessed=2),
        workflow={"next_action": {"code": "REVIEW_FILES", "blocked_reason_code": None,
                                 "target": {"pathname": "/positions/pos-1", "search": "tab=applications"}}},
        criteria_status="APPROVED",
        criteria_stale=False,
        jd_exists=True,
        is_hr=True,
        is_hm=False,
        share_without_feedback=1,
        criteria_approved=True,
    )

    targets = [item["target"] for item in items if item["target"]["pathname"].endswith("/applicants")]
    assert targets, "expected at least one applicant queue link"
    for target in targets:
        code = _queue_from_search(target["search"])
        assert code in RANKING_QUEUE_CODES, f"{target['search']!r} would not filter the ranking page"


def test_position_workspace_links_stay_inside_the_position():
    """Work items must not point at another position's ranking page."""
    items = build_work_queue_items(
        position={"position_id": "pos-9", "position_code": "REQ-9", "title": "Data", "status": "OPEN"},
        counts=_counts(total=1, needs_verification=1),
        workflow={"next_action": {"code": "REVIEW_FILES", "blocked_reason_code": None,
                                 "target": {"pathname": "/positions/pos-9", "search": "tab=applications"}}},
        criteria_status="APPROVED",
        criteria_stale=False,
        jd_exists=True,
        is_hr=True,
        is_hm=False,
        criteria_approved=True,
    )

    for item in items:
        assert "/positions/pos-9" in item["target"]["pathname"]
