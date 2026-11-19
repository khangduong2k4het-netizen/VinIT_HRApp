"""P3-2 — AI quality trends: metric rules, privacy masking and access scope."""
import os
from datetime import date

import pytest
from sqlalchemy import text

from app.services import ai_quality
from app.services.ai_quality import QualityError, proportion, resolve_period, wilson_interval


# ---------------------------------------------------------------- unit tests

def test_wilson_interval_known_values_and_bounds():
    assert wilson_interval(0, 0) is None
    low, high = wilson_interval(5, 10)
    assert round(low, 3) == 0.237 and round(high, 3) == 0.763
    low, high = wilson_interval(0, 30)
    assert low == 0.0 and 0 < high < 0.15
    low, high = wilson_interval(30, 30)
    assert high == 1.0 and 0.85 < low < 1


def test_proportion_withholds_rate_below_minimum_sample():
    small = proportion(3, 19)
    assert small == {"count": 3, "total": 19, "rate": None, "ci_low": None, "ci_high": None, "insufficient": True}
    enough = proportion(5, 20)
    assert enough["rate"] == 0.25 and enough["insufficient"] is False
    assert enough["ci_low"] < 0.25 < enough["ci_high"]
    assert proportion(0, 0)["rate"] is None and proportion(None, None)["total"] == 0
    assert proportion(1, 2, min_sample=2)["rate"] == 0.5


def test_resolve_period_defaults_and_limits():
    today = date(2026, 11, 17)
    assert resolve_period(None, None, "week", today) == (date(2026, 5, 22), today, "week")
    assert resolve_period("2026-01-01", "2026-03-31", "month", today)[2] == "month"
    for bad in (("2026-02-01", "2026-01-01", "week"), ("17/11/2026", None, "week"),
                ("2024-01-01", "2026-11-01", "week"), (None, None, "day")):
        with pytest.raises(QualityError):
            resolve_period(*bad, today)


# ---------------------------------------------------------- integration tests

integration = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                 reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")

if os.environ.get("TEST_DATABASE_URL"):
    from app.db.database import engine
    from test_hr_analytics import _assessed_application
    from test_phase1_integration import client, headers, seed, uid  # noqa: F401 (pytest fixtures)


def _assessment_id(application_id):
    with engine.connect() as conn:
        return conn.execute(text("SELECT assessment_id FROM app_private.assessment_runs WHERE application_id = :a"),
                            {"a": application_id}).scalar_one()


def _inspection(assessment_id, position_id, reasons, status="COMPLETED", verdict=None):
    import json
    with engine.begin() as conn:
        return conn.execute(text("""
            INSERT INTO app_private.quality_inspections(assessment_id, position_id, reasons, status, verdict, completed_at)
            VALUES (:a, :p, CAST(:r AS jsonb), :s, :v, CASE WHEN :s = 'COMPLETED' THEN NOW() END) RETURNING inspection_id
        """), {"a": assessment_id, "p": position_id, "r": json.dumps(reasons), "s": status, "v": verdict}).scalar_one()


def _quality_fixture(seed):
    apps = [_assessed_application(seed, "MEETS_MANDATORY", f"QA {i}") for i in range(4)]
    ids = [_assessment_id(a) for a in apps]
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.assessment_runs SET completed_at = NOW() WHERE assessment_id = ANY(CAST(:ids AS uuid[]))"),
                     {"ids": ids})
    pos = seed["pos"]
    _inspection(ids[0], pos, ["RANDOM_SAMPLE"], verdict="CORRECT")
    flagged = _inspection(ids[1], pos, ["RANDOM_SAMPLE", "SINGLE_MANDATORY_MISS"], verdict="ISSUES_FOUND")
    _inspection(ids[2], pos, ["BORDERLINE_COVERAGE"], verdict="ISSUES_FOUND")
    _inspection(ids[3], pos, ["SINGLE_MANDATORY_MISS"], status="PENDING")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.quality_flags(inspection_id, category, note) VALUES (:i, 'INCORRECT_EVIDENCE', 'x')"),
                     {"i": flagged})
        # One override and one agreement; and one decision made before tracking existed (no AI snapshot).
        for app_id, direction, reason in ((apps[0], "ADVANCED_DESPITE_AI", "SYNONYM_TERMS"), (apps[1], None, None)):
            conn.execute(text("""
                INSERT INTO app_private.application_status_events(application_id, previous_status, new_status, changed_by,
                       ai_matching_status, override_direction, override_reason_code)
                VALUES (:a, 'IN_REVIEW', 'SHORTLIST', :u, 'POSSIBLE_MISMATCH', :d, :r)"""),
                         {"a": app_id, "u": seed["hr"], "d": direction, "r": reason})
        conn.execute(text("""INSERT INTO app_private.application_status_events(application_id, previous_status, new_status, changed_by)
                             VALUES (:a, 'IN_REVIEW', 'SHORTLIST', :u)"""), {"a": apps[2], "u": seed["hr"]})
    return apps


