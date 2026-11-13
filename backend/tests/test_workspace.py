from app.services.workspace import build_work_queue_items, build_workflow, summarize_applications


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
    assert workflow["next_action"]["target"]["search"] == "queue=file_review"
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


def _hm_workflow(criteria_status="APPROVED", shared_shortlisted=0, **count_overrides):
    approved = criteria_status == "APPROVED"
    return build_workflow(
        position_id="pos-1",
        position_status="OPEN",
        jd_exists=True,
        criteria_status=criteria_status,
        criteria_stale=False,
        criteria_approved=approved,
        counts=_counts(**count_overrides),
        active_operation=None,
        is_hr=False,
        is_hm=True,
        shared_shortlisted=shared_shortlisted,
    )


def test_hm_is_never_sent_to_hr_only_pages():
    """HM must not get 'open candidate list' / 'upload CV' etc.: those pages are HR-only and return 403."""
    for counts in ({}, {"total": 3}, {"total": 3, "file_review": 1}, {"total": 3, "not_assessed": 2},
                   {"total": 3, "shortlisted": 1}):
        action = _hm_workflow(**counts)["next_action"]
        assert action["code"] == "WAIT_HR_SHORTLIST", counts
        assert action["blocked_reason_code"] == "WAITING_FOR_HR"
        assert action["target"] == {"pathname": "/positions/pos-1", "search": "tab=criteria"}


def test_hm_goes_to_shortlist_once_hr_shared_with_them():
    action = _hm_workflow(shared_shortlisted=1, total=3, shortlisted=1)["next_action"]
    assert action["code"] == "VIEW_SHORTLIST"
    assert action["target"]["pathname"] == "/shortlist"


def test_hm_waits_for_hr_before_criteria_exist():
    assert _hm_workflow(criteria_status=None)["next_action"]["code"] == "WAIT_HR_REVIEW"


def test_hm_keeps_own_approval_action():
    assert _hm_workflow(criteria_status="PENDING_HM_APPROVAL")["next_action"]["code"] == "APPROVE_CRITERIA_HM"
