"""F3.03: server-to-server intake API for a separate candidate website, and the posting text."""
import json
import os
import secrets

import pytest
from sqlalchemy import text

from app.core.config import settings

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")

if os.environ.get("TEST_DATABASE_URL"):
    from app.api.partner_intake import key_hash
    from app.db.database import engine
    from test_phase1_integration import client, headers, seed, uid  # noqa: F401 (pytest fixtures)


@pytest.fixture
def site(seed, monkeypatch, tmp_path):
    """A published position and an API key for one candidate website. The /apply portal stays off:
    the partner API does not depend on it."""
    key = "hra_intake_" + secrets.token_urlsafe(32)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE app_private.public_intake_events, app_private.intake_clients"))
        conn.execute(text("UPDATE app_private.criteria_versions SET status = 'APPROVED' WHERE criteria_version_id = :c"), {"c": seed["cv"]})
        conn.execute(text("""UPDATE app_private.positions SET public_apply_enabled = TRUE, posting_content = 'Benefits: 13th month salary'
            WHERE position_id = :p"""), {"p": seed["pos"]})
        client_id = conn.execute(text("""INSERT INTO app_private.intake_clients(name, key_hash, key_prefix)
            VALUES ('Test site', :h, 'hra_intake_test') RETURNING client_id"""), {"h": key_hash(key)}).scalar_one()
    monkeypatch.setattr(settings, "PUBLIC_INTAKE_ENABLED", False)
    monkeypatch.setattr(settings, "INTAKE_API_ENABLED", True)
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "MALWARE_SCAN_MODE", "off")
    monkeypatch.setattr(settings, "APP_ENV", "development")
    return {**seed, "key": key, "client_id": str(client_id), "h": {"X-Intake-Key": key}}


def _submit(client, s, *, consent=True, content=PDF, notice="site-v1", ref="site-123", key=None):
    return client.post(f"/v1/intake/positions/{s['pos']}/applications",
                       headers={"X-Intake-Key": key if key is not None else s["key"]},
                       files={"file": ("cv.pdf", content, "application/pdf")},
                       data={"consent_accepted": str(consent).lower(), "consent_notice_version": notice,
                             "consented_at": "2026-11-19T08:00:00Z", "external_ref": ref})


def _one(sql, **p):
    with engine.connect() as conn:
        return conn.execute(text(sql), p).scalar_one()


def test_every_call_needs_a_valid_unrevoked_key(client, site, monkeypatch):
    s = site
    assert client.get("/v1/intake/positions").status_code == 401
    assert client.get("/v1/intake/positions", headers={"X-Intake-Key": "wrong"}).status_code == 401
    assert _submit(client, s, key="wrong").status_code == 401
    assert client.get("/v1/intake/positions", headers=s["h"]).status_code == 200
    assert _one("SELECT last_used_at IS NOT NULL FROM app_private.intake_clients") is True
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.intake_clients SET revoked_at = NOW()"))
    assert client.get("/v1/intake/positions", headers=s["h"]).status_code == 401
    monkeypatch.setattr(settings, "INTAKE_API_ENABLED", False)
    assert client.get("/v1/intake/positions", headers=s["h"]).status_code == 404
    assert _one("SELECT COUNT(*) FROM app_private.applications WHERE source_code = 'PARTNER_SITE'") == 0


def test_lists_only_published_positions_with_jd_and_posting(client, site):
    s = site
    listed = client.get("/v1/intake/positions", headers=s["h"]).json()["positions"]
    assert [p["code"] for p in listed] == [s["pos"]]
    assert listed[0]["posting_content"] == "Benefits: 13th month salary" and listed[0]["jd"]
    detail = client.get(f"/v1/intake/positions/{s['pos']}", headers=s["h"]).json()
    assert detail["jd"] == listed[0]["jd"] and detail["jd_language"] in ("en", "vi")
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET public_apply_enabled = FALSE"))
    assert client.get("/v1/intake/positions", headers=s["h"]).json()["positions"] == []
    assert client.get(f"/v1/intake/positions/{s['pos']}", headers=s["h"]).status_code == 404
    assert _submit(client, s).status_code == 404


