"""Synthetic-only intake, disposable PostgreSQL and mocked malware scanner."""
import io
import os
from uuid import uuid4

import pytest
from docx import Document
from sqlalchemy import text

from app.api import careers_intake
from app.core.config import settings
from app.db.database import engine
from app.services.malware_scan import ScanVerdict
from test_phase1_integration import seed as seed, client as client

pytestmark = pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'), reason='Disposable PostgreSQL required')


@pytest.fixture
def ready(seed, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'PUBLIC_CAREERS_ENABLED', True)
    monkeypatch.setattr(settings, 'PUBLIC_CAREERS_TEST_INTAKE_ENABLED', True)
    monkeypatch.setattr(settings, 'TALENT_POOL_STORAGE_READY', True)
    monkeypatch.setattr(settings, 'TALENT_POOL_REDISCOVERY_ENABLED', True)
    monkeypatch.setattr(settings, 'CLAMAV_UNIX_SOCKET', '/synthetic/clamd.sock')
    monkeypatch.setattr(settings, 'STORAGE_BACKEND', 'local')
    monkeypatch.setattr(settings, 'LOCAL_STORAGE_PATH', str(tmp_path))
    monkeypatch.setattr(careers_intake, 'scan_bytes', lambda *args, **kwargs: ScanVerdict.CLEAN)
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET status='OPEN',application_deadline_at=now()+interval '1 day' WHERE position_id=:p"), {'p': seed['pos']})
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"), {'id': seed['cv']})
    doc = Document(); doc.add_paragraph('Synthetic engineering CV only. ' * 10); out = io.BytesIO(); doc.save(out)
    return seed, out.getvalue()


def send(client, seed, contents, request_id, **fields):
    data = {'request_id': request_id, 'name': 'Synthetic Person', 'email': 'candidate@example.test', **fields}
    return client.post(f"/v1/careers/jobs/{seed['pos']}/apply", data=data,
                       files={'cv': ('synthetic.docx', contents, 'application/octet-stream')})


def test_intake_optin_withdraw_and_idempotent_retry(client, ready):
    seed, content = ready
    req, token = str(uuid4()), 'ab' * 32
    assert send(client, seed, content, req, pool_opt_in='true', pool_token=token).status_code == 202
    assert send(client, seed, content, req, pool_opt_in='true', pool_token=token).status_code == 202
    assert send(client, seed, content, req, name='Other', pool_opt_in='true', pool_token=token).status_code == 409
    with engine.connect() as conn:
        rows = conn.execute(text("""SELECT r.state,a.created_by,a.source_code,i.display_name,i.email,c.notice_version,c.token_hash,d.storage_path
            FROM app_private.careers_intake_receipts r JOIN app_private.applications a USING (application_id)
            JOIN app_private.application_identities i USING (application_id) JOIN app_private.talent_pool_consents c USING (application_id)
            JOIN app_private.application_documents d USING (application_id) WHERE r.request_id=:req"""), {'req': req}).all()
        assert len(rows) == 1 and rows[0][0:5] == ('COMMITTED', None, 'CAREERS', 'Synthetic Person', 'candidate@example.test')
        assert rows[0][5] == careers_intake.TEST_NOTICE and rows[0][6] != token
        assert os.path.isfile(os.path.join(settings.LOCAL_STORAGE_PATH, settings.SUPABASE_STORAGE_BUCKET_CV, rows[0][7]))
    assert client.post('/v1/talent-pool/withdraw', json={'token': token}).status_code == 200
    with engine.connect() as conn:
        assert conn.execute(text('SELECT withdrawn_at IS NOT NULL FROM app_private.talent_pool_consents WHERE token_hash=:hash'), {'hash': careers_intake.hashlib.sha256(token.encode()).hexdigest()}).scalar_one()


