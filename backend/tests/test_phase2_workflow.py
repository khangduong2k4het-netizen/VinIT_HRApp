"""Phase 2 batch 1: F2.01 rubric library and F2.02 scorecards."""
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.services.workflow_rules import add_business_days, scorecard_completion_errors, template_publish_errors

# ---------------------------------------------------------------- unit tests

ITEMS_OK = [
    {"name": "Python", "description": "3 years", "category": "MUST_HAVE", "weight_in_group": 60},
    {"name": "SQL", "description": "Relational DBs", "category": "MUST_HAVE", "weight_in_group": 40},
    {"name": "Docker", "description": "Containers", "category": "NICE_TO_HAVE", "weight_in_group": 100},
]


def test_template_publish_rules_accept_a_complete_rubric():
    assert template_publish_errors(Decimal("70"), Decimal("30"), ITEMS_OK) == []
    only_must = [{**ITEMS_OK[0], "weight_in_group": 100}]
    assert template_publish_errors(100, 0, only_must) == []


@pytest.mark.parametrize("mandatory, nice, items, fragment", [
    (60, 30, ITEMS_OK, "Tổng trọng số nhóm"),
    (70, 30, [], "ít nhất một tiêu chí"),
    (70, 30, [{**ITEMS_OK[2]}], "Bắt buộc có trọng số"),
    (70, 30, [ITEMS_OK[0], ITEMS_OK[2]], "nhóm Bắt buộc phải bằng 100%"),
    (70, 30, [{**ITEMS_OK[0], "weight_in_group": 100}], "chưa có tiêu chí"),
    (70, 30, [*ITEMS_OK[:2], {**ITEMS_OK[2], "weight_in_group": 50}], "nhóm Ưu tiên phải bằng 100%"),
    (100, 0, [{"name": "Under 30", "description": "Young team", "category": "MUST_HAVE", "weight_in_group": 100}],
     "thông tin cá nhân"),
])
def test_template_publish_rules_reject_invalid_rubrics(mandatory, nice, items, fragment):
    assert any(fragment in error for error in template_publish_errors(mandatory, nice, items))


def test_default_due_date_skips_weekends():
    friday = datetime(2026, 11, 13, 9, 0, tzinfo=timezone.utc)
    assert friday.weekday() == 4
    assert add_business_days(friday) == datetime(2026, 11, 18, 9, 0, tzinfo=timezone.utc)  # Wednesday
    monday = datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc)
    assert add_business_days(monday) == datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)


def test_scorecard_completion_requires_every_criterion_and_recommendation():
    rows = [{"criterion_id": "a", "name": "Python", "rating": 4, "evidence_assessment": None},
            {"criterion_id": "b", "name": "SQL", "rating": None, "evidence_assessment": "INSUFFICIENT_EVIDENCE"}]
    assert scorecard_completion_errors(rows, "YES") == []
    assert any("khuyến nghị" in e for e in scorecard_completion_errors(rows, None))
    missing = [*rows, {"criterion_id": "c", "name": "Docker", "rating": None, "evidence_assessment": None}]
    assert any("Docker" in e for e in scorecard_completion_errors(missing, "YES"))
    assert scorecard_completion_errors([], "YES")


# ---------------------------------------------------------- integration tests

integration = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                 reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")

if os.environ.get("TEST_DATABASE_URL"):
    from app.db.database import engine
    from test_phase1_integration import client, headers, seed, uid  # noqa: F401 (pytest fixtures)


@pytest.fixture
def lead(seed):
    """An HR Lead (publisher) in addition to the Phase 1 seed users."""
    lead_id = uid()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO auth.users(id) VALUES (:id)"), {"id": lead_id})
        conn.execute(text("INSERT INTO app_private.user_profiles(user_id, display_name) VALUES (:id, 'LEAD')"), {"id": lead_id})
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id, role_code) VALUES (:id, 'HR_LEAD')"), {"id": lead_id})
    return lead_id


SEEDED_FAMILIES = {"IT_DIGITAL": "IT & Digital", "RESEARCH": "Research"}


