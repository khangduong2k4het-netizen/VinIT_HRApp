"""Opt-in browser → Next proxy → API → disposable PostgreSQL → worker test.

Requires TEST_DATABASE_URL, HRA_TEST_PUBLIC_BROWSER=1, frontend/node_modules,
and a Playwright-compatible Chromium (HRA_E2E_CHROMIUM_EXECUTABLE if needed).
HRA_TEST_CLAMD_PORT optionally enables a real local scanner as well.
"""
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time

import httpx
import pytest
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL") or os.environ.get("HRA_TEST_PUBLIC_BROWSER") != "1",
    reason="Requires disposable TEST_DATABASE_URL and HRA_TEST_PUBLIC_BROWSER=1",
)

if os.environ.get("TEST_DATABASE_URL"):
    from test_phase1_integration import client, headers, seed, uid  # noqa: F401
    from test_public_intake_talent_pool import portal  # noqa: F401


def _port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait(url, process=None):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError("Test Next.js server exited; see next.log")
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(.2)
    raise RuntimeError(f"Test service did not start: {url}")


def test_public_browser_submission_reaches_worker_and_hr(client, portal, monkeypatch, tmp_path):
    from docx import Document
    import uvicorn
    from app.core.config import settings
    from app.db.database import engine
    from app.main import app
    from app.workers.processor import worker
    from test_talent_pool_scan import _stub_ai

    # TestClient normally doesn't run lifespan here; starting uvicorn must not
    # start a competing background worker. Drive the worker explicitly below.
    monkeypatch.setattr(settings, "APP_ENV", "testing")
    if os.environ.get("HRA_TEST_CLAMD_PORT"):
        monkeypatch.setattr(settings, "MALWARE_SCAN_MODE", "clamav")
        monkeypatch.setattr(settings, "CLAMD_HOST", "127.0.0.1")
        monkeypatch.setattr(settings, "CLAMD_PORT", int(os.environ["HRA_TEST_CLAMD_PORT"]))
    _stub_ai(monkeypatch, [])
    root = Path(__file__).resolve().parents[2]
    frontend = root / "frontend"
    # A separate Next build directory prevents collisions with a developer's server.
    next_root = tmp_path / "frontend"
    shutil.copytree(frontend, next_root, ignore=shutil.ignore_patterns("node_modules", ".next", ".env*", "tsconfig.tsbuildinfo"))
    (next_root / "node_modules").symlink_to(frontend / "node_modules", target_is_directory=True)
    fixture = {}
    for key in ("first_cv", "second_cv"):
        doc = Document()
        doc.add_paragraph("Synthetic Candidate " + key)
        doc.add_paragraph("Developed Python systems for five years. Built reliable automated testing systems.")
        buffer = io.BytesIO()
        doc.save(buffer)
        path = tmp_path / f"{key}.docx"
        path.write_bytes(buffer.getvalue())
        fixture[key] = str(path)
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(fixture))
    api_port, next_port = _port(), _port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=api_port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    process = None
    thread.start()
    try:
        _wait(f"http://127.0.0.1:{api_port}/health")
        env = {**os.environ, "API_INTERNAL_URL": f"http://127.0.0.1:{api_port}", "NEXT_TELEMETRY_DISABLED": "1"}
        with (tmp_path / "next.log").open("w+") as log:
            process = subprocess.Popen(["node", str(frontend / "node_modules/next/dist/bin/next"), "dev",
                                        "--hostname", "127.0.0.1", "--port", str(next_port)],
                                       cwd=next_root, env=env, stdout=log, stderr=subprocess.STDOUT)
            _wait(f"http://127.0.0.1:{next_port}/apply", process)
            result = subprocess.run(["node", str(frontend / "tests/public-apply.e2e.cjs")], cwd=frontend,
                                    env={**env, "HRA_E2E_BASE_URL": f"http://127.0.0.1:{next_port}",
                                         "HRA_E2E_FIXTURE": str(fixture_path)},
                                    capture_output=True, text=True, timeout=120)
            assert result.returncode == 0, result.stdout + result.stderr

        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM app_private.applications WHERE source_code = 'PORTAL'")).scalar_one() == 2
            assert conn.execute(text("SELECT COUNT(*) FROM app_private.application_data_consents WHERE purpose = 'THIS_POSITION'")).scalar_one() == 2
            assert conn.execute(text("SELECT COUNT(*) FROM app_private.application_data_consents WHERE purpose = 'TALENT_POOL' AND notice_version = 'v4'")).scalar_one() == 2
            assert conn.execute(text("SELECT COUNT(*) FROM app_private.application_data_consents WHERE purpose = 'TALENT_POOL' AND withdrawn_at IS NOT NULL")).scalar_one() == 1
        worker._process_pending_operations()
        # The second submission arrived while the first was queued. Verify HR
        # can reprocess that parked CV after the first job finishes.
        with engine.connect() as conn:
            parked = conn.execute(text("""SELECT a.application_id FROM app_private.applications a
                JOIN app_private.application_documents d USING (application_id)
                WHERE a.source_code = 'PORTAL' AND d.file_processing_status = 'NEEDS_HR_REVIEW'""")).scalar_one()
        assert client.post(f"/v1/applications/{parked}/reprocess", headers=headers(portal["hr"])).status_code == 202
        worker._process_pending_operations()
        with engine.connect() as conn:
            assert conn.execute(text("""SELECT COUNT(*) FROM app_private.assessment_runs r
                JOIN app_private.applications a USING (application_id)
                WHERE a.source_code = 'PORTAL' AND r.status = 'COMPLETED'""")).scalar_one() == 2
        listed = client.get("/v1/applications", headers=headers(portal["hr"]), params={"position_id": portal["pos"]})
        assert listed.status_code == 200
        assert len([a for a in listed.json() if a["source_code"] == "PORTAL"]) == 2
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        server.should_exit = True
        thread.join(timeout=10)
