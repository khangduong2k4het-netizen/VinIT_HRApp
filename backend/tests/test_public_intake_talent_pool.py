"""P3-3 public portal guards and P3-1 phase 1 Talent Pool eligibility."""
import os
import socket
import struct
import threading
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.services import malware_scan
from app.services.malware_scan import ScanRejected, ScanUnavailable, scan_with_clamd
from app.services.talent_pool import ineligibility_reason, pool_expiry

NOW = datetime(2026, 11, 17, tzinfo=timezone.utc)
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


# ---------------------------------------------------------------- unit tests

def _reason(**over):
    base = dict(status="SHORTLIST", consent_present=True, consent_withdrawn=False,
                received_at=NOW - timedelta(days=30), open_retention_status=None, now=NOW)
    base.update(over)
    return ineligibility_reason(**base)


def test_pool_rules_in_priority_order():
    assert _reason() is None
    assert _reason(consent_present=False, consent_withdrawn=True) == "NO_CONSENT"
    assert _reason(consent_withdrawn=True) == "CONSENT_WITHDRAWN"
    assert _reason(received_at=datetime(2021, 11, 16, tzinfo=timezone.utc)) == "RETENTION_EXPIRED"
    assert _reason(received_at=datetime(2021, 11, 18, tzinfo=timezone.utc)) is None
    assert _reason(open_retention_status="ON_HOLD") == "DELETION_PENDING"
    assert _reason(status="NEW") == "STATUS_NOT_ELIGIBLE"
    # The five years are counted from receipt, not from any later event.
    assert pool_expiry(datetime(2026, 2, 28, tzinfo=timezone.utc)).date().isoformat() == "2031-02-28"


def _fake_clamd(reply):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    seen = {}

    def run():
        conn, _ = server.accept()
        data = b""
        while not data.endswith(struct.pack(">I", 0)):
            part = conn.recv(65536)
            if not part:
                break
            data += part
        seen["data"] = data
        conn.sendall(reply)
        conn.close()
        server.close()
    threading.Thread(target=run, daemon=True).start()
    return server.getsockname()[1], seen


def test_clamd_protocol_and_verdicts():
    port, seen = _fake_clamd(b"stream: OK\0")
    scan_with_clamd(b"hello", "127.0.0.1", port, 2)
    assert seen["data"].startswith(b"zINSTREAM\0") and b"hello" in seen["data"]
    port, _ = _fake_clamd(b"stream: Eicar-Signature FOUND\0")
    with pytest.raises(ScanRejected):
        scan_with_clamd(b"x", "127.0.0.1", port, 2)
    port, _ = _fake_clamd(b"INSTREAM size limit exceeded. ERROR\0")
    with pytest.raises(ScanUnavailable):
        scan_with_clamd(b"x", "127.0.0.1", port, 2)
    with pytest.raises(ScanUnavailable):  # nothing listening: refuse, never accept unscanned
        scan_with_clamd(b"x", "127.0.0.1", 1, 1)


def test_scanning_is_mandatory_in_production(monkeypatch):
    monkeypatch.setattr(settings, "MALWARE_SCAN_MODE", "off")
    monkeypatch.setattr(settings, "APP_ENV", "production")
    with pytest.raises(ScanUnavailable):
        malware_scan.scan_upload(PDF)
    monkeypatch.setattr(settings, "APP_ENV", "development")
    malware_scan.scan_upload(PDF)


# ---------------------------------------------------------- integration tests

integration = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                 reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")

if os.environ.get("TEST_DATABASE_URL"):
    from app.db.database import engine
    from test_hr_analytics import _assessed_application
    from test_phase1_integration import client, headers, seed, uid  # noqa: F401 (pytest fixtures)


@pytest.fixture
def portal(seed, monkeypatch, tmp_path):
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE app_private.public_intake_events"))
        conn.execute(text("UPDATE app_private.criteria_versions SET status = 'APPROVED' WHERE criteria_version_id = :c"), {"c": seed["cv"]})
        conn.execute(text("UPDATE app_private.positions SET public_apply_enabled = TRUE WHERE position_id = :p"), {"p": seed["pos"]})
    monkeypatch.setattr(settings, "PUBLIC_INTAKE_ENABLED", True)
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "MALWARE_SCAN_MODE", "off")
    monkeypatch.setattr(settings, "APP_ENV", "development")
    return seed


def _apply(client, seed, *, pool=True, processing=True, content=PDF, name="cv.pdf", honeypot=""):
    return client.post(f"/v1/public/positions/{seed['pos']}/apply",
                       files={"file": (name, content, "application/pdf")},
                       data={"consent_processing": str(processing).lower(), "consent_talent_pool": str(pool).lower(), "website": honeypot})


def _count(sql, **p):
    with engine.connect() as conn:
        return conn.execute(text(sql), p).scalar_one()


