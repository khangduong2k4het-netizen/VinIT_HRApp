import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location(
    "retention_execute_script", Path(__file__).resolve().parents[2] / "scripts" / "retention_execute_test.py"
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
            (200, {"system_roles": ["HR_LEAD"], "must_change_password": False}),
            (200, [{"retention_case_id": helper.CASE, "application_id": helper.APPLICATION,
                    "position_id": helper.POSITION, "status": "SCHEDULED_FOR_DELETION", "is_due": True}])]


def run(responses, inputs):
    with patch("builtins.input", side_effect=inputs), patch.object(
        helper.getpass, "getpass", return_value="secret-password"
    ), patch.object(helper, "request", side_effect=responses) as request:
        outcome = helper.main()
    return outcome, request.call_args_list


def test_execute_requires_explicit_consent(config_dir, capsys):
    outcome, calls = run(initial_responses() + [(200, {"challenge_id": "challenge-1", "channel": "EMAIL"}),
                                                (200, {"status": "DELETED"})],
                         ["x@example.com", "XOA VINH VIEN IT-0005", "123456"])
    assert outcome == 0
    assert sum(call.args[1].endswith("/execute") for call in calls) == 1
    execute = [call for call in calls if call.args[1].endswith("/execute")][0]
    assert execute.args[3] == {"challenge_id": "challenge-1", "otp": "123456"}
    assert "secret-" not in capsys.readouterr().out


def test_no_otp_no_execute(config_dir):
    outcome, calls = run(initial_responses() + [(200, {"challenge_id": "challenge-1", "channel": "EMAIL"})],
                         ["x@example.com", "XOA VINH VIEN IT-0005", ""])
    assert outcome == 0
    assert not any(call.args[1].endswith("/execute") for call in calls)


def test_no_consent_no_execute(config_dir):
    outcome, calls = run(initial_responses(), ["x@example.com", ""])
    assert outcome == 0 and len(calls) == 3


@pytest.mark.parametrize("field,value", [("application_id", "other"), ("status", "PENDING"), ("is_due", False)])
def test_mismatch_never_executes(config_dir, field, value):
    responses = initial_responses()
    responses[-1][1][0][field] = value
    outcome, calls = run(responses, ["x@example.com"])
    assert outcome == 1 and len(calls) == 3


def test_password_change_required_never_executes(config_dir):
    responses = initial_responses()[:2]
    responses[1][1]["must_change_password"] = True
    outcome, calls = run(responses, ["x@example.com"])
    assert outcome == 1 and len(calls) == 2


def test_failure_warns_not_to_retry(config_dir, capsys):
    outcome, calls = run(initial_responses() + [(200, {"challenge_id": "challenge-1", "channel": "EMAIL"}), (502, {})],
                         ["x@example.com", "XOA VINH VIEN IT-0005", "123456"])
    assert outcome == 1 and len(calls) == 5
    assert "Khong chay lai" in capsys.readouterr().out
