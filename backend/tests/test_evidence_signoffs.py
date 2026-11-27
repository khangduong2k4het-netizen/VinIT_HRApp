"""Closed-loop HR Evidence Sign-Off & P3-2 calibration tests."""
import os
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from app.api.evidence_signoffs import EvidenceSignoffInput


# ---------------------------------------------------------------- unit tests

def test_signoff_input_requires_reason_when_disputed():
    with pytest.raises(ValidationError):
        EvidenceSignoffInput(verdict="DISPUTED")
    with pytest.raises(ValidationError):
        EvidenceSignoffInput(verdict="DISPUTED", reason_code="INVALID_CODE")

    disputed = EvidenceSignoffInput(verdict="DISPUTED", reason_code="WRONG_QUOTE", note="  Trích sai đoạn  ")
    assert disputed.verdict == "DISPUTED"
    assert disputed.reason_code == "WRONG_QUOTE"
    assert disputed.note == "Trích sai đoạn"

    confirmed = EvidenceSignoffInput(verdict="CONFIRMED", reason_code="WRONG_QUOTE", note="   ")
    assert confirmed.verdict == "CONFIRMED"
    assert confirmed.reason_code is None
    assert confirmed.note is None


# ---------------------------------------------------------- integration tests

integration = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database",
)

if os.environ.get("TEST_DATABASE_URL"):
    from app.db.database import engine
    from test_hr_analytics import _assessed_application
    from test_phase1_integration import client, headers, seed, uid  # noqa: F401


def _insert_criterion_results(seed, application_id):
    with engine.begin() as conn:
        assessment_id = conn.execute(
            text("SELECT assessment_id FROM app_private.assessment_runs WHERE application_id = :a"),
            {"a": application_id},
        ).scalar_one()
        criteria = conn.execute(
            text("""
                SELECT criterion_id::text AS criterion_id, name
                FROM app_private.criteria_items
                WHERE criteria_version_id = :cv
                ORDER BY display_order, criterion_id
            """),
            {"cv": seed["cv"]},
        ).mappings().all()
        if not criteria:
            c1 = str(uuid4())
            c2 = str(uuid4())
            conn.execute(
                text("""
                    INSERT INTO app_private.criteria_items
                        (criterion_id, criteria_version_id, name, description, category, weight_in_group, display_order)
                    VALUES
                        (:c1, :cv, 'Python Backend', 'Python', 'MUST_HAVE', 60, 1),
                        (:c2, :cv, 'SQL Modeling', 'SQL', 'NICE_TO_HAVE', 40, 2)
                """),
                {"c1": c1, "c2": c2, "cv": seed["cv"]},
            )
            criteria = [{"criterion_id": c1, "name": "Python Backend"}, {"criterion_id": c2, "name": "SQL Modeling"}]
        result_ids = []
        for c in criteria[:2]:
            rid = conn.execute(
                text("""
                    INSERT INTO app_private.criterion_assessment_results
                        (assessment_id, criterion_id, outcome, score, confidence, reasoning)
                    VALUES (:a, :c, 'MATCH', 85, 0.9, 'Evidence matched')
                    RETURNING result_id::text
                """),
                {"a": assessment_id, "c": c["criterion_id"]},
            ).scalar_one()
            result_ids.append(rid)
        return result_ids


@integration
def test_evidence_signoff_closed_loop_and_permissions(client, seed):
    app_id = _assessed_application(seed, "MEETS_MANDATORY", "Evidence Candidate")
    result_ids = _insert_criterion_results(seed, app_id)
    assert len(result_ids) >= 1
    r1 = result_ids[0]
    r2 = result_ids[1] if len(result_ids) > 1 else None

    # Disputed without reason_code fails validation (422).
    bad = client.post(
        f"/v1/assessments/results/{r1}/signoff",
        headers=headers(seed["hr"]),
        json={"verdict": "DISPUTED"},
    )
    assert bad.status_code == 422

    # Hiring Manager and unrelated HR cannot sign off on evidence.
    hm_post = client.post(
        f"/v1/assessments/results/{r1}/signoff",
        headers=headers(seed["hm"]),
        json={"verdict": "CONFIRMED"},
    )
    assert hm_post.status_code == 403
    other_hr_post = client.post(
        f"/v1/assessments/results/{r1}/signoff",
        headers=headers(seed["hr2"]),
        json={"verdict": "CONFIRMED"},
    )
    assert other_hr_post.status_code == 403

    # HR first confirms r1, then disputes r1 -> latest verdict (DISPUTED) must win with NO double counting.
    c1 = client.post(
        f"/v1/assessments/results/{r1}/signoff",
        headers=headers(seed["hr"]),
        json={"verdict": "CONFIRMED"},
    )
    assert c1.status_code == 201
    assert c1.json()["verdict"] == "CONFIRMED"

    secret_note = "Ứng viên Nguyễn Văn A có 5 năm kinh nghiệm ở trang 2"
    d1 = client.post(
        f"/v1/assessments/results/{r1}/signoff",
        headers=headers(seed["hr"]),
        json={"verdict": "DISPUTED", "reason_code": "WRONG_QUOTE", "note": secret_note},
    )
    assert d1.status_code == 201
    assert d1.json()["verdict"] == "DISPUTED"
    assert d1.json()["reason_code"] == "WRONG_QUOTE"

    if r2:
        c2 = client.post(
            f"/v1/assessments/results/{r2}/signoff",
            headers=headers(seed["hr"]),
            json={"verdict": "CONFIRMED"},
        )
        assert c2.status_code == 201

    # Application GET returns latest verdict per result_id.
    got = client.get(
        f"/v1/assessments/applications/{app_id}/signoffs",
        headers=headers(seed["hr"]),
    )
    assert got.status_code == 200
    signoffs = got.json()["signoffs"]
    assert signoffs[r1]["verdict"] == "DISPUTED"
    assert signoffs[r1]["reason_code"] == "WRONG_QUOTE"
    if r2:
        assert signoffs[r2]["verdict"] == "CONFIRMED"

    # Closed-loop calibration feeds into P3-2 without double counting r1.
    cal = client.get("/v1/analytics/quality/evidence-calibration", headers=headers(seed["hr"]))
    assert cal.status_code == 200
    body = cal.json()
    expected_total = 2 if r2 else 1
    assert body["total_reviewed"] == expected_total
    assert body["disputed_count"] == 1
    assert body["confirmed_count"] == (1 if r2 else 0)
    assert body["by_reason"] == [{"reason_code": "WRONG_QUOTE", "count": 1, "share": 1.0}]
    assert len(body["top_disputed_criteria"]) == 1
    assert body["top_disputed_criteria"][0]["disputed_count"] == 1
    # Never leaks recruiter identity or free-text notes.
    serialized = str(body)
    assert seed["hr"] not in serialized
    assert secret_note not in serialized

    # Hiring Manager cannot access calibration metrics.
    hm_cal = client.get("/v1/analytics/quality/evidence-calibration", headers=headers(seed["hm"]))
    assert hm_cal.status_code == 403

    # Audit event exists and contains no free-text note / PII.
    with engine.connect() as conn:
        audits = conn.execute(
            text("""
                SELECT action_type, object_type, metadata::text AS meta
                FROM app_private.audit_events
                WHERE action_type = 'REVIEW_CRITERION_EVIDENCE' AND object_id = :rid
                ORDER BY created_at DESC
            """),
            {"rid": r1},
        ).mappings().all()
    assert len(audits) == 2
    assert all(secret_note not in (a["meta"] or "") for a in audits)
