#!/usr/bin/env python3
"""Export a weak-label LTR dataset from completed assessments.

Rows are grouped by position.  Final application status is the only
available operational label in the current schema, so the export marks
every row ``WEAK`` and refuses to present it as an HR gold set.  Review
and replace the labels with human relevance judgements before an LTR
artifact trained from this data is approved for ACTIVE mode.

The export contains identifiers, numeric features and outcomes only; it
never exports CV text, evidence quotes or candidate profile details.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.services.ltr import extract_ranking_features  # noqa: E402


def weak_label(application_status: str) -> int | None:
    """Map operational outcome to a weak relevance label (never HR gold)."""
    status = (application_status or "").upper()
    if status in {"ACCEPTED", "HIRED"}:
        return 3
    if status in {"OFFERED", "INTERVIEW", "SHORTLIST"}:
        return 2
    if status in {"IN_REVIEW", "NEW"}:
        return 1
    if status in {"REJECTED_SCREENING", "REJECTED_INTERVIEW", "REJECTED", "WITHDRAWN"}:
        return 0
    return None


def build_dataset(db, *, position_id: str | None = None) -> dict:
    assessments = db.execute(text("""
        WITH latest AS (
            SELECT DISTINCT ON (ar.application_id)
                   ar.assessment_id, ar.application_id, ar.position_id,
                   ar.matching_score, ar.evidence_coverage, ar.matching_status,
                   ar.created_at
            FROM app_private.assessment_runs ar
            WHERE ar.status = 'COMPLETED'
              AND (CAST(:position_id AS uuid) IS NULL OR ar.position_id = CAST(:position_id AS uuid))
            ORDER BY ar.application_id, ar.created_at DESC, ar.assessment_id DESC
        )
        SELECT latest.assessment_id::text AS assessment_id,
               latest.application_id::text AS application_id,
               latest.position_id::text AS position_id,
               latest.matching_score, latest.evidence_coverage, latest.matching_status,
               app.application_status
        FROM latest
        JOIN app_private.applications app ON app.application_id = latest.application_id
        ORDER BY latest.position_id, latest.application_id
    """), {"position_id": position_id}).mappings().all()
    if not assessments:
        return {"examples": [], "label_source": "WEAK_OPERATIONAL_OUTCOME"}

    assessment_ids = [str(row["assessment_id"]) for row in assessments]
    criterion_rows = db.execute(text("""
        SELECT cr.assessment_id::text AS assessment_id, cr.outcome, cr.decision_source,
               cr.evidence_strength, ci.category
        FROM app_private.criterion_assessment_results cr
        JOIN app_private.criteria_items ci ON ci.criterion_id = cr.criterion_id
        WHERE cr.assessment_id = ANY(CAST(:assessment_ids AS uuid[]))
    """), {"assessment_ids": assessment_ids}).mappings().all()
    results_by_assessment: dict[str, list[dict]] = {}
    for row in criterion_rows:
        results_by_assessment.setdefault(str(row["assessment_id"]), []).append(dict(row))

    examples = []
    for row in assessments:
        label = weak_label(str(row["application_status"]))
        if label is None:
            continue
        assessment = {
            "matching_score": float(row["matching_score"]) if row["matching_score"] is not None else None,
            "evidence_coverage": float(row["evidence_coverage"] or 0),
            "matching_status": row["matching_status"],
        }
        examples.append({
            "group_id": str(row["position_id"]),
            "position_id": str(row["position_id"]),
            "application_id": str(row["application_id"]),
            "assessment_id": str(row["assessment_id"]),
            "label": label,
            "label_source": "WEAK",
            "application_status": row["application_status"],
            "features": extract_ranking_features(
                assessment, results_by_assessment.get(str(row["assessment_id"]), [])),
        })
    return {"examples": examples, "label_source": "WEAK_OPERATIONAL_OUTCOME"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--position-id")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    db = SessionLocal()
    try:
        dataset = build_dataset(db, position_id=args.position_id)
    finally:
        db.close()
    Path(args.output).write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(dataset['examples'])} weak-label examples to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