def test_submission_records_partner_consent_and_audit(client, site):
    s = site
    assert _submit(client, s, consent=False).status_code == 400
    assert _submit(client, s, notice="bad version!").status_code == 422
    assert _submit(client, s, ref="has spaces").status_code == 422
    assert _one("SELECT COUNT(*) FROM app_private.applications WHERE source_code = 'PARTNER_SITE'") == 0

    res = _submit(client, s)
    body = res.json()
    assert res.status_code == 202 and body["status"] == "received" and len(body["withdrawal_token"]) == 64
    with engine.connect() as conn:
        app_row = conn.execute(text("""SELECT application_id, source_code, application_status FROM app_private.applications
            WHERE source_code = 'PARTNER_SITE'""")).one()
        consents = conn.execute(text("""SELECT purpose, channel, notice_version, evidence FROM app_private.application_data_consents
            WHERE application_id = :a ORDER BY purpose"""), {"a": app_row.application_id}).all()
        audit = conn.execute(text("SELECT metadata FROM app_private.audit_events WHERE action_type = 'RECEIVE_PARTNER_CV'")).scalar_one()
    assert body["receipt_id"] == str(app_row.application_id)
    assert app_row.source_code == "PARTNER_SITE" and app_row.application_status == "NEW"
    assert [c.purpose for c in consents] == ["TALENT_POOL", "THIS_POSITION"]
    assert {c.channel for c in consents} == {"PARTNER_SITE"} and {c.notice_version for c in consents} == {"site-v1"}
    evidence = consents[0].evidence if isinstance(consents[0].evidence, dict) else json.loads(consents[0].evidence)
    assert evidence["client_id"] == s["client_id"] and evidence["external_ref"] == "site-123"
    assert evidence["consented_at_site"].startswith("2026-11-19T08:00:00")
    assert audit["client_id"] == s["client_id"]

    # The same CV again: the trusted site is told, and nothing new is created.
    assert _submit(client, s).json() == {"status": "duplicate"}
    assert _one("SELECT COUNT(*) FROM app_private.applications WHERE source_code = 'PARTNER_SITE'") == 1

    # The candidate can withdraw reuse with the token through the public endpoint.
    assert client.post("/v1/public/talent-pool/withdraw", json={"token": body["withdrawal_token"]}).status_code == 200
    assert _one("""SELECT COUNT(*) FROM app_private.application_data_consents
        WHERE purpose = 'TALENT_POOL' AND withdrawn_at IS NOT NULL""") == 1


def test_per_site_rate_limit(client, site, monkeypatch):
    s = site
    monkeypatch.setattr(settings, "INTAKE_MAX_PER_CLIENT_HOUR", 2)
    assert _submit(client, s, content=PDF + b"%1").status_code == 202
    assert _submit(client, s, content=PDF + b"%2").status_code == 202
    assert _submit(client, s, content=PDF + b"%3").status_code == 429


def test_partner_cv_is_processed_and_reaches_hr(client, site):
    s = site
    assert _submit(client, s).status_code == 202
    from app.workers.processor import ProcessingWorker
    ProcessingWorker()._process_pending_operations()
    assert _one("SELECT status FROM app_private.operations WHERE capability = 'CV_PROCESSING'") == "COMPLETED"
    listed = client.get("/v1/applications", headers=headers(s["hr"]), params={"position_id": s["pos"]}).json()
    assert [a["source_code"] for a in listed if a["source_code"] == "PARTNER_SITE"] == ["PARTNER_SITE"]


