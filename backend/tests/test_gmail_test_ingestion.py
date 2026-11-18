"""Disposable DB, local Storage, fake Gmail/spam/AV and synthetic data only."""
import io
import os
from email.message import EmailMessage
from unittest.mock import Mock

import pytest
from docx import Document
from sqlalchemy import text

from app.api import gmail_test
from app.core.config import settings
from app.db.database import engine
from app.services.malware_scan import ScanVerdict
from app.services.spam_scan import SpamVerdict
from test_phase1_integration import seed as seed, client as client, headers

pytestmark = pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'), reason='Disposable PostgreSQL required')


@pytest.fixture
def gmail_ready(seed, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'GMAIL_TEST_INGEST_ENABLED', True)
    monkeypatch.setattr(settings, 'GMAIL_TEST_GMAIL_SPAM_ONLY', False)
    monkeypatch.setattr(settings, 'CLAMAV_UNIX_SOCKET', '/synthetic/clamd.sock')
    monkeypatch.setattr(settings, 'SPAMD_UNIX_SOCKET', '/synthetic/spamd.sock')
    monkeypatch.setattr(settings, 'STORAGE_BACKEND', 'local')
    monkeypatch.setattr(settings, 'LOCAL_STORAGE_PATH', str(tmp_path))
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id,role_code) VALUES (:id,'HR_LEAD')"), {'id': seed['hr']})
        conn.execute(text("UPDATE app_private.positions SET status='OPEN',application_deadline_at=now()+interval '1 day' WHERE position_id=:id"), {'id': seed['pos']})
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"), {'id': seed['cv']})
    doc = Document(); doc.add_paragraph('Synthetic email CV data. ' * 10); output = io.BytesIO(); doc.save(output)
    message = EmailMessage(); message['Subject'] = f"[HRA-TEST] Synthetic CV for {seed['pos']}"
    message['From'] = 'fake@example.test'; message['To'] = 'fake@example.test'; message.set_content('Synthetic email only')
    message.add_attachment(output.getvalue(), maintype='application', subtype='vnd.openxmlformats-officedocument.wordprocessingml.document', filename='synthetic.docx')
    raw = message.as_bytes()
    session = Mock()
    monkeypatch.setattr(gmail_test.gmail_test_client, 'open_session', lambda: session)
    monkeypatch.setattr(gmail_test.gmail_test_client, 'mailbox_hash', lambda s: 'ab' * 32)
    monkeypatch.setattr(gmail_test.gmail_test_client, 'list_messages', lambda s, page: (['test-message-1'], None))
    monkeypatch.setattr(gmail_test.gmail_test_client, 'fetch_message', lambda s, mid: (['INBOX'], raw))
    order = []
    def av(content, **kwargs): order.append(('av', len(content))); return ScanVerdict.CLEAN
    def spam(content, **kwargs): order.append(('spam', len(content))); return SpamVerdict.HAM
    monkeypatch.setattr(gmail_test, 'scan_bytes', av)
    monkeypatch.setattr(gmail_test, 'scan_message', spam)
    return seed, raw, session, order


def test_gmail_happy_dedupe_no_implicit_pool_consent(client, gmail_ready):
    seed, raw, session, order = gmail_ready
    assert client.post('/v1/gmail-test/sync', headers=headers(seed['hm'])).status_code == 403
    first = client.post('/v1/gmail-test/sync', headers=headers(seed['hr']))
    assert first.status_code == 200, first.text
    assert first.json() == {'processed': 1, 'next_page_token': None, 'spam_mode': 'SPAMD'}
    assert [x[0] for x in order] == ['av', 'spam', 'av']
    assert client.post('/v1/gmail-test/sync', headers=headers(seed['hr'])).json()['processed'] == 0
    records = client.get('/v1/gmail-test/review', headers=headers(seed['hr'])).json()['items']
    assert len(records) == 1 and records[0]['status'] == 'ACCEPTED'
    with engine.connect() as conn:
        row = conn.execute(text("""SELECT a.source_code,i.display_name,i.email,b.intake_source,r.status
            FROM app_private.gmail_test_messages r JOIN app_private.applications a USING (application_id)
            JOIN app_private.application_identities i USING (application_id)
            JOIN app_private.cv_batch_items bi USING (application_id) JOIN app_private.cv_batches b USING (batch_id)""")).one()
        assert row == ('EMAIL_TEST', 'Gmail thử nghiệm', 'gmail-test@example.test', 'EMAIL_TEST', 'ACCEPTED')
        assert conn.execute(text('SELECT count(*) FROM app_private.talent_pool_consents')).scalar_one() == 0
        assert not conn.execute(text("SELECT has_table_privilege('anon','app_private.gmail_test_messages','select')")).scalar_one()
    assert session.close.call_count == 2


