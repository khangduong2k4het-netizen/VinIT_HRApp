"""F2.03 — HR override tracking and the operational analytics report."""
import os
from datetime import date

import pytest
from sqlalchemy import text

from app.services.analytics import AnalyticsError, resolve_range
from app.services.override_rules import classify_override, override_reason_error


# ---------------------------------------------------------------- unit tests

@pytest.mark.parametrize("new_status, ai, expected", [
    ("SHORTLIST", "POSSIBLE_MISMATCH", "ADVANCED_DESPITE_AI"),
    ("SHORTLIST", "NEEDS_HR_VERIFICATION", "ADVANCED_DESPITE_AI"),
    ("SHORTLIST", "MEETS_MANDATORY", None),
    ("REJECTED_SCREENING", "MEETS_MANDATORY", "REJECTED_DESPITE_AI"),
    ("REJECTED_SCREENING", "POSSIBLE_MISMATCH", None),
    ("SHORTLIST", None, None),                # no AI conclusion -> never an override
    ("SHORTLIST", "NOT_ASSESSED", None),
    ("REJECTED_INTERVIEW", "MEETS_MANDATORY", None),  # post-interview decisions are not compared
    ("IN_REVIEW", "POSSIBLE_MISMATCH", None),
])
def test_classify_override(new_status, ai, expected):
    assert classify_override(new_status, ai) == expected


def test_override_reason_rules():
    assert override_reason_error(None, None, None) is None
    assert "lý do" in override_reason_error("ADVANCED_DESPITE_AI", None, None)
    assert override_reason_error("ADVANCED_DESPITE_AI", "MADE_UP", None)
    assert "Khác" in override_reason_error("ADVANCED_DESPITE_AI", "OTHER", "  ")
    assert override_reason_error("ADVANCED_DESPITE_AI", "OTHER", "Đã gọi xác minh") is None
    assert override_reason_error("REJECTED_DESPITE_AI", "INTERVIEW_VERIFICATION", None) is None


def test_resolve_range_defaults_and_limits():
    today = date(2026, 11, 12)
    assert resolve_range(None, None, today) == (date(2026, 8, 15), today)
    assert resolve_range("2026-01-01", "2026-01-31", today) == (date(2026, 1, 1), date(2026, 1, 31))
    for bad in (("2026-02-01", "2026-01-01"), ("12/11/2026", None), ("2024-01-01", "2026-01-01")):
        with pytest.raises(AnalyticsError):
            resolve_range(*bad, today)


# ---------------------------------------------------------- integration tests

integration = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                 reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")

if os.environ.get("TEST_DATABASE_URL"):
    from app.db.database import engine
    from test_phase1_integration import client, headers, seed, uid  # noqa: F401 (pytest fixtures)


def _assessed_application(seed, matching_status, name):
    """An IN_REVIEW application in seed['pos'] with a valid completed assessment."""
    app_id = uid()
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status = 'APPROVED' WHERE criteria_version_id = :id"), {"id": seed["cv"]})
        conn.execute(text("INSERT INTO app_private.applications(application_id, position_id, created_by, application_status) VALUES (:a, :p, :u, 'IN_REVIEW')"),
                     {"a": app_id, "p": seed["pos"], "u": seed["hr"]})
        conn.execute(text("INSERT INTO app_private.application_identities(application_id, display_name) VALUES (:a, :n)"), {"a": app_id, "n": name})
        doc = conn.execute(text("""INSERT INTO app_private.application_documents(application_id,bucket,storage_path,original_filename,mime_type,size_bytes,file_processing_status)
            VALUES (:a,'cv','x','cv.pdf','application/pdf',10,'COMPLETED') RETURNING document_id"""), {"a": app_id}).scalar_one()
        profile = conn.execute(text("""INSERT INTO app_private.profile_versions(application_id,source_document_id,version_number,status)
            VALUES (:a,:d,1,'COMPLETED') RETURNING profile_version_id"""), {"a": app_id, "d": doc}).scalar_one()
        conn.execute(text("""INSERT INTO app_private.assessment_runs(position_id,application_id,jd_version_id,criteria_version_id,profile_version_id,status,matching_status,matching_score,evidence_coverage)
            VALUES (:p,:a,:jd,:cv,:pv,'COMPLETED',:ms,61.5,0.55)"""),
                     {"p": seed["pos"], "a": app_id, "jd": seed["jd"], "cv": seed["cv"], "pv": profile, "ms": matching_status})
        conn.execute(text("INSERT INTO app_private.application_status_events(application_id, previous_status, new_status, changed_by) VALUES (:a, 'NEW', 'IN_REVIEW', :u)"),
                     {"a": app_id, "u": seed["hr"]})
    return app_id