def _family(conn, code="IT_DIGITAL"):
    # test_accounts TRUNCATEs auth.users CASCADE, which also empties job_families
    # (created_by FK); restore the migration-seeded rows this module relies on.
    conn.execute(text("INSERT INTO app_private.job_families (code, name) VALUES (:c, :n) ON CONFLICT (code) DO NOTHING"),
                 {"c": code, "n": SEEDED_FAMILIES[code]})
    return str(conn.execute(text("SELECT job_family_id FROM app_private.job_families WHERE code = :c"), {"c": code}).scalar_one())


@pytest.fixture(autouse=True)
def _seeded_families():
    if os.environ.get("TEST_DATABASE_URL"):
        with engine.begin() as conn:
            for code in SEEDED_FAMILIES:
                _family(conn, code)


def _published_template(client, seed, lead, *, level="Senior"):
    with engine.connect() as conn:
        family = _family(conn)
    created = client.post("/v1/rubric-library/templates", headers=headers(seed["hr"]),
                          json={"job_family_id": family, "title": f"Backend {uid()[:8]}", "level_band": level})
    assert created.status_code == 201, created.text
    version = created.json()["draft_version_id"]
    for item in ITEMS_OK:
        r = client.post(f"/v1/rubric-library/template-versions/{version}/items", headers=headers(seed["hr"]),
                        json={**item, "expected_evidence_keywords": [item["name"]]})
        assert r.status_code == 201, r.text
    published = client.post(f"/v1/rubric-library/template-versions/{version}/publish", headers=headers(lead), json={})
    assert published.status_code == 200, published.text
    return created.json()["template_id"], version


@integration
def test_rubric_library_roles_lifecycle_and_immutability(client, seed, lead):
    hr, hm = headers(seed["hr"]), headers(seed["hm"])
    assert client.get("/v1/rubric-library/families", headers=hm).status_code == 403
    families = client.get("/v1/rubric-library/families", headers=hr)
    assert families.status_code == 200 and {f["code"] for f in families.json()} >= {"IT_DIGITAL", "RESEARCH"}
    # Only Admin/HR Lead manage families; codes are unique.
    assert client.post("/v1/rubric-library/families", headers=hr, json={"code": "LAB", "name": "Lab"}).status_code == 403
    code = "LAB_" + uid()[:6].upper()
    family = client.post("/v1/rubric-library/families", headers=headers(lead), json={"code": code, "name": "Lab"})
    assert family.status_code == 201
    assert client.post("/v1/rubric-library/families", headers=headers(lead), json={"code": code, "name": "Dup"}).status_code == 409
    inactive = client.patch(f"/v1/rubric-library/families/{family.json()['job_family_id']}", headers=headers(lead), json={"status": "INACTIVE"})
    assert inactive.status_code == 200
    assert client.post("/v1/rubric-library/templates", headers=hr,
                       json={"job_family_id": family.json()["job_family_id"], "title": "X"}).status_code == 400

    with engine.connect() as conn:
        it_family = _family(conn)
    created = client.post("/v1/rubric-library/templates", headers=hr, json={"job_family_id": it_family, "title": "QA Engineer"})
    version = created.json()["draft_version_id"]
    base = f"/v1/rubric-library/template-versions/{version}"
    item = client.post(base + "/items", headers=hr, json={"name": "Testing", "description": "pytest", "category": "MUST_HAVE",
                                                          "weight_in_group": 60}).json()
    # Publishing needs HR Lead and valid weights.
    assert client.post(base + "/publish", headers=hr, json={}).status_code == 403
    invalid = client.post(base + "/publish", headers=headers(lead), json={})
    assert invalid.status_code == 400 and "100%" in invalid.json()["detail"]
    assert client.get(base, headers=hr).json()["publish_errors"]
    assert client.patch(f"/v1/rubric-library/template-items/{item['template_item_id']}", headers=hr,
                        json={"weight_in_group": 100}).status_code == 200
    assert client.patch(base, headers=hr, json={"mandatory_weight_total": 100, "nice_to_have_weight_total": 0}).status_code == 200
    # Another HR recruiter cannot edit someone else's draft.
    assert client.patch(base, headers=headers(seed["hr2"]), json={"change_note": "x"}).status_code == 403
    published = client.post(base + "/publish", headers=headers(lead), json={"comment": "OK"})
    assert published.status_code == 200 and published.json()["status"] == "PUBLISHED"
    assert published.json()["review_events"][0]["decision"] == "PUBLISH"
    # Published versions are immutable.
    assert client.post(base + "/items", headers=hr, json={"name": "Y", "description": "Y", "category": "MUST_HAVE",
                                                          "weight_in_group": 1}).status_code == 400
    assert client.delete(f"/v1/rubric-library/template-items/{item['template_item_id']}", headers=headers(lead)).status_code == 400

    # A new version copies items; publishing it archives the previous one atomically.
    template_id = created.json()["template_id"]
    v2 = client.post(f"/v1/rubric-library/templates/{template_id}/versions", headers=hr, json={"change_note": "v2"})
    assert v2.status_code == 201 and v2.json()["version_number"] == 2 and len(v2.json()["items"]) == 1
    assert client.post(f"/v1/rubric-library/templates/{template_id}/versions", headers=hr, json={}).status_code == 409
    assert client.post(f"/v1/rubric-library/template-versions/{v2.json()['template_version_id']}/publish",
                       headers=headers(lead), json={}).status_code == 200
    detail = client.get(f"/v1/rubric-library/templates/{template_id}", headers=hr).json()
    assert [(v["version_number"], v["status"]) for v in detail["versions"]] == [(2, "PUBLISHED"), (1, "ARCHIVED")]
    listing = client.get("/v1/rubric-library/templates", headers=hr, params={"status": "PUBLISHED", "q": "QA Engineer"}).json()
    assert [t["template_id"] for t in listing] == [template_id]
    with engine.connect() as conn:
        actions = set(conn.execute(text("SELECT action_type FROM app_private.audit_events WHERE object_id = :id"),
                                   {"id": v2.json()["template_version_id"]}).scalars())
    assert {"CREATE_RUBRIC_TEMPLATE_VERSION", "PUBLISH_RUBRIC_TEMPLATE"} <= actions


