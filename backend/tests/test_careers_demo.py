"""Synthetic demo integration on disposable local PostgreSQL only."""
import io
import os
from uuid import uuid4

import pytest
from docx import Document
from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine
from test_phase1_integration import seed as seed, client as client, headers

pytestmark = pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'), reason='Disposable PostgreSQL required')


@pytest.fixture(autouse=True)
def enabled(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'CAREERS_DEMO_ENABLED', True)
    monkeypatch.setattr(settings, 'STORAGE_BACKEND', 'local')
    monkeypatch.setattr(settings, 'LOCAL_STORAGE_PATH', str(tmp_path))


def test_demo_gate_and_job_listing(client, seed, monkeypatch):
    url = '/v1/careers-demo/jobs'
    assert client.get(url).json() == []
    # HR alone can set a timezone-aware deadline; no deadline means private.
    assert client.patch(f"/v1/positions/{seed['pos']}", headers=headers(seed['hm']), json={'application_deadline_at': '2099-01-01T00:00:00Z'}).status_code == 403
    assert client.patch(f"/v1/positions/{seed['pos']}", headers=headers(seed['hr']), json={'application_deadline_at': '2099-01-01T00:00:00'}).status_code == 400
    assert client.patch(f"/v1/positions/{seed['pos']}", headers=headers(seed['hr']), json={'application_deadline_at': '2099-01-01T00:00:00Z'}).status_code == 200
    result = client.get(url).json()
    assert len(result) == 1 and result[0]['position_id'] == seed['pos'] and not result[0]['can_apply']
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET status='PAUSED' WHERE position_id=:id"), {'id': seed['pos']})
    assert client.get(url).json() == []
    monkeypatch.setattr(settings, 'APP_ENV', 'production')
    assert client.get(url).status_code == 404
    monkeypatch.setattr(settings, 'APP_ENV', 'testing')
    monkeypatch.setattr(settings, 'DATABASE_URL', 'postgresql://user@remote.example/hra_test')
    assert client.get(url).status_code == 404


def test_apply_demo_atomic_idempotent_and_visible_to_hr(client, seed, monkeypatch):
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET application_deadline_at=now()+interval '1 day' WHERE position_id=:id"), {'id': seed['pos']})
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"), {'id': seed['cv']})
    document = Document(); document.add_paragraph('Synthetic test document for a Python backend engineer with examples only. ' * 4); out = io.BytesIO(); document.save(out)
    url = f"/v1/careers-demo/jobs/{seed['pos']}/apply"
    request_id = str(uuid4())
    def send():
        return client.post(url, data={'request_id': request_id, 'name': 'Synthetic Name', 'email': 'synthetic@example.org'}, files={'cv': ('synthetic.docx', out.getvalue(), 'application/octet-stream')})
    first = send()
    assert first.status_code == 202, first.text
    assert send().status_code == 202
    with engine.connect() as conn:
        row = conn.execute(text("""SELECT a.application_id,a.created_by,i.display_name,i.email,b.uploaded_by,b.intake_source
            FROM app_private.applications a JOIN app_private.application_identities i USING (application_id)
            JOIN app_private.cv_batch_items bi USING (application_id) JOIN app_private.cv_batches b USING (batch_id)
            WHERE a.source_code='CAREERS_DEMO'""")).mappings().one()
        assert row['created_by'] is None and row['uploaded_by'] is None
        assert row['display_name'] == 'Synthetic Name' and row['email'] == 'synthetic@example.org'
        assert row['intake_source'] == 'CAREERS_DEMO'
    listing = client.get("/v1/applications", params={"position_id": seed["pos"]}, headers=headers(seed["hr"]))
    assert listing.status_code == 200, listing.text
    assert any(str(x['application_id']) == str(row['application_id']) for x in listing.json())
    # Exercise the existing fenced worker with a synthetic document and mocked model.
    from app.workers.processor import worker, llm_client
    async def synthetic_profile(**kwargs):
        return {'education': [], 'work_history': [], 'skills': []}
    monkeypatch.setattr(llm_client, 'extract_candidate_profile', synthetic_profile)
    worker._process_pending_operations()
    with engine.connect() as conn:
        identity = conn.execute(text('SELECT display_name,email FROM app_private.application_identities WHERE application_id=:id'), {'id': row['application_id']}).one()
        document_status = conn.execute(text('SELECT file_processing_status FROM app_private.application_documents WHERE application_id=:id'), {'id': row['application_id']}).scalar_one()
    assert identity == ('Synthetic Name', 'synthetic@example.org')
    assert document_status == 'COMPLETED'
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET application_deadline_at=now()-interval '1 second' WHERE position_id=:id"), {'id': seed['pos']})
    assert send().status_code == 404


def test_deadline_rechecked_after_waiting_for_position_lock(client, seed):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"), {'id': seed['cv']})
    document = Document(); document.add_paragraph('Synthetic test content ' * 10); out = io.BytesIO(); document.save(out)
    started = Event()
    def send():
        started.set()
        return client.post(f"/v1/careers-demo/jobs/{seed['pos']}/apply", data={
            'request_id': str(uuid4()), 'name': 'Synthetic', 'email': 'test@example.org'},
            files={'cv': ('synthetic.docx', out.getvalue(), 'application/octet-stream')})
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET application_deadline_at=clock_timestamp()+interval '1 second' WHERE position_id=:id"), {'id': seed['pos']})
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(send)
            assert started.wait(5)
            conn.execute(text('SELECT pg_sleep(1.2)'))
            # Releasing the lock must happen before waiting for the request.
            conn.commit()
            assert future.result(timeout=10).status_code == 404
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM app_private.applications WHERE source_code='CAREERS_DEMO'")).scalar_one() == 0