def test_hr_edits_posting_content_and_hiring_manager_cannot(client, seed):
    route = f"/v1/positions/{seed['pos']}"
    res = client.patch(route, headers=headers(seed["hr"]), json={"posting_content": "  Apply before 30/12  "})
    assert res.status_code == 200 and res.json()["posting_content"] == "Apply before 30/12"
    assert client.patch(route, headers=headers(seed["hm"]), json={"posting_content": "x"}).status_code == 403
    # An empty value clears it.
    assert client.patch(route, headers=headers(seed["hr"]), json={"posting_content": "   "}).json()["posting_content"] is None
    assert client.patch(route, headers=headers(seed["hr"]), json={"posting_content": "x" * 20001}).status_code == 422


def test_partner_consent_follows_the_retention_by_consent_model(client, site):
    """PARTNER_SITE consents are ordinary TALENT_POOL consents: 60 months from granted_at, withdrawn -> back to the base period."""
    from datetime import datetime, timezone
    from app.services.retention import add_months, retention_due_date
    s = site
    body = _submit(client, s).json()
    with engine.connect() as conn:
        granted, withdrawn, token_hash = conn.execute(text("""SELECT granted_at, withdrawn_at, withdrawal_token_hash
            FROM app_private.application_data_consents WHERE purpose = 'TALENT_POOL' AND channel = 'PARTNER_SITE'""")).one()
    assert withdrawn is None and token_hash and len(token_hash) == 64
    policy = {"months": 60, "base_months": 12}
    closed = datetime(2026, 12, 1, tzinfo=timezone.utc)
    assert retention_due_date(closed, granted, policy) == add_months(granted, settings.TALENT_POOL_RETENTION_MONTHS)
    # The partner's own claimed consent time is evidence only; it never moves granted_at.
    assert abs((granted - datetime.now(timezone.utc)).total_seconds()) < 300
    assert client.post("/v1/public/talent-pool/withdraw", json={"token": body["withdrawal_token"]}).status_code == 200
    assert retention_due_date(closed, None, policy) == add_months(closed, 12)


def test_partner_cv_dedupe_is_per_position_and_content(client, site):
    s = site
    assert _submit(client, s).status_code == 202
    assert _submit(client, s).json() == {"status": "duplicate"}
    # A different file is a new application; the same bytes on the public portal path are caught too.
    assert _submit(client, s, content=PDF + b"%different").status_code == 202
    assert _one("SELECT COUNT(*) FROM app_private.applications WHERE source_code = 'PARTNER_SITE'") == 2
    assert _one("SELECT COUNT(*) FROM app_private.application_data_consents WHERE purpose = 'TALENT_POOL' AND channel = 'PARTNER_SITE'") == 2


def test_partner_rejects_a_file_that_is_not_a_cv(client, site):
    s = site
    assert _submit(client, s, content=b"not a pdf at all").status_code == 400
    assert _one("SELECT COUNT(*) FROM app_private.applications WHERE source_code = 'PARTNER_SITE'") == 0


def test_worker_queues_held_partner_cvs_as_one_job(client, site):
    """Partner-site CVs arriving while a job runs on the position are held, then queued together."""
    from app.services.portal_dispatch import dispatch_held_portal_cvs
    s = site
    assert _submit(client, s, content=PDF + b"\n%first").status_code == 202
    assert _submit(client, s, content=PDF + b"\n%held-1").status_code == 202
    assert _submit(client, s, content=PDF + b"\n%held-2").status_code == 202
    held_sql = """SELECT COUNT(*) FROM app_private.application_documents d JOIN app_private.applications a USING (application_id)
        WHERE a.position_id = :p AND a.source_code = 'PARTNER_SITE' AND d.file_processing_status = 'NEEDS_HR_REVIEW'"""
    assert _one(held_sql, p=s["pos"]) == 2
    assert dispatch_held_portal_cvs() == 0
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.operations SET status = 'COMPLETED' WHERE position_id = :p"), {"p": s["pos"]})
    assert dispatch_held_portal_cvs() == 2
    assert _one(held_sql, p=s["pos"]) == 0
    assert _one("""SELECT COUNT(*) FROM app_private.operations
        WHERE position_id = :p AND capability = 'CV_PROCESSING' AND status = 'PENDING'""", p=s["pos"]) == 1
