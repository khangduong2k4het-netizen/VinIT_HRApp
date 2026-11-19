"""F2.05 backfill: scan applications that existed before cross-position detection.

New CVs are scanned by the worker and identity edits rescan the application,
but applications created before migration 00017 were never scanned. This runs
the same detector (`refresh_application`) over existing applications.

Safe to re-run: signals are upserted by (pair, fingerprints), reviewed signals
keep their decision, and nothing is merged or deleted. Default is a dry run that
rolls everything back and only reports what would change.

Usage (from backend/, uses DATABASE_URL from the environment/.env):
    python scripts/backfill_cross_duplicates.py                 # dry run, all applications
    python scripts/backfill_cross_duplicates.py --apply         # write signals
    python scripts/backfill_cross_duplicates.py --position-id <uuid> --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.services.cross_duplicates import refresh_application  # noqa: E402

_COUNTS = "SELECT review_status, COUNT(*) FROM app_private.cross_position_duplicates GROUP BY review_status"


def _counts(db) -> dict[str, int]:
    return {status: count for status, count in db.execute(text(_COUNTS)).all()}


def backfill(session_factory: Callable, *, apply: bool, position_id: str | None = None,
             limit: int | None = None) -> dict:
    """Scan applications oldest first. With apply=True each application is its
    own short transaction (the detector holds a global lock until commit);
    otherwise one transaction is rolled back at the end."""
    db = session_factory()
    try:
        before = _counts(db)
        ids = [str(row[0]) for row in db.execute(text("""
            SELECT application_id FROM app_private.applications
            WHERE CAST(:p AS uuid) IS NULL OR position_id = CAST(:p AS uuid)
            ORDER BY created_at, application_id
        """), {"p": position_id}).all()][:limit]
        if apply:
            db.commit()
        for application_id in ids:
            refresh_application(db, application_id)
            if apply:
                db.commit()
        after = _counts(db)
        if not apply:
            db.rollback()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return {"applied": apply, "applications_scanned": len(ids), "before": before, "after": after}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Write signals (default: dry run, rolled back)")
    parser.add_argument("--position-id", default=None, help="Only scan applications of this position")
    parser.add_argument("--limit", type=int, default=None, help="Only the first N applications (oldest first)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    from app.db.database import SessionLocal
    result = backfill(SessionLocal, apply=args.apply, position_id=args.position_id, limit=args.limit)
    print(f"{'ĐÃ GHI' if result['applied'] else 'CHẠY THỬ (không ghi)'}: quét {result['applications_scanned']} hồ sơ")
    for status in sorted(set(result["before"]) | set(result["after"])):
        print(f"  {status:<11} {result['before'].get(status, 0):>5} -> {result['after'].get(status, 0):>5}")
    if not result["applied"]:
        print("Thêm --apply để ghi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
