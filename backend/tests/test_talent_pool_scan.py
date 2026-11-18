"""P3-1 phase 2: scanning the Talent Pool for a new position."""
import io
import os

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.services.talent_pool_scan import criteria_summary, rank_key


# ---------------------------------------------------------------- unit tests

def test_rank_key_orders_like_the_position_ranking():
    rows = [
        {"application_id": "c", "matching_status": "NEEDS_HR_VERIFICATION", "matching_score": 95, "evidence_coverage": 0.9},
        {"application_id": "a", "matching_status": "MEETS_MANDATORY", "matching_score": 70, "evidence_coverage": 1.0},
        {"application_id": "b", "matching_status": "MEETS_MANDATORY", "matching_score": 90, "evidence_coverage": 0.8},
        {"application_id": "d", "matching_status": "POSSIBLE_MISMATCH", "matching_score": None, "evidence_coverage": 0},
    ]
    assert [r["application_id"] for r in sorted(rows, key=rank_key)] == ["b", "a", "c", "d"]


def test_criteria_summary_keeps_only_verified_quotes_and_truncates():
    items = [{"criterion_id": "1", "name": "Python", "category": "MUST_HAVE"},
             {"criterion_id": "2", "name": "SQL", "category": "NICE_TO_HAVE"}]
    results = [
        {"criterion_id": "1", "outcome": "MATCH", "evidence_verified": True, "evidence": {"verbatim_quote": "x" * 500}},
        {"criterion_id": "2", "outcome": "UNCLEAR", "evidence_verified": False, "evidence": {"verbatim_quote": "invented"}},
    ]
    summary = criteria_summary(results, items)
    assert summary[0]["name"] == "Python" and len(summary[0]["quote"]) == 300
    assert summary[1]["quote"] is None and summary[1]["outcome"] == "UNCLEAR"


# ---------------------------------------------------------- integration tests

integration = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                 reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")

if os.environ.get("TEST_DATABASE_URL"):
    from app.db.database import engine
    from test_phase1_integration import client, headers, seed, uid  # noqa: F401 (pytest fixtures)
    from test_public_intake_talent_pool import portal  # noqa: F401 (pytest fixture)

QUOTE = "Developed Python systems for five years"


def _docx(lines):
    from docx import Document
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _stub_ai(monkeypatch, calls):
    from app.workers.processor import llm_client

    async def extract(**kwargs):
        return {"education": [], "work_history": [], "skills": ["Python"], "certifications": []}

    async def match(**kwargs):
        calls.append([c["criterion_id"] for c in kwargs["rubric"]])
        return {"findings": [{"criterion_id": c["criterion_id"], "outcome": "STRONG_MATCH", "confidence": .9,
                              "confidence_band": "HIGH", "evidence": {"verbatim_quote": QUOTE}} for c in kwargs["rubric"]]}
    monkeypatch.setattr(llm_client, "extract_candidate_profile", extract)
    monkeypatch.setattr(llm_client, "match_criterion_evidence", match)