@integration
def test_apply_template_creates_traceable_draft_that_still_needs_dual_approval(client, seed, lead):
    _, version = _published_template(client, seed, lead)
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET job_family_id = :f, level = 'senior' WHERE position_id = :p"),
                     {"f": _family(conn), "p": seed["pos"]})
    route = f"/v1/criteria/position/{seed['pos']}"
    assert client.get(route + "/template-matches", headers=headers(seed["hm"])).status_code == 403
    matches = client.get(route + "/template-matches", headers=headers(seed["hr"])).json()
    mine = next(m for m in matches if m["template_version_id"] == version)
    assert mine["family_match"] and mine["level_match"] and mine["must_have_count"] == 2
    assert matches.index(mine) == 0 or all(m["family_match"] and m["level_match"] for m in matches[:matches.index(mine)])
    # The seed already has an open DRAFT for this position.
    assert client.post(route + "/apply-template", headers=headers(seed["hr"]), json={"template_version_id": version}).status_code == 409
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status = 'REJECTED' WHERE criteria_version_id = :id"), {"id": seed["cv"]})
    assert client.post(route + "/apply-template", headers=headers(seed["hr2"]), json={"template_version_id": version}).status_code == 403
    applied = client.post(route + "/apply-template", headers=headers(seed["hr"]), json={"template_version_id": version})
    assert applied.status_code == 201, applied.text
    body = applied.json()
    assert body["status"] == "DRAFT" and body["origin"] == "TEMPLATE_CLONE"
    assert body["source_template_version_id"] == version and body["mandatory_weight_total"] == 70
    assert len(body["criteria"]) == 3 and all(c["source_template_item_id"] for c in body["criteria"])
    approved = client.get(f"/v1/criteria/position/{seed['pos']}/approved", headers=headers(seed["hr"])).json()
    assert approved is None  # still requires HR + HM approval
    approve = f"/v1/criteria/{body['criteria_version_id']}/approve"
    assert client.post(approve, headers=headers(seed["hr"]), json={"action": "APPROVE"}).json()["status"] == "PENDING_HM_APPROVAL"
    assert client.post(approve, headers=headers(seed["hm"]), json={"action": "APPROVE"}).json()["status"] == "APPROVED"


