"""F2.01 extension: save a position's approved criteria as a rubric template draft."""
import json
import os

import pytest
from sqlalchemy import text

integration = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                 reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")

if os.environ.get("TEST_DATABASE_URL"):
    from app.db.database import engine
    from test_phase1_integration import client, headers, seed, uid  # noqa: F401 (pytest fixtures)
    from test_phase2_workflow import _family, lead  # noqa: F401 (pytest fixtures)

ROUTE = "/v1/rubric-library/templates/from-criteria"
YEARS_SPEC = {"kind": "YEARS", "min_years": 3, "terms": ["python"]}


def _approve_seed_criteria(seed, *, extra_items: bool = True):
    """Turn the seed's DRAFT criteria into an approved set like HR would leave it."""
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status = 'APPROVED', mandatory_weight_total = 80, "
                          "nice_to_have_weight_total = 20 WHERE criteria_version_id = :id"), {"id": seed["cv"]})
        conn.execute(text("UPDATE app_private.criteria_items SET expected_evidence_keywords = '[\"Python\", \"FastAPI\"]'::jsonb, "
                          "requirement_spec = CAST(:spec AS jsonb), weight_in_group = 70 WHERE criterion_id = :id"),
                     {"spec": json.dumps(YEARS_SPEC), "id": seed["criterion"]})
        if extra_items:
            conn.execute(text("""
                INSERT INTO app_private.criteria_items (criteria_version_id, name, description, category, weight_in_group, display_order)
                VALUES (:cv, 'PostgreSQL', '  ', 'MUST_HAVE', 30, 2), (:cv, 'Docker', 'Containers', 'NICE_TO_HAVE', 100, 3)
            """), {"cv": seed["cv"]})


@integration
def test_approved_criteria_become_a_new_template_draft(client, seed, lead):
    _approve_seed_criteria(seed)
    with engine.connect() as conn:
        family = _family(conn)
    hr = headers(seed["hr"])
    created = client.post(ROUTE, headers=hr, json={"criteria_version_id": seed["cv"], "job_family_id": family,
                                                   "title": "Backend Python (từ vị trí)", "level_band": "Junior"})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["version_number"] == 1 and body["item_count"] == 3 and body["status"] == "DRAFT"

    version = client.get(f"/v1/rubric-library/template-versions/{body['template_version_id']}", headers=hr).json()
    assert version["status"] == "DRAFT"
    assert (float(version["mandatory_weight_total"]), float(version["nice_to_have_weight_total"])) == (80.0, 20.0)
    by_name = {i["name"]: i for i in version["items"]}
    assert set(by_name) == {"Python", "PostgreSQL", "Docker"}
    # A blank description falls back to the name; keywords and the HR-edited rule are kept.
    assert by_name["PostgreSQL"]["description"] == "PostgreSQL"
    assert by_name["Python"]["expected_evidence_keywords"] == ["Python", "FastAPI"]
    with engine.connect() as conn:
        spec, source = conn.execute(text("""
            SELECT i.requirement_spec, v.source_criteria_version_id::text FROM app_private.rubric_template_items i
            JOIN app_private.rubric_template_versions v USING (template_version_id)
            WHERE i.template_version_id = :v AND i.name = 'Python'
        """), {"v": body["template_version_id"]}).one()
        actions = set(conn.execute(text("SELECT action_type FROM app_private.audit_events WHERE object_id = :id"),
                                   {"id": body["template_version_id"]}).scalars())
    assert spec == YEARS_SPEC and source == seed["cv"]
    assert "CREATE_RUBRIC_TEMPLATE_FROM_CRITERIA" in actions

    # Still a draft: an HR Lead publishes it, and the next position gets the same rule back.
    assert client.post(f"/v1/rubric-library/template-versions/{body['template_version_id']}/publish",
                       headers=headers(lead), json={}).status_code == 200
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status = 'REJECTED' WHERE criteria_version_id = :id"),
                     {"id": seed["cv"]})
    applied = client.post(f"/v1/criteria/position/{seed['pos']}/apply-template", headers=hr,
                          json={"template_version_id": body["template_version_id"]})
    assert applied.status_code == 201, applied.text
    python = next(c for c in applied.json()["criteria"] if c["name"] == "Python")
    assert python["requirement_spec"]["kind"] == "YEARS" and float(python["requirement_spec"]["min_years"]) == 3


@integration
def test_only_approved_criteria_and_only_the_positions_hr(client, seed, lead):
    with engine.connect() as conn:
        family = _family(conn)
    payload = {"criteria_version_id": seed["cv"], "job_family_id": family, "title": "X"}
    # The seed criteria are still a DRAFT.
    draft = client.post(ROUTE, headers=headers(seed["hr"]), json=payload)
    assert draft.status_code == 400 and "đã duyệt" in draft.json()["detail"]
    _approve_seed_criteria(seed, extra_items=False)
    # HR of another position, and a Hiring Manager, cannot.
    assert client.post(ROUTE, headers=headers(seed["hr2"]), json=payload).status_code == 403
    assert client.post(ROUTE, headers=headers(seed["hm"]), json=payload).status_code == 403
    # A new template needs a family.
    no_family = client.post(ROUTE, headers=headers(seed["hr"]), json={"criteria_version_id": seed["cv"]})
    assert no_family.status_code == 400
    assert client.post(ROUTE, headers=headers(seed["hr"]), json={"criteria_version_id": uid(), "job_family_id": family}).status_code == 404


