"""Interview Coordination, panelist conflict checks, RFC 5545 .ics export & AI Prep Brief."""
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.db.database import engine
from app.services.interview_calendar import build_ics, build_prep_brief, format_vn_slot

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")

if os.environ.get("TEST_DATABASE_URL"):
    from test_phase1_integration import client, headers, seed  # noqa: F401


def test_calendar_ics_and_prep_brief_helpers_are_pii_free_and_ordered():
    start = datetime(2026, 12, 1, 2, 0, tzinfo=timezone.utc)  # 09:00 GMT+7
    end = datetime(2026, 12, 1, 3, 0, tzinfo=timezone.utc)    # 10:00 GMT+7
    assert format_vn_slot(start, end) == "09:00 - 10:00, 01/12/2026 (GMT+7)"
    ics = build_ics(
        session_id="sess-1", position_code="REQ-IT-101", position_title="Backend Engineer",
        round_no=1, title="Phỏng vấn kỹ thuật", starts_at=start, ends_at=end,
        fmt="ONLINE", location_or_link="https://meet.vinuni.edu.vn/room-1",
    ).decode("utf-8")
    assert "BEGIN:VCALENDAR" in ics and "DTSTART:20261201T020000Z" in ics and "DTEND:20261201T030000Z" in ics
    assert "REQ-IT-101" in ics and "https://meet.vinuni.edu.vn/room-1" in ics

    brief = build_prep_brief([
        {"criterion_id": "c1", "criterion_name": "Python", "category": "MUST_HAVE", "outcome": "STRONG_MATCH", "requires_verification": False, "quote": "5 years Python", "page_number": 1},
        {"criterion_id": "c2", "criterion_name": "Kubernetes", "category": "NICE_TO_HAVE", "outcome": "UNCLEAR", "requires_verification": False, "quote": None, "page_number": None},
        {"criterion_id": "c3", "criterion_name": "PostgreSQL", "category": "MUST_HAVE", "outcome": "UNCLEAR", "requires_verification": True, "quote": "Worked with SQL", "page_number": 2},
    ])
    assert brief["probe_count"] == 2 and brief["strength_count"] == 1
    assert brief["probe_points"][0]["criterion_name"] == "PostgreSQL"  # MUST_HAVE high priority first
    assert brief["strengths"][0]["criterion_name"] == "Python"