def _shareable_application(seed):
    """Give seed['app'] a completed assessment on an approved rubric and move it to SHORTLIST."""
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status = 'APPROVED' WHERE criteria_version_id = :id"), {"id": seed["cv"]})
        conn.execute(text("INSERT INTO app_private.criteria_items(criteria_version_id,name,description,category,weight_in_group,display_order) "
                          "VALUES (:cv,'Docker','Containers','NICE_TO_HAVE',100,2)"), {"cv": seed["cv"]})
        doc = conn.execute(text("""INSERT INTO app_private.application_documents(application_id,bucket,storage_path,original_filename,mime_type,size_bytes,file_processing_status)
            VALUES (:app,'cv','x','cv.pdf','application/pdf',10,'COMPLETED') RETURNING document_id"""), {"app": seed["app"]}).scalar_one()
        profile = conn.execute(text("""INSERT INTO app_private.profile_versions(application_id,source_document_id,version_number,status)
            VALUES (:app,:doc,1,'COMPLETED') RETURNING profile_version_id"""), {"app": seed["app"], "doc": doc}).scalar_one()
        assessment = conn.execute(text("""INSERT INTO app_private.assessment_runs(position_id,application_id,jd_version_id,criteria_version_id,profile_version_id,status,matching_status,matching_score)
            VALUES (:pos,:app,:jd,:cv,:profile,'COMPLETED','MEETS_MANDATORY',88) RETURNING assessment_id"""),
            {"pos": seed["pos"], "app": seed["app"], "jd": seed["jd"], "cv": seed["cv"], "profile": profile}).scalar_one()
        conn.execute(text("UPDATE app_private.applications SET application_status = 'SHORTLIST' WHERE application_id = :app"), {"app": seed["app"]})
    return str(assessment)


