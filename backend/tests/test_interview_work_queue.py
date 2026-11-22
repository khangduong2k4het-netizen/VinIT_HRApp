"""B4 — lịch phỏng vấn vào hàng đợi việc.

Hai con số, và ba cách chúng có thể sai:

1. Đếm cả buổi đã huỷ/đã xong → con số không bao giờ về 0, người dùng học cách
   bỏ qua nó. Đây là kiểu hỏng tệ nhất của một badge.
2. Tính "hôm nay" theo UTC → buổi 06:00 sáng giờ Việt Nam (23:00 UTC hôm trước)
   không hiện trong việc hôm nay, đúng lúc HR cần thấy nhất.
3. Đếm phiếu đã nộp là quá hạn → nhắc mãi một việc đã xong.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.workspace import summarize_interview_work

BACKEND = Path(__file__).resolve().parents[1]
DASHBOARD = (BACKEND / "app" / "api" / "dashboard.py").read_text()

NOW = datetime(2026, 12, 8, 3, 0, tzinfo=timezone.utc)   # 10:00 giờ Việt Nam


def row(**kwargs):
    base = {"interview_id": "i", "status": "SCHEDULED", "starts_at": None,
            "scorecard_status": None, "scorecard_due_at": None}
    return {**base, **kwargs}


def test_counts_a_scheduled_interview_today():
    result = summarize_interview_work([row(starts_at=NOW + timedelta(hours=4))], now=NOW)
    assert result["interviews_today"] == 1


def test_today_is_vietnam_time_not_utc():
    """23:00 UTC hôm trước = 06:00 hôm nay giờ Việt Nam.

    Tính theo UTC thì buổi sáng sớm này bị xếp vào hôm qua và biến mất khỏi
    "việc hôm nay" — đúng buổi HR dễ quên nhất.
    """
    early_morning_vn = datetime(2026, 12, 7, 23, 0, tzinfo=timezone.utc)  # 06:00 ngày 8/12 VN
    result = summarize_interview_work([row(starts_at=early_morning_vn)], now=NOW)
    assert result["interviews_today"] == 1


def test_yesterday_does_not_count():
    yesterday = datetime(2026, 12, 6, 5, 0, tzinfo=timezone.utc)  # 12:00 ngày 6/12 VN
    result = summarize_interview_work([row(starts_at=yesterday)], now=NOW)
    assert result["interviews_today"] == 0


def test_cancelled_and_done_do_not_count_as_today_work():
    """Việc đã xong phải biến mất khỏi badge, nếu không badge thành nhiễu."""
    same_day = NOW + timedelta(hours=2)
    rows = [row(status="CANCELLED", starts_at=same_day),
            row(status="DONE", starts_at=same_day),
            row(status="NO_SHOW", starts_at=same_day)]
    assert summarize_interview_work(rows, now=NOW)["interviews_today"] == 0


def test_overdue_scorecard_counts():
    result = summarize_interview_work(
        [row(status="DONE", scorecard_status="IN_PROGRESS",
             scorecard_due_at=NOW - timedelta(days=1))], now=NOW)
    assert result["scorecards_overdue"] == 1


def test_submitted_scorecard_does_not_count_as_overdue():
    result = summarize_interview_work(
        [row(status="DONE", scorecard_status="SUBMITTED",
             scorecard_due_at=NOW - timedelta(days=1))], now=NOW)
    assert result["scorecards_overdue"] == 0


def test_future_due_is_not_overdue():
    result = summarize_interview_work(
        [row(status="DONE", scorecard_status="NOT_STARTED",
             scorecard_due_at=NOW + timedelta(days=1))], now=NOW)
    assert result["scorecards_overdue"] == 0


def test_string_timestamps_are_accepted():
    """Dữ liệu từ DB qua `mappings()` có thể về dạng chuỗi; đừng để nổ."""
    result = summarize_interview_work(
        [row(starts_at=(NOW + timedelta(hours=3)).isoformat()),
         row(status="DONE", scorecard_status="IN_PROGRESS",
             scorecard_due_at=(NOW - timedelta(hours=1)).isoformat())], now=NOW)
    assert result["interviews_today"] == 1
    assert result["scorecards_overdue"] == 1


def test_empty_input():
    assert summarize_interview_work([], now=NOW) == {"interviews_today": 0, "scorecards_overdue": 0}


# ---------------------------------------------------------------------------
# Nối vào dashboard
# ---------------------------------------------------------------------------

def test_dashboard_adds_items_with_their_own_target():
    """Item của lịch phải mở trang lịch, không phải trang vị trí.

    Gộp vào item của vị trí sẽ cho ra một nút dẫn sai chỗ — người dùng bấm
    "3 buổi hôm nay" mà mở ra danh sách vị trí.
    """
    assert '"type": "INTERVIEW_TODAY"' in DASHBOARD
    assert '"type": "SCORECARD_OVERDUE"' in DASHBOARD
    assert DASHBOARD.count('"target": {"page": "interviews"}') == 2


def test_summary_keys_are_additive():
    """Client cũ không biết hai key mới vẫn phải chạy — nên luôn có mặt, giá trị 0."""
    assert '"interviews_today": interview_counts["interviews_today"]' in DASHBOARD
    assert '"scorecards_overdue": interview_counts["scorecards_overdue"]' in DASHBOARD


def test_items_only_added_when_positive():
    assert 'if interview_counts["interviews_today"]:' in DASHBOARD
    assert 'if interview_counts["scorecards_overdue"]:' in DASHBOARD
