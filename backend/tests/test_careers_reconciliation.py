"""Tests only delete local files created under a pytest temporary directory."""
import os
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import text
from storage3.exceptions import StorageApiError

from app.api import careers_intake
from app.core.config import settings
from app.db.database import engine
from app.services import careers_storage
from app.services.careers_reconciliation import dry_run, reconcile
from test_careers_real_intake import ready as ready, send
from test_phase1_integration import seed as seed, client as client

pytestmark = pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'), reason='Disposable PostgreSQL required')


def staged(client, ready, monkeypatch):
    seed, content = ready
    original = careers_intake._store
    def fail_after_upload(*args):
        original(*args)
        raise OSError('synthetic storage error')
    monkeypatch.setattr(careers_intake, '_store', fail_after_upload)
    req = str(uuid4())
    assert send(client, seed, content, req).status_code == 503
    monkeypatch.setattr(careers_intake, '_store', original)
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.careers_intake_receipts SET updated_at=now()-interval '25 hours' WHERE request_id=:id"), {'id': req})
        path = conn.execute(text('SELECT storage_path FROM app_private.careers_intake_receipts WHERE request_id=:id'), {'id': req}).scalar_one()
    return seed, content, req, path


def test_stale_cleanup_keeps_tombstone_and_retry_cannot_recreate(client, ready, monkeypatch):
    seed, content, req, path = staged(client, ready, monkeypatch)
    full_path = os.path.join(settings.LOCAL_STORAGE_PATH, settings.SUPABASE_STORAGE_BUCKET_CV, path)
    with open(full_path + '.part', 'wb') as stream:
        stream.write(b'synthetic partial')
    assert dry_run(older_hours=24) == {'stale': 1, 'matching_destination': 1, 'missing_destination': 0}
    assert reconcile(older_hours=24, limit=20) == {'abandoned': 1, 'error': False}
    assert not os.path.exists(full_path) and not os.path.exists(full_path + '.part')
    with engine.connect() as conn:
        assert conn.execute(text('SELECT state FROM app_private.careers_intake_receipts WHERE request_id=:id'), {'id': req}).scalar_one() == 'ABANDONED'
        assert conn.execute(text("SELECT count(*) FROM app_private.audit_events WHERE action_type='CAREERS_TEST_RECONCILE' AND object_id=:id"), {'id': req}).scalar_one() == 1
    assert send(client, seed, content, req).status_code == 410
    assert reconcile(older_hours=24, limit=20) == {'abandoned': 0, 'error': False}


def test_active_row_lock_skipped_then_abandoned(client, ready, monkeypatch):
    seed, content, req, path = staged(client, ready, monkeypatch)
    full_path = os.path.join(settings.LOCAL_STORAGE_PATH, settings.SUPABASE_STORAGE_BUCKET_CV, path)
    with engine.begin() as conn:
        conn.execute(text('SELECT 1 FROM app_private.careers_intake_receipts WHERE request_id=:id FOR UPDATE'), {'id': req})
        assert reconcile(older_hours=24, limit=20) == {'abandoned': 0, 'error': False}
        assert os.path.exists(full_path)
    assert reconcile(older_hours=24, limit=20)['abandoned'] == 1