@integration
def test_scorecard_lifecycle_snapshot_and_access(client, seed):
    assessment = _shareable_application(seed)
    hr, hm = headers(seed["hr"]), headers(seed["hm"])
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    payload = {"position_id": seed["pos"], "shared_with_user_id": seed["hm"], "application_ids": [seed["app"]]}
    assert client.post("/v1/shortlist/share", headers=hr, json={**payload, "due_at": past}).status_code == 400
    shared = client.post("/v1/shortlist/share", headers=hr, json=payload)
    assert shared.status_code == 201, shared.text
    share_id = shared.json()["share_id"]
    due = datetime.fromisoformat(str(shared.json()["due_at"]).replace("Z", "+00:00"))
    # 3 working days; on Mon–Wed that is exactly 3 calendar days, so allow clock skew.
    assert timedelta(days=3, minutes=-1) <= due - datetime.now(timezone.utc) <= timedelta(days=5, minutes=1)

    inbox = client.get("/v1/shortlist/my-scorecards", headers=hm).json()
    assert inbox["summary"]["not_started"] == 1
    scorecard = inbox["items"][0]
    assert scorecard["assessment_id"] == assessment and scorecard["criteria_version_id"] == seed["cv"]
    assert client.get("/v1/shortlist/my-scorecards", headers=hr).json()["summary"]["total"] == 0
    route = f"/v1/shortlist/scorecards/{scorecard['scorecard_id']}"
    assert client.get(route, headers=headers(seed["other"])).status_code == 403
    assert client.get(route, headers=headers(seed["hr2"])).status_code == 403
    detail = client.get(route, headers=hm).json()
    assert detail["can_edit"] and not detail["can_reopen"] and len(detail["criteria"]) == 2
    assert "private" not in str(detail).lower()

    # A rubric approved after the share does not change the locked criteria.
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.criteria_versions(position_id,jd_version_id,version_number,status) VALUES (:p,:jd,2,'APPROVED')"),
                     {"p": seed["pos"], "jd": seed["jd"]})
    assert client.get(route, headers=hm).json()["criteria_version_id"] == seed["cv"]

    python, docker = detail["criteria"][0]["criterion_id"], detail["criteria"][1]["criterion_id"]
    assert client.patch(route, headers=hr, json={"overall_recommendation": "YES"}).status_code == 403
    bad = client.patch(route, headers=hm, json={"criteria": [{"criterion_id": uid(), "rating": 3}]})
    assert bad.status_code == 400
    assert client.patch(route, headers=hm, json={"criteria": [{"criterion_id": python, "rating": 3, "insufficient_evidence": True}]}).status_code == 422
    saved = client.patch(route, headers=hm, json={"criteria": [{"criterion_id": python, "rating": 4, "comment": "Solid"}],
                                                   "strengths": "Python depth"})
    assert saved.status_code == 200 and saved.json()["status"] == "IN_PROGRESS"
    incomplete = client.post(route + "/submit", headers=hm)
    assert incomplete.status_code == 400 and "Docker" in incomplete.json()["detail"]
    client.patch(route, headers=hm, json={"criteria": [{"criterion_id": docker, "insufficient_evidence": True}],
                                          "overall_recommendation": "STRONG_YES"})
    submitted = client.post(route + "/submit", headers=hm)
    assert submitted.status_code == 200 and submitted.json()["status"] == "SUBMITTED"
    assert client.patch(route, headers=hm, json={"strengths": "edit"}).status_code == 400

    summary = client.get(f"/v1/shortlist/{share_id}/scorecard-summary", headers=hr).json()
    assert summary["submitted"] == 1 and summary["recommendations"]["STRONG_YES"] == 1
    listed = client.get(f"/v1/shortlist/{share_id}", headers=hm).json()
    assert listed["applications"][0]["scorecard_status"] == "SUBMITTED"
    assert client.get("/v1/shortlist/shared-with-me", headers=hr).json()[0]["scorecards_submitted"] == 1

    # Reopen: HR only, reason required, audited without content.
    assert client.post(route + "/reopen", headers=hm, json={"reason": "x"}).status_code == 403
    assert client.post(route + "/reopen", headers=hr, json={"reason": ""}).status_code == 422
    reopened = client.post(route + "/reopen", headers=hr, json={"reason": "Thêm nhận xét về SQL"})
    assert reopened.status_code == 200 and reopened.json()["status"] == "IN_PROGRESS"
    assert reopened.json()["reopen_reason"] == "Thêm nhận xét về SQL" and reopened.json()["submitted_at"] is None
    with engine.connect() as conn:
        audit = conn.execute(text("SELECT action_type, metadata FROM app_private.audit_events WHERE object_id = :id ORDER BY created_at"),
                             {"id": scorecard["scorecard_id"]}).mappings().all()
    assert [a["action_type"] for a in audit] == ["SUBMIT_SCORECARD", "REOPEN_SCORECARD"]
    assert "SQL" not in str(audit)

    # Revoking the share removes the HM's access; HR keeps the history.
    assert client.post(f"/v1/shortlist/{share_id}/revoke", headers=hr).status_code == 200
    assert client.get(route, headers=hm).status_code == 403
    assert client.patch(route, headers=hm, json={"strengths": "late"}).status_code == 403
    assert client.get(route, headers=hr).status_code == 200
    assert client.get("/v1/shortlist/my-scorecards", headers=hm).json()["summary"]["total"] == 0


@integration
def test_share_without_assessment_creates_pending_scorecard(client, seed):
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.applications SET application_status = 'SHORTLIST' WHERE application_id = :app"), {"app": seed["app"]})
    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    shared = client.post("/v1/shortlist/share", headers=headers(seed["hr"]), json={
        "position_id": seed["pos"], "shared_with_user_id": seed["hm"], "application_ids": [seed["app"]], "due_at": due})
    assert shared.status_code == 201
    item = client.get("/v1/shortlist/my-scorecards", headers=headers(seed["hm"])).json()["items"][0]
    assert item["criteria_version_id"] is None
    route = f"/v1/shortlist/scorecards/{item['scorecard_id']}"
    assert client.get(route, headers=headers(seed["hm"])).json()["can_edit"] is False
    assert client.patch(route, headers=headers(seed["hm"]), json={"overall_recommendation": "YES"}).status_code == 400
    assert client.post(route + "/submit", headers=headers(seed["hm"])).status_code == 400


@integration
def test_position_job_family_selection(client, seed):
    with engine.connect() as conn:
        family = _family(conn, "RESEARCH")
    route = f"/v1/positions/{seed['pos']}"
    updated = client.patch(route, headers=headers(seed["hr"]), json={"job_family_id": family, "level": " Senior "})
    assert updated.status_code == 200
    assert updated.json()["job_family"] == "Research" and updated.json()["level"] == "Senior"
    assert client.patch(route, headers=headers(seed["hr"]), json={"job_family_id": uid()}).status_code == 400
