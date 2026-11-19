#!/usr/bin/env python3
"""Push matching repeatability aggregates to Langfuse scores.

Input is the same snapshot JSON accepted by ``evaluate_matching.py``. The
script computes the existing deterministic repeatability report locally and,
only with ``--send``, sends aggregate scores to Langfuse. It never sends CV
text, profile facts, evidence quotes or per-application details.

Examples, from ``backend/``:

    .venv/bin/python scripts/push_langfuse_evaluation.py snapshot.json
    .venv/bin/python scripts/push_langfuse_evaluation.py snapshot.json --send --run-name matching-v2.1-check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import langfuse_observability as observability
from app.services.evaluation import build_repeatability_report, compare_rankings


def _run_id(run: dict[str, Any]) -> str:
    return str(run.get("application_id") or run.get("candidate_id") or run.get("id") or "")


def _derived_ranking(runs: list[dict[str, Any]], *, latest: bool) -> list[str]:
    from app.services.evaluation import _chronologically_ordered

    selected: dict[str, dict[str, Any]] = {}
    for run in _chronologically_ordered(runs):
        application_id = _run_id(run)
        if not application_id:
            continue
        if latest or application_id not in selected:
            selected[application_id] = run

    def sort_key(item: tuple[str, dict[str, Any]]) -> tuple[float, float, str]:
        application_id, run = item
        score = run.get("matching_score", run.get("score"))
        coverage = run.get("evidence_coverage", run.get("coverage"))
        return (
            -(float(score) if score is not None else -1),
            -(float(coverage) if coverage is not None else 0),
            application_id,
        )

    return [application_id for application_id, _ in sorted(selected.items(), key=sort_key)]


def build_report(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        runs, reuse, rankings = payload, None, {}
    elif isinstance(payload, dict):
        runs = payload.get("runs", [])
        reuse = payload.get("reuse")
        rankings = payload.get("rankings") or {}
    else:
        raise TypeError("Snapshot JSON must be a list or an object with a runs list")
    runs = [run for run in runs if isinstance(run, dict)]

    grouped: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        fingerprint = str(run.get("assessment_fingerprint") or run.get("fingerprint") or "unknown")
        grouped.setdefault(fingerprint, []).append(run)
    groups = [
        {"fingerprint": fingerprint, "runs": grouped[fingerprint]}
        for fingerprint in sorted(grouped)
    ]
    baseline_ranking = rankings.get("baseline") or _derived_ranking(runs, latest=False)
    candidate_ranking = rankings.get("candidate") or _derived_ranking(runs, latest=True)
    report = build_repeatability_report(
        groups,
        reuse_stats=reuse,
        baseline_ranking=baseline_ranking if runs else None,
        candidate_ranking=candidate_ranking if runs else None,
    )
    if runs:
        report["ranking"] = compare_rankings(baseline_ranking, candidate_ranking)
    return report


def evaluation_scores(report: dict[str, Any], *, run_name: str) -> list[dict[str, Any]]:
    aggregate = report.get("aggregate") or {}
    ranking = report.get("ranking") or {}
    scores: list[dict[str, Any]] = []
    metadata = {"run_name": run_name, "evaluation_type": "matching_repeatability"}

    def add(name: str, value: Any, data_type: str = "NUMERIC") -> None:
        if value is not None:
            scores.append({"name": name, "value": value, "data_type": data_type, "metadata": metadata})

    add("repeatability_mean_score_drift", aggregate.get("mean_score_drift"))
    add("repeatability_max_score_drift", aggregate.get("max_score_drift"))
    add("repeatability_p95_score_drift", aggregate.get("p95_score_drift"))
    add("criterion_flip_rate", aggregate.get("criterion_flip_rate"))
    add("fingerprint_reuse_rate", report.get("fingerprint_reuse_rate"))
    add("ranking_kendall_tau", ranking.get("kendall_tau"))
    top_k = ranking.get("top_k_overlap") or {}
    add("ranking_top10_overlap", top_k.get("10"))
    add("repeatability_passed", bool(report.get("passed")), "BOOLEAN")
    return scores


def push_report(report: dict[str, Any], *, run_name: str) -> bool:
    if not observability.get_observability_status()["configured"]:
        return False
    scores = evaluation_scores(report, run_name=run_name)
    aggregate = report.get("aggregate") or {}
    with observability.span(
        "hra.evaluation.repeatability",
        metadata={
            "run_name": run_name,
            "evaluation_type": "matching_repeatability",
            "group_count": len(report.get("groups") or []),
            "criterion_compared": aggregate.get("criterion_compared"),
            "passed": bool(report.get("passed")),
        },
        input_data={"run_name": run_name, "score_count": len(scores)},
    ) as evaluation_span:
        evaluation_span.update(output={
            "passed": bool(report.get("passed")),
            "score_count": len(scores),
            "criterion_compared": aggregate.get("criterion_compared"),
            "criterion_flips": aggregate.get("criterion_flips"),
        })
        for score in scores:
            evaluation_span.score_trace(**score)
        for group in report.get("groups") or []:
            group_metadata = {
                "run_name": run_name,
                "assessment_fingerprint": group.get("fingerprint"),
                "evaluation_type": "matching_repeatability",
            }
            if group.get("p95_score_drift") is not None:
                evaluation_span.score(
                    name="group_p95_score_drift",
                    value=group["p95_score_drift"],
                    data_type="NUMERIC",
                    metadata=group_metadata,
                )
            if group.get("criterion_flip_rate") is not None:
                evaluation_span.score(
                    name="group_criterion_flip_rate",
                    value=group["criterion_flip_rate"],
                    data_type="NUMERIC",
                    metadata=group_metadata,
                )
    observability.flush()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Path to a matching snapshot JSON file")
    parser.add_argument("--run-name", default="matching-repeatability", help="Evaluation run label")
    parser.add_argument("--send", action="store_true", help="Send aggregate scores to Langfuse")
    parser.add_argument("--output", help="Write the full local repeatability report JSON here")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    report = build_report(payload)
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "run_name": args.run_name,
        "aggregate": report.get("aggregate"),
        "ranking": report.get("ranking"),
        "fingerprint_reuse_rate": report.get("fingerprint_reuse_rate"),
        "checks": report.get("checks"),
        "passed": report.get("passed"),
        "scores": evaluation_scores(report, run_name=args.run_name),
        "langfuse_status": observability.get_observability_status(),
        "sent": False,
    }
    if args.send:
        if not push_report(report, run_name=args.run_name):
            print("Langfuse is not configured; scores were not sent.", file=sys.stderr)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 2
        summary["sent"] = True
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
