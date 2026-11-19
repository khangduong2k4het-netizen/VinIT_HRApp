#!/usr/bin/env python3
"""Purge all candidate CV data from a disposable HRA test environment.

This is an operator-run reset for a test stack, not the retention workflow
and not evidence for DEP-02. It preserves user accounts, positions, JD and
criteria while deleting every application/CV and candidate-derived result.

Safety properties:

* dry-run is the default and only prints aggregate counts;
* execution requires the exact ``--confirm PURGE_ALL_CV_KEEP_ACCOUNTS``;
* execution refuses to run while an operation is pending/processing;
* storage objects are deleted before the database transaction, matching the
  retention service order so a failed database purge can be retried;
* no names, emails, filenames, storage paths, quotes or CV text are printed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.services.retention import delete_storage_objects, extracted_storage_paths  # noqa: E402

CONFIRMATION = "PURGE_ALL_CV_KEEP_ACCOUNTS"

PRESERVED_COUNT_QUERIES: dict[str, str] = {
    "auth_users": "SELECT count(*) FROM auth.users",
    "user_profiles": "SELECT count(*) FROM app_private.user_profiles",
    "positions": "SELECT count(*) FROM app_private.positions",
    "jd_versions": "SELECT count(*) FROM app_private.jd_versions",
    "criteria_versions": "SELECT count(*) FROM app_private.criteria_versions",
    "ai_configuration_versions": "SELECT count(*) FROM app_private.ai_configuration_versions",
}

TARGET_COUNT_QUERIES: dict[str, str] = {
    "applications": "SELECT count(*) FROM app_private.applications",
    "application_identities": "SELECT count(*) FROM app_private.application_identities",
    "application_documents": "SELECT count(*) FROM app_private.application_documents",
    "document_processing_runs": "SELECT count(*) FROM app_private.document_processing_runs",
    "profile_versions": "SELECT count(*) FROM app_private.profile_versions",
    "profile_facts": """
        SELECT count(*) FROM app_private.profile_facts f
        JOIN app_private.profile_versions p ON p.profile_version_id = f.profile_version_id
    """,
    "assessment_runs": "SELECT count(*) FROM app_private.assessment_runs",
    "criterion_assessment_results": """
        SELECT count(*) FROM app_private.criterion_assessment_results r
        JOIN app_private.assessment_runs a ON a.assessment_id = r.assessment_id
    """,
    "evidence_items": """
        SELECT count(*) FROM app_private.evidence_items e
        JOIN app_private.criterion_assessment_results r ON r.result_id = e.criterion_result_id
        JOIN app_private.assessment_runs a ON a.assessment_id = r.assessment_id
    """,
    "ranking_items": "SELECT count(*) FROM app_private.ranking_items",
    "ranking_runs": "SELECT count(*) FROM app_private.ranking_runs",
    "shortlist_share_items": "SELECT count(*) FROM app_private.shortlist_share_items",
    "shortlist_feedback_for_applications": """
        SELECT count(*) FROM app_private.shortlist_feedback WHERE application_id IS NOT NULL
    """,
    "duplicate_signals": "SELECT count(*) FROM app_private.duplicate_signals",
    "cv_chunk_embeddings": "SELECT count(*) FROM app_private.cv_chunk_embeddings",
    "application_private_notes": "SELECT count(*) FROM app_private.application_private_notes",
    "application_status_events": "SELECT count(*) FROM app_private.application_status_events",
    "linked_cv_batch_items": """
        SELECT count(*) FROM app_private.cv_batch_items WHERE application_id IS NOT NULL
    """,
    "retention_cases_linked_to_applications": """
        SELECT count(*) FROM app_private.application_retention_cases WHERE application_id IS NOT NULL
    """,
}

# Explicit order matters: children and cross-references are removed before
# applications. Several tables also cascade, but the reset must not depend on
# remembering which relation happens to cascade in a given migration.
DELETE_STATEMENTS: list[tuple[str, str]] = [
    ("shortlist_feedback", """
        DELETE FROM app_private.shortlist_feedback WHERE application_id IS NOT NULL
    """),
    ("shortlist_share_items", "DELETE FROM app_private.shortlist_share_items"),
    ("ranking_items", "DELETE FROM app_private.ranking_items"),
    ("duplicate_signals", "DELETE FROM app_private.duplicate_signals"),
    ("cv_chunk_embeddings", "DELETE FROM app_private.cv_chunk_embeddings"),
    ("assessment_runs", "DELETE FROM app_private.assessment_runs"),
    ("profile_versions", "DELETE FROM app_private.profile_versions"),
    ("application_private_notes", "DELETE FROM app_private.application_private_notes"),
    ("application_identities", "DELETE FROM app_private.application_identities"),
    ("application_status_events", "DELETE FROM app_private.application_status_events"),
    ("application_documents", "DELETE FROM app_private.application_documents"),
    ("cv_batch_items_unlink", """
        UPDATE app_private.cv_batch_items
        SET application_id = NULL, original_filename = '[DELETED]'
        WHERE application_id IS NOT NULL
    """),
    ("applications", "DELETE FROM app_private.applications"),
    ("empty_ranking_runs", """
        DELETE FROM app_private.ranking_runs r
        WHERE NOT EXISTS (
            SELECT 1 FROM app_private.ranking_items i WHERE i.ranking_run_id = r.ranking_run_id
        )
    """),
]


def ensure_confirmation(*, execute: bool, confirmation: str | None) -> None:
    if execute and confirmation != CONFIRMATION:
        raise ValueError(f"execution requires --confirm {CONFIRMATION}")


def _collect_counts(db, queries: dict[str, str]) -> dict[str, int]:
    return {name: int(db.execute(text(sql)).scalar_one()) for name, sql in queries.items()}


def _active_operation_count(db) -> int:
    return int(db.execute(text("""
        SELECT count(*) FROM app_private.operations WHERE status IN ('PENDING', 'PROCESSING')
    """)).scalar_one())


def _collect_storage_inputs(db) -> tuple[list[dict[str, Any]], list[str]]:
    originals = [dict(row) for row in db.execute(text("""
        SELECT bucket, storage_path FROM app_private.application_documents
    """)).mappings().all()]
    extracted_paths = [row[0] for row in db.execute(text("""
        SELECT pr.extracted_text_storage_path
        FROM app_private.document_processing_runs pr
        JOIN app_private.application_documents d ON d.document_id = pr.document_id
        WHERE pr.extracted_text_storage_path IS NOT NULL
    """)).all()]
    return originals, extracted_paths


def count_storage_targets(originals: list[dict[str, Any]], extracted_paths: list[str]) -> int:
    """Count unique storage objects referenced by the current CV rows."""
    targets: set[tuple[str, str]] = set()
    for document in originals:
        bucket, path = document.get("bucket"), document.get("storage_path")
        if bucket and path:
            targets.add((str(bucket), str(path)))
    for extracted_path in extracted_paths:
        for path in extracted_storage_paths(extracted_path):
            targets.add((settings.SUPABASE_STORAGE_BUCKET_EXTRACTED, path))
    return len(targets)


def _storage_item_value(item: Any, key: str) -> Any:
    return item.get(key) if isinstance(item, dict) else getattr(item, key, None)


def list_supabase_storage_paths(client, bucket: str) -> list[str]:
    """Recursively list file paths in a Supabase Storage bucket."""
    storage = client.storage.from_(bucket)
    paths: list[str] = []
    stack = [""]
    while stack:
        prefix = stack.pop()
        for item in storage.list(prefix) or []:
            name = _storage_item_value(item, "name")
            if not name:
                continue
            full_path = f"{prefix}/{name}" if prefix else str(name)
            if _storage_item_value(item, "id") is None:
                stack.append(full_path)
            else:
                paths.append(full_path)
    return sorted(paths)


def list_storage_paths(bucket: str) -> list[str]:
    """List all file paths in one configured CV storage bucket."""
    backend = (settings.STORAGE_BACKEND or "").strip().lower()
    if backend == "local":
        bucket_dir = Path(settings.LOCAL_STORAGE_PATH).expanduser() / bucket
        if not bucket_dir.exists():
            return []
        return sorted(
            path.relative_to(bucket_dir).as_posix()
            for path in bucket_dir.rglob("*")
            if path.is_file()
        )
    if backend == "supabase":
        from app.db.supabase import get_supabase_client

        client = get_supabase_client()
        if not client:
            raise RuntimeError("Supabase storage is not configured")
        return list_supabase_storage_paths(client, bucket)
    raise RuntimeError("Storage backend is not supported by the purge script")


def purge_storage_orphans() -> dict[str, dict[str, int]]:
    """Delete every remaining object in the two CV buckets via the storage API.

    The main purge deletes objects referenced by database rows. Failed or
    interrupted attempts can leave orphan extracted-text objects behind; this
    optional sweep removes only objects in the configured CV buckets and
    reports counts, never paths.
    """
    summary: dict[str, dict[str, int]] = {}
    for bucket in (settings.SUPABASE_STORAGE_BUCKET_CV, settings.SUPABASE_STORAGE_BUCKET_EXTRACTED):
        paths = list_storage_paths(bucket)
        delete_summary = (
            delete_storage_objects(
                [{"bucket": bucket, "storage_path": path} for path in paths], []
            )
            if paths
            else {"storage_objects_deleted": 0, "storage_objects_missing": 0}
        )
        remaining = list_storage_paths(bucket)
        summary[bucket] = {
            "objects_found": len(paths),
            **delete_summary,
            "objects_remaining": len(remaining),
        }
        if remaining:
            raise RuntimeError(f"storage orphan purge incomplete for bucket {bucket}")
    return summary


def _snapshot(db) -> dict[str, Any]:
    originals, extracted_paths = _collect_storage_inputs(db)
    return {
        "preserved": _collect_counts(db, PRESERVED_COUNT_QUERIES),
        "targets": _collect_counts(db, TARGET_COUNT_QUERIES),
        "active_operations": _active_operation_count(db),
        "storage_targets_referenced": count_storage_targets(originals, extracted_paths),
        "storage_backend": settings.STORAGE_BACKEND,
    }


def run(*, execute: bool, confirmation: str | None, include_storage_orphans: bool = False) -> dict[str, Any]:
    ensure_confirmation(execute=execute, confirmation=confirmation)

    db = SessionLocal()
    try:
        before = _snapshot(db)
        originals, extracted_paths = _collect_storage_inputs(db)
    finally:
        db.close()

    if include_storage_orphans and not execute:
        before["storage_orphans_present"] = {
            bucket: len(list_storage_paths(bucket))
            for bucket in (settings.SUPABASE_STORAGE_BUCKET_CV, settings.SUPABASE_STORAGE_BUCKET_EXTRACTED)
        }

    if not execute:
        return {"mode": "dry-run", **before}
    if before["active_operations"]:
        raise RuntimeError("pending/processing operations exist; stop and drain hra-backend first")

    storage_summary = delete_storage_objects(originals, extracted_paths)

    db = SessionLocal()
    try:
        # The backend must stay stopped while this runs. Recheck inside the
        # purge transaction so a newly started job blocks the destructive step.
        if _active_operation_count(db):
            raise RuntimeError("pending/processing operations exist; stop and drain hra-backend first")
        db.execute(text("LOCK TABLE app_private.applications IN EXCLUSIVE MODE"))
        deleted: dict[str, int] = {}
        for label, sql in DELETE_STATEMENTS:
            deleted[label] = int(db.execute(text(sql)).rowcount or 0)
        db.commit()
        after = _snapshot(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    remaining = {name: count for name, count in after["targets"].items() if count}
    if remaining:
        raise RuntimeError(f"purge verification failed; non-empty targets remain: {sorted(remaining)}")
    if after["preserved"] != before["preserved"]:
        raise RuntimeError("purge verification failed; preserved account/position counts changed")

    result = {
        "mode": "execute",
        "before": before,
        "storage": storage_summary,
        "deleted": deleted,
        "after": after,
    }
    if include_storage_orphans:
        result["storage_orphans"] = purge_storage_orphans()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="only print aggregate counts; this is the default")
    parser.add_argument("--execute", action="store_true", help="perform the purge")
    parser.add_argument("--include-storage-orphans", action="store_true",
                        help="also list/delete every remaining object in the configured CV buckets")
    parser.add_argument("--confirm", default="", help=f"required with --execute: {CONFIRMATION}")
    args = parser.parse_args(argv)
    if args.dry_run and args.execute:
        parser.error("--dry-run and --execute are mutually exclusive")
    try:
        result = run(
            execute=args.execute,
            confirmation=args.confirm,
            include_storage_orphans=args.include_storage_orphans,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error_type": type(exc).__name__, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
