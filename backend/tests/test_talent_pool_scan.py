"""P3-1 phase 2: scanning the Talent Pool against a new position (rules only)."""
from __future__ import annotations

import os

import pytest

from app.services.talent_pool_scan import score_cv

CRITERIA = [
    {"criterion_id": "c-py", "name": "Python", "description": "Python experience", "category": "MUST_HAVE",
     "weight_in_group": 100.0, "expected_evidence_keywords": ["Python"], "requirement_spec": None},
]
WEIGHTS = {"MUST_HAVE": 0.7, "NICE_TO_HAVE": 0.3}


def test_rules_only_scoring_keeps_verified_quotes():
    strong = score_cv("Kinh nghiệm\nPython developer, built Django services in Python for 3 years.", CRITERIA,
                      {"candidate_identifier": "x"}, WEIGHTS)
    assert strong["criterion_results"][0]["name"] == "Python"
    assert strong["criterion_results"][0]["outcome"] != "UNCLEAR"
    assert "Python" in (strong["criterion_results"][0]["quote"] or "")
    weak = score_cv("Kế toán tổng hợp, lập báo cáo thuế.", CRITERIA, {"candidate_identifier": "y"}, WEIGHTS)
    # Not decided by the rules: stays UNCLEAR and is counted for HR, never sent to an LLM.
    assert (strong["score"] or 0) >= (weak["score"] or 0)
    assert weak["unresolved_count"] + sum(1 for r in weak["criterion_results"] if r["outcome"] != "UNCLEAR") == 1


integration = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                 reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")

if os.environ.get("TEST_DATABASE_URL"):
    from sqlalchemy import text

    from app.core.config import settings
    from app.db.database import engine
    from test_phase1_integration import client, headers, seed, uid  # noqa: F401
    from test_public_intake_talent_pool import _consented_application


def _run_worker():
    from app.workers.processor import ProcessingWorker
    ProcessingWorker()._process_pending_operations()


def _scan_and_run(client, seed):
    """Queue a scan for pos2 as its HR and let the worker finish it."""
    queued = client.post(f"/v1/talent-pool/positions/{seed['pos2']}/scan", headers=headers(seed["hr2"]))
    assert queued.status_code == 202, queued.text
    _run_worker()
    return queued.json()


def _target_position(seed):
    """pos2 (HR: hr2) gets an approved rubric so it can be scanned."""
    jd, cv = uid(), uid()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.jd_versions(jd_version_id,position_id,version_number,content_text,created_by) VALUES (:id,:p,1,'JD',:u)"),
                     {"id": jd, "p": seed["pos2"], "u": seed["hr2"]})
        conn.execute(text("INSERT INTO app_private.criteria_versions(criteria_version_id,position_id,jd_version_id,version_number,status) VALUES (:id,:p,:jd,1,'APPROVED')"),
                     {"id": cv, "p": seed["pos2"], "jd": jd})
        conn.execute(text("""INSERT INTO app_private.criteria_items(criterion_id,criteria_version_id,name,description,category,weight_in_group,display_order,expected_evidence_keywords)
            VALUES (:id,:cv,'Python','Python experience','MUST_HAVE',100,1,'["Python"]'::jsonb)"""), {"id": uid(), "cv": cv})


def _with_text(app_id, body, tmp_path):
    path = f"{app_id}/cv.txt"
    full = tmp_path / settings.SUPABASE_STORAGE_BUCKET_EXTRACTED / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(body, encoding="utf-8")
    with engine.begin() as conn:
        doc = conn.execute(text("SELECT document_id FROM app_private.application_documents WHERE application_id = :a"),
                           {"a": app_id}).scalar_one()
        conn.execute(text("""INSERT INTO app_private.document_processing_runs(document_id, extraction_type, status, extracted_text_storage_path)
            VALUES (:d, 'INITIAL_EXTRACTION', 'COMPLETED', :p)"""), {"d": doc, "p": path})


