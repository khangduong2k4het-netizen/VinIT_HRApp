"""Local mocks only: never contact Google or use real OAuth credentials."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

PATH = Path(__file__).resolve().parents[1] / 'scripts/gmail_readonly_smoke.py'
spec = importlib.util.spec_from_file_location('gmail_readonly_smoke', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_client_file_policy_and_endpoint_allowlist(tmp_path):
    client = tmp_path / 'synthetic-google-client.json'
    client.write_text(json.dumps({'installed': {'client_id': 'synthetic', 'client_secret': 'synthetic',
        'auth_uri': 'https://accounts.google.com/o/oauth2/auth', 'token_uri': 'https://oauth2.googleapis.com/token'}}))
    client.chmod(0o600)
    assert module.validate_client_file(str(client)) == client
    client.chmod(0o644)
    with pytest.raises(ValueError): module.validate_client_file(str(client))
    client.chmod(0o600)
    client.write_text(json.dumps({'installed': {'client_id': 'x', 'client_secret': 'x', 'auth_uri': 'https://example.invalid', 'token_uri': 'https://example.invalid'}}))
    with pytest.raises(ValueError): module.validate_client_file(str(client))
    with pytest.raises(ValueError): module.validate_client_file(str(PATH))


def test_readonly_smoke_requests_only_label_and_never_prints_messages(capsys, tmp_path):
    flow = Mock()
    flow.run_local_server.return_value = object()
    flow_factory = Mock(); flow_factory.from_client_secrets_file.return_value = flow
    session = Mock(); session.get.return_value.json.return_value = {'messages': [{'id': 'secret-id'}]}
    session_factory = Mock(return_value=session)
    assert module.run_smoke(tmp_path / 'client.json', 8765, flow_factory, session_factory) == 1
    flow_factory.from_client_secrets_file.assert_called_once_with(str(tmp_path / 'client.json'), [module.SCOPE], autogenerate_code_verifier=True)
    kwargs = flow.run_local_server.call_args.kwargs
    assert kwargs['host'] == 'localhost' and kwargs['bind_addr'] == '127.0.0.1' and kwargs['access_type'] == 'online' and not kwargs['open_browser']
    session.get.assert_called_once_with(module.GMAIL_URL, params={'q': 'label:HRA_TEST', 'maxResults': 5}, timeout=20)
    session.close.assert_called_once()
    assert 'secret-id' not in capsys.readouterr().out
