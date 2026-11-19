"""F2.04/F2.05 sampling, identity safety and database-backed RBAC regressions."""
import os

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.services.identity_matching import identity_signal, normalize_email, normalize_phone
from app.services.quality import ocr_mean_confidence, read_storage, risk_reasons, select_samples


def test_contact_normalization_is_conservative():
    assert normalize_email('  Person+job@Example.COM ') == 'person+job@example.com'
    assert normalize_email('bad @example.com') == ''
    assert normalize_phone('090 123 4567') == normalize_phone('+84 (90) 123-4567') == normalize_phone('0084 90 123 4567')
    assert normalize_phone('ext 0901234567') == ''
    assert identity_signal({'email': 'a+job@example.com'}, {'email': 'a@example.com'}) is None
    assert identity_signal({'email': None, 'phone': ''}, {'email': None, 'phone': ''}) is None
    assert identity_signal({'phone': '0901234567'}, {'phone': '+84901234567'}) == ('PHONE_MATCH', 0.95)


def test_name_alone_or_generic_career_content_never_matches():
    first = {'display_name': 'Nguyễn Văn An', 'career_text': 'Python SQL Docker'}
    second = {'display_name': 'Nguyen Van An', 'career_text': 'Python SQL Docker'}
    assert identity_signal(first, second) is None
    text_value = ' '.join(f'employer{i}' for i in range(25))
    first['career_text'] = second['career_text'] = text_value
    assert identity_signal(first, second) == ('NAME_CONTENT_MATCH', 0.85)
    second['career_text'] = ' '.join(f'different{i}' for i in range(25))
    assert identity_signal(first, second) is None


def test_samples_include_all_risks_and_freeze_random_selection():
    rows = [{'assessment_id': str(i), 'evidence_coverage': 0.9, 'mandatory_misses': 0} for i in range(30)]
    rows[10]['mandatory_misses'] = 1
    rows[11]['evidence_coverage'] = 0.65
    rows[12]['evidence_coverage'] = 0.75
    selected = select_samples(rows, set(), 'position')
    random = {key for key, reasons in selected.items() if 'RANDOM_SAMPLE' in reasons}
    assert len(random) == 3
    assert 'SINGLE_MANDATORY_MISS' in selected['10']
    assert all('BORDERLINE_COVERAGE' in selected[str(i)] for i in (11,12))
    assert select_samples(list(reversed(rows)), set(), 'position') == selected
    rows.append({'assessment_id': 'new', 'evidence_coverage': 1, 'mandatory_misses': 0})
    updated = select_samples(rows, random, 'position')
    assert all('RANDOM_SAMPLE' in updated[key] for key in random)
    assert sum('RANDOM_SAMPLE' in r for r in updated.values()) == 4
    assert risk_reasons(0.64, 2) == []


def test_borderline_band_follows_configured_coverage_threshold(monkeypatch):
    from app.services.quality import settings
    monkeypatch.setattr(settings, 'MIN_EVIDENCE_COVERAGE', 0.7)
    assert risk_reasons(0.70, 0) == risk_reasons(0.65, 0) == risk_reasons(0.75, 0) == ['BORDERLINE_COVERAGE']
    assert risk_reasons(0.76, 0) == []
    monkeypatch.setattr(settings, 'MIN_EVIDENCE_COVERAGE', 0.6)
    assert risk_reasons(0.60, 0) == risk_reasons(0.55, 0) == ['BORDERLINE_COVERAGE']
    assert risk_reasons(0.70, 0) == []


def test_ocr_confidence_discards_sentinels_and_does_not_store_text():
    assert ocr_mean_confidence([{'ocr_confidence': {'conf': ['-1','80','100','nan',None], 'text': ['private']}}]) == 90
    assert ocr_mean_confidence([{'content': 'native text'}]) is None


def test_qa_storage_rejects_paths_outside_bucket(tmp_path, monkeypatch):
    from app.services.quality import settings
    monkeypatch.setattr(settings, 'LOCAL_STORAGE_PATH', str(tmp_path))
    monkeypatch.setattr(settings, 'STORAGE_BACKEND', 'local')
    for path in ('../secret', '/secret', 'nested/../../secret', 'nested\\secret'):
        with pytest.raises(HTTPException):
            read_storage(settings.SUPABASE_STORAGE_BUCKET_CV, path)
    bucket = tmp_path / settings.SUPABASE_STORAGE_BUCKET_CV
    bucket.mkdir()
    secret = tmp_path / 'secret'
    secret.write_text('private')
    try:
        (bucket / 'link').symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip('symlinks unavailable (no privilege on this OS account)')
    with pytest.raises(HTTPException):
        read_storage(settings.SUPABASE_STORAGE_BUCKET_CV, 'link')


