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
        "verification_complete": 0,
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
        "verification_complete": 0,
    }


def test_a_fully_reviewed_application_leaves_the_verification_queue():
    """The queue is a to-do list, not a permanent label.

    Until HR could record a review, the only way an application left "needs
    verification" was a recruiting decision (reject, or move to interview), because
    SHORTLIST is still a screening status. That pushed HR into making a hiring call
    to clear a technical queue. Once every flagged criterion carries a review the
    row belongs to verification_complete instead — with its application_status
    untouched.
    """
    base = {
        "application_status": "IN_REVIEW",
        "processing": False,
        "needs_review": False,
        "duplicate": False,
        "matching_status": "NEEDS_HR_VERIFICATION",
        "evidence_coverage": 0.9,
    }
    pending = summarize_applications([{**base, "pending_reviews": 2, "reviewed_criteria": 1}])
    assert pending["needs_verification"] == 1
    assert pending["verification_complete"] == 0

    done = summarize_applications([{**base, "pending_reviews": 0, "reviewed_criteria": 3}])
    assert done["needs_verification"] == 0
    assert done["verification_complete"] == 1
    # Still counted as work that exists, never silently dropped from "assessed".
    assert done["assessed"] == 1
    assert done["total"] == 1


def test_a_flagged_row_with_no_reviews_at_all_still_needs_verification():
    """A flagged criterion nobody has looked at must not count as complete."""
    counts = summarize_applications([{
        "application_status": "NEW",
        "processing": False,
        "needs_review": False,
        "duplicate": False,
        "matching_status": "NEEDS_HR_VERIFICATION",
        "evidence_coverage": 0.9,
        "pending_reviews": 1,
        "reviewed_criteria": 0,
    }])
    assert counts["needs_verification"] == 1
    assert counts["verification_complete"] == 0


def test_low_coverage_without_flagged_criteria_is_never_marked_complete():
    """Low coverage alone is not something a reviewer can sign off.

    The engine can flag no criterion at all and still fall under the coverage
    threshold. Treating "nothing pending" as "reviewed" would then quietly hide
    rows nobody has checked.
    """
    counts = summarize_applications([{
        "application_status": "IN_REVIEW",
        "processing": False,
        "needs_review": False,
        "duplicate": False,
        "matching_status": "MEETS_MANDATORY",
        "evidence_coverage": 0.4,
        "pending_reviews": 0,
        "reviewed_criteria": 0,
    }])
    assert counts["needs_verification"] == 1
    assert counts["verification_complete"] == 0


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


def test_queue_counts_ignore_applications_outside_screening():
    """Work queues must describe work left to do, not position history.

    An application that was rejected, interviewed or already offered is still
    counted in the status breakdown (a different query), but it must never
    inflate a queue the dashboard links to: the ranking page cannot show it, so
    the number would open a shorter list than it promised.
    """
    rows = [
        {"application_status": "IN_REVIEW", "matching_status": "NEEDS_HR_VERIFICATION",
         "evidence_coverage": 0.4, "needs_review": True, "duplicate": False},
        {"application_status": "SHORTLIST", "matching_status": "MEETS_MANDATORY",
         "evidence_coverage": 0.9, "needs_review": False, "duplicate": False},
        # Outside screening: same kind of problems, must not be counted.
        {"application_status": "REJECTED_SCREENING", "matching_status": "NEEDS_HR_VERIFICATION",
         "evidence_coverage": 0.3, "needs_review": True, "duplicate": True},
        {"application_status": "INTERVIEW", "matching_status": "NEEDS_HR_VERIFICATION",
         "evidence_coverage": 0.5, "needs_review": True, "duplicate": True},
        {"application_status": "OFFERED", "matching_status": "NOT_ASSESSED",
         "evidence_coverage": 0.0, "needs_review": False, "duplicate": False},
    ]

    counts = summarize_applications(rows)

    assert counts["total"] == 2
    assert counts["needs_verification"] == 1
    assert counts["file_review"] == 1
    assert counts["duplicate_pending"] == 0
    assert counts["not_assessed"] == 0


def test_unassessed_application_is_not_also_needing_verification():
    """One application, one queue: no score means nothing to verify yet."""
    counts = summarize_applications([
        {"application_status": "NEW", "matching_status": "NOT_ASSESSED",
         "evidence_coverage": 0.0, "needs_review": False, "duplicate": False},
        {"application_status": "IN_REVIEW", "matching_status": "NEEDS_HR_VERIFICATION",
         "evidence_coverage": 0.0, "needs_review": False, "duplicate": False},
    ])

    assert counts["not_assessed"] == 1
    assert counts["needs_verification"] == 1, "chỉ hồ sơ đã đánh giá mới được tính"
    assert counts["total"] == 2