def test_scanners_fail_closed_and_review_can_retry(client, gmail_ready, monkeypatch):
    seed, raw, _, order = gmail_ready
    monkeypatch.setattr(gmail_test, 'scan_bytes', lambda *a, **k: ScanVerdict.UNAVAILABLE)
    assert client.post('/v1/gmail-test/sync', headers=headers(seed['hr'])).status_code == 200
    assert client.get('/v1/gmail-test/review', headers=headers(seed['hr'])).json()['items'][0]['reason'] == 'ANTIVIRUS_UNAVAILABLE'
    assert not order
    monkeypatch.setattr(gmail_test, 'scan_bytes', lambda *a, **k: ScanVerdict.CLEAN)
    monkeypatch.setattr(gmail_test, 'scan_message', lambda *a, **k: SpamVerdict.UNAVAILABLE)
    assert client.post('/v1/gmail-test/sync', headers=headers(seed['hr'])).status_code == 200
    assert client.get('/v1/gmail-test/review', headers=headers(seed['hr'])).json()['items'][0]['reason'] == 'SPAM_FILTER_UNAVAILABLE'
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM app_private.applications WHERE source_code='EMAIL_TEST'")).scalar_one() == 0


def test_spam_malware_and_missing_synthetic_marker_do_not_import(client, gmail_ready, monkeypatch):
    seed, raw, _, _ = gmail_ready
    monkeypatch.setattr(gmail_test, 'scan_message', lambda *a, **k: SpamVerdict.SPAM)
    assert client.post('/v1/gmail-test/sync', headers=headers(seed['hr'])).status_code == 200
    assert client.get('/v1/gmail-test/review', headers=headers(seed['hr'])).json()['items'][0]['status'] == 'SPAM'
    monkeypatch.setattr(gmail_test.gmail_test_client, 'list_messages', lambda s, page: (['test-message-2'], None))
    monkeypatch.setattr(gmail_test, 'scan_bytes', lambda *a, **k: ScanVerdict.INFECTED)
    assert client.post('/v1/gmail-test/sync', headers=headers(seed['hr'])).status_code == 200
    assert {r['status'] for r in client.get('/v1/gmail-test/review', headers=headers(seed['hr'])).json()['items']} == {'SPAM', 'MALWARE'}
    monkeypatch.setattr(gmail_test.gmail_test_client, 'list_messages', lambda s, page: (['test-message-3'], None))
    monkeypatch.setattr(gmail_test.gmail_test_client, 'fetch_message', lambda s, mid: (['INBOX'], raw.replace(b'[HRA-TEST] ', b'[NO-TEST] ')))
    monkeypatch.setattr(gmail_test, 'scan_bytes', lambda *a, **k: ScanVerdict.CLEAN)
    monkeypatch.setattr(gmail_test, 'scan_message', lambda *a, **k: SpamVerdict.HAM)
    assert client.post('/v1/gmail-test/sync', headers=headers(seed['hr'])).status_code == 200
    assert 'SYNTHETIC_MARKER_REQUIRED' in {r['reason'] for r in client.get('/v1/gmail-test/review', headers=headers(seed['hr'])).json()['items']}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM app_private.applications WHERE source_code='EMAIL_TEST'")).scalar_one() == 0


def test_disabled_before_mailbox_access(client, gmail_ready, monkeypatch):
    seed, _, _, _ = gmail_ready
    monkeypatch.setattr(settings, 'GMAIL_TEST_INGEST_ENABLED', False)
    monkeypatch.setattr(gmail_test.gmail_test_client, 'open_session', Mock(side_effect=AssertionError('must not connect')))
    assert client.post('/v1/gmail-test/sync', headers=headers(seed['hr'])).status_code == 404


