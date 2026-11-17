"""Talent Pool API against disposable PostgreSQL; synthetic test data only."""
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.db.database import SessionLocal, engine
from app.services.talent_pool import create_consent, hash_token
from test_phase1_integration import seed as seed, client as client, headers

pytestmark = pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'), reason='Disposable PostgreSQL required')


@pytest.fixture
def setup_pool(seed, monkeypatch):
    monkeypatch.setattr(settings, 'TALENT_POOL_STORAGE_READY', True)
    monkeypatch.setattr(settings, 'TALENT_POOL_REDISCOVERY_ENABLED', True)
    target_jd, target_cv = str(uuid4()), str(uuid4())
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET status='OPEN' WHERE position_id IN (:a,:b)"), {'a': seed['pos'], 'b': seed['pos2']})
        conn.execute(text("INSERT INTO app_private.position_assignments(position_id,user_id,position_role) VALUES (:p,:u,'HR_RECRUITER')"), {'p': seed['pos2'], 'u': seed['hr']})
        conn.execute(text("INSERT INTO app_private.jd_versions(jd_version_id,position_id,version_number,content_text,created_by) VALUES (:id,:p,1,'synthetic',:u)"), {'id': target_jd, 'p': seed['pos2'], 'u': seed['hr']})
        conn.execute(text("INSERT INTO app_private.criteria_versions(criteria_version_id,position_id,jd_version_id,version_number,status) VALUES (:id,:p,:jd,1,'APPROVED')"), {'id': target_cv, 'p': seed['pos2'], 'jd': target_jd})
        conn.execute(text("""INSERT INTO app_private.application_documents(application_id,bucket,storage_path,original_filename,mime_type,size_bytes,file_processing_status)
            VALUES (:app,'synthetic','synthetic','synthetic.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document',1,'COMPLETED')"""), {'app': seed['app']})
    db = SessionLocal()
    try:
        token = create_consent(db, application_id=seed['app'], notice_version='synthetic-test-v1',
                               consent_expires_at=datetime.now(timezone.utc)+timedelta(days=5),
                               retention_expires_at=datetime.now(timezone.utc)+timedelta(days=3))
        db.commit()
    finally:
        db.close()
    return seed, token


def get_scan(client, seed, user):
    return client.get('/v1/talent-pool/scan', params={'source_position_id': seed['pos'], 'target_position_id': seed['pos2']}, headers=headers(user))


def test_consent_security_permissions_and_withdrawal(client, setup_pool, monkeypatch):
    seed, token = setup_pool
    with engine.connect() as conn:
        stored = conn.execute(text('SELECT token_hash,notice_version FROM app_private.talent_pool_consents WHERE application_id=:id'), {'id': seed['app']}).one()
        assert stored == (hash_token(token), 'synthetic-test-v1') and stored[0] != token
        assert not conn.execute(text("SELECT has_table_privilege('anon','app_private.talent_pool_consents','SELECT')")).scalar_one()
        assert not conn.execute(text("SELECT has_table_privilege('authenticated','app_private.talent_pool_consents','SELECT')")).scalar_one()
    assert get_scan(client, seed, seed['hm']).status_code == 403
    assert get_scan(client, seed, seed['hr2']).status_code == 403
    result = get_scan(client, seed, seed['hr'])
    assert result.status_code == 200 and result.headers['cache-control'] == 'no-store'
    assert [x['application_id'] for x in result.json()['items']] == [seed['app']]
    assert all(key not in result.json()['items'][0] for key in ['email', 'phone', 'token_hash'])
    # Disabling discovery never disables withdrawal.
    monkeypatch.setattr(settings, 'TALENT_POOL_REDISCOVERY_ENABLED', False)
    assert get_scan(client, seed, seed['hr']).status_code == 404
    response = client.post('/v1/talent-pool/withdraw', json={'token': token})
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    assert client.post('/v1/talent-pool/withdraw', json={'token': 'ab' * 32}).json() == response.json()
    assert client.post('/v1/talent-pool/withdraw', json={'token': token}).json() == response.json()
    monkeypatch.setattr(settings, 'TALENT_POOL_REDISCOVERY_ENABLED', True)
    assert get_scan(client, seed, seed['hr']).json()['items'] == []
    assert client.post('/v1/talent-pool/withdraw', json={'token': 'invalid'}).status_code == 422
    monkeypatch.setattr(settings, 'TALENT_POOL_STORAGE_READY', False)
    assert client.post('/v1/talent-pool/withdraw', json={'token': token}).status_code == 404


