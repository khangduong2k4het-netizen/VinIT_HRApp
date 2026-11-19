#!/usr/bin/env python3
"""Export a read-only matching snapshot for the stability evaluator.

The export contains assessment identifiers, fingerprints, scores and
per-criterion outcomes only.  It deliberately excludes CV text, candidate
profile facts, evidence quotes and provider snapshots, so the resulting
JSON can be used as QA input to ``evaluate_matching.py`` without copying
candidate content out of the assessment tables.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.db.database import SessionLocal


def build_snapshot(db, *, position_id: str | None = None, limit: int = 1000) -> dict[str, Any]:
    """Return evaluator-shaped runs ordered by explicit creation time."""
    runs = db.execute(text("""
        SELECT ar.assessment_id, ar.application_id, ar.position_id,
               ar.assessment_fingerprint, ar.matching_score, ar.evidence_coverage,
               ar.matching_status, ar.created_at,
               COALESCE(
                   jsonb_agg(
                       jsonb_build_object(
                           'criterion_id', cr.criterion_id,
                           'outcome', cr.outcome,
                           'decision_source', cr.decision_source
                       ) ORDER BY cr.criterion_id
                   ) FILTER (WHERE cr.criterion_id IS NOT NULL),
                   '[]'::jsonb
               ) AS criterion_results
        FROM app_private.assessment_runs ar
        LEFT JOIN app_private.criterion_assessment_results cr
          ON cr.assessment_id = ar.assessment_id
        WHERE ar.status = 'COMPLETED'
          AND (CAST(:position_id AS uuid) IS NULL OR ar.position_id = CAST(:position_id AS uuid))
        GROUP BY ar.assessment_id
        ORDER BY ar.created_at, ar.assessment_id
        LIMIT :limit
    """), {"position_id": position_id, "limit": limit}).mappings().all()

    ranking_rows = db.execute(text("""
        SELECT ri.application_id, ri.rank_number
        FROM app_private.ranking_items ri
        JOIN app_private.ranking_runs rr ON rr.ranking_run_id = ri.ranking_run_id
        WHERE rr.status = 'COMPLETED'
          AND (CAST(:position_id AS uuid) IS NULL OR rr.position_id = CAST(:position_id AS uuid))
          AND rr.created_at = (
              SELECT MAX(rr2.created_at) FROM app_private.ranking_runs rr2
              WHERE rr2.status = 'COMPLETED'
                AND (CAST(:position_id AS uuid) IS NULL OR rr2.position_id = CAST(:position_id AS uuid))
          )
        ORDER BY ri.rank_number, ri.application_id
    """), {"position_id": position_id}).mappings().all()

    return {
        "runs": [
            {
                "assessment_id": str(run["assessment_id"]),
                "application_id": str(run["application_id"]),
                "position_id": str(run["position_id"]),
                "assessment_fingerprint": run["assessment_fingerprint"],
                "matching_score": float(run["matching_score"]) if run["matching_score"] is not None else None,
                "evidence_coverage": float(run["evidence_coverage"]) if run["evidence_coverage"] is not None else None,
                "matching_status": run["matching_status"],
                "created_at": run["created_at"].isoformat() if run["created_at"] else None,
                "criterion_results": run["criterion_results"] or [],
            }
            for run in runs
        ],
        "rankings": {
            "candidate": [str(row["application_id"]) for row in ranking_rows],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--position-id", help="Only export this position")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--output", help="Write JSON here instead of stdout")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        snapshot = build_snapshot(db, position_id=args.position_id, limit=args.limit)
    finally:
        db.close()

    rendered = json.dumps(snapshot, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