def test_antivirus_fail_closed_before_validation_or_storage(client, ready, monkeypatch):
    seed, content = ready
    def forbid(*args, **kwargs):
        raise AssertionError('validation or storage must not run')
    monkeypatch.setattr(careers_intake.document_processor, 'validate_file', forbid)
    monkeypatch.setattr(careers_intake, '_store', forbid)
    for verdict, status in [(ScanVerdict.UNAVAILABLE, 503), (ScanVerdict.INFECTED, 400)]:
        monkeypatch.setattr(careers_intake, 'scan_bytes', lambda *args, v=verdict, **kwargs: v)
        assert send(client, seed, content, str(uuid4())).status_code == status
    with engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM app_private.careers_intake_receipts')).scalar_one() == 0


def test_flags_synthetic_scope_and_receipt_retry_after_storage_failure(client, ready, monkeypatch):
    seed, content = ready
    monkeypatch.setattr(settings, 'PUBLIC_CAREERS_TEST_INTAKE_ENABLED', False)
    assert send(client, seed, content, str(uuid4())).status_code == 404
    monkeypatch.setattr(settings, 'PUBLIC_CAREERS_TEST_INTAKE_ENABLED', True)
    assert send(client, seed, content, str(uuid4()), email='person@gmail.com').status_code == 400
    original = careers_intake._store
    def failed_after_write(*args):
        original(*args)
        raise OSError('synthetic ambiguous storage failure')
    monkeypatch.setattr(careers_intake, '_store', failed_after_write)
    req = str(uuid4())
    assert send(client, seed, content, req).status_code == 503
    with engine.connect() as conn:
        receipt = conn.execute(text('SELECT state,storage_path FROM app_private.careers_intake_receipts WHERE request_id=:req'), {'req': req}).one()
        assert receipt.state == 'STAGING'
        assert os.path.exists(os.path.join(settings.LOCAL_STORAGE_PATH, settings.SUPABASE_STORAGE_BUCKET_CV, receipt.storage_path))
    monkeypatch.setattr(careers_intake, '_store', original)
    assert send(client, seed, content, req).status_code == 202
    with engine.connect() as conn:
        receipt_after = conn.execute(text('SELECT state,storage_path FROM app_private.careers_intake_receipts WHERE request_id=:req'), {'req': req}).one()
        assert receipt_after == ('COMMITTED', receipt.storage_path)


def test_existing_worker_processes_real_intake_and_preserves_form_identity(client, ready, monkeypatch):
    from app.workers.processor import ProcessingWorker, llm_client
    seed, content = ready
    async def profile(**kwargs):
        return {'education': [], 'work_history': [], 'skills': [], 'certifications': []}
    async def match(**kwargs):
        return {'findings': []}
    monkeypatch.setattr(llm_client, 'extract_candidate_profile', profile)
    monkeypatch.setattr(llm_client, 'match_criterion_evidence', match)
    req = str(uuid4())
    assert send(client, seed, content, req).status_code == 202
    ProcessingWorker()._process_pending_operations()
    with engine.connect() as conn:
        result = conn.execute(text("""SELECT o.status,d.file_processing_status,i.display_name,i.email
            FROM app_private.careers_intake_receipts r JOIN app_private.applications a USING (application_id)
            JOIN app_private.application_identities i USING (application_id)
            JOIN app_private.application_documents d USING (application_id)
            JOIN app_private.cv_batch_items bi USING (application_id)
            JOIN app_private.cv_batches b USING (batch_id) JOIN app_private.operations o USING (operation_id)
            WHERE r.request_id=:req"""), {'req': req}).one()
        assert result == ('COMPLETED', 'COMPLETED', 'Synthetic Person', 'candidate@example.test')


def test_concurrent_duplicate_request_does_not_deadlock_or_duplicate(client, ready, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    seed, content = ready
    original, entered, release = careers_intake._store, Event(), Event()
    def slow_store(*args):
        entered.set()
        assert release.wait(5)
        original(*args)
    monkeypatch.setattr(careers_intake, '_store', slow_store)
    req = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(send, client, seed, content, req)
        assert entered.wait(5)
        second = pool.submit(send, client, seed, content, req)
        release.set()
        assert first.result(timeout=10).status_code == 202
        assert second.result(timeout=10).status_code == 202
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM app_private.applications WHERE source_code='CAREERS'")).scalar_one() == 1