def test_schedule_conflict_detection_rbac_ics_and_status_update(client, seed):
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET position_code = 'REQ-IT-888', title = 'AI Engineer' WHERE position_id = :p"),
                     {"p": seed["pos"]})
        # Add a second application in pos so we can test panelist conflict across candidates.
        app2 = conn.execute(text("""
            INSERT INTO app_private.applications (position_id, application_status, source_code)
            VALUES (:p, 'SHORTLIST', 'MANUAL') RETURNING application_id
        """), {"p": seed["pos"]}).scalar_one()

    start = (datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=2, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=1)
    payload = {
        "round_no": 1,
        "title": "Phỏng vấn vòng 1",
        "starts_at": start.isoformat(),
        "ends_at": end.isoformat(),
        "format": "ONLINE",
        "location_or_link": "https://teams.microsoft.com/l/meetup-join/demo",
        "panelists": [{"user_id": seed["hm"], "panel_role": "LEAD_INTERVIEWER"}],
    }

    # Hiring Manager and unrelated HR cannot schedule.
    assert client.post(f"/v1/interviews/applications/{seed['app']}", headers=headers(seed["hm"]), json=payload).status_code == 403
    assert client.post(f"/v1/interviews/applications/{seed['app']}", headers=headers(seed["hr2"]), json=payload).status_code == 403

    # Position HR schedules round 1.
    created = client.post(f"/v1/interviews/applications/{seed['app']}", headers=headers(seed["hr"]), json=payload)
    assert created.status_code == 201, created.text
    sid = created.json()["session_id"]
    assert created.json()["round_no"] == 1 and len(created.json()["panelists"]) == 1

    # Duplicate active round 1 on the same application -> 409.
    dup = client.post(f"/v1/interviews/applications/{seed['app']}", headers=headers(seed["hr"]), json={
        **payload, "starts_at": (start + timedelta(hours=3)).isoformat(), "ends_at": (end + timedelta(hours=3)).isoformat(),
    })
    assert dup.status_code == 409

    # Overlapping panelist on another application -> 409 with structured conflict details (no candidate PII).
    conflict = client.post(f"/v1/interviews/applications/{app2}", headers=headers(seed["hr"]), json=payload)
    assert conflict.status_code == 409
    assert isinstance(conflict.json()["detail"], dict) and len(conflict.json()["detail"]["conflicts"]) == 1

    # Explicit allow_conflict=True succeeds.
    forced = client.post(f"/v1/interviews/applications/{app2}", headers=headers(seed["hr"]), json={**payload, "allow_conflict": True})
    assert forced.status_code == 201 and len(forced.json()["conflicts"]) == 1

    # HM (panelist) sees the interview in /my-schedule and can download .ics; unrelated hr2 sees nothing and gets 403 on .ics.
    hm_sched = client.get("/v1/interviews/my-schedule", headers=headers(seed["hm"]),
                          params={"from_date": (start - timedelta(days=1)).isoformat(), "to_date": (end + timedelta(days=1)).isoformat()})
    assert hm_sched.status_code == 200 and any(item["session_id"] == sid for item in hm_sched.json()["items"])
    hr2_sched = client.get("/v1/interviews/my-schedule", headers=headers(seed["hr2"]),
                           params={"from_date": (start - timedelta(days=1)).isoformat(), "to_date": (end + timedelta(days=1)).isoformat()})
    assert hr2_sched.status_code == 200 and hr2_sched.json()["items"] == []

    ics_ok = client.get(f"/v1/interviews/{sid}/calendar.ics", headers=headers(seed["hm"]))
    assert ics_ok.status_code == 200 and "BEGIN:VEVENT" in ics_ok.text
    assert "interview-REQ-IT-888-round-1.ics" in ics_ok.headers["content-disposition"]
    assert client.get(f"/v1/interviews/{sid}/calendar.ics", headers=headers(seed["hr2"])).status_code == 403

    # HR marks session COMPLETED.
    upd = client.patch(f"/v1/interviews/{sid}", headers=headers(seed["hr"]), json={"session_status": "COMPLETED"})
    assert upd.status_code == 200 and upd.json()["session_status"] == "COMPLETED"


