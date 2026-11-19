"""F2.07: run one retention cycle (for cron on hosts without the in-process scheduler).

The cycle cancels cases of reopened positions, creates cases for closed
positions that are due or within the reminder window, and records the
30/15/7-day reminders (emails only when SMTP is configured). It never deletes
candidate data. Safe to re-run: reminders are unique per closure, milestone,
recipient and channel, and a PostgreSQL advisory lock stops parallel runs.

Usage (from backend/, uses DATABASE_URL from the environment/.env):
    python scripts/run_retention_cycle.py

Example cron (every hour):
    0 * * * * cd /srv/hra/backend && .venv/bin/python scripts/run_retention_cycle.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.retention_automation import run_retention_cycle  # noqa: E402


def main() -> int:
    print(json.dumps(run_retention_cycle(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
