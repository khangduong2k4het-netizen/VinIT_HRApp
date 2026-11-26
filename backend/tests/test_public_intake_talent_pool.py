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
    assert _reason(received_at=None) == "RETENTION_EXPIRED"
    assert _reason(open_retention_status="ON_HOLD") == "DELETION_PENDING"
    assert _reason(status="NEW") == "STATUS_NOT_ELIGIBLE"
    # The five years start when the application is received.
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


@pytest.mark.parametrize("reply", [b"stream: NOT OK\0", b"stream: OK", b"OK\0", b"stream: OK\0extra"])
def test_clamd_rejects_malformed_or_incomplete_clean_verdicts(reply):
    port, _ = _fake_clamd(reply)
    with pytest.raises(ScanUnavailable):
        scan_with_clamd(b"safe synthetic content", "127.0.0.1", port, 2)


@pytest.mark.skipif(not os.environ.get("HRA_TEST_CLAMD_PORT"), reason="Set HRA_TEST_CLAMD_PORT for a real local clamd")
def test_real_clamd_accepts_clean_content_and_rejects_eicar():
    port = int(os.environ["HRA_TEST_CLAMD_PORT"])
    scan_with_clamd(b"Synthetic recruitment test document", "127.0.0.1", port, 10)
    # Standard harmless antivirus test string; never a real malware sample.
    eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    with pytest.raises(ScanRejected):
        scan_with_clamd(eicar, "127.0.0.1", port, 10)


def test_scanning_is_mandatory_in_production(monkeypatch):
    monkeypatch.setattr(settings, "MALWARE_SCAN_MODE", "off")
    monkeypatch.setattr(settings, "APP_ENV", "production")
    with pytest.raises(ScanUnavailable):
        malware_scan.scan_upload(PDF)
    monkeypatch.setattr(settings, "APP_ENV", "development")
    malware_scan.scan_upload(PDF)
    # Allowlist, not a single exact value: staging and typos must also refuse.
    for env in ("staging", "prod", "test", "Production"):
        monkeypatch.setattr(settings, "APP_ENV", env)
        with pytest.raises(ScanUnavailable):
            malware_scan.scan_upload(PDF)


def test_portal_refuses_to_start_with_unsafe_settings_outside_development():
    from pydantic import ValidationError
    from app.core.config import Settings
    safe = dict(_env_file=None, APP_ENV="staging", PUBLIC_INTAKE_ENABLED=True, MALWARE_SCAN_MODE="clamav",
                PUBLIC_INTAKE_IP_SALT="x" * 32, PUBLIC_INTAKE_TRUSTED_PROXY_HOPS=1)
    assert Settings(**safe).PUBLIC_INTAKE_ENABLED is True
    for override in ({"MALWARE_SCAN_MODE": "off"},                 # files accepted unscanned
                     {"PUBLIC_INTAKE_IP_SALT": ""},                  # IP hashes reversible
                     {"PUBLIC_INTAKE_TRUSTED_PROXY_HOPS": 0}):       # one shared bucket behind the proxy
        with pytest.raises(ValidationError):
            Settings(**{**safe, **override})
    # Development keeps its shortcuts, and a disabled portal needs none of this.
    assert Settings(**{**safe, "APP_ENV": "development", "MALWARE_SCAN_MODE": "off",
                       "PUBLIC_INTAKE_IP_SALT": "", "PUBLIC_INTAKE_TRUSTED_PROXY_HOPS": 0})
    assert Settings(_env_file=None, APP_ENV="production", PUBLIC_INTAKE_ENABLED=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, APP_ENV="staging", INTAKE_API_ENABLED=True, MALWARE_SCAN_MODE="off")
    assert Settings(_env_file=None, APP_ENV="staging", INTAKE_API_ENABLED=True, MALWARE_SCAN_MODE="clamav").INTAKE_API_ENABLED is True


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
    monkeypatch.setattr(settings, "PUBLIC_INTAKE_NOTICE_VERSION", "v4")
    return seed


