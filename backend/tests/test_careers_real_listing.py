"""Real listing tests; only run against disposable local migrated PostgreSQL."""
import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine
from test_phase1_integration import seed as seed, client as client

pytestmark = pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'), reason='Disposable PostgreSQL required')


def test_disabled_by_default_and_open_jobs_only(client, seed, monkeypatch):
    monkeypatch.setattr(settings, 'PUBLIC_CAREERS_ENABLED', False)
    assert client.get('/v1/careers/jobs').status_code == 404
    monkeypatch.setattr(settings, 'PUBLIC_CAREERS_ENABLED', True)
    assert client.get('/v1/careers/jobs').json()['items'] == []
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET status='OPEN', application_deadline_at=now()+interval '1 day' WHERE position_id=:id"), {'id': seed['pos']})
        conn.execute(text("UPDATE app_private.positions SET status='PAUSED', application_deadline_at=now()+interval '1 day' WHERE position_id=:id"), {'id': seed['pos2']})
        conn.execute(text("INSERT INTO app_private.jd_versions(position_id,version_number,content_text,created_by) VALUES (:p,2,'Newest JD',:u)"), {'p': seed['pos'], 'u': seed['hr']})
    res = client.get('/v1/careers/jobs')
    assert res.status_code == 200 and res.headers['cache-control'] == 'no-store'
    job = res.json()['items'][0]
    assert len(res.json()['items']) == 1 and job['position_id'] == seed['pos'] and job['description'] == 'Newest JD'
    assert set(job) == {'position_id', 'position_code', 'title', 'org_unit', 'work_location', 'work_mode', 'employment_type', 'application_deadline_at', 'description', 'can_apply_test'}
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET application_deadline_at=now()-interval '1 second' WHERE position_id=:id"), {'id': seed['pos']})
    assert client.get('/v1/careers/jobs').json()['items'] == []


def test_pagination_and_missing_jd(client, seed, monkeypatch):
    monkeypatch.setattr(settings, 'PUBLIC_CAREERS_ENABLED', True)
    with engine.begin() as conn:
        for i in range(105):
            conn.execute(text("""INSERT INTO app_private.positions(position_id,position_code,title,created_by,status,application_deadline_at)
                VALUES (:id,:code,'Synthetic',:creator,'OPEN',now()+interval '1 day')"""),
                {'id': str(uuid4()), 'code': f'synthetic-{i}', 'creator': seed['hr']})
    first = client.get('/v1/careers/jobs?limit=100').json()
    assert len(first['items']) == 100 and first['next_cursor']
    second = client.get('/v1/careers/jobs', params={'limit': 100, 'cursor': first['next_cursor']}).json()
    assert len(second['items']) == 5 and second['next_cursor'] is None
    ids = [job['position_id'] for job in first['items'] + second['items']]
    assert len(set(ids)) == 105
    assert all(job['description'] is None for job in first['items'] + second['items'])
    assert client.get('/v1/careers/jobs?limit=101').status_code == 422
    assert client.get('/v1/careers/jobs?cursor=invalid').status_code == 422
