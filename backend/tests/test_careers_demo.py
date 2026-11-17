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


def test_demo_pool_opt_in_permissions_withdrawal_and_retention(client, seed):
    target_jd, target_cv = str(uuid4()), str(uuid4())
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET application_deadline_at=now()+interval '1 day' WHERE position_id=:id"), {'id': seed['pos']})
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"), {'id': seed['cv']})
        conn.execute(text("INSERT INTO app_private.position_assignments(position_id,user_id,position_role) VALUES (:p,:u,'HR_RECRUITER')"), {'p': seed['pos2'], 'u': seed['hr']})
        conn.execute(text("INSERT INTO app_private.jd_versions(jd_version_id,position_id,version_number,content_text,created_by) VALUES (:id,:p,1,'synthetic',:u)"), {'id': target_jd, 'p': seed['pos2'], 'u': seed['hr']})
        conn.execute(text("INSERT INTO app_private.criteria_versions(criteria_version_id,position_id,jd_version_id,version_number,status) VALUES (:id,:p,:jd,1,'APPROVED')"), {'id': target_cv, 'p': seed['pos2'], 'jd': target_jd})
        assert not conn.execute(text("SELECT has_table_privilege('anon','app_private.talent_pool_demo_consents','SELECT')")).scalar_one()
    document = Document(); document.add_paragraph('Synthetic demo CV ' * 10); out = io.BytesIO(); document.save(out)
    token = 'ab' * 32
    response = client.post(f"/v1/careers-demo/jobs/{seed['pos']}/apply", data={
        'request_id': str(uuid4()), 'name': 'Demo opted in', 'email': 'demo@example.org', 'pool_opt_in': 'true', 'pool_token': token},
        files={'cv': ('synthetic.docx', out.getvalue(), 'application/octet-stream')})
    assert response.status_code == 202, response.text
    with engine.begin() as conn:
        app = conn.execute(text("SELECT application_id FROM app_private.applications WHERE source_code='CAREERS_DEMO'")).scalar_one()
        conn.execute(text("UPDATE app_private.application_documents SET file_processing_status='COMPLETED' WHERE application_id=:a"), {'a': app})
        assert conn.execute(text('SELECT token_hash FROM app_private.talent_pool_demo_consents WHERE application_id=:a'), {'a': app}).scalar_one() != token
    params = {'source_position_id': seed['pos'], 'target_position_id': seed['pos2']}
    scan = lambda user: client.get('/v1/careers-demo/pool/scan', params=params, headers=headers(user))
    assert scan(seed['hm']).status_code == 403
    assert scan(seed['hr2']).status_code == 403
    result = scan(seed['hr'])
    assert result.status_code == 200, result.text
    assert [r['display_name'] for r in result.json()['items']] == ['Demo opted in']
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET status='CLOSED',closed_at=now() WHERE position_id=:p"), {'p': seed['pos']})
    assert scan(seed['hr']).json()['items'] == []
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET status='OPEN',closed_at=NULL WHERE position_id=:p"), {'p': seed['pos']})
        conn.execute(text("UPDATE app_private.talent_pool_demo_consents SET expires_at=now()-interval '1 day', accepted_at=now()-interval '2 days' WHERE application_id=:a"), {'a': app})
    assert scan(seed['hr']).json()['items'] == []
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.talent_pool_demo_consents SET expires_at=now()+interval '1 day' WHERE application_id=:a"), {'a': app})
    assert len(scan(seed['hr']).json()['items']) == 1
    with engine.begin() as conn:
        policy = conn.execute(text('SELECT policy_version FROM app_private.retention_policy_versions LIMIT 1')).scalar_one()
        case = conn.execute(text("""INSERT INTO app_private.application_retention_cases
            (application_id,position_id,policy_version,position_closed_at,due_date,status)
            VALUES (:a,:p,:policy,now(),now(),'PENDING') RETURNING retention_case_id"""), {'a': app, 'p': seed['pos'], 'policy': policy}).scalar_one()
    assert scan(seed['hr']).json()['items'] == []
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.application_retention_cases SET status='CANCELLED' WHERE retention_case_id=:case"), {'case': case})
    assert len(scan(seed['hr']).json()['items']) == 1
    assert client.post('/v1/careers-demo/pool/withdraw', json={'token': token}).status_code == 200
    assert client.post('/v1/careers-demo/pool/withdraw', json={'token': token}).status_code == 200
    assert scan(seed['hr']).json()['items'] == []