def _apply(client, seed, *, pool=True, processing=True, content=PDF, name="cv.pdf", honeypot="", notice="v4"):
    return client.post(f"/v1/public/positions/{seed['pos']}/apply",
                       files={"file": (name, content, "application/pdf")},
                       data={"consent_processing": str(processing).lower(), "consent_talent_pool": str(pool).lower(),
                             "website": honeypot, "notice_version": notice})


def _count(sql, **p):
    with engine.connect() as conn:
        return conn.execute(text(sql), p).scalar_one()


@integration
def test_portal_is_off_by_default_and_lists_only_published_positions(client, portal, monkeypatch):
    seed = portal
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET posting_content = 'Competitive salary and health insurance' WHERE position_id = :p"),
                     {"p": seed["pos"]})
    listed = client.get("/v1/public/positions").json()["positions"]
    assert [p["code"] for p in listed] == [seed["pos"]] and set(listed[0]) == {"code", "title", "unit", "location", "employment_type"}
    detail = client.get(f"/v1/public/positions/{seed['pos']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["posting_content"] == "Competitive salary and health insurance" and body["jd"]
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET public_apply_enabled = FALSE"))
    assert client.get("/v1/public/positions").json()["positions"] == []
    assert client.get(f"/v1/public/positions/{seed['pos']}").status_code == 404
    assert _apply(client, seed).status_code == 404
    monkeypatch.setattr(settings, "PUBLIC_INTAKE_ENABLED", False)
    assert client.get("/v1/public/positions").status_code == 404
    assert client.get(f"/v1/public/positions/{seed['pos']}").status_code == 404


@integration
def test_apply_creates_application_with_consents_and_audit(client, portal, tmp_path):
    seed = portal
    res = _apply(client, seed)
    assert res.status_code == 202 and res.json()["status"] == "received" and len(res.json()["withdrawal_token"]) == 64
    with engine.connect() as conn:
        app_row = conn.execute(text("""SELECT application_id, source_code, created_by, application_status FROM app_private.applications
            WHERE source_code = 'PORTAL'""")).one()
        consents = {r[0] for r in conn.execute(text("SELECT purpose FROM app_private.application_data_consents WHERE application_id = :a"),
                                               {"a": app_row.application_id})}
        doc = conn.execute(text("SELECT file_processing_status, content_sha256 FROM app_private.application_documents WHERE application_id = :a"),
                           {"a": app_row.application_id}).one()
        audit = conn.execute(text("SELECT metadata FROM app_private.audit_events WHERE action_type = 'RECEIVE_PUBLIC_CV'")).scalar_one()
        queued = conn.execute(text("""SELECT COUNT(*) FROM app_private.document_processing_runs r JOIN app_private.operations o USING (operation_id)
            WHERE o.status = 'PENDING' AND o.requested_by IS NULL AND o.position_id = :p"""), {"p": seed["pos"]}).scalar_one()
    assert app_row.created_by is None and app_row.application_status == "NEW"
    assert consents == {"THIS_POSITION", "TALENT_POOL"} and doc.file_processing_status == "RECEIVED" and len(doc.content_sha256) == 64
    assert set(audit) == {"talent_pool_consent", "size_bytes"} and queued == 1
    assert any(files for _, _, files in os.walk(tmp_path))
    # Notice v4: the single required checkbox covers processing and reuse.
    again = _apply(client, seed, pool=False, content=PDF + b"\n%second")
    assert again.status_code == 202 and len(again.json()["withdrawal_token"]) == 64
    assert _count("SELECT COUNT(*) FROM app_private.application_data_consents WHERE purpose = 'TALENT_POOL'") == 2
    assert _count("SELECT COUNT(*) FROM app_private.application_data_consents WHERE notice_version = 'v4'") == 4
    # Without the mandatory consent nothing is created.
    assert _apply(client, seed, processing=False, content=PDF + b"\n%third").status_code == 400
    assert _count("SELECT COUNT(*) FROM app_private.applications WHERE source_code = 'PORTAL'") == 2


@integration
def test_missing_or_stale_notice_cannot_grant_current_consent(client, portal, monkeypatch):
    from app.api import public_intake
    calls = []
    monkeypatch.setattr(public_intake, "scan_upload", lambda content: calls.append(content))
    for notice in ("", "v1", "v2", "v3"):
        assert _apply(client, portal, notice=notice).status_code == 409
    assert calls == []
    assert _count("SELECT COUNT(*) FROM app_private.applications WHERE source_code = 'PORTAL'") == 0
    assert _count("SELECT COUNT(*) FROM app_private.application_data_consents") == 0


@integration
def test_combined_consent_allows_hr_to_mark_eligible_application(client, portal):
    assert _apply(client, portal, pool=False).status_code == 202
    with engine.begin() as conn:
        app_id = str(conn.execute(text("SELECT application_id FROM app_private.applications WHERE source_code = 'PORTAL'")).scalar_one())
        conn.execute(text("UPDATE app_private.applications SET application_status = 'SHORTLIST' WHERE application_id = :a"), {"a": app_id})
    response = client.post(f"/v1/talent-pool/applications/{app_id}/mark", headers=headers(portal["hr"]),
                           json={"reason_code": "STRONG_FIT"})
    assert response.status_code == 201
    assert _count("SELECT COUNT(*) FROM app_private.talent_pool_marks") == 1


@integration
@pytest.mark.skipif(not os.environ.get("HRA_TEST_CLAMD_PORT"), reason="Set HRA_TEST_CLAMD_PORT for a real local clamd")
def test_portal_uses_real_clamd_and_refuses_when_it_is_unavailable(client, portal, monkeypatch):
    monkeypatch.setattr(settings, "MALWARE_SCAN_MODE", "clamav")
    monkeypatch.setattr(settings, "CLAMD_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "CLAMD_PORT", int(os.environ["HRA_TEST_CLAMD_PORT"]))
    assert _apply(client, portal).status_code == 202
    monkeypatch.setattr(settings, "CLAMD_PORT", 1)
    assert _apply(client, portal, content=PDF + b"\n%scanner-down").status_code == 503
    assert _count("SELECT COUNT(*) FROM app_private.applications WHERE source_code = 'PORTAL'") == 1


@integration
def test_portal_application_reaches_the_worker_and_the_hr_list(client, portal):
    seed = portal
    assert _apply(client, seed).status_code == 202
    from app.workers.processor import ProcessingWorker
    ProcessingWorker()._process_pending_operations()
    with engine.connect() as conn:
        operation = conn.execute(text("SELECT status FROM app_private.operations WHERE capability = 'CV_PROCESSING'")).scalar_one()
    assert operation == "COMPLETED"  # a portal batch has no uploader but is processed like an HR upload
    listed = client.get("/v1/applications", headers=headers(seed["hr"]), params={"position_id": seed["pos"]}).json()
    assert [a["source_code"] for a in listed if a["source_code"] == "PORTAL"] == ["PORTAL"]
    detail = client.get(f"/v1/applications/{listed[0]['application_id']}", headers=headers(seed["hr"]))
    assert detail.status_code == 200


def test_body_limit_counts_chunked_bodies_too():
    import asyncio
    from app.core.body_limit import PublicBodyLimit
    sent = []

    async def app(scope, receive, send):
        while (await receive()).get("more_body"):
            pass
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def run(chunks):
        queue = [{"type": "http.request", "body": c, "more_body": i < len(chunks) - 1} for i, c in enumerate(chunks)]

        async def receive():
            return queue.pop(0)

        async def send(message):
            sent.append(message)
        await PublicBodyLimit(app, "/v1/public/", 100)(
            {"type": "http", "path": "/v1/public/x", "method": "POST", "headers": []}, receive, send)
    asyncio.run(run([b"a" * 60, b"b" * 60]))      # no Content-Length, 120 bytes > 100
    assert sent[0]["status"] == 413
    sent.clear()
    asyncio.run(run([b"a" * 60]))
    assert sent[0]["status"] == 200


@integration
def test_oversized_public_body_is_refused_before_parsing(client, portal, monkeypatch):
    seed = portal
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_BYTES", 1000)
    big = PDF + b"x" * 200_000
    res = _apply(client, seed, content=big)
    assert res.status_code == 413
    assert _count("SELECT COUNT(*) FROM app_private.applications WHERE source_code = 'PORTAL'") == 0
    # Authenticated endpoints keep their own limits and are not capped by this wrapper.
    assert client.get("/v1/public/positions").status_code == 200


@integration
def test_portal_job_is_tied_to_position_and_waits_for_a_running_job(client, portal):
    """The worker needs operations.position_id to assess and rank a portal CV, and the
    one-job-per-position guard must see portal jobs. A CV that arrives while a job is
    running is held; HR can still queue it with the existing reprocess action."""
    seed = portal
    assert _apply(client, seed).status_code == 202
    first = _count("""SELECT COUNT(*) FROM app_private.operations
        WHERE position_id = :p AND capability = 'CV_PROCESSING' AND status = 'PENDING'""", p=seed["pos"])
    assert first == 1
    # HR upload now sees the portal job as the position's active job.
    active = client.get(f"/v1/operations/position/{seed['pos']}/active", headers=headers(seed["hr"]))
    assert active.status_code == 200 and active.json()

    assert _apply(client, seed, content=PDF + b"\n%while-busy").status_code == 202
    with engine.connect() as conn:
        parked = conn.execute(text("""SELECT a.application_id, d.file_processing_status, d.processing_error
            FROM app_private.applications a JOIN app_private.application_documents d USING (application_id)
            WHERE a.source_code = 'PORTAL' ORDER BY a.created_at DESC LIMIT 1""")).one()
    from app.services.portal_dispatch import DEFERRED_WHILE_BUSY
    assert parked.file_processing_status == "NEEDS_HR_REVIEW" and parked.processing_error == DEFERRED_WHILE_BUSY
    assert _count("SELECT COUNT(*) FROM app_private.operations WHERE position_id = :p", p=seed["pos"]) == 1

    # Once the running job ends, HR's reprocess action queues the parked CV.
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.operations SET status = 'COMPLETED' WHERE position_id = :p"), {"p": seed["pos"]})
    res = client.post(f"/v1/applications/{parked.application_id}/reprocess", headers=headers(seed["hr"]))
    assert res.status_code == 202
    assert _count("""SELECT COUNT(*) FROM app_private.operations
        WHERE position_id = :p AND status = 'PENDING'""", p=seed["pos"]) == 1


@integration
def test_worker_assesses_a_portal_cv(client, portal, monkeypatch):
    """Regression: a portal job without position_id was extracted but then failed with
    'Operation has no associated position' and was never assessed or ranked."""
    import io
    from docx import Document
    from app.workers.processor import worker, llm_client
    seed = portal

    async def extract(**kwargs):
        return {"education": [], "work_history": [], "skills": ["Python"], "certifications": []}

    async def match(**kwargs):
        return {"findings": [{"criterion_id": seed["criterion"], "outcome": "STRONG_MATCH", "confidence": .9,
                              "confidence_band": "HIGH", "evidence": {"verbatim_quote": "Developed Python systems for five years"}}]}
    monkeypatch.setattr(llm_client, "extract_candidate_profile", extract)
    monkeypatch.setattr(llm_client, "match_criterion_evidence", match)
    document = Document()
    document.add_paragraph("Developed Python systems for five years. Built reliable automated testing systems.")
    content = io.BytesIO()
    document.save(content)
    docx_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    res = client.post(f"/v1/public/positions/{seed['pos']}/apply",
                      files={"file": ("candidate.docx", content.getvalue(), docx_mime)},
                      data={"consent_processing": "true", "consent_talent_pool": "false", "website": "", "notice_version": "v4"})
    assert res.status_code == 202
    worker._process_pending_operations()
    with engine.connect() as conn:
        op = conn.execute(text("""SELECT operation_id, status, error_code FROM app_private.operations
            WHERE position_id = :p AND capability = 'CV_PROCESSING' ORDER BY created_at DESC LIMIT 1"""), {"p": seed["pos"]}).one()
        assessed = conn.execute(text("""SELECT COUNT(*) FROM app_private.assessment_runs r
            JOIN app_private.applications a USING (application_id)
            WHERE a.source_code = 'PORTAL' AND r.status = 'COMPLETED'""")).scalar_one()
    assert op.status == "COMPLETED", (op.status, op.error_code)
    assert assessed == 1


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


@integration
def test_parallel_attempts_cannot_exceed_the_rate_limit(client, portal, monkeypatch):
    """Count-then-insert without a lock let N parallel requests all see a count under
    the limit. Attempts from one address are now serialised by an advisory lock."""
    from concurrent.futures import ThreadPoolExecutor
    seed = portal
    monkeypatch.setattr(settings, "PUBLIC_INTAKE_MAX_PER_IP_HOUR", 3)
    with ThreadPoolExecutor(max_workers=8) as pool:
        # Honeypot submissions are cheap and still count as attempts.
        codes = list(pool.map(lambda _: _apply(client, seed, honeypot="bot").status_code, range(12)))
    assert codes.count(202) == 3 and codes.count(429) == 9
    assert _count("SELECT COUNT(*) FROM app_private.public_intake_events") == 3


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
    detail = client.get(f"/v1/positions/{seed['pos']}", headers=headers(seed["hr"])).json()
    assert detail["public_apply_enabled"] is True          # the position page reads the switch state from here
    assert detail["public_intake_enabled"] == settings.PUBLIC_INTAKE_ENABLED


# ---- Talent Pool eligibility ----

def _consented_application(seed, pool=True, status="SHORTLIST", received=None, consented=None):
    app_id = _assessed_application(seed, "MEETS_MANDATORY", "Pool " + uid()[:4])
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.applications SET application_status = :s, created_at = COALESCE(:r, created_at) WHERE application_id = :a"),
                     {"s": status, "r": received, "a": app_id})
        if pool:
            conn.execute(text("""INSERT INTO app_private.application_data_consents(application_id, purpose, notice_version, channel, granted_at)
                VALUES (:a, 'TALENT_POOL', 'v1', 'PORTAL', COALESCE(CAST(:g AS timestamptz), NOW()))"""), {"a": app_id, "g": consented})
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
    long_ago = datetime.now(timezone.utc) - timedelta(days=365 * 5 + 30)
    old = _consented_application(seed, received=long_ago, consented=long_ago)
    state = client.get(f"/v1/talent-pool/applications/{old}", headers=hr).json()
    assert state["reason"] == "RETENTION_EXPIRED"
    # The window starts when the CV was received, not when consent was ticked: an
    # old CV whose Talent Pool consent was given recently is already past its five years.
    late = _consented_application(seed, received=long_ago)
    state = client.get(f"/v1/talent-pool/applications/{late}", headers=hr).json()
    assert state["reason"] == "RETENTION_EXPIRED" and state["can_mark"] is False
    fresh = _consented_application(seed, received=datetime.now(timezone.utc) - timedelta(days=30))
    state = client.get(f"/v1/talent-pool/applications/{fresh}", headers=hr).json()
    assert state["reason"] is None and state["can_mark"] is True
    assert state["expires_on"] == pool_expiry(datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
    metadata = _count("SELECT metadata::text FROM app_private.audit_events WHERE action_type = 'MARK_TALENT_POOL'")
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
    # Plain HR Recruiter cannot record written consent withdrawal; HR Lead or Admin can (spec §7).
    assert client.get(f"/v1/talent-pool/applications/{withdrawn}", headers=hr).json()["can_withdraw_consent"] is False
    assert client.post(f"/v1/talent-pool/applications/{withdrawn}/withdraw-consent", headers=hr, json={"reference": "ref-1"}).status_code == 403
    lead = headers(seed["other"])
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id, role_code) VALUES (:u, 'HR_LEAD')"),
                     {"u": seed["other"]})
    assert client.get(f"/v1/talent-pool/applications/{withdrawn}", headers=lead).json()["can_withdraw_consent"] is True
    assert client.post(f"/v1/talent-pool/applications/{withdrawn}/withdraw-consent", headers=lead, json={"reference": "ref-1"}).status_code == 200
    assert _count("""SELECT evidence->>'withdrawal_reference' FROM app_private.application_data_consents
        WHERE application_id = :a AND purpose = 'TALENT_POOL'""", a=withdrawn) == "ref-1"
    assert client.post(f"/v1/talent-pool/applications/{withdrawn}/withdraw-consent", headers=lead, json={}).status_code == 404
    with engine.begin() as conn:
        # The five years count from receipt of the CV, not from the consent tick.
        conn.execute(text("UPDATE app_private.applications SET created_at = NOW() - INTERVAL '61 months' WHERE application_id = :a"), {"a": expired})
        # An old consent date alone does not expire the pool.
        conn.execute(text("""UPDATE app_private.application_data_consents SET granted_at = NOW() - INTERVAL '61 months'
            WHERE application_id = :a AND purpose = 'TALENT_POOL'"""), {"a": good})
        conn.execute(text("""INSERT INTO app_private.application_retention_cases(application_id, policy_version, position_closed_at, due_date, status)
            SELECT :a, policy_version, NOW(), NOW(), 'ON_HOLD' FROM app_private.retention_policy_versions LIMIT 1"""), {"a": held})
    assert ids() == {good}
    # Unmarking also removes a candidate from the pool.
    assert client.delete(f"/v1/talent-pool/applications/{good}/mark", headers=hr).status_code == 200
    assert ids() == set()