def test_eligibility_retention_and_documents(client, setup_pool):
    seed, _ = setup_pool
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.talent_pool_consents SET retention_expires_at=now()-interval '1 day', accepted_at=now()-interval '2 days' WHERE application_id=:id"), {'id': seed['app']})
    assert get_scan(client, seed, seed['hr']).json()['items'] == []
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.talent_pool_consents SET retention_expires_at=now()+interval '1 day', consent_expires_at=now()-interval '1 second' WHERE application_id=:id"), {'id': seed['app']})
    assert get_scan(client, seed, seed['hr']).json()['items'] == []
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.talent_pool_consents SET consent_expires_at=now()+interval '1 day' WHERE application_id=:id"), {'id': seed['app']})
        conn.execute(text("UPDATE app_private.application_documents SET file_processing_status='RECEIVED' WHERE application_id=:id"), {'id': seed['app']})
    assert get_scan(client, seed, seed['hr']).json()['items'] == []
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.application_documents SET file_processing_status='COMPLETED' WHERE application_id=:id"), {'id': seed['app']})
        policy = conn.execute(text('SELECT policy_version FROM app_private.retention_policy_versions LIMIT 1')).scalar_one()
        conn.execute(text("""INSERT INTO app_private.application_retention_cases(application_id,position_id,policy_version,position_closed_at,due_date,status)
            VALUES (:app,:pos,:policy,now(),now(),'PENDING')"""), {'app': seed['app'], 'pos': seed['pos'], 'policy': policy})
    assert get_scan(client, seed, seed['hr']).json()['items'] == []


def test_withdrawal_blocks_concurrent_discovery(client, setup_pool):
    seed, token = setup_pool
    started = Event()
    def scan():
        started.set()
        return get_scan(client, seed, seed['hr'])
    with engine.connect() as conn:
        txn = conn.begin()
        conn.execute(text("UPDATE app_private.talent_pool_consents SET withdrawn_at=clock_timestamp() WHERE token_hash=:token"), {'token': hash_token(token)})
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(scan)
            assert started.wait(5)
            deadline = time.monotonic() + 5
            blocked = False
            while time.monotonic() < deadline:
                with engine.connect() as observer:
                    blocked = observer.execute(text("""SELECT EXISTS (SELECT 1 FROM pg_stat_activity
                        WHERE datname=current_database() AND wait_event_type='Lock'
                        AND query LIKE '%FROM app_private.talent_pool_consents c%')""")).scalar_one()
                if blocked:
                    break
                time.sleep(0.05)
            txn.commit()
            assert blocked, 'scan did not wait on the consent lock'
            assert future.result(timeout=10).json()['items'] == []


def test_closed_source_or_unready_target_not_discoverable(client, setup_pool):
    seed, _ = setup_pool
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET status='CLOSED',closed_at=now() WHERE position_id=:id"), {'id': seed['pos']})
    assert get_scan(client, seed, seed['hr']).json()['items'] == []
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET status='OPEN',closed_at=NULL WHERE position_id=:id"), {'id': seed['pos']})
        conn.execute(text("UPDATE app_private.positions SET status='PAUSED' WHERE position_id=:id"), {'id': seed['pos2']})
    assert get_scan(client, seed, seed['hr']).status_code == 409