def test_queue_counts_match_the_ranking_page_dataset():
    """Same fixture, two definitions: workspace counts and the FE chip must agree.

    The ranking endpoint returns only screening applications and, since the same
    change, only marks assessed rows as needing verification. This test pins the
    backend half of that contract; frontend/tests/workspace-ui.test.cjs pins the
    other half on an identical fixture.
    """
    rows = [
        {"application_status": "IN_REVIEW", "matching_status": "NEEDS_HR_VERIFICATION", "evidence_coverage": 0.55},
        {"application_status": "SHORTLIST", "matching_status": "MEETS_MANDATORY", "evidence_coverage": 0.92},
        {"application_status": "IN_REVIEW", "matching_status": "NEEDS_HR_VERIFICATION", "evidence_coverage": 0.61},
        {"application_status": "IN_REVIEW", "matching_status": "POSSIBLE_MISMATCH", "evidence_coverage": 0.78},
        {"application_status": "IN_REVIEW", "matching_status": "MEETS_MANDATORY", "evidence_coverage": 0.49},
        {"application_status": "NEW", "matching_status": "NOT_ASSESSED", "evidence_coverage": 0.0},
        {"application_status": "REJECTED_SCREENING", "matching_status": "NEEDS_HR_VERIFICATION", "evidence_coverage": 0.3},
    ]

    counts = summarize_applications(rows)

    assert counts["total"] == 6
    assert counts["needs_verification"] == 3
    assert counts["not_assessed"] == 1
    assert counts["possible_mismatch"] == 1


# --- R5 mức B: hạn ứng tuyển và tuổi hồ sơ -------------------------------------
# Giờ được bơm cố định để test không phụ thuộc ngày chạy.
from datetime import datetime, timedelta, timezone  # noqa: E402

from app.services.workspace import (  # noqa: E402
    DEADLINE_SOON_DAYS,
    WAITING_ATTENTION_DAYS,
    deadline_days_left,
    deadline_is_passed,
    summarize_waiting,
)

NOW = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)


def _queue(deadline_at, *, status="OPEN", approved=True, criteria_status="APPROVED", now=NOW):
    counts = _counts(total=1, needs_verification=1)
    workflow = build_workflow(
        position_id="pos-1", position_status=status, jd_exists=True,
        criteria_status=criteria_status, criteria_stale=False, criteria_approved=approved,
        counts=counts, active_operation=None, is_hr=True, is_hm=False,
    )
    return build_work_queue_items(
        position={"position_id": "pos-1", "position_code": "REQ-1", "title": "Engineer",
                  "status": status, "position_roles": ["HR_RECRUITER"], "system_roles": []},
        counts=counts, workflow=workflow, criteria_status=criteria_status,
        criteria_stale=False, jd_exists=True, is_hr=True, is_hm=False,
        criteria_approved=approved, deadline_at=deadline_at, now=now,
    )


def _deadline_items(items):
    return [i for i in items if i["type"].startswith("POSITION_DEADLINE_")]


def test_passed_deadline_becomes_a_high_priority_item():
    passed = _deadline_items(_queue(NOW - timedelta(days=2)))

    assert [i["type"] for i in passed] == ["POSITION_DEADLINE_PASSED"]
    assert passed[0]["priority"] == "HIGH"
    assert passed[0]["days_left"] == -2
    assert passed[0]["due_at"].startswith("2026-11-17")
    assert passed[0]["target"] == {"pathname": "/positions/pos-1", "search": "tab=overview"}


def test_deadline_within_a_week_is_medium_and_the_boundary_is_exact():
    soon = _deadline_items(_queue(NOW + timedelta(days=3)))
    assert [i["type"] for i in soon] == ["POSITION_DEADLINE_SOON"]
    assert soon[0]["priority"] == "MEDIUM"

    assert _deadline_items(_queue(NOW + timedelta(days=DEADLINE_SOON_DAYS)))
    assert not _deadline_items(_queue(NOW + timedelta(days=DEADLINE_SOON_DAYS + 1)))


def test_no_deadline_means_no_item_and_no_invented_zero():
    """Không có hạn thì không có việc, và cũng không được coi là "còn 0 ngày"."""
    assert deadline_days_left(None) is None
    assert deadline_days_left("") is None
    assert deadline_days_left("không phải ngày") is None
    assert _deadline_items(_queue(None)) == []


def test_deadline_item_waits_until_criteria_are_approved():
    """Vị trí đang chờ duyệt tiêu chí đã có dòng riêng; không thêm dòng thứ hai."""
    items = _queue(NOW + timedelta(days=1), approved=False, criteria_status="PENDING_HM_APPROVAL")

    assert [i["type"] for i in items] == ["CRITERIA_PENDING_HM"], "một vị trí, một dòng việc"


def test_days_left_never_drifts_by_one_on_past_deadlines():
    """CI từng bắt lỗi này: timedelta.days làm tròn xuống nên -2 thành -3."""
    assert deadline_days_left(NOW - timedelta(days=2), NOW) == -2
    assert deadline_days_left(NOW - timedelta(days=2, seconds=1), NOW) == -2
    assert deadline_days_left(NOW - timedelta(days=2, hours=23), NOW) == -2
    assert deadline_days_left(NOW + timedelta(days=2), NOW) == 2
    assert deadline_days_left(NOW + timedelta(days=2, hours=23), NOW) == 2