@integration
def test_trends_keep_random_sample_separate_from_risk_group(client, seed, monkeypatch):
    _quality_fixture(seed)
    hr = headers(seed["hr"])
    monkeypatch.setattr(ai_quality, "MIN_SAMPLE_SIZE", 2)
    body = client.get("/v1/analytics/quality/trends", headers=hr).json()
    assert body["range"]["grain"] == "week" and body["min_sample"] == 2
    assert len(body["series"]) == 1
    row = body["series"][0]
    # Random sample: 2 cases, 1 with issues. Pooling every inspection would give 2/3 instead.
    assert (row["qa_random_sample"]["count"], row["qa_random_sample"]["total"], row["qa_random_sample"]["rate"]) == (1, 2, 0.5)
    # Risk group: a case drawn at random that is also risky belongs to both groups.
    assert (row["qa_risk_group"]["count"], row["qa_risk_group"]["total"], row["qa_risk_group"]["rate"]) == (2, 2, 1.0)
    assert row["qa_completed"] == 3 and row["qa_flags_by_category"] == {"INCORRECT_EVIDENCE": 1}
    # Decisions without an AI snapshot are excluded rather than guessed.
    assert (row["overrides"]["count"], row["overrides"]["total"], row["overrides"]["rate"]) == (1, 2, 0.5)
    assert row["overrides"]["advanced_despite_ai"] == 1
    assert row["assessments"]["completed"] == 4 and row["assessments"]["average_evidence_coverage"] == 0.55
    assert body["qa_backlog"]["open_cases"] == 1 and body["qa_backlog"]["oldest_created_at"] is not None


@integration
def test_small_samples_hide_rates_but_keep_counts(client, seed):
    _quality_fixture(seed)
    row = client.get("/v1/analytics/quality/trends", headers=headers(seed["hr"])).json()["series"][0]
    for key in ("qa_random_sample", "qa_risk_group", "overrides"):
        assert row[key]["insufficient"] is True and row[key]["rate"] is None and row[key]["ci_low"] is None
    assert row["qa_random_sample"]["total"] == 2


@integration
def test_access_scope_and_validation(client, seed):
    _quality_fixture(seed)
    route = "/v1/analytics/quality/trends"
    assert client.get(route, headers=headers(seed["hm"])).status_code == 403
    assert client.get(route, headers=headers(seed["hr"]), params={"grain": "day"}).status_code == 400
    assert client.get(route, headers=headers(seed["hr"]), params={"date_from": "nope"}).status_code == 400
    # Another recruiter sees only their own position, which has no QA data; nothing about the first position leaks.
    other = client.get(route, headers=headers(seed["hr2"])).json()
    assert other["series"] == [] and other["qa_backlog"]["open_cases"] == 0
    narrowed = client.get(route, headers=headers(seed["hr"]), params={"position_id": seed["pos2"]}).json()
    assert narrowed["series"] == [] and narrowed["qa_backlog"]["open_cases"] == 0
    old = client.get(route, headers=headers(seed["hr"]), params={"date_from": "2020-01-01", "date_to": "2020-06-30"}).json()
    assert old["series"] == []
    # Never broken down by recruiter.
    assert "changed_by" not in str(client.get(route, headers=headers(seed["hr"])).json())


@integration
def test_breakdowns(client, seed):
    _quality_fixture(seed)
    hr = headers(seed["hr"])
    route = "/v1/analytics/quality/breakdown"
    assert client.get(route, headers=hr, params={"dimension": "recruiter"}).status_code == 400
    assert client.get(route, headers=headers(seed["hm"]), params={"dimension": "flag_category"}).status_code == 403

    reasons = client.get(route, headers=hr, params={"dimension": "override_reason"}).json()["rows"]
    assert reasons == [{"key": "SYNONYM_TERMS", "count": 1, "share": None}]  # share hidden below the minimum sample
    flags = client.get(route, headers=hr, params={"dimension": "flag_category"}).json()["rows"]
    assert flags == [{"key": "INCORRECT_EVIDENCE", "count": 1, "share": None}]
    families = client.get(route, headers=hr, params={"dimension": "job_family"}).json()["rows"]
    assert len(families) == 1 and families[0]["key"] is None
    assert families[0]["overrides"]["total"] == 2 and families[0]["qa_random_sample"]["total"] == 2
    versions = client.get(route, headers=hr, params={"dimension": "matching_policy_version"}).json()["rows"]
    assert sum(v["completed"] for v in versions) == 4
    file_types = client.get(route, headers=hr, params={"dimension": "file_type"}).json()["rows"]
    assert isinstance(file_types, list)
    crit_types = client.get(route, headers=hr, params={"dimension": "criterion_type"}).json()["rows"]
    assert isinstance(crit_types, list)
    assert client.get(route, headers=headers(seed["hr2"]), params={"dimension": "flag_category"}).json()["rows"] == []


