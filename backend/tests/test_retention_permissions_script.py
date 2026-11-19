import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location(
    "retention_permissions_script", Path(__file__).resolve().parents[2] / "scripts" / "retention_permissions_check.py"
)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(f"SUPABASE_URL=https://{helper.PROJECT}\nSUPABASE_ANON_KEY=public\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(helper.sys.stdin, "isatty", lambda: True)


def test_expected_permissions_and_audit(config_dir, capsys):
    responses = [(200, {"access_token": "secret-recruiter"}),
                 (200, {"user_id": helper.RECRUITER, "must_change_password": False, "system_roles": ["HR_RECRUITER"], "position_assignments": []}),
                 (403, {}), (403, {}), (200, {"access_token": "secret-admin"}),
                 (200, {"must_change_password": False, "system_roles": ["ADMIN"]}),
                 (200, {"valid": True, "checked_events": 1, "broken_events": 0})]
    with patch("builtins.input", return_value="x@example.com"), patch.object(
        helper.getpass, "getpass", return_value="secret-password"
    ), patch.object(helper, "request", side_effect=responses) as request:
        assert helper.main() == 0
    calls = request.call_args_list
    confirm = [call for call in calls if call.args[1].endswith("/confirm")]
    assert len(confirm) == 1
    assert confirm[0].args[2]["Authorization"] == "Bearer secret-recruiter"
    assert all(not call.args[1].endswith("/execute") for call in calls)
    output = capsys.readouterr().out
    assert "valid=True" in output and "secret-" not in output


def test_wrong_recruiter_stops_before_confirm(config_dir):
    responses = [(200, {"access_token": "x"}),
                 (200, {"user_id": "wrong", "must_change_password": False, "system_roles": ["HR_RECRUITER"]})]
    with patch("builtins.input", return_value="x@example.com"), patch.object(
        helper.getpass, "getpass", return_value="password"
    ), patch.object(helper, "request", side_effect=responses) as request:
        assert helper.main() == 1
    assert len(request.call_args_list) == 2


def test_unexpected_confirm_success_stops_before_admin(config_dir, capsys):
    responses = [(200, {"access_token": "x"}),
                 (200, {"user_id": helper.RECRUITER, "must_change_password": False, "system_roles": ["HR_RECRUITER"]}),
                 (403, {}), (200, {"status": "SCHEDULED_FOR_DELETION"})]
    with patch("builtins.input", return_value="x@example.com"), patch.object(
        helper.getpass, "getpass", return_value="password"
    ), patch.object(helper, "request", side_effect=responses) as request:
        assert helper.main() == 1
    assert len(request.call_args_list) == 4
    assert "SCHEDULED_FOR_DELETION" in capsys.readouterr().out


def test_password_change_required_does_not_test_permissions(config_dir, capsys):
    responses = [(200, {"access_token": "x"}),
                 (200, {"user_id": helper.RECRUITER, "system_roles": ["HR_RECRUITER"],
                        "must_change_password": True})]
    with patch("builtins.input", return_value="x@example.com"), patch.object(
        helper.getpass, "getpass", return_value="password"
    ), patch.object(helper, "request", side_effect=responses) as request:
        assert helper.main() == 1
    assert len(request.call_args_list) == 2
    assert "doi mat khau" in capsys.readouterr().out