def test_gmail_to_worker_preserves_synthetic_identity(client, gmail_ready, monkeypatch):
    from app.workers.processor import ProcessingWorker, llm_client
    seed, _, _, _ = gmail_ready
    async def profile(**kwargs):
        return {'education': [], 'work_history': [], 'skills': [], 'certifications': []}
    async def match(**kwargs):
        return {'findings': []}
    monkeypatch.setattr(llm_client, 'extract_candidate_profile', profile)
    monkeypatch.setattr(llm_client, 'match_criterion_evidence', match)
    assert client.post('/v1/gmail-test/sync', headers=headers(seed['hr'])).status_code == 200
    ProcessingWorker()._process_pending_operations()
    with engine.connect() as conn:
        row = conn.execute(text("""SELECT o.status,d.file_processing_status,i.display_name,i.email
            FROM app_private.gmail_test_messages r JOIN app_private.application_identities i USING (application_id)
            JOIN app_private.application_documents d USING (application_id)
            JOIN app_private.cv_batch_items bi USING (application_id)
            JOIN app_private.cv_batches b USING (batch_id) JOIN app_private.operations o USING (operation_id)""")).one()
        assert row == ('COMPLETED', 'COMPLETED', 'Gmail thử nghiệm', 'gmail-test@example.test')


def test_gmail_labels_only_mode_still_requires_antivirus_and_guards(client, gmail_ready, monkeypatch):
    seed, raw, _, order = gmail_ready
    monkeypatch.setattr(settings, 'GMAIL_TEST_GMAIL_SPAM_ONLY', True)
    monkeypatch.setattr(settings, 'SPAMD_UNIX_SOCKET', '')
    never_spamd = Mock(side_effect=AssertionError('spamd must not be called'))
    monkeypatch.setattr(gmail_test, 'scan_message', never_spamd)
    result = client.post('/v1/gmail-test/sync', headers=headers(seed['hr']))
    assert result.status_code == 200 and result.json()['spam_mode'] == 'GMAIL_LABELS_ONLY_TEST'
    assert [step for step, _ in order] == ['av', 'av'] and not never_spamd.called
    assert client.get('/v1/gmail-test/review', headers=headers(seed['hr'])).json()['spam_mode'] == 'GMAIL_LABELS_ONLY_TEST'
    with engine.connect() as conn:
        assert conn.execute(text("SELECT metadata->>'spam_mode' FROM app_private.audit_events WHERE action_type='GMAIL_TEST_PROCESS' ORDER BY created_at DESC LIMIT 1")).scalar_one() == 'GMAIL_LABELS_ONLY_TEST'
    monkeypatch.setattr(gmail_test.gmail_test_client, 'list_messages', lambda s, page: (['test-message-2'], None))
    monkeypatch.setattr(gmail_test, 'scan_bytes', lambda *a, **k: ScanVerdict.UNAVAILABLE)
    assert client.post('/v1/gmail-test/sync', headers=headers(seed['hr'])).status_code == 200
    assert 'ANTIVIRUS_UNAVAILABLE' in {item['reason'] for item in client.get('/v1/gmail-test/review', headers=headers(seed['hr'])).json()['items']}
    monkeypatch.setattr(gmail_test.gmail_test_client, 'list_messages', lambda s, page: (['test-message-3'], None))
    monkeypatch.setattr(gmail_test.gmail_test_client, 'fetch_message', lambda s, mid: (['SPAM'], raw))
    assert client.post('/v1/gmail-test/sync', headers=headers(seed['hr'])).status_code == 200
    assert 'GMAIL_SPAM_OR_TRASH' in {item['reason'] for item in client.get('/v1/gmail-test/review', headers=headers(seed['hr'])).json()['items']}
    monkeypatch.setattr(settings, 'CLAMAV_UNIX_SOCKET', '')
    assert client.post('/v1/gmail-test/sync', headers=headers(seed['hr'])).status_code == 503


def test_spamd_is_required_by_default(client, gmail_ready, monkeypatch):
    seed, _, _, _ = gmail_ready
    monkeypatch.setattr(settings, 'SPAMD_UNIX_SOCKET', '')
    assert client.post('/v1/gmail-test/sync', headers=headers(seed['hr'])).status_code == 503


