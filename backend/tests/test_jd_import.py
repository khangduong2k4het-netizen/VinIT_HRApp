"""Synthetic, offline JD import tests; never access external networks."""
import io
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.api import jd_import
from app.core.security import get_current_user
from app.main import app
from app.services.jd_import import ImportErrorDetail, extract_file, extract_job_html, fetch_job, validate_source_url
from app.services.malware_scan import ScanVerdict
from app.schemas.positions import PositionCreate


def test_allowed_url_is_exact_and_rejects_unsafe_destinations():
    assert validate_source_url('https://careerportalvinuni.talent.vn/job/vinfast-data-engineer-16526') == '/job/vinfast-data-engineer-16526'
    for url in ['http://careerportalvinuni.talent.vn/job/a-1',
                'https://careerportalvinuni.talent.vn.evil.test/job/a-1',
                'https://careerportalvinuni.talent.vn@127.0.0.1/job/a-1',
                'https://careerportalvinuni.talent.vn:444/job/a-1',
                'https://careerportalvinuni.talent.vn/job/a-1?q=secret',
                'https://careerportalvinuni.talent.vn/job/../a-1',
                'https://careerportalvinuni.talent.vn/job/a-1#fragment']:
        with pytest.raises(ImportErrorDetail):
            validate_source_url(url)


def test_html_extract_keeps_requirements_excludes_form_navigation_and_scripts():
    html = '''<h1>Related jobs</h1><h2>Job Description</h2>
    <p>Responsible for building and operating synthetic data pipelines.</p>
    <script>ignore malicious text</script><h3>Requirements</h3><ul><li>Python</li><li>SQL</li></ul>
    <h1>Application Tracking Form</h1><form>Candidate email<input></form><footer>footer text</footer>'''
    value = extract_job_html(html)
    assert 'Requirements' in value and 'Python' in value and 'SQL' in value
    assert 'Related jobs' not in value and 'Candidate email' not in value and 'malicious' not in value
    with pytest.raises(ImportErrorDetail):
        extract_job_html('<h2>Job Description</h2><p>missing end boundary</p>')
    with pytest.raises(ImportErrorDetail):
        extract_job_html('<h2>Job Description</h2><p>x</p><h2>Job Description</h2><form></form>')


def test_reject_dns_private_and_mixed_answers_before_any_socket(monkeypatch):
    for ips in [['127.0.0.1'], ['8.8.8.8', '169.254.169.254'], ['::1']]:
        monkeypatch.setattr('app.services.jd_import.socket.getaddrinfo', lambda *a, **k: [(None, None, None, None, (ip, 443)) for ip in ips])
        with pytest.raises(ImportErrorDetail):
            fetch_job('https://careerportalvinuni.talent.vn/job/test-123')


def test_text_and_docx_content_including_tables():
    assert extract_file('Xin chào Python'.encode(), 'jd.TXT') == 'Xin chào Python'
    doc = Document(); doc.add_paragraph('Vai trò Python'); table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = 'Yêu cầu'; table.cell(0, 1).text = 'SQL'
    doc.add_paragraph('Kết thúc')
    buf = io.BytesIO(); doc.save(buf)
    result = extract_file(buf.getvalue(), 'jd.docx')
    assert result.index('Vai trò') < result.index('Yêu cầu') < result.index('Kết thúc')
    assert 'SQL' in result
    for data, name in [(b'a', 'old.doc'), (b'\xff', 'broken.txt'), (b'\x00abc', 'bad.txt'), (b'not zip', 'bad.docx'), (b'', 'empty.txt')]:
        with pytest.raises(ImportErrorDetail):
            extract_file(data, name)


