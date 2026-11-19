"""Safety checks for the interactive DEP-02 generate-only helper."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "retention_generate.py"
spec = importlib.util.spec_from_file_location("retention_generate_script", SCRIPT)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        f"SUPABASE_URL=https://{helper.PROJECT}\nSUPABASE_ANON_KEY=test-public-key\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(helper.sys.stdin, "isatty", lambda: True)


def test_generate_only_and_no_secrets_printed(config_dir, capsys):
    responses = [
        (200, {"access_token": "test-token"}),
        (200, {"created_count": 0, "due_date": "2027-11-11", "cases": []}),
        (200, {"created_count": 1, "due_date": "2026-10-11", "cases": [
            {"retention_case_id": "case-1", "status": "PENDING"}]}),
    ]
    with patch("builtins.input", return_value="test@example.com"), patch.object(
        helper.getpass, "getpass", return_value="test-password"
    ), patch.object(helper, "request", side_effect=responses) as request:
        assert helper.main() == 0
    paths = [call.args[1] for call in request.call_args_list]
    assert len(paths) == 3
    assert all("/confirm" not in p and "/execute" not in p for p in paths)
    out = capsys.readouterr().out
    assert "case-1" in out and "PENDING" in out
    assert "test-token" not in out and "test-password" not in out


def test_existing_case_reported_not_claimed_as_new(config_dir, capsys):
    responses = [(200, {"access_token": "test-token"}),
                 (200, {"created_count": 0}), (200, {"created_count": 0}),
                 (200, [{"retention_case_id": "existing", "status": "PENDING"}])]
    with patch("builtins.input", return_value="test@example.com"), patch.object(
        helper.getpass, "getpass", return_value="test-password"
    ), patch.object(helper, "request", side_effect=responses):
        assert helper.main() == 1
    assert "case da co: existing, status=PENDING" in capsys.readouterr().out


def test_wrong_project_stops_before_auth(config_dir, tmp_path, capsys):
    (tmp_path / ".env").write_text("SUPABASE_URL=https://other.supabase.co\nSUPABASE_ANON_KEY=key\n")
    with patch.object(helper, "request") as request:
        assert helper.main() == 1
    request.assert_not_called()