def test_retry_review_by_receipt_without_relisting(client, gmail_ready, monkeypatch):
    seed, _, _, _ = gmail_ready
    monkeypatch.setattr(gmail_test, 'scan_bytes', lambda *a, **k: ScanVerdict.UNAVAILABLE)
    assert client.post('/v1/gmail-test/sync', headers=headers(seed['hr'])).status_code == 200
    receipt = client.get('/v1/gmail-test/review', headers=headers(seed['hr'])).json()['items'][0]
    url = f"/v1/gmail-test/review/{receipt['receipt_id']}/retry"
    assert client.post(url, headers=headers(seed['hm'])).status_code == 403
    monkeypatch.setattr(gmail_test.gmail_test_client, 'list_messages', Mock(side_effect=AssertionError('must not list')))
    monkeypatch.setattr(gmail_test.gmail_test_client, 'mailbox_hash', lambda s: 'cd' * 32)
    assert client.post(url, headers=headers(seed['hr'])).status_code == 409
    monkeypatch.setattr(gmail_test.gmail_test_client, 'mailbox_hash', lambda s: 'ab' * 32)
    monkeypatch.setattr(gmail_test, 'scan_bytes', lambda *a, **k: ScanVerdict.CLEAN)
    result = client.post(url, headers=headers(seed['hr']))
    assert result.status_code == 200 and result.json()['status'] == 'ACCEPTED'
    assert client.post(url, headers=headers(seed['hr'])).status_code == 409
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM app_private.applications WHERE source_code='EMAIL_TEST'")).scalar_one() == 1


def test_confirm_only_synthetic_identity_with_conflict_and_audit(client, gmail_ready, monkeypatch):
    seed, _, _, _ = gmail_ready
    assert client.post('/v1/gmail-test/sync', headers=headers(seed['hr'])).status_code == 200
    receipt = client.get('/v1/gmail-test/review', headers=headers(seed['hr'])).json()['items'][0]
    url = f"/v1/gmail-test/review/{receipt['receipt_id']}/identity"
    assert client.get(url, headers=headers(seed['hm'])).status_code == 403
    info = client.get(url, headers=headers(seed['hr']))
    assert info.status_code == 200 and info.headers['cache-control'] == 'no-store'
    body = {'display_name': 'Ứng viên giả', 'email': 'fake@example.test',
            'expected_updated_at': info.json()['updated_at'], 'confirm_synthetic': True}
    assert client.put(url, headers=headers(seed['hr']), json=body).status_code == 409  # worker active
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.operations SET status='COMPLETED' WHERE position_id=:pos AND capability='CV_PROCESSING'"), {'pos': seed['pos']})
    for invalid in ({'email': 'real@gmail.com'}, {'confirm_synthetic': False}, {'display_name': '   '}):
        assert client.put(url, headers=headers(seed['hr']), json={**body, **invalid}).status_code == 400
    assert client.put(url, headers=headers(seed['hm']), json=body).status_code == 403
    saved = client.put(url, headers=headers(seed['hr']), json=body)
    assert saved.status_code == 200, saved.text
    assert client.put(url, headers=headers(seed['hr']), json=body).status_code == 409
    with engine.connect() as conn:
        data = conn.execute(text("""SELECT display_name,email FROM app_private.application_identities i
            JOIN app_private.gmail_test_messages r USING(application_id) WHERE r.receipt_id=:id"""), {'id': receipt['receipt_id']}).one()
        assert data == ('Ứng viên giả', 'fake@example.test')
        assert conn.execute(text("SELECT count(*) FROM app_private.audit_events WHERE action_type='GMAIL_TEST_CONFIRM_IDENTITY' AND actor_user_id=:id"), {'id': seed['hr']}).scalar_one() == 1
        assert conn.execute(text('SELECT count(*) FROM app_private.talent_pool_consents')).scalar_one() == 0
    monkeypatch.setattr(settings, 'GMAIL_TEST_INGEST_ENABLED', False)
    assert client.put(url, headers=headers(seed['hr']), json=body).status_code == 404


