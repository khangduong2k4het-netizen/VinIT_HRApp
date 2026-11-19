import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location(
    "retention_lead_confirm_script", Path(__file__).resolve().parents[2] / "scripts" / "retention_lead_confirm.py"
)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(f"SUPABASE_URL=https://{helper.PROJECT}\nSUPABASE_ANON_KEY=public\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(helper.sys.stdin, "isatty", lambda: True)


def initial_responses():
    return [(200, {"access_token": "secret-token"}),
            (200, {"must_change_password": False, "system_roles": ["HR_LEAD"]}),
            (200, [{"retention_case_id": helper.CASE, "application_id": helper.APPLICATION,
                    "position_id": helper.POSITION, "status": "PENDING", "is_due": True}])]


def test_confirmation_with_consent_never_executes(config_dir, capsys):
    responses = initial_responses() + [(200, {"status": "SCHEDULED_FOR_DELETION"})]
    with patch("builtins.input", side_effect=["x@example.com", "XAC NHAN IT-0005"]), patch.object(
        helper.getpass, "getpass", return_value="secret-password"
    ), patch.object(helper, "request", side_effect=responses) as request:
        assert helper.main() == 0
    urls = [call.args[1] for call in request.call_args_list]
    assert sum(url.endswith("/confirm") for url in urls) == 1
    assert not any(url.endswith("/execute") for url in urls)
    out = capsys.readouterr().out
    assert "SCHEDULED_FOR_DELETION" in out and "secret-" not in out


def test_no_consent_no_confirm(config_dir):
    with patch("builtins.input", side_effect=["x@example.com", ""]), patch.object(
        helper.getpass, "getpass", return_value="password"
    ), patch.object(helper, "request", side_effect=initial_responses()) as request:
        assert helper.main() == 0
    assert len(request.call_args_list) == 3


def test_incorrect_application_is_not_confirmed(config_dir):
    responses = initial_responses()
    responses[-1][1][0]["application_id"] = "other"
    with patch("builtins.input", return_value="x@example.com"), patch.object(
        helper.getpass, "getpass", return_value="password"
    ), patch.object(helper, "request", side_effect=responses) as request:
        assert helper.main() == 1
    assert len(request.call_args_list) == 3


def test_password_change_required_stops_before_case_read(config_dir):
    responses = [(200, {"access_token": "x"}),
                 (200, {"system_roles": ["HR_LEAD"], "must_change_password": True})]
    with patch("builtins.input", return_value="x@example.com"), patch.object(
        helper.getpass, "getpass", return_value="password"
    ), patch.object(helper, "request", side_effect=responses) as request:
        assert helper.main() == 1
    assert len(request.call_args_list) == 2
