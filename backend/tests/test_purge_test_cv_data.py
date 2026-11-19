import importlib.util
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "purge_test_cv_data.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("purge_test_cv_data", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_purge_requires_exact_confirmation_for_execute():
    script = _load_script()

    script.ensure_confirmation(execute=False, confirmation="")
    script.ensure_confirmation(execute=True, confirmation=script.CONFIRMATION)
    with pytest.raises(ValueError):
        script.ensure_confirmation(execute=True, confirmation="yes")


def test_purge_sql_preserves_accounts_positions_jd_and_criteria():
    script = _load_script()
    sql = "\n".join(statement for _, statement in script.DELETE_STATEMENTS).lower()

    assert "delete from app_private.applications" in sql
    assert "delete from auth.users" not in sql
    assert "delete from app_private.user_profiles" not in sql
    assert "delete from app_private.positions" not in sql
    assert "delete from app_private.jd_versions" not in sql
    assert "delete from app_private.criteria_versions" not in sql
    assert "delete from app_private.ai_configuration_versions" not in sql


def test_purge_delete_order_unlinks_batches_before_deleting_applications():
    script = _load_script()
    labels = [label for label, _ in script.DELETE_STATEMENTS]

    assert labels.index("assessment_runs") < labels.index("profile_versions")
    assert labels.index("profile_versions") < labels.index("application_documents")
    assert labels.index("application_documents") < labels.index("cv_batch_items_unlink")
    assert labels.index("cv_batch_items_unlink") < labels.index("applications")
    assert labels.index("applications") < labels.index("empty_ranking_runs")
    assert "cv_chunk_embeddings" in labels
    assert "duplicate_signals" in labels


def test_storage_target_count_expands_extracted_pages_and_deduplicates():
    script = _load_script()
    originals = [{"bucket": "cv-originals", "storage_path": "app/cv.pdf"}]

    assert script.count_storage_targets(originals, ["app/extracted.txt", "app/extracted.txt"]) == 3


def test_list_supabase_storage_paths_recurses_into_folders():
    script = _load_script()

    class FakeBucket:
        def list(self, prefix):
            return {
                "": [{"name": "app", "id": None}, {"name": "root.txt", "id": "1"}],
                "app": [{"name": "attempt", "id": None}],
                "app/attempt": [{"name": "extracted.txt", "id": "2"}, {"name": "pages.json", "id": "3"}],
            }[prefix]

    class FakeStorage:
        def from_(self, bucket):
            assert bucket == "cv-extracted-text"
            return FakeBucket()

    client = type("Client", (), {"storage": FakeStorage()})()

    assert script.list_supabase_storage_paths(client, "cv-extracted-text") == [
        "app/attempt/extracted.txt",
        "app/attempt/pages.json",
        "root.txt",
    ]