@integration
def test_candidate_withdraws_with_token_and_duplicates_are_idempotent(client, portal):
    seed = portal
    first = _apply(client, seed)
    token = first.json()["withdrawal_token"]
    assert len(token) == 64 and _count("SELECT COUNT(*) FROM app_private.application_data_consents WHERE withdrawal_token_hash = :h", h=token) == 0
    assert _count("SELECT COUNT(*) FROM app_private.application_data_consents WHERE withdrawal_token_hash IS NOT NULL") == 1
    again = _apply(client, seed)  # identical file: no new application, no token
    assert again.status_code == 202 and again.json()["withdrawal_token"] != token  # only a throwaway token
    assert _count("SELECT COUNT(*) FROM app_private.applications WHERE source_code = 'PORTAL'") == 1
    # The v4 checkbox grants reuse regardless of the obsolete optional field.
    assert len(_apply(client, seed, pool=False, content=PDF + b"\n%other").json()["withdrawal_token"]) == 64
    wrong = client.post("/v1/public/talent-pool/withdraw", json={"token": "0" * 64})
    assert wrong.status_code == 200 and wrong.json() == {"status": "ok"}  # same answer for unknown tokens
    assert _count("SELECT COUNT(*) FROM app_private.application_data_consents WHERE purpose = 'TALENT_POOL' AND withdrawn_at IS NOT NULL") == 0
    assert client.post("/v1/public/talent-pool/withdraw", json={"token": token}).json() == {"status": "ok"}
    assert _count("SELECT COUNT(*) FROM app_private.application_data_consents WHERE purpose = 'TALENT_POOL' AND withdrawn_at IS NOT NULL") == 1
    assert _count("""SELECT COUNT(*) FROM app_private.audit_events
        WHERE action_type = 'WITHDRAW_TALENT_POOL_CONSENT_BY_CANDIDATE' AND position_id = :p""", p=seed["pos"]) == 1
    assert client.post("/v1/public/talent-pool/withdraw", json={"token": "xyz"}).status_code == 422