integration = pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'), reason='Requires disposable local *_test PostgreSQL')
if os.environ.get('TEST_DATABASE_URL'):
    from app.db.database import engine
    from test_phase1_integration import client, seed, headers  # noqa: F401
    from test_hr_analytics import _assessed_application


@integration
def test_quality_scope_lifecycle_idempotence_and_no_decision_mutation(client, seed):
    from app.services.quality import generate_samples
    application_id = _assessed_application(seed, 'MEETS_MANDATORY', 'Synthetic QA')
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id,role_code) VALUES (:u,'HR_LEAD')"), {'u': seed['other']})
        before = conn.execute(text('SELECT application_status FROM app_private.applications WHERE application_id=:a'), {'a': application_id}).scalar_one()
        assessment = conn.execute(text('SELECT assessment_id FROM app_private.assessment_runs WHERE application_id=:a'), {'a': application_id}).scalar_one()
        conn.execute(text('UPDATE app_private.assessment_runs SET evidence_coverage=0.70 WHERE assessment_id=:a'), {'a': assessment})
        assert generate_samples(conn, seed['pos']) == 1
        assert generate_samples(conn, seed['pos']) == 0
    lead = headers(seed['other'])
    for role in ('hr','hm','hr2'):
        assert client.get('/v1/quality/inspections', headers=headers(seed[role])).status_code == 403
    queue = client.get('/v1/quality/inspections', headers=lead)
    assert queue.status_code == 200, queue.text
    case = queue.json()[0]
    route = f"/v1/quality/inspections/{case['inspection_id']}"
    detail = client.get(route, headers=lead)
    assert detail.status_code == 200, detail.text
    assert 'BORDERLINE_COVERAGE' in detail.json()['case']['reasons']
    assert client.get(route, headers=headers(seed['hr'])).status_code == 403
    assert client.post(route+'/claim', headers=lead, json={'expected_revision': 0}).status_code == 200
    assert client.post(route+'/claim', headers=lead, json={'expected_revision': 0}).status_code == 409
    assert client.post(route+'/submit', headers=lead, json={'expected_revision': 1, 'verdict': 'ISSUES_FOUND'}).status_code == 400
    response = client.post(route+'/submit', headers=lead, json={'expected_revision': 1, 'verdict': 'ISSUES_FOUND',
        'flags': [{'category': 'MISSING_CONTENT', 'note': 'Synthetic omitted section'}]})
    assert response.status_code == 200, response.text
    assert client.post(route+'/submit', headers=lead, json={'expected_revision': 1, 'verdict': 'CORRECT'}).status_code == 409
    with engine.connect() as conn:
        assert conn.execute(text('SELECT application_status FROM app_private.applications WHERE application_id=:a'), {'a': application_id}).scalar_one() == before
        assert conn.execute(text('SELECT matching_status FROM app_private.assessment_runs WHERE assessment_id=:a'), {'a': assessment}).scalar_one() == 'MEETS_MANDATORY'


@integration
def test_cross_position_redaction_review_and_identity_refresh(client, seed):
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.application_identities SET email='same@example.test' WHERE application_id IN (:a,:b)"),
                     {'a': seed['app'], 'b': seed['app2']})
    route = f"/v1/cross-duplicates/applications/{seed['app']}"
    hr = headers(seed['hr'])
    result = client.post(route+'/scan', headers=hr)
    assert result.status_code == 200, result.text
    assert result.json() == {'matches': [], 'has_restricted_matches': True}
    assert seed['pos2'] not in result.text and seed['app2'] not in result.text
    assert client.get(route, headers=headers(seed['hm'])).status_code == 403
    with engine.begin() as conn:
        signal = str(conn.execute(text('SELECT signal_id FROM app_private.cross_position_duplicates')).scalar_one())
    assert client.post(f'/v1/cross-duplicates/signals/{signal}/review', headers=hr, json={'decision':'CONFIRMED'}).status_code == 404
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.position_assignments(position_id,user_id,position_role) VALUES (:p,:u,'HR_RECRUITER')"),
                     {'p': seed['pos2'], 'u': seed['hr']})
    shown = client.get(route, headers=hr).json()
    assert shown['matches'][0]['application_id'] == seed['app2']
    assert client.post(f'/v1/cross-duplicates/signals/{signal}/review', headers=hr, json={'decision':'DISMISSED'}).status_code == 200
    assert client.post(route+'/scan', headers=hr).json()['matches'] == []  # dismissal survives retry
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.application_identities SET email='different@example.test' WHERE application_id=:a"), {'a': seed['app2']})
    assert client.post(route+'/scan', headers=hr).json() == {'matches': [], 'has_restricted_matches': False}
    with engine.connect() as conn:
        assert conn.execute(text('SELECT review_status FROM app_private.cross_position_duplicates WHERE signal_id=:s'), {'s': signal}).scalar_one() == 'SUPERSEDED'
        assert conn.execute(text('SELECT COUNT(*) FROM app_private.applications')).scalar_one() == 2


