import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location(
    "shortlist_e2e09_script", Path(__file__).resolve().parents[2] / "scripts" / "shortlist_e2e09_check.py"
)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(f"SUPABASE_URL=https://{helper.PROJECT}\nSUPABASE_ANON_KEY=public\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(helper.sys.stdin, "isatty", lambda: True)


def pre_responses():
    return [(200, {"access_token": "hm-secret-token"}),
            (200, {"user_id": helper.HM, "system_roles": ["HIRING_MANAGER"],
                   "must_change_password": False,
                   "position_assignments": [{"position_id": helper.POSITION, "position_role": "HIRING_MANAGER"}]}),
            (200, {"status": "ACTIVE", "allow_cv_view": False, "position_id": helper.POSITION,
                   "shared_with": helper.HM, "applications": [{"application_id": helper.SHARED}],
                   "feedback": [{"feedback_id": "feedback"}]}),
            (200, {"can_view_cv": False, "documents": []}), (403, {}), (403, {}),
            (200, {"access_token": "admin-secret-token"}),
            (200, {"system_roles": ["ADMIN"], "must_change_password": False})]


def run(responses, inputs):
    with patch("builtins.input", side_effect=inputs), patch.object(
        helper.getpass, "getpass", return_value="secret-password"
    ), patch.object(helper, "request", side_effect=responses) as request:
        result = helper.main()
    return result, request.call_args_list


def test_expected_sequence_and_revoke(config_dir, capsys):
    responses = pre_responses() + [(200, {"status": "REVOKED"}), (403, {}), (403, {}), (403, {})]
    result, calls = run(responses, ["hm@example.com", "admin@example.com", "THU HOI IT-0004"])
    assert result == 0
    posts = [c for c in calls if c.args[0] == "POST" and c.args[1].startswith(helper.API)]
    assert len(posts) == 1 and posts[0].args[1].endswith(f"/{helper.SHARE}/revoke")
    assert "secret-" not in capsys.readouterr().out


def test_no_consent_never_revokes(config_dir):
    result, calls = run(pre_responses(), ["hm@example.com", "admin@example.com", ""])
    assert result == 0 and not any(c.args[1].endswith("/revoke") for c in calls)


def test_cv_leak_stops_before_revoke(config_dir):
    responses = pre_responses()[:5]
    responses[-1] = (200, {"signed_url": "secret-url"})
    result, calls = run(responses, ["hm@example.com"])
    assert result == 1 and len(calls) == 5
    assert not any(c.args[1].endswith("/revoke") for c in calls)


def test_password_change_stops_before_access_tests(config_dir):
    responses = pre_responses()[:2]
    responses[1][1]["must_change_password"] = True
    result, calls = run(responses, ["hm@example.com"])
    assert result == 1 and len(calls) == 2


def test_shared_wrong_candidate_never_revokes(config_dir):
    responses = pre_responses()[:3]
    responses[-1][1]["applications"][0]["application_id"] = helper.UNSHARED
    result, calls = run(responses, ["hm@example.com"])
    assert result == 1 and len(calls) == 3


def test_after_revoke_failure_reported(config_dir):
    responses = pre_responses() + [(200, {"status": "REVOKED"}), (200, {}), (403, {}), (403, {})]
    result, calls = run(responses, ["hm@example.com", "admin@example.com", "THU HOI IT-0004"])
    assert result == 1 and len(calls) == 12