@integration
def test_repeat_and_bot_submissions_look_like_a_fresh_receipt(client, portal):
    seed = portal
    real = _apply(client, seed).json()["withdrawal_token"]
    repeat = _apply(client, seed).json()
    bot = _apply(client, seed, honeypot="x", content=PDF + b"\n%bot").json()
    assert len(repeat["withdrawal_token"]) == 64 and repeat["withdrawal_token"] != real and len(bot["withdrawal_token"]) == 64
    assert _count("SELECT COUNT(*) FROM app_private.application_data_consents WHERE withdrawal_token_hash IS NOT NULL") == 1
    assert client.post("/v1/public/talent-pool/withdraw", json={"token": repeat["withdrawal_token"]}).status_code == 200
    assert _count("SELECT COUNT(*) FROM app_private.application_data_consents WHERE withdrawn_at IS NOT NULL") == 0


@integration
def test_withdrawal_still_works_when_the_portal_is_off(client, portal, monkeypatch):
    token = _apply(client, portal).json()["withdrawal_token"]
    monkeypatch.setattr(settings, "PUBLIC_INTAKE_ENABLED", False)
    assert client.post("/v1/public/talent-pool/withdraw", json={"token": token}).status_code == 200
    assert _count("SELECT COUNT(*) FROM app_private.application_data_consents WHERE withdrawn_at IS NOT NULL") == 1