@integration
def test_status_changes_snapshot_ai_and_require_override_reasons(client, seed):
    hr = headers(seed["hr"])
    weak = _assessed_application(seed, "POSSIBLE_MISMATCH", "Ứng viên Yếu")
    strong = _assessed_application(seed, "MEETS_MANDATORY", "Ứng viên Mạnh")
    normal = _assessed_application(seed, "MEETS_MANDATORY", "Ứng viên Bình thường")

    check = client.get(f"/v1/applications/{weak}/override-check", headers=hr, params={"new_status": "SHORTLIST"}).json()
    assert check["is_override"] and check["direction"] == "ADVANCED_DESPITE_AI" and check["ai_matching_status"] == "POSSIBLE_MISMATCH"
    assert len(check["reason_codes"]) == 7
    assert client.get(f"/v1/applications/{weak}/override-check", headers=headers(seed["hm"]),
                      params={"new_status": "SHORTLIST"}).status_code == 403

    route = f"/v1/applications/{weak}/status"
    assert client.patch(route, headers=hr, json={"new_status": "SHORTLIST"}).status_code == 400
    assert client.patch(route, headers=hr, json={"new_status": "SHORTLIST", "override_reason_code": "OTHER"}).status_code == 400
    ok = client.patch(route, headers=hr, json={"new_status": "SHORTLIST", "override_reason_code": "synonym_terms"})
    assert ok.status_code == 200, ok.text

    assert client.patch(f"/v1/applications/{strong}/status", headers=hr, json={
        "new_status": "REJECTED_SCREENING", "reason": "Không đạt phỏng vấn sơ bộ qua điện thoại",
        "override_reason_code": "INTERVIEW_VERIFICATION"}).status_code == 200
    # Agreeing with the AI needs no override reason, and any code sent is not stored.
    assert client.patch(f"/v1/applications/{normal}/status", headers=hr, json={
        "new_status": "SHORTLIST", "override_reason_code": "SYNONYM_TERMS"}).status_code == 200

    with engine.connect() as conn:
        events = {str(r["application_id"]): dict(r) for r in conn.execute(text("""
            SELECT application_id, ai_matching_status, ai_matching_score, ai_evidence_coverage, ai_assessment_id,
                   override_direction, override_reason_code
            FROM app_private.application_status_events WHERE new_status IN ('SHORTLIST', 'REJECTED_SCREENING')
        """)).mappings()}
        audit = conn.execute(text("""SELECT metadata FROM app_private.audit_events
            WHERE action_type = 'UPDATE_APPLICATION_STATUS' AND object_id = :a"""), {"a": weak}).scalar_one()
    assert events[weak]["override_direction"] == "ADVANCED_DESPITE_AI" and events[weak]["override_reason_code"] == "SYNONYM_TERMS"
    assert float(events[weak]["ai_matching_score"]) == 61.5 and events[weak]["ai_assessment_id"] is not None
    assert events[strong]["override_direction"] == "REJECTED_DESPITE_AI"
    assert events[normal]["override_direction"] is None and events[normal]["override_reason_code"] is None
    assert events[normal]["ai_matching_status"] == "MEETS_MANDATORY"
    assert audit == {"override_direction": "ADVANCED_DESPITE_AI", "override_reason_code": "SYNONYM_TERMS"}


@integration
def test_operational_report_scope_metrics_and_privacy(client, seed):
    hr = headers(seed["hr"])
    weak = _assessed_application(seed, "POSSIBLE_MISMATCH", "Ứng viên Yếu")
    normal = _assessed_application(seed, "MEETS_MANDATORY", "Ứng viên Bình thường")
    client.patch(f"/v1/applications/{weak}/status", headers=hr, json={"new_status": "SHORTLIST", "override_reason_code": "EQUIVALENT_CREDENTIAL"})
    client.patch(f"/v1/applications/{normal}/status", headers=hr, json={"new_status": "SHORTLIST"})
    client.patch(f"/v1/applications/{normal}/status", headers=hr, json={"new_status": "INTERVIEW"})

    route = "/v1/analytics/operations"
    assert client.get(route, headers=headers(seed["hm"])).status_code == 403
    assert client.get(route, headers=hr, params={"date_from": "2026-13-01"}).status_code == 400
    report = client.get(route, headers=hr)
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["scope"] == {"global": False, "positions": 1}
    assert body["volume"]["applications_received"] == 3  # seed app + 2 assessed applications
    funnel = {row["stage"]: row["count"] for row in body["funnel"]}
    assert funnel["IN_REVIEW"] == 2 and funnel["SHORTLIST"] == 2 and funnel["INTERVIEW"] == 1 and funnel["OFFERED"] == 0
    assert body["time_to_shortlist"]["applications"] == 2 and body["time_to_shortlist"]["average_hours"] is not None
    overrides = body["overrides"]
    assert overrides["decisions_with_ai"] == 2 and overrides["overrides"] == 1 and overrides["override_rate"] == 0.5
    assert {r["code"]: r["count"] for r in overrides["by_reason"]}["EQUIVALENT_CREDENTIAL"] == 1
    case = overrides["cases"][0]
    assert case["candidate_name"] == "Ứng viên Yếu" and case["ai_matching_status"] == "POSSIBLE_MISMATCH"
    assert "changed_by" not in case and "HR" not in str(case.get("actor_name", ""))  # never per recruiter
    assert body["technical_errors"]["files_uploaded"] == 0 and body["technical_errors"]["error_rate"] is None

    # Another recruiter sees only their own position; filters narrow the scope.
    other = client.get(route, headers=headers(seed["hr2"])).json()
    assert other["overrides"]["overrides"] == 0 and other["volume"]["applications_received"] == 1
    narrowed = client.get(route, headers=hr, params={"position_id": seed["pos2"]}).json()
    assert narrowed["scope"]["positions"] == 0 and narrowed["volume"]["applications_received"] == 0
    old = client.get(route, headers=hr, params={"date_from": "2020-01-01", "date_to": "2020-12-31"}).json()
    assert old["volume"]["applications_received"] == 0 and old["overrides"]["override_rate"] is None