@pytest.fixture
def pool(client, seed, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    _target_position(seed)
    hr = headers(seed["hr"])
    strong, weak, no_text, unmarked = (_consented_application(seed) for _ in range(4))
    for a in (strong, weak, no_text):
        assert client.post(f"/v1/talent-pool/applications/{a}/mark", headers=hr, json={"reason_code": "STRONG_FIT"}).status_code == 201
    _with_text(strong, "Kinh nghiệm\nPython developer at Acme, built Python services for 4 years.", tmp_path)
    _with_text(weak, "Kế toán tổng hợp, lập báo cáo thuế.", tmp_path)
    _with_text(unmarked, "Python developer.", tmp_path)
    return {"strong": strong, "weak": weak, "no_text": no_text, "unmarked": unmarked}


@integration
def test_scan_ranks_the_pool_with_evidence_and_no_pii(client, seed, pool):
    hr2 = headers(seed["hr2"])
    # Only HR of the target position (or HR Lead) may scan; HM and HR of another position may not.
    assert client.post(f"/v1/talent-pool/positions/{seed['pos2']}/scan", headers=headers(seed["hm"])).status_code == 403
    assert client.post(f"/v1/talent-pool/positions/{seed['pos2']}/scan", headers=headers(seed["hr"])).status_code == 403
    body = _scan_and_run(client, seed)

    scan = client.get(f"/v1/talent-pool/scans/{body['scan_id']}", headers=hr2)
    assert scan.status_code == 200
    head = scan.json()
    assert head["status"] == "COMPLETED" and head["completed_at"] and head["failed_count"] == 0
    assert head["eligible_count"] == 3 and head["scored_count"] == 2 and head["skipped_counts"] == {"NO_EXTRACTED_TEXT": 1}
    results = scan.json()["results"]
    assert [r["application_id"] for r in results][0] == pool["strong"]
    assert {r["application_id"] for r in results} == {pool["strong"], pool["weak"]}
    top = results[0]
    assert top["rank"] == 1 and top["source_position_id"] == seed["pos"] and top["pool_expires_on"]
    assert "Python" in (top["criterion_results"][0]["quote"] or "")
    assert "Pool" not in scan.text  # display names never appear
    assert client.get(f"/v1/talent-pool/scans/{body['scan_id']}", headers=headers(seed["hr"])).status_code == 403
    with engine.connect() as conn:
        audit = conn.execute(text("""SELECT metadata::text FROM app_private.audit_events
            WHERE action_type = 'SCAN_TALENT_POOL' ORDER BY created_at DESC LIMIT 1""")).scalar_one()
    assert "Pool" not in audit and '"scored_count": 2' in audit
    listed = client.get(f"/v1/talent-pool/positions/{seed['pos2']}/scans", headers=hr2).json()["items"]
    assert listed[0]["scan_id"] == body["scan_id"]


@integration
def test_withdrawn_candidate_disappears_from_results_and_cannot_be_decided(client, seed, pool):
    hr, hr2 = headers(seed["hr"]), headers(seed["hr2"])
    scan_id = _scan_and_run(client, seed)["scan_id"]
    route = f"/v1/talent-pool/scans/{scan_id}/results/{{}}/decision"
    assert client.post(route.format(pool["strong"]), headers=hr2, json={"decision": "MAYBE"}).status_code == 400
    assert client.post(route.format(pool["strong"]), headers=hr2, json={"decision": "CONTACT"}).status_code == 200
    # Consent withdrawn after the scan: the result is removed before anything is shown.
    assert client.post(f"/v1/talent-pool/applications/{pool['weak']}/withdraw-consent", headers=hr, json={}).status_code == 200
    assert client.post(route.format(pool["weak"]), headers=hr2, json={"decision": "LATER"}).status_code == 409
    results = client.get(f"/v1/talent-pool/scans/{scan_id}", headers=hr2).json()["results"]
    assert [(r["application_id"], r["hr_decision"]) for r in results] == [(pool["strong"], "CONTACT")]
    with engine.connect() as conn:
        left = conn.execute(text("SELECT COUNT(*) FROM app_private.talent_pool_scan_results WHERE scan_id = :s"),
                            {"s": scan_id}).scalar_one()
    assert left == 1


@integration
def test_scan_needs_an_open_position_with_approved_criteria(client, seed, pool):
    hr = headers(seed["hr"])
    # seed['pos'] has approved criteria (set by _assessed_application) but is closed here.
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET status = 'CLOSED', closed_at = NOW() WHERE position_id = :p"), {"p": seed["pos"]})
    assert client.post(f"/v1/talent-pool/positions/{seed['pos']}/scan", headers=hr).status_code == 409
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status = 'DRAFT' WHERE position_id = :p"), {"p": seed["pos2"]})
    assert client.post(f"/v1/talent-pool/positions/{seed['pos2']}/scan", headers=headers(seed["hr2"])).status_code == 409


@integration
def test_marks_list_is_scoped_to_the_source_position_hr(client, seed, pool):
    mine = client.get("/v1/talent-pool/marks", headers=headers(seed["hr"])).json()["items"]
    assert {i["application_id"] for i in mine} == {pool["strong"], pool["weak"], pool["no_text"]}
    assert all(i["eligible"] and i["expires_on"] for i in mine)
    assert client.get("/v1/talent-pool/marks", headers=headers(seed["hr2"])).json()["items"] == []


def _set_contact(app_id, email=None, phone=None):
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.application_identities SET email = :e, phone = :p WHERE application_id = :a"),
                     {"e": email, "p": phone, "a": app_id})