def _pooled_portal_application(client, seed, email="pool.candidate@example.org"):
    """A portal CV on seed['pos'], processed by the worker, then marked into the pool by its HR."""
    from app.workers.processor import worker
    content = _docx(["Pool Candidate", f"Email {email}", QUOTE + ". Built reliable automated testing systems."])
    res = client.post(f"/v1/public/positions/{seed['pos']}/apply",
                      files={"file": ("pool.docx", content,
                                      "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                      data={"consent_processing": "true", "website": ""})
    assert res.status_code == 202, res.text
    worker._process_pending_operations()
    with engine.begin() as conn:
        app_id = str(conn.execute(text("SELECT application_id FROM app_private.applications WHERE source_code = 'PORTAL'")).scalar_one())
        conn.execute(text("UPDATE app_private.applications SET application_status = 'SHORTLIST' WHERE application_id = :a"), {"a": app_id})
        conn.execute(text("UPDATE app_private.application_identities SET email = :e WHERE application_id = :a"), {"e": email, "a": app_id})
    marked = client.post(f"/v1/talent-pool/applications/{app_id}/mark", headers=headers(seed["hr"]),
                         json={"reason_code": "NEAR_MISS"})
    assert marked.status_code == 201, marked.text
    return app_id


def _approve_target_criteria(seed):
    """Give seed['pos2'] (owned by hr2) a JD and an approved rubric."""
    jd, cv, item = uid(), uid(), uid()
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO app_private.jd_versions(jd_version_id, position_id, version_number, content_text, created_by)
            VALUES (:jd, :p, 1, 'Python backend engineer', :u)"""), {"jd": jd, "p": seed["pos2"], "u": seed["hr2"]})
        conn.execute(text("""INSERT INTO app_private.criteria_versions(criteria_version_id, position_id, jd_version_id, version_number, status)
            VALUES (:cv, :p, :jd, 1, 'APPROVED')"""), {"cv": cv, "p": seed["pos2"], "jd": jd})
        conn.execute(text("""INSERT INTO app_private.criteria_items(criterion_id, criteria_version_id, name, description, category,
                weight_in_group, display_order) VALUES (:i, :cv, 'Python systems', 'Builds Python systems', 'MUST_HAVE', 100, 1)"""),
                     {"i": item, "cv": cv})
    return cv, item


@integration
def test_scan_scores_the_pool_for_a_new_position_without_touching_its_applicants(client, portal, monkeypatch):
    from app.workers.processor import worker
    seed = portal
    monkeypatch.setattr(settings, "PUBLIC_INTAKE_MAX_PER_IP_HOUR", 100)
    calls = []
    _stub_ai(monkeypatch, calls)
    pooled = _pooled_portal_application(client, seed)

    # Pool list: HR sees the candidate and source position, never contact details; HM is refused.
    listed = client.get("/v1/talent-pool", headers=headers(seed["hr2"])).json()["items"]
    assert [i["application_id"] for i in listed] == [pooled] and "email" not in listed[0]
    assert client.get("/v1/talent-pool", headers=headers(seed["hm"])).status_code == 403

    scan_route = f"/v1/talent-pool/positions/{seed['pos2']}/scans"
    assert client.post(scan_route, headers=headers(seed["hr2"])).status_code == 409  # no approved criteria yet
    _approve_target_criteria(seed)
    assert client.post(scan_route, headers=headers(seed["hm"])).status_code == 403
    assert client.post(scan_route, headers=headers(seed["hr"])).status_code == 403   # HR of another position
    started = client.post(scan_route, headers=headers(seed["hr2"]))
    assert started.status_code == 202, started.text
    assert started.json()["candidate_count"] == 1 and started.json()["status"] == "PENDING"
    assert client.post(scan_route, headers=headers(seed["hr2"])).status_code == 409  # one scan at a time

    worker._process_pending_operations()
    latest = client.get(f"{scan_route}/latest", headers=headers(seed["hr2"])).json()
    assert latest["scan"]["status"] == "COMPLETED" and latest["scan"]["scored_count"] == 1, latest
    result = latest["results"][0]
    assert result["application_id"] == pooled and result["rank_number"] == 1 and result["status"] == "SCORED"
    assert result["matching_status"] == "MEETS_MANDATORY" and result["email"] == "pool.candidate@example.org"
    assert result["criteria"][0]["quote"] == QUOTE and result["reason_code"] == "NEAR_MISS"
    with engine.connect() as conn:
        target_apps = conn.execute(text("SELECT COUNT(*) FROM app_private.applications WHERE position_id = :p"),
                                   {"p": seed["pos2"]}).scalar_one()
        target_runs = conn.execute(text("SELECT COUNT(*) FROM app_private.assessment_runs WHERE position_id = :p"),
                                   {"p": seed["pos2"]}).scalar_one()
        audit = conn.execute(text("""SELECT array_agg(action_type ORDER BY created_at) FROM app_private.audit_events
            WHERE action_type IN ('START_TALENT_POOL_SCAN', 'VIEW_TALENT_POOL_RESULTS')""")).scalar_one()
    assert target_apps == 1 and target_runs == 0  # only seed's own app2; nothing added or assessed there
    assert audit == ["START_TALENT_POOL_SCAN", "VIEW_TALENT_POOL_RESULTS"]

    # Consent withdrawn after the scan: the result disappears from the list.
    assert client.post(f"/v1/talent-pool/applications/{pooled}/withdraw-consent", headers=headers(seed["hr"]),
                       json={}).status_code == 200
    after = client.get(f"{scan_route}/latest", headers=headers(seed["hr2"])).json()
    assert after["results"] == [] and after["hidden_count"] == 1


@integration
def test_scan_skips_people_who_already_applied_to_the_position(client, portal, monkeypatch):
    seed = portal
    monkeypatch.setattr(settings, "PUBLIC_INTAKE_MAX_PER_IP_HOUR", 100)
    _stub_ai(monkeypatch, [])
    _pooled_portal_application(client, seed, email="Same.Person@Example.org")
    _approve_target_criteria(seed)
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.application_identities SET email = 'same.person@example.org' WHERE application_id = :a"),
                     {"a": seed["app2"]})
    started = client.post(f"/v1/talent-pool/positions/{seed['pos2']}/scans", headers=headers(seed["hr2"]))
    assert started.status_code == 202 and started.json()["candidate_count"] == 0


@integration
def test_failed_scan_is_reported_and_a_new_one_can_start(client, portal, monkeypatch):
    from app.workers.processor import worker
    seed = portal
    monkeypatch.setattr(settings, "PUBLIC_INTAKE_MAX_PER_IP_HOUR", 100)
    _stub_ai(monkeypatch, [])
    _pooled_portal_application(client, seed)
    cv, _ = _approve_target_criteria(seed)
    scan_route = f"/v1/talent-pool/positions/{seed['pos2']}/scans"
    assert client.post(scan_route, headers=headers(seed["hr2"])).status_code == 202
    with engine.begin() as conn:  # the rubric changes before the worker runs
        conn.execute(text("UPDATE app_private.criteria_versions SET status = 'REJECTED' WHERE criteria_version_id = :c"), {"c": cv})
    worker._process_pending_operations()
    failed = client.get(f"{scan_route}/latest", headers=headers(seed["hr2"])).json()["scan"]
    assert failed["status"] == "FAILED" and failed["error_message"]
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status = 'APPROVED' WHERE criteria_version_id = :c"), {"c": cv})
    assert client.post(scan_route, headers=headers(seed["hr2"])).status_code == 202