def test_preview_auth_and_scanner_fail_closed(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {'user_id': 'synthetic'}
    try:
        # Authorization dependency itself is independently exercised below; the
        # rest of this test deliberately mocks it and never contacts a DB.
        app.dependency_overrides[jd_import.require_hr] = lambda: {'user_id': 'synthetic'}
        with TestClient(app) as client:
            monkeypatch.setattr(jd_import, 'scan_bytes', lambda *a, **k: ScanVerdict.UNAVAILABLE)
            assert client.post('/v1/jd-import/file', files={'file': ('jd.txt', b'hello', 'text/plain')}).status_code == 503
            monkeypatch.setattr(jd_import, 'scan_bytes', lambda *a, **k: ScanVerdict.INFECTED)
            assert client.post('/v1/jd-import/file', files={'file': ('jd.txt', b'hello', 'text/plain')}).status_code == 400
            monkeypatch.setattr(jd_import, 'scan_bytes', lambda *a, **k: ScanVerdict.CLEAN)
            assert client.post('/v1/jd-import/file', files={'file': ('jd.txt', b'JD synthetic', 'text/plain')}).json()['content'] == 'JD synthetic'
            assert client.post('/v1/jd-import/file', files={'file': ('jd.doc', b'bad', 'application/msword')}).status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_role_enforced_by_import_dependency(monkeypatch):
    db = SimpleNamespace(execute=Mock(return_value=SimpleNamespace(first=lambda: None)), close=Mock())
    monkeypatch.setattr(jd_import, 'SessionLocal', lambda: db)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        jd_import.require_hr({'user_id': 'synthetic'})
    assert exc.value.status_code == 403
    db.close.assert_called_once()


def test_position_contract_language_defaults_and_jd_required():
    from uuid import uuid4
    from pydantic import ValidationError
    args = {'department_id': uuid4(), 'title': 'Synthetic', 'jd_content': 'JD synthetic', 'hiring_manager_user_id': uuid4()}
    assert PositionCreate(**args).jd_language_code == 'en'
    assert PositionCreate(**args, jd_language_code='vi').jd_language_code == 'vi'
    with pytest.raises(ValidationError):
        PositionCreate(**args, jd_language_code='fr')
    with pytest.raises(ValidationError):
        PositionCreate(department_id=uuid4(), title='Synthetic')


@pytest.mark.asyncio
async def test_create_position_saves_first_jd_language_and_deadline_atomically(monkeypatch):
    from datetime import datetime, timezone
    from uuid import uuid4
    from app.api import positions

    class Result:
        def __init__(self, value): self.value = value
        def scalar_one_or_none(self): return self.value
        def scalars(self): return self
        def all(self): return self.value
        def mappings(self): return self
        def first(self): return self.value
        def one(self): return self.value
    class Db:
        def __init__(self): self.calls = []; self.committed = False
        def execute(self, stmt, params):
            sql = str(stmt); self.calls.append((sql, dict(params)))
            if 'SELECT account_status' in sql: return Result('ACTIVE')
            if 'FROM app_private.user_role_assignments' in sql: return Result(['HIRING_MANAGER'] if len([s for s, _ in self.calls if 'SELECT account_status' in s]) > 1 else ['HR_RECRUITER'])
            if 'FROM app_private.position_assignments' in sql: return Result([])
            if 'FROM app_private.departments' in sql: return Result({'name': 'IT', 'code_format': 'REQ-IT-{SEQ:000}', 'is_active': True})
            if 'INSERT INTO app_private.positions' in sql: return Result({'position_id': uuid4(), 'title': 'Demo'})
            return Result(None)
        def commit(self): self.committed = True
        def rollback(self): pass
        def close(self): pass

    db = Db()
    monkeypatch.setattr(positions, 'SessionLocal', lambda: db)
    monkeypatch.setattr(positions, 'next_position_code', lambda *_: ('REQ-IT-001', 1))
    deadline = datetime(2030, 1, 1, tzinfo=timezone.utc)
    p = PositionCreate(department_id=uuid4(), title='Demo', jd_content='JD giả', hiring_manager_user_id=uuid4(), jd_language_code='vi', application_deadline_at=deadline)
    from fastapi import Response
    result = await positions.create_position(p, Response(), {'user_id': str(uuid4())})
    insert_position = next(x for x in db.calls if 'INSERT INTO app_private.positions' in x[0])
    insert_jd = next(x for x in db.calls if 'INSERT INTO app_private.jd_versions' in x[0])
    assert insert_position[1]['application_deadline_at'] == deadline
    assert insert_jd[1]['language'] == 'vi'
    assert insert_jd[1]['content'] == 'JD giả'
    assert db.committed and result['department_name'] == 'IT'


def test_remote_adapter_parses_html_and_rejects_redirect_without_following(monkeypatch):
    from app.services import jd_import as service
    requests = []
    class FakeSocket:
        def settimeout(self, timeout): pass
    class FakeResponse:
        status = 200
        def __init__(self):
            self.fp = SimpleNamespace(raw=SimpleNamespace(_sock=FakeSocket()))
            self.data = b'<h2>Job Description</h2><p>Synthetic position for Python, SQL and testing work.</p><h3>Requirements</h3><p>Python</p><h2>Application Tracking Form</h2>'
        def getheader(self, name, default=''):
            return 'text/html; charset=utf-8' if name == 'Content-Type' else default
        def isclosed(self): return not self.data
        def read1(self, size):
            result, self.data = self.data[:size], self.data[size:]
            return result
    class FakeConnection:
        def __init__(self, *args, **kwargs): pass
        def request(self, method, path, headers): requests.append((method, path, headers))
        def getresponse(self): return FakeResponse()
        def close(self): pass
    monkeypatch.setattr(service.socket, 'getaddrinfo', lambda *a, **k: [(None, None, None, None, ('8.8.8.8', 443))])
    monkeypatch.setattr(service.http.client, 'HTTPSConnection', FakeConnection)
    value = service.fetch_job('https://careerportalvinuni.talent.vn/job/test-123')
    assert 'Requirements' in value and 'Application Tracking Form' not in value
    assert requests[0][1] == '/job/test-123'
    FakeResponse.status = 302
    with pytest.raises(ImportErrorDetail):
        service.fetch_job('https://careerportalvinuni.talent.vn/job/test-123')
    assert len(requests) == 2  # no redirected request


def test_fetch_job_total_budget_covers_dns_and_does_not_leak_slots(monkeypatch):
    import time
    from app.services import jd_import as service

    class SlowSocket:
        def settimeout(self, timeout):
            self.timeout = timeout

    class SlowResponse:
        status = 200
        def __init__(self):
            self.fp = SimpleNamespace(raw=SimpleNamespace(_sock=SlowSocket()))
            self.first = True
        def getheader(self, name, default=''):
            return 'text/html; charset=utf-8' if name == 'Content-Type' else default
        def isclosed(self):
            return False
        def read1(self, _size):
            if self.first:
                self.first = False
                time.sleep(0.2)  # slower than the whole budget below
                return b'<h2>Job Description</h2>'
            return b'<p>Never reached within budget</p>'

    class SlowConnection:
        def __init__(self, *args, **kwargs): pass
        def request(self, *args, **kwargs): pass
        def getresponse(self): return SlowResponse()
        def close(self): pass

    monkeypatch.setattr(service, 'FETCH_BUDGET', 0.05)
    monkeypatch.setattr(service.socket, 'getaddrinfo', lambda *a, **k: [(None, None, None, None, ('8.8.8.8', 443))])
    monkeypatch.setattr(service.http.client, 'HTTPSConnection', SlowConnection)
    # Nothing from earlier tests may still hold a fetch slot.
    assert [service._FETCH_SLOTS.acquire(blocking=False) for _ in range(2)] == [True, True]
    for _ in range(2):
        service._FETCH_SLOTS.release()
    with pytest.raises(TimeoutError):
        service.fetch_job('https://careerportalvinuni.talent.vn/job/data-engineer-1')
    # A timed-out import must give both slots back rather than blocking later previews.
    assert [service._FETCH_SLOTS.acquire(blocking=False) for _ in range(2)] == [True, True]
    for _ in range(2):
        service._FETCH_SLOTS.release()


@pytest.mark.asyncio
async def test_url_preview_response_deadline_even_if_worker_is_blocked(monkeypatch):
    import asyncio
    import threading
    gate = threading.Event()
    started = threading.Event()
    def blocked(_url):
        started.set()
        gate.wait(3)
        return 'text'
    monkeypatch.setattr(jd_import, 'fetch_job', blocked)
    monkeypatch.setattr(jd_import, 'URL_RESPONSE_TIMEOUT', 0.05)
    try:
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            await jd_import.preview_url(jd_import.UrlInput(url='https://example.test'), {'user_id': 'synthetic'})
        assert started.is_set() and exc.value.status_code == 504
    finally:
        gate.set()
        await asyncio.sleep(0.01)
