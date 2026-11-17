import base64
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.core.config import settings
from app.services import gmail_test_client as gmail


def response(data):
    result = Mock()
    result.iter_content.return_value = [json.dumps(data).encode()]
    return result


def test_read_only_client_uses_label_metadata_and_bounded_raw():
    session = Mock()
    raw = b'Subject: synthetic\r\n\r\nTest only.'
    responses = [response({'emailAddress': 'mailbox@example.test'}),
        response({'messages': [{'id': 'test-1'}], 'nextPageToken': '123/+='}),
        response({'id': 'test-1', 'labelIds': ['INBOX'], 'sizeEstimate': len(raw)}),
        response({'id': 'test-1', 'labelIds': ['INBOX'], 'raw': base64.urlsafe_b64encode(raw).decode().rstrip('=')})]
    session.get.side_effect = responses
    assert len(gmail.mailbox_hash(session)) == 64
    assert gmail.list_messages(session) == (['test-1'], '123/+=')
    assert gmail.fetch_message(session, 'test-1') == (['INBOX'], raw)
    assert session.get.call_args_list[1].kwargs['params']['q'] == 'label:HRA_TEST'
    assert session.get.call_args_list[2].kwargs['params']['format'] == 'metadata'
    assert session.get.call_args_list[3].kwargs['params']['format'] == 'raw'
    assert all(call.kwargs['stream'] is True for call in session.get.call_args_list)
    assert all(resp.close.called for resp in responses)


def test_spam_and_oversize_are_not_downloaded():
    session = Mock()
    session.get.return_value = response({'id': 'test-1', 'labelIds': ['SPAM'], 'sizeEstimate': 5})
    assert gmail.fetch_message(session, 'test-1') == (['SPAM'], None)
    assert session.get.call_count == 1
    session.get.return_value = response({'id': 'test-1', 'labelIds': ['INBOX'], 'sizeEstimate': gmail.MAX_RAW_BYTES + 1})
    assert gmail.fetch_message(session, 'test-1') == (['INBOX'], None)
    assert session.get.call_count == 2
    with pytest.raises(ValueError): gmail.fetch_message(session, '../unsafe')


def test_response_size_is_bounded():
    session = Mock(); item = Mock(); item.iter_content.return_value = [b'x' * 11]; session.get.return_value = item
    with pytest.raises(ValueError): gmail._get_json(session, 'https://example.invalid', {}, limit=10)
    item.close.assert_called_once()


def test_token_permissions_and_credentials_allowlist(tmp_path, monkeypatch):
    token = tmp_path / 'token.json'
    token.write_text(json.dumps({'token_uri': 'https://evil.invalid/token', 'client_id': 'fake', 'client_secret': 'fake', 'refresh_token': 'fake', 'scopes': [gmail.SCOPE]}))
    token.chmod(0o600)
    monkeypatch.setattr(settings, 'GMAIL_TEST_TOKEN_FILE', str(token))
    with pytest.raises(ValueError): gmail.open_session()
    token.chmod(0o644)
    with pytest.raises(ValueError): gmail._token_path()
    monkeypatch.setattr(settings, 'GMAIL_TEST_TOKEN_FILE', str(Path(__file__).resolve()))
    with pytest.raises(ValueError): gmail._token_path()


def test_authorize_token_save_never_overwrites(tmp_path):
    import sys
    scripts = str(Path(__file__).resolve().parents[1] / 'scripts')
    sys.path.insert(0, scripts)
    try:
        spec = importlib.util.spec_from_file_location('gmail_authorize_test', str(Path(scripts) / 'gmail_authorize_test.py'))
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        directory = tmp_path / 'private'; directory.mkdir(mode=0o700)
        path = directory / 'token.json'
        module.save_new_token(str(path), '{"synthetic":"token"}')
        assert path.stat().st_mode & 0o777 == 0o600
        with pytest.raises(FileExistsError): module.save_new_token(str(path), 'not-overwritten')
        assert path.read_text() == '{"synthetic":"token"}'
    finally:
        sys.path.remove(scripts)
