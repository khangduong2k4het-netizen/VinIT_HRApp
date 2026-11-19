"""Phase 1 completion: S-19 cross-position retention queue and S-20 audit log viewer."""
import os

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")

if os.environ.get("TEST_DATABASE_URL"):
    from app.db.database import engine
    from test_phase1_integration import client, headers, seed, uid  # noqa: F401 (pytest fixtures)


def _due_case(seed, position="pos", app="app"):
    case_id = uid()
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE app_private.positions SET status = 'CLOSED', closed_at = NOW() - INTERVAL '13 months'
            WHERE position_id = :p
        """), {"p": seed[position]})
        conn.execute(text("""
            INSERT INTO app_private.application_retention_cases
                (retention_case_id, application_id, position_id, application_opaque_id,
                 policy_version, position_closed_at, due_date, status)
            VALUES (:id, :app, :p, repeat('b', 64), 'v1.0-12month',
                    NOW() - INTERVAL '13 months', NOW() - INTERVAL '1 month', 'PENDING')
        """), {"id": case_id, "app": seed[app], "p": seed[position]})
    return case_id


def test_retention_queue_is_scoped_and_reports_confirm_rights(client, seed):
    mine = _due_case(seed)
    other = _due_case(seed, "pos2", "app2")
    hr = client.get("/v1/retention/queue", headers=headers(seed["hr"]))
    assert hr.status_code == 200, hr.text
    body = hr.json()
    assert [c["retention_case_id"] for c in body["cases"]] == [mine]  # pos2 belongs to another recruiter
    case = body["cases"][0]
    assert case["position_title"] == "pos" and case["is_due"] is True
    assert case["can_confirm"] is False  # a recruiter needs HR_LEAD or a CONFIRM_DELETION grant
    assert [p["position_id"] for p in body["closed_positions"]] == [seed["pos"]]
    assert "application_identities" not in str(body) and "Candidate" not in str(body)

    hm_queue = client.get("/v1/retention/queue", headers=headers(seed["hm"])).json()
    assert hm_queue["cases"] == [] and hm_queue["closed_positions"] == []
    assert client.get("/v1/retention/queue", headers=headers(seed["hr"]), params={"status": "BOGUS"}).status_code == 400
    assert client.get("/v1/retention/queue", headers=headers(seed["hr"]), params={"status": "DELETED"}).json()["cases"] == []

    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id, role_code) VALUES (:u, 'HR_LEAD')"),
                     {"u": seed["other"]})
    lead = client.get("/v1/retention/queue", headers=headers(seed["other"])).json()
    assert {c["retention_case_id"] for c in lead["cases"]} == {mine, other}
    assert all(c["can_confirm"] for c in lead["cases"])


def test_audit_log_is_admin_only_filterable_and_hides_metadata(client, seed):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id, role_code) VALUES (:u, 'ADMIN')"),
                     {"u": seed["other"]})
        conn.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
            VALUES (:hr, 'UPDATE_POSITION', 'POSITION', :p, :p, 'SUCCESS', '{"secret": "do-not-leak"}'::jsonb),
                   (:hr, 'SHARE_SHORTLIST', 'SHORTLIST_SHARE', :p, :p, 'SUCCESS', NULL),
                   (:hm, 'REVIEW_CRITERIA', 'CRITERIA_VERSION', :p, :p2, 'APPROVED', NULL)
        """), {"hr": seed["hr"], "hm": seed["hm"], "p": seed["pos"], "p2": seed["pos2"]})
    route = "/v1/admin/audit/events"
    assert client.get(route, headers=headers(seed["hr"])).status_code == 403
    admin = headers(seed["other"])
    everything = client.get(route, headers=admin)
    assert everything.status_code == 200, everything.text
    body = everything.json()
    assert body["total"] >= 3 and "do-not-leak" not in str(body) and "metadata" not in body["items"][0]
    assert {"UPDATE_POSITION", "SHARE_SHORTLIST", "REVIEW_CRITERIA"} <= set(body["action_types"])
    first = next(i for i in body["items"] if i["action_type"] == "UPDATE_POSITION")
    assert first["actor_name"] == "HR" and first["position_title"] == "pos"

    by_action = client.get(route, headers=admin, params={"action_type": "SHARE_SHORTLIST"}).json()
    assert {i["action_type"] for i in by_action["items"]} == {"SHARE_SHORTLIST"}
    by_actor = client.get(route, headers=admin, params={"actor_user_id": seed["hm"]}).json()
    assert by_actor["items"] and {i["actor_user_id"] for i in by_actor["items"]} == {seed["hm"]}
    by_position = client.get(route, headers=admin, params={"position_id": seed["pos2"]}).json()
    assert [i["action_type"] for i in by_position["items"]] == ["REVIEW_CRITERIA"]
    future = client.get(route, headers=admin, params={"date_from": "2999-01-01"}).json()
    assert future["total"] == 0 and future["items"] == []
    paged = client.get(route, headers=admin, params={"page_size": 1, "page": 2}).json()
    assert len(paged["items"]) == 1 and paged["total"] == body["total"]
    assert client.get(route, headers=admin, params={"action_type": "x;drop"}).status_code == 400
    assert client.get(route, headers=admin, params={"date_from": "11/12/2026"}).status_code == 400