@integration
def test_portal_gives_up_with_503_while_hr_holds_the_position(client, portal, monkeypatch):
    from app.api import public_intake
    monkeypatch.setattr(public_intake, "LOCK_TIMEOUT", "300ms")
    conn = engine.connect()
    trans = conn.begin()
    try:
        conn.execute(text("SELECT 1 FROM app_private.positions WHERE position_id = :p FOR UPDATE"), {"p": portal["pos"]})
        assert _apply(client, portal).status_code == 503
    finally:
        trans.rollback()
        conn.close()
    assert _count("SELECT COUNT(*) FROM app_private.applications WHERE source_code = 'PORTAL'") == 0
    assert _apply(client, portal).status_code == 202


@integration
def test_position_unpublished_after_lookup_is_refused_under_the_lock(client, portal, monkeypatch):
    from app.api import public_intake
    real_admit = public_intake._admit

    def admit_then_unpublish(code, ip_hash):
        pos = real_admit(code, ip_hash)
        with engine.begin() as conn:
            conn.execute(text("UPDATE app_private.positions SET public_apply_enabled = FALSE WHERE position_id = :p"), {"p": portal["pos"]})
        return pos
    monkeypatch.setattr(public_intake, "_admit", admit_then_unpublish)
    assert _apply(client, portal).status_code == 404
    assert _count("SELECT COUNT(*) FROM app_private.applications WHERE source_code = 'PORTAL'") == 0


