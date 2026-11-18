"""Retention by consent (migration 00023).

5 years only while a Talent Pool consent is in force; otherwise 12 months
after the position closes.
"""
from __future__ import annotations

import contextlib
import os
from datetime import datetime, timezone

import pytest

from app.services.retention import add_months, earliest_retention_months, retention_due_date

CLOSED = datetime(2026, 1, 15, tzinfo=timezone.utc)
POLICY = {"policy_version": "p", "months": 60, "base_months": 12}
LEGACY = {"policy_version": "old", "months": 60, "base_months": None}


def test_without_consent_due_12_months_after_closing():
    assert retention_due_date(CLOSED, None, POLICY) == add_months(CLOSED, 12)


def test_with_consent_due_5_years_from_consent():
    consent = datetime(2025, 11, 1, tzinfo=timezone.utc)
    assert retention_due_date(CLOSED, consent, POLICY) == add_months(consent, 60)


def test_never_earlier_than_12_months_after_closing():
    # Position that stayed open for years: closing + 12 months wins.
    consent = datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert retention_due_date(CLOSED, consent, POLICY) == add_months(CLOSED, 12)


def test_policy_without_the_column_keeps_the_old_rule():
    consent = datetime(2025, 11, 1, tzinfo=timezone.utc)
    assert retention_due_date(CLOSED, consent, LEGACY) == add_months(CLOSED, 60)
    assert retention_due_date(CLOSED, None, LEGACY) == add_months(CLOSED, 60)
    assert earliest_retention_months(LEGACY) == 60 and earliest_retention_months(POLICY) == 12


integration = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                 reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")

if os.environ.get("TEST_DATABASE_URL"):
    from sqlalchemy import text

    from app.db.database import engine
    from app.services import retention_automation as automation
    from test_ocr_images_retention import _close, _grant_lead
    from test_phase1_integration import client, headers, seed, uid  # noqa: F401


@contextlib.contextmanager
def _policy(version, months, without_consent):
    with engine.begin() as conn:
        approved = list(conn.execute(text(
            "SELECT policy_version FROM app_private.retention_policy_versions WHERE status = 'APPROVED'")).scalars())
        conn.execute(text("UPDATE app_private.retention_policy_versions SET status = 'SUPERSEDED' WHERE status = 'APPROVED'"))
        conn.execute(text("""INSERT INTO app_private.retention_policy_versions
                (policy_version, retention_months, retention_months_without_consent, trigger_event, status)
            VALUES (:v, :m, :b, 'POSITION_CLOSED', 'APPROVED')
            ON CONFLICT (policy_version) DO UPDATE SET status = 'APPROVED'"""),
                     {"v": version, "m": months, "b": without_consent})
    try:
        yield
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE app_private.retention_policy_versions SET status = 'SUPERSEDED' WHERE status = 'APPROVED'"))
            conn.execute(text("UPDATE app_private.retention_policy_versions SET status = 'APPROVED' WHERE policy_version = ANY(:v)"),
                         {"v": approved})
            fallback = approved[0] if approved else "v1.0-12month"
            conn.execute(text("UPDATE app_private.application_retention_cases SET policy_version = :f WHERE policy_version = :v"),
                         {"f": fallback, "v": version})
            conn.execute(text("DELETE FROM app_private.retention_policy_versions WHERE policy_version = :v"), {"v": version})


def _consent(seed, *, months_ago, app="app"):
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO app_private.application_data_consents
                (application_id, purpose, notice_version, channel, granted_at)
            VALUES (:a, 'TALENT_POOL', 'v2', 'PORTAL', NOW() - make_interval(months => :m))"""),
                     {"a": seed[app], "m": months_ago})


def _withdraw(seed, app="app"):
    with engine.begin() as conn:
        conn.execute(text("""UPDATE app_private.application_data_consents SET withdrawn_at = NOW()
            WHERE application_id = :a AND purpose = 'TALENT_POOL'"""), {"a": seed[app]})


def _generate(client, seed):
    r = client.post(f"/v1/retention/positions/{seed['pos']}/cases/generate", headers=headers(seed["hr"]))
    assert r.status_code == 200, r.text
    return r.json()


@integration
def test_application_without_consent_is_due_12_months_after_closing(client, seed):
    _close(seed, months_ago=13)
    with _policy("test-consent", 60, 12):
        result = _generate(client, seed)
        assert result["created_count"] == 1 and result["retention_months"] == 60
        case = result["cases"][0]
        assert datetime.fromisoformat(case["due_date"]) < datetime.now(timezone.utc)


@integration
def test_consented_application_is_kept_until_consent_is_withdrawn(client, seed):
    _close(seed, months_ago=13)
    _consent(seed, months_ago=14)
    with _policy("test-consent", 60, 12):
        assert _generate(client, seed)["created_count"] == 0
        assert automation.run_retention_cycle()["cases_created"] == 0
        _withdraw(seed)
        # Withdrawn: back to 12 months after closing, which has passed.
        assert automation.run_retention_cycle()["cases_created"] == 1


@integration
def test_switching_policy_cancels_only_cases_of_consented_applications(client, seed):
    _close(seed, months_ago=13)
    _close(seed, months_ago=13, position="pos2")
    _consent(seed, months_ago=14, app="app")
    _grant_lead(seed)
    # Both cases are created under a 12-month policy first.
    with _policy("test-12month", 12, None):
        assert _generate(client, seed)["created_count"] == 1
        r = client.post(f"/v1/retention/positions/{seed['pos2']}/cases/generate", headers=headers(seed["hr2"]))
        assert r.json()["created_count"] == 1
    with _policy("test-consent", 60, 12):
        summary = automation.run_retention_cycle()
        assert summary["cases_cancelled_policy_extended"] == 1
        with engine.connect() as conn:
            rows = dict(conn.execute(text("""SELECT application_id::text, status FROM app_private.application_retention_cases
                WHERE application_id IN (:a, :b)"""), {"a": seed["app"], "b": seed["app2"]}).all())
        assert rows == {seed["app"]: "CANCELLED", seed["app2"]: "PENDING"}
        assert automation.run_retention_cycle()["cases_cancelled_policy_extended"] == 0