def test_a_deadline_that_passed_earlier_today_is_already_closed():
    """0 ngày là "hôm nay": còn mở hay đã đóng phải do giờ quyết định."""
    earlier_today = NOW - timedelta(hours=3)
    later_today = NOW + timedelta(hours=3)

    assert deadline_days_left(earlier_today, NOW) == 0
    assert deadline_days_left(later_today, NOW) == 0
    assert deadline_is_passed(earlier_today, NOW) is True
    assert deadline_is_passed(later_today, NOW) is False
    # Sáng nay đã đóng thì phải là "quá hạn", không phải "sắp hết hạn".
    assert [i["type"] for i in _deadline_items(_queue(earlier_today))] == ["POSITION_DEADLINE_PASSED"]
    assert [i["type"] for i in _deadline_items(_queue(later_today))] == ["POSITION_DEADLINE_SOON"]


def test_closed_position_gets_no_deadline_item():
    assert _deadline_items(_queue(NOW - timedelta(days=2), status="CLOSED")) == []


def test_waiting_age_counts_only_screening_rows_and_never_invents_zero():
    waiting = summarize_waiting([
        {"application_status": "IN_REVIEW", "created_at": NOW - timedelta(days=WAITING_ATTENTION_DAYS + 5)},
        {"application_status": "IN_REVIEW", "created_at": NOW - timedelta(days=2)},
        {"application_status": "NEW", "created_at": NOW - timedelta(days=30)},
        # Ngoài sàng lọc: có tuổi nhưng không phải việc đang chờ xử lý.
        {"application_status": "REJECTED_SCREENING", "created_at": NOW - timedelta(days=90)},
        # Không có mốc thời gian: im lặng, không bịa 0.
        {"application_status": "IN_REVIEW", "created_at": None},
    ], now=NOW)

    # Tuổi trong sàng lọc: 12, 2, 30 (hồ sơ bị loại và hồ sơ không có mốc bị bỏ qua).
    # Quá ngưỡng: 12 và 30 → 2. Trung vị của [2, 12, 30] là 12. Lâu nhất 30.
    assert waiting == {"waiting_over_7d": 2, "oldest_waiting_days": 30, "median_waiting_days": 12}


def test_waiting_age_is_none_when_nothing_has_a_timestamp():
    waiting = summarize_waiting([{"application_status": "IN_REVIEW"}], now=NOW)

    assert waiting["oldest_waiting_days"] is None
    assert waiting["median_waiting_days"] is None
    assert waiting["waiting_over_7d"] == 0


# --- KPI "Vị trí đang mở": quá hạn thì không còn là đang mở ---------------------
from app.api.dashboard import build_dashboard  # noqa: E402  (import sau các test ở trên là chủ đích)


def _kpi(positions):
    return build_dashboard(positions, [], now=NOW)


def _pos(position_id, status="OPEN", deadline_at=None):
    return {"position_id": position_id, "position_code": position_id.upper(),
            "title": position_id, "status": status, "application_deadline_at": deadline_at}


def test_open_positions_kpi_hides_positions_whose_deadline_passed():
    data = _kpi([
        _pos("a", deadline_at=NOW + timedelta(days=10)),
        _pos("b", deadline_at=NOW - timedelta(days=1)),
        _pos("c", deadline_at=None),
        _pos("d", status="PAUSED", deadline_at=None),
    ])

    # "c" không có hạn nên vẫn đang mở; "d" bị tạm dừng nên không tính.
    assert data["open_positions"] == 2
    # Vị trí quá hạn không biến mất khỏi số liệu: nó được báo riêng để giải thích
    # vì sao 3 vị trí OPEN trên danh sách chỉ còn 2 trong KPI.
    assert data["open_positions_deadline_passed"] == 1


def test_open_positions_kpi_counts_the_deadline_day_itself():
    # Đến đúng thời điểm hạn thì cổng đóng (careers_intake.py dùng deadline <= now).
    assert _kpi([_pos("a", deadline_at=NOW)])["open_positions"] == 0
    # Còn vài giờ trong ngày hạn thì vẫn đang mở, và vẫn là "sắp hết hạn".
    assert _kpi([_pos("a", deadline_at=NOW + timedelta(hours=1))])["open_positions"] == 1
    assert _kpi([_pos("a", deadline_at=NOW - timedelta(hours=1))])["open_positions"] == 0


def test_dashboard_kpi_payload_stays_small():
    """Tổng hợp việc cần làm không nằm trong /dashboard: nó thuộc /work-queue."""
    data = _kpi([_pos("a")])

    assert "applications_waiting_over_threshold" not in data
    assert "open_positions_deadline_passed" in data