@integration
def test_oversized_chunked_upload_is_413_through_the_real_app(client, portal, monkeypatch):
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_BYTES", 1000)

    def chunks():  # a valid multipart body sent with no Content-Length, as the Next proxy does
        yield b'--b\r\nContent-Disposition: form-data; name="file"; filename="cv.pdf"\r\nContent-Type: application/pdf\r\n\r\n'
        yield b"x" * 60_000
        yield b"x" * 60_000
        yield b"\r\n--b--\r\n"
    res = client.post(f"/v1/public/positions/{portal['pos']}/apply", content=chunks(),
                      headers={"content-type": "multipart/form-data; boundary=b"})
    assert res.status_code == 413, res.text


@integration
def test_worker_queues_held_portal_cvs_as_one_job(client, portal):
    """Bug #2: CVs that arrive while the position is busy are held, then queued together
    as one job once the position is free, without HR pressing "reprocess" for each."""
    from app.services.portal_dispatch import LEGACY_DEFERRED_WHILE_BUSY, dispatch_held_portal_cvs
    seed = portal
    assert _apply(client, seed).status_code == 202  # first CV starts a job right away
    for i in range(3):
        assert _apply(client, seed, content=PDF + f"\n%held-{i}".encode()).status_code == 202
    held_sql = """SELECT COUNT(*) FROM app_private.application_documents d JOIN app_private.applications a USING (application_id)
        WHERE a.position_id = :p AND d.file_processing_status = 'NEEDS_HR_REVIEW'"""
    assert _count(held_sql, p=seed["pos"]) == 3
    # An older row stored with the previous wording is picked up as well.
    with engine.begin() as conn:
        conn.execute(text("""UPDATE app_private.application_documents SET processing_error = :t WHERE document_id = (
            SELECT d.document_id FROM app_private.application_documents d JOIN app_private.applications a USING (application_id)
            WHERE a.position_id = :p AND d.file_processing_status = 'NEEDS_HR_REVIEW' ORDER BY d.created_at LIMIT 1)"""),
                     {"t": LEGACY_DEFERRED_WHILE_BUSY, "p": seed["pos"]})

    # Still busy: nothing is queued.
    assert dispatch_held_portal_cvs() == 0
    assert _count("SELECT COUNT(*) FROM app_private.operations WHERE position_id = :p", p=seed["pos"]) == 1

    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.operations SET status = 'COMPLETED' WHERE position_id = :p"), {"p": seed["pos"]})
    assert dispatch_held_portal_cvs() == 3
    pending = _count("""SELECT COUNT(*) FROM app_private.operations
        WHERE position_id = :p AND capability = 'CV_PROCESSING' AND status = 'PENDING'""", p=seed["pos"])
    assert pending == 1
    with engine.connect() as conn:
        batch = conn.execute(text("""SELECT b.total_files, (SELECT COUNT(*) FROM app_private.cv_batch_items i WHERE i.batch_id = b.batch_id) AS items,
                (SELECT COUNT(*) FROM app_private.document_processing_runs r WHERE r.operation_id = b.operation_id) AS runs
            FROM app_private.cv_batches b JOIN app_private.operations o USING (operation_id)
            WHERE o.position_id = :p AND o.status = 'PENDING'"""), {"p": seed["pos"]}).one()
        audited = conn.execute(text("""SELECT COUNT(*) FROM app_private.audit_events
            WHERE action_type = 'QUEUE_HELD_PUBLIC_CVS' AND position_id = :p"""), {"p": seed["pos"]}).scalar_one()
    assert (batch.total_files, batch.items, batch.runs) == (3, 3, 3) and audited == 1
    assert _count(held_sql, p=seed["pos"]) == 0
    # Nothing left: a second poll is a no-op.
    assert dispatch_held_portal_cvs() == 0


@integration
def test_held_portal_cvs_wait_while_position_is_closed(client, portal):
    from app.services.portal_dispatch import dispatch_held_portal_cvs
    seed = portal
    assert _apply(client, seed).status_code == 202
    assert _apply(client, seed, content=PDF + b"\n%held-closed").status_code == 202
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.operations SET status = 'COMPLETED' WHERE position_id = :p"), {"p": seed["pos"]})
        conn.execute(text("UPDATE app_private.positions SET status = 'CLOSED', closed_at = NOW() WHERE position_id = :p"), {"p": seed["pos"]})
    assert dispatch_held_portal_cvs() == 0
    assert _count("""SELECT COUNT(*) FROM app_private.operations WHERE position_id = :p AND status = 'PENDING'""", p=seed["pos"]) == 0