def test_referenced_or_changed_destination_never_removed(client, ready, monkeypatch):
    seed, content, req, path = staged(client, ready, monkeypatch)
    full_path = os.path.join(settings.LOCAL_STORAGE_PATH, settings.SUPABASE_STORAGE_BUCKET_CV, path)
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO app_private.application_documents(application_id,bucket,storage_path,original_filename,mime_type,size_bytes)
            VALUES (:app,:bucket,:path,'synthetic.docx','application/octet-stream',1)"""), {'app': seed['app'], 'bucket': settings.SUPABASE_STORAGE_BUCKET_CV, 'path': path})
    assert reconcile(older_hours=24, limit=20) == {'abandoned': 0, 'error': True}
    assert os.path.exists(full_path)
    monkeypatch.setattr(settings, 'SUPABASE_STORAGE_BUCKET_CV', 'other-bucket')
    assert dry_run(older_hours=24)['matching_destination'] == 0
    assert reconcile(older_hours=24, limit=20) == {'abandoned': 0, 'error': False}
    assert os.path.exists(full_path)
    with engine.connect() as conn:
        assert conn.execute(text('SELECT state FROM app_private.careers_intake_receipts WHERE request_id=:id'), {'id': req}).scalar_one() == 'STAGING'


def test_delete_failure_does_not_mark_receipt_abandoned(client, ready, monkeypatch):
    seed, content, req, path = staged(client, ready, monkeypatch)
    monkeypatch.setattr('app.services.careers_reconciliation.remove', Mock(side_effect=OSError('synthetic')))
    assert reconcile(older_hours=24, limit=20) == {'abandoned': 0, 'error': True}
    with engine.connect() as conn:
        assert conn.execute(text('SELECT state FROM app_private.careers_intake_receipts WHERE request_id=:id'), {'id': req}).scalar_one() == 'STAGING'
    for hours, limit in [(0, 1), (24, 0), (24, 101)]:
        with pytest.raises(ValueError): reconcile(older_hours=hours, limit=limit)


def test_remote_delete_verifies_absence_and_bucket(monkeypatch):
    monkeypatch.setattr(settings, 'STORAGE_BACKEND', 'supabase')
    monkeypatch.setattr(settings, 'SUPABASE_URL', 'https://synthetic.supabase.co')
    monkeypatch.setattr(settings, 'SUPABASE_STORAGE_BUCKET_CV', 'cv-test')
    client = Mock()
    remote = client.storage.from_.return_value
    missing = StorageApiError('synthetic', 'not_found', 404)
    remote.info.side_effect = [{'id': 'synthetic'}, missing]
    monkeypatch.setattr(careers_storage, 'get_supabase_client', lambda: client)
    backend, bucket, identity = careers_storage.destination()
    path = f'careers/{uuid4()}/{uuid4()}.docx'
    careers_storage.remove(backend, bucket, identity, path)
    client.storage.get_bucket.assert_called_once_with(bucket)
    remote.remove.assert_called_once_with([path])
    remote.info.side_effect = None; remote.info.return_value = {'id': 'still-there'}
    with pytest.raises(RuntimeError): careers_storage.remove(backend, bucket, identity, path)
    with pytest.raises(ValueError): careers_storage.remove(backend, bucket, identity, '../../other')


def test_legacy_unknown_destination_and_config_change_fail_closed(client, ready, monkeypatch):
    seed, content, req, path = staged(client, ready, monkeypatch)
    full_path = os.path.join(settings.LOCAL_STORAGE_PATH, settings.SUPABASE_STORAGE_BUCKET_CV, path)
    with engine.begin() as conn:
        conn.execute(text('UPDATE app_private.careers_intake_receipts SET storage_identity=NULL WHERE request_id=:id'), {'id': req})
    assert dry_run(older_hours=24)['missing_destination'] == 1
    assert reconcile(older_hours=24, limit=10)['abandoned'] == 0
    assert send(client, seed, content, req).status_code == 503
    assert os.path.isfile(full_path)


def test_local_storage_rejects_escaping_symlink(tmp_path, monkeypatch):
    outside = tmp_path / 'outside'; outside.mkdir()
    base = tmp_path / 'storage'; base.mkdir()
    (base / 'cv-originals').symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(settings, 'STORAGE_BACKEND', 'local')
    monkeypatch.setattr(settings, 'LOCAL_STORAGE_PATH', str(base))
    monkeypatch.setattr(settings, 'SUPABASE_STORAGE_BUCKET_CV', 'cv-originals')
    backend, bucket, identity = careers_storage.destination()
    with pytest.raises(ValueError):
        careers_storage.remove(backend, bucket, identity, f'careers/{uuid4()}/{uuid4()}.docx')