@integration
def test_saving_into_an_existing_template_makes_its_next_draft(client, seed, lead):
    _approve_seed_criteria(seed)
    with engine.connect() as conn:
        family = _family(conn)
    hr = headers(seed["hr"])
    first = client.post(ROUTE, headers=hr, json={"criteria_version_id": seed["cv"], "job_family_id": family, "title": "Backend"}).json()
    # The template still has its v1 draft: a second draft is refused.
    again = client.post(ROUTE, headers=hr, json={"criteria_version_id": seed["cv"], "template_id": first["template_id"]})
    assert again.status_code == 409
    assert client.post(f"/v1/rubric-library/template-versions/{first['template_version_id']}/publish",
                       headers=headers(lead), json={}).status_code == 200
    second = client.post(ROUTE, headers=hr, json={"criteria_version_id": seed["cv"], "template_id": first["template_id"],
                                                  "change_note": "Cập nhật từ vị trí"})
    assert second.status_code == 201, second.text
    assert second.json()["version_number"] == 2 and second.json()["template_id"] == first["template_id"]
    detail = client.get(f"/v1/rubric-library/templates/{first['template_id']}", headers=hr).json()
    assert [(v["version_number"], v["status"]) for v in detail["versions"]] == [(2, "DRAFT"), (1, "PUBLISHED")]
    assert detail["versions"][0]["change_note"] == "Cập nhật từ vị trí"


@integration
def test_editing_a_template_item_drops_the_copied_rule(client, seed, lead):
    _approve_seed_criteria(seed, extra_items=False)
    with engine.connect() as conn:
        family = _family(conn)
    hr = headers(seed["hr"])
    body = client.post(ROUTE, headers=hr, json={"criteria_version_id": seed["cv"], "job_family_id": family, "title": "Y"}).json()
    item = client.get(f"/v1/rubric-library/template-versions/{body['template_version_id']}", headers=hr).json()["items"][0]
    route = f"/v1/rubric-library/template-items/{item['template_item_id']}"
    # Weight-only edits keep the rule; a new description means the rule must be inferred again.
    assert client.patch(route, headers=hr, json={"weight_in_group": 100}).status_code == 200
    with engine.connect() as conn:
        read = lambda: conn.execute(text("SELECT requirement_spec FROM app_private.rubric_template_items WHERE template_item_id = :id"),
                                    {"id": item["template_item_id"]}).scalar_one()
        assert read() == YEARS_SPEC
    assert client.patch(route, headers=hr, json={"description": "Kinh nghiệm Go"}).status_code == 200
    with engine.connect() as conn:
        assert conn.execute(text("SELECT requirement_spec FROM app_private.rubric_template_items WHERE template_item_id = :id"),
                            {"id": item["template_item_id"]}).scalar_one() is None


@integration
def test_template_carries_the_positions_jd_as_an_editable_sample(client, seed, lead):
    _approve_seed_criteria(seed)  # full weights, so the version can be published below
    with engine.begin() as conn:
        family = _family(conn)
        conn.execute(text("UPDATE app_private.jd_versions SET content_text = :jd WHERE jd_version_id = :id"),
                     {"jd": "  Backend engineer.\nBuild REST APIs in Python.  ", "id": seed["jd"]})
    hr = headers(seed["hr"])
    body = client.post(ROUTE, headers=hr, json={"criteria_version_id": seed["cv"], "job_family_id": family, "title": "JD"}).json()
    route = f"/v1/rubric-library/template-versions/{body['template_version_id']}"
    # The JD the criteria were approved against is copied (trimmed) as the sample JD.
    assert client.get(route, headers=hr).json()["jd_template"] == "Backend engineer.\nBuild REST APIs in Python."
    # Editable while the version is a draft; an empty value clears it.
    edited = client.patch(route, headers=hr, json={"jd_template": "Mẫu JD cho Backend"})
    assert edited.status_code == 200 and edited.json()["jd_template"] == "Mẫu JD cho Backend"
    assert client.patch(route, headers=hr, json={"jd_template": ""}).json()["jd_template"] is None
    assert client.patch(route, headers=hr, json={"jd_template": "JD cuối"}).status_code == 200
    assert client.post(route + "/publish", headers=headers(lead), json={}).status_code == 200
    # Frozen once published; the library listing says the published version has a JD.
    assert client.patch(route, headers=hr, json={"jd_template": "khác"}).status_code == 400
    listed = next(t for t in client.get("/v1/rubric-library/templates", headers=hr, params={"status": "PUBLISHED"}).json()
                  if t["template_id"] == body["template_id"])
    assert listed["published_has_jd"] is True
    # A new draft version starts from the published sample JD.
    v2 = client.post(f"/v1/rubric-library/templates/{body['template_id']}/versions", headers=hr, json={})
    assert v2.status_code == 201 and v2.json()["jd_template"] == "JD cuối"