@integration
def test_portal_is_off_by_default_and_lists_only_published_positions(client, portal, monkeypatch):
    seed = portal
    listed = client.get("/v1/public/positions").json()["positions"]
    assert [p["code"] for p in listed] == [seed["pos"]] and set(listed[0]) == {"code", "title", "unit", "location", "employment_type"}
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET public_apply_enabled = FALSE"))
    assert client.get("/v1/public/positions").json()["positions"] == []
    assert _apply(client, seed).status_code == 404
    monkeypatch.setattr(settings, "PUBLIC_INTAKE_ENABLED", False)
    assert client.get("/v1/public/positions").status_code == 404


@integration
def test_apply_creates_application_with_consents_and_audit(client, portal, tmp_path):
    seed = portal
    res = _apply(client, seed)
    assert res.status_code == 202 and res.json() == {"status": "received"}
    with engine.connect() as conn:
        app_row = conn.execute(text("""SELECT application_id, source_code, created_by, application_status FROM app_private.applications
            WHERE source_code = 'PORTAL'""")).one()
        consents = {r[0] for r in conn.execute(text("SELECT purpose FROM app_private.application_data_consents WHERE application_id = :a"),
                                               {"a": app_row.application_id})}
        doc = conn.execute(text("SELECT file_processing_status, content_sha256 FROM app_private.application_documents WHERE application_id = :a"),
                           {"a": app_row.application_id}).one()
        audit = conn.execute(text("SELECT metadata FROM app_private.audit_events WHERE action_type = 'PUBLIC_CV_RECEIVED'")).scalar_one()
        queued = conn.execute(text("""SELECT COUNT(*) FROM app_private.document_processing_runs r JOIN app_private.operations o USING (operation_id)
            WHERE o.status = 'PENDING' AND o.requested_by IS NULL""")).scalar_one()
    assert app_row.created_by is None and app_row.application_status == "NEW"
    assert consents == {"THIS_POSITION", "TALENT_POOL"} and doc.file_processing_status == "RECEIVED" and len(doc.content_sha256) == 64
    assert set(audit) == {"talent_pool_consent", "size_bytes"} and queued == 1
    assert any(files for _, _, files in os.walk(tmp_path))
    # Ticking only the first box gives only the first consent.
    assert _apply(client, seed, pool=False, content=PDF + b"\n%second").status_code == 202
    assert _count("SELECT COUNT(*) FROM app_private.application_data_consents WHERE purpose = 'TALENT_POOL'") == 1


@integration
def test_apply_guards(client, portal, monkeypatch):
    seed = portal
    monkeypatch.setattr(settings, "PUBLIC_INTAKE_MAX_PER_IP_HOUR", 100)
    assert _apply(client, seed, processing=False).status_code == 400
    assert _apply(client, seed, content=b"MZ not a pdf", name="cv.pdf").status_code == 400
    assert _apply(client, seed, honeypot="http://spam").status_code == 202  # looks successful to a bot
    assert _count("SELECT COUNT(*) FROM app_private.applications WHERE source_code = 'PORTAL'") == 0
    assert client.post("/v1/public/positions/UNKNOWN/apply", files={"file": ("cv.pdf", PDF, "application/pdf")},
                       data={"consent_processing": "true"}).status_code == 404

    # Scanner verdicts: reject infected files, refuse when the scanner is down.
    def infected(_):
        raise ScanRejected()

    def down(_):
        raise ScanUnavailable("down")
    from app.api import public_intake
    monkeypatch.setattr(public_intake, "scan_upload", infected)
    bad = _apply(client, seed)
    assert bad.status_code == 400 and "Eicar" not in bad.text
    monkeypatch.setattr(public_intake, "scan_upload", down)
    assert _apply(client, seed).status_code == 503
    assert _count("SELECT COUNT(*) FROM app_private.applications WHERE source_code = 'PORTAL'") == 0


@integration
def test_duplicate_content_and_rate_limit(client, portal, monkeypatch):
    seed = portal
    assert _apply(client, seed).status_code == 202 and _apply(client, seed).status_code == 202
    assert _count("SELECT COUNT(*) FROM app_private.applications WHERE source_code = 'PORTAL'") == 1
    monkeypatch.setattr(settings, "PUBLIC_INTAKE_MAX_PER_IP_HOUR", 3)
    assert _apply(client, seed).status_code == 202  # third attempt still allowed
    assert _apply(client, seed).status_code == 429
    assert "testclient" not in str(_count("SELECT string_agg(ip_hash, ',') FROM app_private.public_intake_events"))


def test_client_address_trusts_only_configured_proxy_hops(monkeypatch):
    from types import SimpleNamespace
    from app.api.public_intake import client_address
    request = SimpleNamespace(headers={"x-forwarded-for": "6.6.6.6, 203.0.113.9"}, client=SimpleNamespace(host="10.0.0.2"))
    monkeypatch.setattr(settings, "PUBLIC_INTAKE_TRUSTED_PROXY_HOPS", 0)
    assert client_address(request) == "10.0.0.2"          # header ignored unless a proxy is trusted
    monkeypatch.setattr(settings, "PUBLIC_INTAKE_TRUSTED_PROXY_HOPS", 1)
    assert client_address(request) == "203.0.113.9"       # a forged left-hand entry has no effect
    monkeypatch.setattr(settings, "PUBLIC_INTAKE_TRUSTED_PROXY_HOPS", 3)
    assert client_address(request) == "10.0.0.2"          # chain shorter than the hops: fall back