def test_confirm_rejects_retention_and_non_gmail_source(client, gmail_ready):
    seed, _, _, _ = gmail_ready
    assert client.post('/v1/gmail-test/sync', headers=headers(seed['hr'])).status_code == 200
    item = client.get('/v1/gmail-test/review', headers=headers(seed['hr'])).json()['items'][0]
    url = f"/v1/gmail-test/review/{item['receipt_id']}/identity"
    data = client.get(url, headers=headers(seed['hr'])).json()
    body = {'display_name': 'Giả', 'email': 'fake@example.test', 'expected_updated_at': data['updated_at'], 'confirm_synthetic': True}
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.operations SET status='COMPLETED' WHERE position_id=:id AND capability='CV_PROCESSING'"), {'id': seed['pos']})
        conn.execute(text("UPDATE app_private.applications SET source_code='CAREERS' WHERE application_id=:id"), {'id': item['application_id']})
    assert client.get(url, headers=headers(seed['hr'])).status_code == 404
    assert client.put(url, headers=headers(seed['hr']), json=body).status_code == 404
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.applications SET source_code='EMAIL_TEST' WHERE application_id=:id"), {'id': item['application_id']})
        policy = conn.execute(text('SELECT policy_version FROM app_private.retention_policy_versions LIMIT 1')).scalar_one()
        conn.execute(text("""INSERT INTO app_private.application_retention_cases(application_id,position_id,policy_version,position_closed_at,due_date,status)
            VALUES (:app,:pos,:policy,now(),now(),'PENDING')"""), {'app': item['application_id'], 'pos': seed['pos'], 'policy': policy})
    assert client.get(url, headers=headers(seed['hr'])).status_code == 404
    assert client.put(url, headers=headers(seed['hr']), json=body).status_code == 404


def test_concurrent_identity_updates_have_one_winner(client, gmail_ready):
    from concurrent.futures import ThreadPoolExecutor
    seed, _, _, _ = gmail_ready
    assert client.post('/v1/gmail-test/sync', headers=headers(seed['hr'])).status_code == 200
    item = client.get('/v1/gmail-test/review', headers=headers(seed['hr'])).json()['items'][0]
    url = f"/v1/gmail-test/review/{item['receipt_id']}/identity"
    info = client.get(url, headers=headers(seed['hr'])).json()
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.operations SET status='COMPLETED' WHERE position_id=:id AND capability='CV_PROCESSING'"), {'id': seed['pos']})
    body = {'display_name': 'Fake', 'email': 'fake@example.test', 'expected_updated_at': info['updated_at'], 'confirm_synthetic': True}
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(client.put, url, headers=headers(seed['hr']), json=body) for _ in range(2)]
        assert sorted(f.result(timeout=10).status_code for f in futures) == [200, 409]


def test_retry_after_commit_response_lost_does_not_duplicate(client, gmail_ready, monkeypatch):
    seed, _, _, _ = gmail_ready
    original = gmail_test._commit_intake
    def commit_then_lose_response(*args, **kwargs):
        original(*args, **kwargs)
        raise OSError('synthetic lost response after commit')
    monkeypatch.setattr(gmail_test, '_commit_intake', commit_then_lose_response)
    assert client.post('/v1/gmail-test/sync', headers=headers(seed['hr'])).status_code == 200
    item = client.get('/v1/gmail-test/review', headers=headers(seed['hr'])).json()['items'][0]
    assert (item['status'], item['reason']) == ('REVIEW', 'PROCESSING_UNAVAILABLE')
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM app_private.applications WHERE source_code='EMAIL_TEST'")).scalar_one() == 1
    monkeypatch.setattr(gmail_test, '_commit_intake', original)
    result = client.post(f"/v1/gmail-test/review/{item['receipt_id']}/retry", headers=headers(seed['hr']))
    assert result.status_code == 200 and result.json()['status'] == 'ACCEPTED'
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM app_private.applications WHERE source_code='EMAIL_TEST'")).scalar_one() == 1
        assert conn.execute(text("SELECT count(*) FROM app_private.talent_pool_consents")).scalar_one() == 0


def test_concurrent_gmail_sync_creates_one_receipt_and_application(client, gmail_ready, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from app.api import careers_intake
    seed, _, _, _ = gmail_ready
    original = careers_intake._store
    entered, release = Event(), Event()
    def pause_storage(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)
    monkeypatch.setattr(careers_intake, '_store', pause_storage)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.post, '/v1/gmail-test/sync', headers=headers(seed['hr']))
        assert entered.wait(5)
        second = pool.submit(client.post, '/v1/gmail-test/sync', headers=headers(seed['hr']))
        release.set()
        results = [first.result(timeout=10), second.result(timeout=10)]
    assert all(result.status_code == 200 for result in results)
    assert sorted(result.json()['processed'] for result in results) == [0, 1]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM app_private.applications WHERE source_code='EMAIL_TEST'")).scalar_one() == 1
        assert conn.execute(text('SELECT count(*) FROM app_private.gmail_test_messages')).scalar_one() == 1