@integration
def test_quality_document_is_pinned_and_admin_is_not_a_reviewer(client, seed, tmp_path, monkeypatch):
    from uuid import uuid4
    from app.core.config import settings
    from app.services.quality import generate_samples
    application = _assessed_application(seed, 'MEETS_MANDATORY', 'Synthetic source')
    monkeypatch.setattr(settings, 'STORAGE_BACKEND', 'local')
    monkeypatch.setattr(settings, 'LOCAL_STORAGE_PATH', str(tmp_path))
    bucket = tmp_path / settings.SUPABASE_STORAGE_BUCKET_EXTRACTED
    bucket.mkdir(parents=True)
    (bucket / 'original.txt').write_text('--- Page 1 ---\nOriginal assessment text')
    (bucket / 'new.txt').write_text('Different reprocessed text')
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id,role_code) VALUES (:u,'ADMIN')"), {'u': seed['other']})
        assert client.get('/v1/quality/inspections', headers=headers(seed['other'])).status_code == 403
        conn.execute(text("INSERT INTO app_private.position_assignments(position_id,user_id,position_role) VALUES (:p,:u,'HR_LEAD')"),
                     {'p': seed['pos'], 'u': seed['hr2']})
        row = conn.execute(text('SELECT a.assessment_id,p.source_document_id FROM app_private.assessment_runs a JOIN app_private.profile_versions p USING(profile_version_id) WHERE a.application_id=:a'),
                           {'a': application}).mappings().one()
        conn.execute(text("UPDATE app_private.assessment_runs SET source_extracted_text_path='original.txt' WHERE assessment_id=:a"), {'a': row['assessment_id']})
        conn.execute(text("""INSERT INTO app_private.document_processing_runs(document_id,extraction_type,status,extracted_text_storage_path,created_at,ocr_mean_confidence)
            SELECT :d,'PDF_SCANNED','COMPLETED','original.txt',created_at-interval '1 second',87 FROM app_private.assessment_runs WHERE assessment_id=:a"""),
            {'a': row['assessment_id'], 'd': row['source_document_id']})
        conn.execute(text("""INSERT INTO app_private.document_processing_runs(document_id,extraction_type,status,extracted_text_storage_path)
            VALUES (:d,'PDF_SCANNED','COMPLETED','new.txt')"""), {'d': row['source_document_id']})
        generate_samples(conn, seed['pos'])
    lead = headers(seed['hr2'])
    case = client.get('/v1/quality/inspections', headers=lead).json()[0]
    route = f"/v1/quality/inspections/{case['inspection_id']}"
    data = client.get(route+'/text', headers=lead).json()
    assert data['text'].endswith('Original assessment text') and data['exact_snapshot'] is True
    assert data['ocr_mean_confidence'] == 87
    assert client.post('/v1/quality/positions/'+str(uuid4())+'/sample', headers=headers(seed['other'])).status_code == 403
    assert client.post(route+'/claim', headers=lead, json={'expected_revision':0}).status_code == 200
    # A finding from another assessment must not be attached to this review.
    response = client.post(route+'/submit', headers=lead, json={'expected_revision':1,'verdict':'ISSUES_FOUND',
        'flags':[{'category':'INCORRECT_MATCH','criterion_result_id':str(uuid4()),'note':'Synthetic mismatch'}]})
    assert response.status_code == 400
    assert client.get(route, headers=lead).json()['flags'] == []
    assert client.post(route+'/submit', headers=lead, json={'expected_revision':1,'verdict':'CORRECT'}).status_code == 200
    feedback = client.get(route+'/feedback', headers=lead)
    assert feedback.status_code == 200 and feedback.json()['verdict'] == 'CORRECT'
    assert 'candidate_name' not in feedback.json()
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.position_assignments SET revoked_at=NOW() WHERE user_id=:u AND position_role='HR_LEAD'"), {'u':seed['hr2']})
    assert client.get(route+'/text', headers=lead).status_code == 403
    assert client.get(route+'/feedback', headers=lead).status_code == 403
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM app_private.assessment_runs WHERE assessment_id=:a'), {'a': row['assessment_id']})
        assert conn.execute(text('SELECT COUNT(*) FROM app_private.quality_inspections')).scalar_one() == 0
        assert conn.execute(text('SELECT COUNT(*) FROM app_private.quality_inspection_events')).scalar_one() == 0