@integration
def test_golden_set_export_anonymized_and_lead_or_admin_only(client, seed):
    apps = _quality_fixture(seed)
    with engine.begin() as conn:
        # An OTHER override should be excluded from the golden set per P3-2 spec §5.
        conn.execute(text("""
            INSERT INTO app_private.application_status_events(application_id, previous_status, new_status, changed_by,
                   note, ai_matching_status, override_direction, override_reason_code)
            VALUES (:a, 'IN_REVIEW', 'SHORTLIST', :u, 'misc note', 'POSSIBLE_MISMATCH', 'ADVANCED_DESPITE_AI', 'OTHER')
        """), {"a": apps[3], "u": seed["hr"]})
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id, role_code) VALUES (:u, 'HR_LEAD')"),
                     {"u": seed["other"]})
    route = "/v1/analytics/quality/golden-set/export"
    assert client.get(route, headers=headers(seed["hm"])).status_code == 403
    assert client.get(route, headers=headers(seed["hr"])).status_code == 403

    lead = headers(seed["other"])
    res_json = client.get(route, headers=lead, params={"format": "json"})
    assert res_json.status_code == 200, res_json.text
    payload = res_json.json()
    sources = [item["source"] for item in payload["items"]]
    assert "QA_ISSUES_FOUND" in sources and "QA_RANDOM_CORRECT" in sources and "HR_OVERRIDE" in sources
    assert all(item["override_reason_code"] != "OTHER" for item in payload["items"])
    raw_text = res_json.text
    for app_id in apps:
        assert app_id not in raw_text
    assert "QA 0" not in raw_text and "QA 1" not in raw_text

    res_csv = client.get(route, headers=lead, params={"format": "csv"})
    assert res_csv.status_code == 200 and "text/csv" in res_csv.headers["content-type"]
    assert "application_opaque_id" in res_csv.text and "QA 0" not in res_csv.text
    with engine.connect() as conn:
        audits = conn.execute(text("""SELECT COUNT(*) FROM app_private.audit_events
            WHERE action_type = 'EXPORT_QUALITY_GOLDEN_SET'""")).scalar_one()
    assert audits == 2


@integration
def test_markers_admin_only_write_audited_without_text(client, seed):
    admin = seed["other"]
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM app_private.quality_markers"))
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id, role_code) VALUES (:u, 'ADMIN')"), {"u": admin})
    body = {"occurred_on": date.today().isoformat(), "title": "Cập nhật từ điển đồng nghĩa khối Tài chính", "note": "v2"}
    route = "/v1/analytics/quality/markers"
    assert client.post(route, headers=headers(seed["hr"]), json=body).status_code == 403
    assert client.post(route, headers=headers(admin), json={**body, "title": "   "}).status_code == 400
    assert client.post(route, headers=headers(admin), json={**body, "extra": 1}).status_code == 422
    created = client.post(route, headers=headers(admin), json=body)
    assert created.status_code == 201, created.text
    listed = client.get(route, headers=headers(seed["hr"])).json()["markers"]
    manual = [m for m in listed if m["kind"] == "MANUAL"]
    assert len(manual) == 1 and manual[0]["title"] == body["title"] and manual[0]["note"] == "v2"
    assert client.get(route, headers=headers(seed["hm"])).status_code == 403
    with engine.connect() as conn:
        metadata = conn.execute(text("""SELECT metadata FROM app_private.audit_events
            WHERE action_type = 'CREATE_QUALITY_MARKER'""")).scalar_one()
    assert set(metadata) == {"occurred_on", "title_length"} and "từ điển" not in str(metadata)


@integration
def test_version_markers_report_first_use_of_each_version(client, seed):
    apps = [_assessed_application(seed, "MEETS_MANDATORY", f"V {i}") for i in range(2)]
    with engine.begin() as conn:
        conn.execute(text("""UPDATE app_private.assessment_runs SET matching_policy_version = 'det-v1.5', prompt_version = 'p-1',
                             completed_at = NOW() WHERE application_id = :a"""), {"a": apps[0]})
        conn.execute(text("""UPDATE app_private.assessment_runs SET matching_policy_version = 'det-v1.5', prompt_version = 'p-1',
                             completed_at = NOW() WHERE application_id = :a"""), {"a": apps[1]})
    markers = client.get("/v1/analytics/quality/markers", headers=headers(seed["hr"])).json()["markers"]
    titles = sorted(m["title"] for m in markers if m["kind"] == "VERSION")
    assert titles == ["MATCHING_POLICY det-v1.5", "PROMPT p-1"]  # one marker per version, not per assessment
    # The other recruiter has no assessments in scope, so no version markers.
    assert [m for m in client.get("/v1/analytics/quality/markers", headers=headers(seed["hr2"])).json()["markers"]
            if m["kind"] == "VERSION"] == []