def test_offline_email_intake_permission_routing_and_idempotency(client, seed):
    from email.message import EmailMessage
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET application_deadline_at=now()+interval '1 day' WHERE position_id=:id"), {'id': seed['pos']})
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"), {'id': seed['cv']})
        code = conn.execute(text('SELECT position_code FROM app_private.positions WHERE position_id=:id'), {'id': seed['pos']}).scalar_one()
    doc = Document(); doc.add_paragraph('Synthetic CV ' * 10); out = io.BytesIO(); doc.save(out)
    msg = EmailMessage(); msg['From'] = 'unverified@example.invalid'; msg['Subject'] = f'Apply {code}'; msg.set_content('Synthetic only')
    msg.add_attachment(out.getvalue(), maintype='application', subtype='octet-stream', filename='synthetic.docx')
    request_id = str(uuid4())
    def send(user, data=None):
        return client.post('/v1/careers-demo/email/ingest', headers=headers(user), data={'request_id': request_id}, files={'message': ('synthetic.eml', data or msg.as_bytes(), 'message/rfc822')})
    assert send(seed['hm']).status_code == 403
    accepted = send(seed['hr'])
    assert accepted.status_code == 202 and accepted.json()['status'] == 'ACCEPTED', accepted.text
    assert send(seed['hr']).json()['status'] == 'ACCEPTED'
    with engine.connect() as conn:
        row = conn.execute(text("""SELECT a.application_id,a.created_by,i.email,b.intake_source,b.uploaded_by
            FROM app_private.applications a JOIN app_private.application_identities i USING(application_id)
            JOIN app_private.cv_batch_items bi USING(application_id) JOIN app_private.cv_batches b USING(batch_id)
            WHERE a.source_code='EMAIL_DEMO'""")).mappings().one()
        assert str(row['created_by']) == seed['hr'] and str(row['uploaded_by']) == seed['hr']
        assert row['email'] == 'email-demo@example.invalid' and row['intake_source'] == 'EMAIL_DEMO'
        assert not conn.execute(text('SELECT 1 FROM app_private.talent_pool_demo_consents WHERE application_id=:id'), {'id': row['application_id']}).first()
    wrong = EmailMessage(); wrong['Subject'] = 'No known code'; wrong.set_content('synthetic')
    review = send(seed['hr'], wrong.as_bytes())
    assert review.status_code == 202 and review.json() == {'status': 'REVIEW', 'reason': 'POSITION_AMBIGUOUS'}
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET status='PAUSED' WHERE position_id=:id"), {'id': seed['pos']})
    assert send(seed['hr']).status_code == 404


def test_scan_waiting_on_withdrawal_does_not_return_candidate(client, seed):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    import time
    target_jd, target_cv = str(uuid4()), str(uuid4())
    app, document = str(uuid4()), str(uuid4())
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.position_assignments(position_id,user_id,position_role) VALUES (:p,:u,'HR_RECRUITER')"), {'p': seed['pos2'], 'u': seed['hr']})
        conn.execute(text("INSERT INTO app_private.jd_versions(jd_version_id,position_id,version_number,content_text,created_by) VALUES (:id,:p,1,'synthetic',:u)"), {'id': target_jd, 'p': seed['pos2'], 'u': seed['hr']})
        conn.execute(text("INSERT INTO app_private.criteria_versions(criteria_version_id,position_id,jd_version_id,version_number,status) VALUES (:id,:p,:jd,1,'APPROVED')"), {'id': target_cv, 'p': seed['pos2'], 'jd': target_jd})
        conn.execute(text("INSERT INTO app_private.applications(application_id,position_id,source_code) VALUES (:a,:p,'CAREERS_DEMO')"), {'a': app, 'p': seed['pos']})
        conn.execute(text("INSERT INTO app_private.application_identities(application_id,display_name) VALUES (:a,'synthetic')"), {'a': app})
        conn.execute(text("""INSERT INTO app_private.application_documents(document_id,application_id,bucket,storage_path,original_filename,mime_type,size_bytes,file_processing_status)
            VALUES (:id,:a,'synthetic','synthetic','synthetic.pdf','application/pdf',10,'COMPLETED')"""), {'id': document, 'a': app})
        conn.execute(text("""INSERT INTO app_private.talent_pool_demo_consents(application_id,notice_version,token_hash,expires_at)
            VALUES (:a,'synthetic-demo-v1',:hash,now()+interval '1 day')"""), {'a': app, 'hash': 'ab' * 32})
    started = Event()
    def scan():
        started.set()
        return client.get('/v1/careers-demo/pool/scan', headers=headers(seed['hr']), params={'source_position_id': seed['pos'], 'target_position_id': seed['pos2']})
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.talent_pool_demo_consents SET withdrawn_at=now() WHERE application_id=:a"), {'a': app})
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(scan)
            assert started.wait(5)
            waiting = 0
            for _ in range(100):
                conn.execute(text('SELECT pg_stat_clear_snapshot()'))
                waiting = conn.execute(text("""SELECT count(*) FROM pg_stat_activity
                    WHERE datname=current_database() AND wait_event_type='Lock'
                      AND query LIKE 'SELECT a.application_id, a.position_id, i.display_name%'""")).scalar_one()
                if waiting:
                    break
                time.sleep(0.02)
            conn.commit()
            assert waiting, 'scan did not block on the consent row'
            response = future.result(timeout=10)
            assert response.status_code == 200 and response.json()['items'] == []