@integration
def test_duplicate_concurrent_review_has_one_winner_and_revocation_hides_peer(client, seed):
    from concurrent.futures import ThreadPoolExecutor
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.application_identities SET phone='0901234567' WHERE application_id IN (:a,:b)"), {'a':seed['app'],'b':seed['app2']})
        conn.execute(text("INSERT INTO app_private.position_assignments(position_id,user_id,position_role) VALUES (:p,:u,'HR_RECRUITER')"),
                     {'p':seed['pos2'],'u':seed['hr']})
    route = f"/v1/cross-duplicates/applications/{seed['app']}"
    hr = headers(seed['hr'])
    signal = client.post(route+'/scan', headers=hr).json()['matches'][0]['signal_id']
    def decide(decision):
        return client.post(f'/v1/cross-duplicates/signals/{signal}/review', headers=hr,json={'decision':decision}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(decide, ['CONFIRMED','CONFIRMED']))
    assert sorted(codes) == [200,409]
    with engine.begin() as conn:
        conn.execute(text('UPDATE app_private.position_assignments SET revoked_at=NOW() WHERE position_id=:p AND user_id=:u'), {'p':seed['pos2'],'u':seed['hr']})
    assert client.get(route, headers=hr).json() == {'matches':[], 'has_restricted_matches':True}


@integration
def test_new_tables_are_not_browser_readable():
    with engine.connect() as conn:
        for table in ('quality_inspections','quality_flags','quality_inspection_events','cross_position_duplicates'):
            for role in ('anon','authenticated'):
                assert conn.execute(text("SELECT has_table_privilege(:r,:t,'SELECT')"), {'r':role,'t':'app_private.'+table}).scalar_one() is False


@integration
def test_sampling_uses_only_each_applications_latest_completed_assessment(client, seed):
    from app.services.quality import generate_samples
    application_id = _assessed_application(seed, 'MEETS_MANDATORY', 'Synthetic reassessed QA')
    with engine.begin() as conn:
        old = conn.execute(text('SELECT assessment_id FROM app_private.assessment_runs WHERE application_id=:a'),
                           {'a': application_id}).scalar_one()
        # The old run sits in the borderline band; the reassessment does not.
        conn.execute(text("UPDATE app_private.assessment_runs SET evidence_coverage=0.70,completed_at=NOW()-INTERVAL '1 day' WHERE assessment_id=:a"),
                     {'a': old})
        new = conn.execute(text("""
            INSERT INTO app_private.assessment_runs(position_id,application_id,jd_version_id,criteria_version_id,profile_version_id,
                                                   policy_version,status,matching_status,matching_score,evidence_coverage,completed_at)
            SELECT position_id,application_id,jd_version_id,criteria_version_id,profile_version_id,
                   policy_version,'COMPLETED','MEETS_MANDATORY',90,0.95,NOW()
            FROM app_private.assessment_runs WHERE assessment_id=:a RETURNING assessment_id
        """), {'a': old}).scalar_one()
        assert generate_samples(conn, seed['pos']) == 1
        cases = conn.execute(text('SELECT assessment_id,reasons FROM app_private.quality_inspections WHERE position_id=:p'),
                             {'p': seed['pos']}).mappings().all()
    assert [(str(c['assessment_id']), c['reasons']) for c in cases] == [(str(new), ['RANDOM_SAMPLE'])]


@integration
def test_backfill_scans_existing_applications_dry_run_first_and_is_rerunnable(seed):
    import importlib.util
    from pathlib import Path
    from sqlalchemy.orm import sessionmaker
    spec = importlib.util.spec_from_file_location(
        'backfill_cross_duplicates', Path(__file__).resolve().parents[1] / 'scripts' / 'backfill_cross_duplicates.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    factory = sessionmaker(bind=engine)
    def count():
        with engine.connect() as conn:
            return conn.execute(text("SELECT review_status,COUNT(*) FROM app_private.cross_position_duplicates GROUP BY 1")).all()
    # Two applications in different positions that predate detection: no signal yet.
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.application_identities SET email='old@example.test' WHERE application_id IN (:a,:b)"),
                     {'a': seed['app'], 'b': seed['app2']})
    assert count() == []
    dry = module.backfill(factory, apply=False)
    assert dry['applications_scanned'] == 2 and dry['after'] == {'PENDING': 1}
    assert count() == []  # dry run wrote nothing
    assert module.backfill(factory, apply=True)['after'] == {'PENDING': 1}
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.cross_position_duplicates SET review_status='DISMISSED'"))
    # Re-running keeps the HR decision and creates no duplicate rows.
    assert module.backfill(factory, apply=True)['after'] == {'DISMISSED': 1}
    assert module.backfill(factory, apply=False, position_id=seed['pos2'])['applications_scanned'] == 1
