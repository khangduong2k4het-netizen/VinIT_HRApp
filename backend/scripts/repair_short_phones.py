"""Repair phone numbers extracted before the year-range fix (13/11/2026).

The old extractor read study years such as "(2016 - 2020)" as phone 20162020,
which created "same phone" duplicate warnings between unrelated candidates.
The new extractor (identity_matching.extract_phone) never returns fewer than
9 digits, so any stored phone shorter than that is a leftover of the bug.

This script clears those phones, dismisses PENDING within-position PHONE_MATCH
warnings that relied on them (reviewed warnings are left as HR decided), and
re-runs cross-position detection for the affected applications.

Dry run by default (rolled back); --apply writes.
Usage (from backend/): python scripts/repair_short_phones.py [--apply]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.services.cross_duplicates import refresh_application  # noqa: E402

_SHORT = "phone IS NOT NULL AND length(regexp_replace(phone, '\\D', '', 'g')) < 9"


def repair(db) -> dict:
    affected = [str(r[0]) for r in db.execute(text(
        f"SELECT application_id FROM app_private.application_identities WHERE {_SHORT}"))]
    if not affected:
        return {"phones_cleared": 0, "warnings_dismissed": 0, "applications": []}
    dismissed = db.execute(text("""
        UPDATE app_private.duplicate_signals SET review_status = 'DISMISSED',
               detector_version = 'phone-year-range-repair', reviewed_at = NOW()
        WHERE signal_type = 'PHONE_MATCH' AND review_status = 'PENDING'
          AND (application_id_1 = ANY(CAST(:ids AS uuid[])) OR application_id_2 = ANY(CAST(:ids AS uuid[])))
    """), {"ids": affected}).rowcount
    cleared = db.execute(text(
        f"UPDATE app_private.application_identities SET phone = NULL, updated_at = NOW() WHERE {_SHORT}")).rowcount
    for application_id in affected:
        refresh_application(db, application_id)
    return {"phones_cleared": cleared, "warnings_dismissed": dismissed, "applications": affected}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Write the repair (default: dry run, rolled back)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    from app.db.database import SessionLocal
    db = SessionLocal()
    try:
        result = repair(db)
        if args.apply:
            db.commit()
        else:
            db.rollback()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print(f"{'ĐÃ GHI' if args.apply else 'CHẠY THỬ (không ghi)'}: xóa {result['phones_cleared']} số điện thoại sai, "
          f"đóng {result['warnings_dismissed']} cảnh báo trùng đang chờ, quét lại {len(result['applications'])} hồ sơ")
    if not args.apply:
        print("Thêm --apply để ghi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