def test_panelist_must_be_active_and_position_eligible_and_prep_brief_queries_evidence(client, seed):
    from uuid import uuid4
    from test_hr_analytics import _assessed_application

    app_id = _assessed_application(seed, "NEEDS_HR_VERIFICATION", "Brief Candidate")
    with engine.begin() as conn:
        aid = conn.execute(
            text("SELECT assessment_id FROM app_private.assessment_runs WHERE application_id = :a"),
            {"a": app_id},
        ).scalar_one()
        cid = conn.execute(
            text("SELECT criterion_id FROM app_private.criteria_items WHERE criteria_version_id = :cv LIMIT 1"),
            {"cv": seed["cv"]},
        ).scalar_one_or_none()
        if not cid:
            cid = str(uuid4())
            conn.execute(text("""
                INSERT INTO app_private.criteria_items
                    (criterion_id, criteria_version_id, name, description, category, weight_in_group, display_order)
                VALUES (:c, :cv, 'System Design', 'Distributed systems', 'MUST_HAVE', 100, 1)
            """), {"c": cid, "cv": seed["cv"]})
        rid = conn.execute(text("""
            INSERT INTO app_private.criterion_assessment_results
                (assessment_id, criterion_id, outcome, score, confidence, reasoning, requires_hr_verification)
            VALUES (:a, :c, 'UNCLEAR', 40, 0.5, 'Need interview check', TRUE)
            RETURNING result_id
        """), {"a": aid, "c": cid}).scalar_one()
        doc_id = conn.execute(text("""
            INSERT INTO app_private.application_documents
                (application_id, document_type, bucket, storage_path, original_filename, mime_type, size_bytes, file_processing_status)
            VALUES (:a, 'CV', 'cv', 'test/brief.pdf', 'brief.pdf', 'application/pdf', 1024, 'COMPLETED')
            RETURNING document_id
        """), {"a": app_id}).scalar_one()
        conn.execute(text("""
            INSERT INTO app_private.evidence_items
                (criterion_result_id, source_document_id, verbatim_quote, page_number, verification_status)
            VALUES (:r, :d, 'Built internal API gateway', 1, 'VERIFIED')
        """), {"r": rid, "d": doc_id})

        # Create a disabled user who even has a position assignment — must still be rejected.
        inactive_uid = str(uuid4())
        conn.execute(text("""
            INSERT INTO auth.users (id, email) VALUES (:u, 'disabled-panelist@example.com')
        """), {"u": inactive_uid})
        conn.execute(text("""
            INSERT INTO app_private.user_profiles (user_id, display_name, account_status)
            VALUES (:u, 'Suspended Reviewer', 'SUSPENDED')
        """), {"u": inactive_uid})
        conn.execute(text("""
            INSERT INTO app_private.position_assignments (position_id, user_id, position_role)
            VALUES (:p, :u, 'HIRING_MANAGER')
        """), {"p": seed["pos"], "u": inactive_uid})

    start = (datetime.now(timezone.utc) + timedelta(days=5)).replace(hour=2, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=1)
    base = {
        "round_no": 1,
        "title": "Vòng kiểm tra quyền hội đồng",
        "starts_at": start.isoformat(),
        "ends_at": end.isoformat(),
        "format": "ONLINE",
        "location_or_link": "https://meet.vinuni.edu.vn/check",
    }

    # Unrelated active HR (not assigned to this position) -> 400.
    bad_unrelated = client.post(
        f"/v1/interviews/applications/{app_id}",
        headers=headers(seed["hr"]),
        json={**base, "panelists": [{"user_id": seed["hr2"], "panel_role": "INTERVIEWER"}]},
    )
    assert bad_unrelated.status_code == 400

    # Disabled user even with position assignment -> 400.
    bad_inactive = client.post(
        f"/v1/interviews/applications/{app_id}",
        headers=headers(seed["hr"]),
        json={**base, "panelists": [{"user_id": inactive_uid, "panel_role": "INTERVIEWER"}]},
    )
    assert bad_inactive.status_code == 400

    # Eligible active HM on this position succeeds -> 201, and PATCH also rejects ineligible panelists.
    ok = client.post(
        f"/v1/interviews/applications/{app_id}",
        headers=headers(seed["hr"]),
        json={**base, "panelists": [{"user_id": seed["hm"], "panel_role": "LEAD_INTERVIEWER"}]},
    )
    assert ok.status_code == 201, ok.text
    sid = ok.json()["session_id"]

    bad_patch = client.patch(
        f"/v1/interviews/{sid}",
        headers=headers(seed["hr"]),
        json={"panelists": [{"user_id": inactive_uid, "panel_role": "OBSERVER"}]},
    )
    assert bad_patch.status_code == 400

    # GET /applications/{app_id} synthesizes the real AI Prep Brief from criterion_assessment_results + evidence_items.
    detail = client.get(f"/v1/interviews/applications/{app_id}", headers=headers(seed["hr"]))
    assert detail.status_code == 200, detail.text
    brief = detail.json()["prep_brief"]
    assert brief["probe_count"] == 1
    assert brief["probe_points"][0]["evidence_quote"] == "Built internal API gateway"
    assert brief["probe_points"][0]["page_number"] == 1