@integration
def test_hr_publishes_position_and_hiring_manager_cannot(client, seed):
    route = f"/v1/positions/{seed['pos']}/public-apply"
    assert client.put(route, headers=headers(seed["hm"]), json={"enabled": True}).status_code == 403
    assert client.put(route, headers=headers(seed["hr2"]), json={"enabled": True}).status_code == 403
    assert client.put(route, headers=headers(seed["hr"]), json={"enabled": True}).json() == {"public_apply_enabled": True}
    assert _count("SELECT COUNT(*) FROM app_private.audit_events WHERE action_type = 'SET_PUBLIC_APPLY'") == 1


# ---- Talent Pool eligibility ----

def _consented_application(seed, pool=True, status="SHORTLIST", received=None):
    app_id = _assessed_application(seed, "MEETS_MANDATORY", "Pool " + uid()[:4])
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.applications SET application_status = :s, created_at = COALESCE(:r, created_at) WHERE application_id = :a"),
                     {"s": status, "r": received, "a": app_id})
        if pool:
            conn.execute(text("""INSERT INTO app_private.application_data_consents(application_id, purpose, notice_version, channel)
                VALUES (:a, 'TALENT_POOL', 'v1', 'PORTAL')"""), {"a": app_id})
    return app_id


@integration
def test_mark_requires_valid_consent_and_scope(client, seed):
    hr, route = headers(seed["hr"]), "/v1/talent-pool/applications/{}/mark"
    none = _consented_application(seed, pool=False)
    state = client.get(f"/v1/talent-pool/applications/{none}", headers=hr).json()
    assert state["can_mark"] is False and state["reason"] == "NO_CONSENT"
    assert client.post(route.format(none), headers=hr, json={"reason_code": "STRONG_FIT"}).status_code == 409

    ok = _consented_application(seed)
    assert client.post(route.format(ok), headers=hr, json={"reason_code": "bogus"}).status_code == 400
    assert client.post(route.format(ok), headers=headers(seed["hm"]), json={"reason_code": "STRONG_FIT"}).status_code == 403
    assert client.post(route.format(ok), headers=headers(seed["hr2"]), json={"reason_code": "STRONG_FIT"}).status_code == 403
    assert client.post(route.format(ok), headers=hr, json={"reason_code": "STRONG_FIT"}).status_code == 201
    assert client.post(route.format(ok), headers=hr, json={"reason_code": "STRONG_FIT"}).status_code == 409

    too_early = _consented_application(seed, status="NEW")
    assert client.post(route.format(too_early), headers=hr, json={"reason_code": "NEAR_MISS"}).status_code == 409
    old = _consented_application(seed, received=datetime.now(timezone.utc) - timedelta(days=365 * 5 + 30))
    state = client.get(f"/v1/talent-pool/applications/{old}", headers=hr).json()
    assert state["reason"] == "RETENTION_EXPIRED"
    metadata = _count("SELECT metadata::text FROM app_private.audit_events WHERE action_type = 'TALENT_POOL_MARK'")
    assert "Pool" not in metadata


@integration
def test_eligible_pool_excludes_withdrawn_expired_and_pending_deletion(client, seed):
    from app.db.database import SessionLocal
    from app.services.talent_pool import eligible_pool
    hr = headers(seed["hr"])
    good, withdrawn, expired, held = (_consented_application(seed) for _ in range(4))
    for a in (good, withdrawn, expired, held):
        assert client.post(f"/v1/talent-pool/applications/{a}/mark", headers=hr, json={"reason_code": "STRONG_FIT"}).status_code == 201

    def ids():
        db = SessionLocal()
        try:
            return {str(r["application_id"]) for r in eligible_pool(db)}
        finally:
            db.close()
    assert ids() == {good, withdrawn, expired, held}
    assert client.post(f"/v1/talent-pool/applications/{withdrawn}/withdraw-consent", headers=hr, json={"reference": "ref-1"}).status_code == 200
    assert client.post(f"/v1/talent-pool/applications/{withdrawn}/withdraw-consent", headers=hr, json={}).status_code == 404
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.applications SET created_at = NOW() - INTERVAL '61 months' WHERE application_id = :a"), {"a": expired})
        conn.execute(text("""INSERT INTO app_private.application_retention_cases(application_id, policy_version, position_closed_at, due_date, status)
            SELECT :a, policy_version, NOW(), NOW(), 'ON_HOLD' FROM app_private.retention_policy_versions LIMIT 1"""), {"a": held})
    assert ids() == {good}
    # Unmarking also removes a candidate from the pool.
    assert client.delete(f"/v1/talent-pool/applications/{good}/mark", headers=hr).status_code == 200
    assert ids() == set()