@integration
def test_scan_runs_in_the_worker_and_allows_one_active_scan_per_position(client, seed, pool):
    hr2, route = headers(seed["hr2"]), f"/v1/talent-pool/positions/{seed['pos2']}/scan"
    queued = client.post(route, headers=hr2)
    assert queued.status_code == 202
    scan_id, operation_id = queued.json()["scan_id"], queued.json()["operation_id"]
    pending = client.get(f"/v1/talent-pool/scans/{scan_id}", headers=hr2).json()
    assert pending["status"] == "PENDING" and pending["results"] == []
    assert client.post(route, headers=hr2).status_code == 409  # only one active scan per position
    _run_worker()
    done = client.get(f"/v1/talent-pool/scans/{scan_id}", headers=hr2).json()
    assert done["status"] == "COMPLETED" and len(done["results"]) == 2
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM app_private.operations WHERE operation_id = :o"),
                            {"o": operation_id}).scalar_one() == "COMPLETED"
    assert client.post(route, headers=hr2).status_code == 202  # a finished scan no longer blocks


@integration
def test_failed_scan_records_the_error_and_can_be_retried(client, seed, pool, monkeypatch):
    hr2, route = headers(seed["hr2"]), f"/v1/talent-pool/positions/{seed['pos2']}/scan"
    from app.services import talent_pool_scan

    def boom(*args, **kwargs):
        raise RuntimeError("secret detail must not leak")
    with monkeypatch.context() as patch:
        patch.setattr(talent_pool_scan, "run_scan", boom)
        scan_id = client.post(route, headers=hr2).json()["scan_id"]
        _run_worker()
    failed = client.get(f"/v1/talent-pool/scans/{scan_id}", headers=hr2).json()
    assert failed["status"] == "FAILED" and failed["completed_at"] and failed["results"] == []
    assert failed["error_message"] and "secret" not in failed["error_message"]

    # The position closing before the worker picks the job up is reported as the failure reason.
    scan_id = client.post(route, headers=hr2).json()["scan_id"]
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET status = 'CLOSED', closed_at = NOW() WHERE position_id = :p"), {"p": seed["pos2"]})
    _run_worker()
    failed = client.get(f"/v1/talent-pool/scans/{scan_id}", headers=hr2).json()
    assert failed["status"] == "FAILED" and "đang mở" in failed["error_message"]
    listed = client.get(f"/v1/talent-pool/positions/{seed['pos2']}/scans", headers=hr2).json()["items"]
    assert [i["status"] for i in listed] == ["FAILED", "FAILED"]


@integration
def test_scan_skips_candidates_who_already_applied_and_duplicate_emails(client, seed, pool, tmp_path):
    hr2 = headers(seed["hr2"])
    # A candidate already in the target position (email in another case, phone in another format).
    _set_contact(seed["app2"], email="Applied@Example.com", phone="+84 901 234 567")
    _set_contact(pool["strong"], email=" applied@example.COM ")
    _set_contact(pool["weak"], phone="0901234567")
    second = _consented_application(seed)
    third = _consented_application(seed)
    for a, mail in ((second, "Dup@Example.com"), (third, "dup@example.com")):
        assert client.post(f"/v1/talent-pool/applications/{a}/mark", headers=headers(seed["hr"]),
                           json={"reason_code": "STRONG_FIT"}).status_code == 201
        _set_contact(a, email=mail)
    _with_text(second, "Kế toán tổng hợp.", tmp_path)
    _with_text(third, "Python developer, built Python services for 5 years.", tmp_path)

    scan_id = _scan_and_run(client, seed)["scan_id"]
    scan = client.get(f"/v1/talent-pool/scans/{scan_id}", headers=hr2).json()
    assert scan["skipped_counts"] == {"ALREADY_APPLIED": 2, "NO_EXTRACTED_TEXT": 1, "DUPLICATE_EMAIL": 1}
    # The better of the two duplicate-email applications is the one kept.
    assert [r["application_id"] for r in scan["results"]] == [third]
    assert scan["eligible_count"] == 5 and scan["scored_count"] == 1
