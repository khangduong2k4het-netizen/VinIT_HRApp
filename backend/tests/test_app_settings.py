"""HR thresholds: validation, defaults and how they reach the work queue."""
import pytest
from datetime import datetime, timedelta, timezone

from app.services.app_settings import (
    SETTINGS,
    SettingError,
    load_settings,
    public_payload,
    save_setting,
    validated_value,
)
from app.services.workspace import build_work_queue_items, build_workflow, summarize_applications, summarize_waiting

NOW = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)


class FakeDB:
    """Minimal stand-in for a SQLAlchemy session: one table, no SQL."""

    def __init__(self, rows=None, *, fail=False):
        self.rows = dict(rows or {})
        self.fail = fail
        self.executed = []

    def execute(self, statement, params=None):
        if self.fail:
            raise RuntimeError("relation app_private.app_settings does not exist")
        self.executed.append((str(statement), params))
        if str(statement).strip().upper().startswith("SELECT"):
            return self
        if "INSERT" in str(statement).upper():
            self.rows[params["key"]] = params["value"]
        return self

    def all(self):
        return list(self.rows.items())


def test_defaults_are_used_when_the_table_is_empty_or_missing():
    assert load_settings(FakeDB())["deadline_soon_days"] == 7
    # A read path must not break because the settings table is unreachable.
    assert load_settings(FakeDB(fail=True))["waiting_attention_days"] == 7


def test_out_of_range_stored_values_fall_back_instead_of_being_trusted():
    db = FakeDB({"deadline_soon_days": 999, "waiting_attention_days": 0})
    values = load_settings(db)

    assert values["deadline_soon_days"] == 7, "giá trị vô lý trong DB không được áp dụng"
    assert values["waiting_attention_days"] == 7


def test_unknown_keys_and_non_integers_are_refused_with_a_usable_message():
    with pytest.raises(SettingError, match="Không có cài đặt"):
        validated_value("not_a_setting", 5)
    with pytest.raises(SettingError, match="số nguyên"):
        validated_value("deadline_soon_days", "5")
    # bool is an int in Python: True must not silently become "1 day".
    with pytest.raises(SettingError, match="số nguyên"):
        validated_value("deadline_soon_days", True)


def test_range_is_enforced_at_both_ends_and_the_message_names_the_range():
    spec = SETTINGS["deadline_soon_days"]
    assert validated_value("deadline_soon_days", spec.minimum) == spec.minimum
    assert validated_value("deadline_soon_days", spec.maximum) == spec.maximum
    with pytest.raises(SettingError, match=f"{spec.minimum}–{spec.maximum}"):
        validated_value("deadline_soon_days", spec.maximum + 1)
    with pytest.raises(SettingError, match=f"{spec.minimum}–{spec.maximum}"):
        validated_value("deadline_soon_days", spec.minimum - 1)


def test_saving_writes_the_validated_value():
    db = FakeDB()
    assert save_setting(db, "deadline_soon_days", 3, "user-1") == 3
    assert db.rows["deadline_soon_days"] == 3


def test_payload_describes_every_setting_for_the_screen():
    payload = public_payload(load_settings(FakeDB()))

    assert {item["key"] for item in payload} == set(SETTINGS)
    for item in payload:
        assert item["description"], "mỗi cài đặt phải nói nó đổi điều gì"
        assert item["min"] <= item["value"] <= item["max"]


def _queue(deadline_at, *, soon_days):
    counts = summarize_applications([])
    workflow = build_workflow(
        position_id="pos-1", position_status="OPEN", jd_exists=True,
        criteria_status="APPROVED", criteria_stale=False, criteria_approved=True,
        counts=counts, active_operation=None, is_hr=True, is_hm=False,
    )
    return build_work_queue_items(
        position={"position_id": "pos-1", "position_code": "REQ-1", "title": "Engineer",
                  "status": "OPEN", "position_roles": ["HR_RECRUITER"], "system_roles": []},
        counts=counts, workflow=workflow, criteria_status="APPROVED",
        criteria_stale=False, jd_exists=True, is_hr=True, is_hm=False,
        criteria_approved=True, deadline_at=deadline_at, now=NOW, deadline_soon_days=soon_days,
    )


def test_the_configured_threshold_decides_whether_a_deadline_is_soon():
    deadline = NOW + timedelta(days=10)

    assert "POSITION_DEADLINE_SOON" not in [i["type"] for i in _queue(deadline, soon_days=7)]
    assert [i["type"] for i in _queue(deadline, soon_days=14)] == ["POSITION_DEADLINE_SOON"]


def test_the_configured_threshold_decides_what_counts_as_waiting_too_long():
    applications = [{"application_status": "IN_REVIEW", "created_at": NOW - timedelta(days=4)}]

    assert summarize_waiting(applications, NOW, threshold_days=7)["waiting_over_7d"] == 0
    assert summarize_waiting(applications, NOW, threshold_days=3)["waiting_over_7d"] == 1
    # Changing the threshold never changes the measured age itself.
    assert summarize_waiting(applications, NOW, threshold_days=3)["oldest_waiting_days"] == 4
