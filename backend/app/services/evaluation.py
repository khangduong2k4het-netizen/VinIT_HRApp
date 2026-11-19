"""Repeatability and ranking-stability metrics for matching assessments.

The functions in this module are deterministic and side-effect free.  They
accept assessment snapshots (for example JSON exported from assessment runs)
and quantify whether repeated processing produces the same scores, the same
per-criterion outcomes and the same ranking.  They intentionally do not judge
whether a decision is *correct*; correctness requires the separate HR-labelled
golden set described in doc/MATCHING_STABILITY.md.
"""

from __future__ import annotations

import math
from datetime import datetime
from collections.abc import Iterable, Mapping
from typing import Any

DEFAULT_THRESHOLDS = {
    "max_p95_score_drift": 2.0,
    "max_criterion_flip_rate": 0.02,
    "min_ranking_kendall": 0.90,
    "min_top10_overlap": 0.90,
    "required_fingerprint_reuse_rate": 1.0,
}


def _run_id(run: Mapping[str, Any]) -> str:
    return str(run.get("application_id") or run.get("candidate_id") or run.get("id") or "")


def _run_chronology_key(run: Mapping[str, Any], index: int = 0) -> tuple[int, float, int]:
    """Explicit run order: run_index/sequence, then created_at, then input order."""
    for key in ("run_index", "sequence", "attempt"):
        try:
            return (0, float(run.get(key)), index)
        except (TypeError, ValueError):
            continue
    raw = run.get("created_at") or run.get("completed_at") or run.get("timestamp")
    if raw is not None:
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return (1, parsed.timestamp(), index)
        except ValueError:
            pass
    return (2, 0.0, index)


def _chronologically_ordered(runs: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        run for _, run in sorted(
            enumerate(runs),
            key=lambda item: _run_chronology_key(item[1], item[0]),
        )
    ]


def _run_score(run: Mapping[str, Any]) -> float | None:
    value = run.get("matching_score", run.get("score"))
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return score if math.isfinite(score) else None


def _run_outcomes(run: Mapping[str, Any]) -> dict[str, str]:
    items = run.get("criterion_results") or run.get("criteria") or run.get("findings") or []
    outcomes: dict[str, str] = {}
    if isinstance(items, Mapping):
        items = [
            {"criterion_id": criterion_id, "outcome": outcome}
            for criterion_id, outcome in items.items()
        ]
    for item in items if isinstance(items, Iterable) else []:
        if not isinstance(item, Mapping):
            continue
        criterion_id = str(item.get("criterion_id") or item.get("id") or "")
        if criterion_id:
            outcomes[criterion_id] = str(item.get("outcome") or "UNCLEAR").upper()
    return outcomes


def normalize_run(run: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "application_id": _run_id(run),
        "score": _run_score(run),
        "outcomes": _run_outcomes(run),
        "fingerprint": run.get("assessment_fingerprint") or run.get("fingerprint"),
    }


def percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil((percent / 100) * len(ordered)) - 1)
    return ordered[index]


def compare_assessments(
    baseline_runs: Iterable[Mapping[str, Any]],
    candidate_runs: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare two assessment sets application-by-application."""
    baseline = {_run_id(run): normalize_run(run) for run in baseline_runs if _run_id(run)}
    candidate = {_run_id(run): normalize_run(run) for run in candidate_runs if _run_id(run)}
    application_ids = sorted(set(baseline) & set(candidate))

    score_drifts: list[float] = []
    criterion_compared = 0
    criterion_flips = 0
    exact_applications = 0
    details: list[dict[str, Any]] = []

    for application_id in application_ids:
        base, cand = baseline[application_id], candidate[application_id]
        drift = None
        if base["score"] is not None and cand["score"] is not None:
            drift = round(abs(base["score"] - cand["score"]), 4)
            score_drifts.append(drift)
        criterion_ids = sorted(set(base["outcomes"]) | set(cand["outcomes"]))
        flipped = [
            criterion_id for criterion_id in criterion_ids
            if base["outcomes"].get(criterion_id) != cand["outcomes"].get(criterion_id)
        ]
        criterion_compared += len(criterion_ids)
        criterion_flips += len(flipped)
        exact = drift == 0 and not flipped
        exact_applications += int(exact)
        details.append({
            "application_id": application_id,
            "score_drift": drift,
            "flipped_criterion_ids": flipped,
            "exact": exact,
        })

    return {
        "applications_compared": len(application_ids),
        "applications_only_in_baseline": sorted(set(baseline) - set(candidate)),
        "applications_only_in_candidate": sorted(set(candidate) - set(baseline)),
        "mean_score_drift": round(sum(score_drifts) / len(score_drifts), 4) if score_drifts else None,
        "max_score_drift": max(score_drifts) if score_drifts else None,
        "p95_score_drift": percentile(score_drifts, 95),
        "criterion_compared": criterion_compared,
        "criterion_flips": criterion_flips,
        "criterion_flip_rate": round(criterion_flips / criterion_compared, 6) if criterion_compared else None,
        "exact_application_agreement": (
            round(exact_applications / len(application_ids), 6) if application_ids else None
        ),
        "details": details,
    }


def _ranking_entries(ranking: Iterable[Any]) -> list[tuple[str, float]]:
    """(application_id, rank position) pairs, preserving explicit ties."""
    items = list(ranking)
    if all(isinstance(item, str) for item in items):
        return [(str(item), float(index)) for index, item in enumerate(items, start=1)]
    runs = [item for item in items if isinstance(item, Mapping)]
    if any(item.get("rank_number") is not None or item.get("rank") is not None for item in runs):
        runs.sort(key=lambda item: (
            item.get("rank_number") if item.get("rank_number") is not None else item.get("rank"),
            _run_id(item),
        ))
        return [
            (_run_id(item), float(
                item.get("rank_number") if item.get("rank_number") is not None else item.get("rank")
            ))
            for item in runs if _run_id(item)
        ]
    return [(_run_id(item), float(index)) for index, item in enumerate(runs, start=1) if _run_id(item)]


def _ranking_ids(ranking: Iterable[Any]) -> list[str]:
    return [application_id for application_id, _ in _ranking_entries(ranking)]


def _rank_positions(ids: list[str]) -> dict[str, float]:
    positions: dict[str, list[int]] = {}
    for index, application_id in enumerate(ids, start=1):
        positions.setdefault(application_id, []).append(index)
    return {key: sum(value) / len(value) for key, value in positions.items()}


def _ranking_positions(ranking: Iterable[Any]) -> dict[str, float]:
    positions: dict[str, list[float]] = {}
    for application_id, position in _ranking_entries(ranking):
        positions.setdefault(application_id, []).append(position)
    return {key: sum(value) / len(value) for key, value in positions.items()}


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    mean_left, mean_right = sum(left) / len(left), sum(right) / len(right)
    numerator = sum((x - mean_left) * (y - mean_right) for x, y in zip(left, right, strict=True))
    denominator = math.sqrt(
        sum((x - mean_left) ** 2 for x in left) * sum((y - mean_right) ** 2 for y in right)
    )
    return round(numerator / denominator, 6) if denominator else 1.0


def compare_rankings(
    baseline_ranking: Iterable[Any],
    candidate_ranking: Iterable[Any],
) -> dict[str, Any]:
    """Spearman/Kendall/top-k agreement for two rankings."""
    baseline_ids = _ranking_ids(baseline_ranking)
    candidate_ids = _ranking_ids(candidate_ranking)
    common = sorted(set(baseline_ids) & set(candidate_ids))
    baseline_rank = _ranking_positions(baseline_ranking)
    candidate_rank = _ranking_positions(candidate_ranking)

    spearman = _pearson(
        [baseline_rank[item] for item in common],
        [candidate_rank[item] for item in common],
    )

    concordant = discordant = 0
    baseline_ties = candidate_ties = 0
    for index, first in enumerate(common):
        for second in common[index + 1:]:
            baseline_order = baseline_rank[first] - baseline_rank[second]
            candidate_order = candidate_rank[first] - candidate_rank[second]
            baseline_tied = baseline_order == 0
            candidate_tied = candidate_order == 0
            if baseline_tied:
                baseline_ties += 1
            if candidate_tied:
                candidate_ties += 1
            if baseline_tied or candidate_tied:
                continue
            if (baseline_order > 0) == (candidate_order > 0):
                concordant += 1
            else:
                discordant += 1
    # Kendall tau-b: pairs tied in both rankings are excluded from both
    # tie counts by using the standard n1/n2 correction below.
    both_ties = 0
    for index, first in enumerate(common):
        for second in common[index + 1:]:
            if baseline_rank[first] == baseline_rank[second] and candidate_rank[first] == candidate_rank[second]:
                both_ties += 1
    n1 = baseline_ties - both_ties
    n2 = candidate_ties - both_ties
    denominator = math.sqrt((concordant + discordant + n1) * (concordant + discordant + n2))
    kendall = round((concordant - discordant) / denominator, 6) if denominator else None

    top_k: dict[str, float | None] = {}
    for k in (5, 10, 20):
        effective = min(k, len(baseline_ids), len(candidate_ids))
        top_k[str(k)] = (
            round(len(set(baseline_ids[:effective]) & set(candidate_ids[:effective])) / effective, 6)
            if effective else None
        )

    return {
        "baseline_size": len(baseline_ids),
        "candidate_size": len(candidate_ids),
        "common_applications": len(common),
        "spearman": spearman,
        "kendall_tau": kendall,
        "kendall_tau_b": kendall,
        "top_k_overlap": top_k,
    }


def _split_repeats(runs: list[Mapping[str, Any]]) -> tuple[list[Mapping[str, Any]], list[list[Mapping[str, Any]]]]:
    baseline_by_id: dict[str, Mapping[str, Any]] = {}
    repeats_by_id: dict[str, list[Mapping[str, Any]]] = {}
    for run in _chronologically_ordered(runs):
        application_id = _run_id(run)
        if not application_id:
            continue
        if application_id not in baseline_by_id:
            baseline_by_id[application_id] = run
        else:
            repeats_by_id.setdefault(application_id, []).append(run)
    baseline = [baseline_by_id[key] for key in sorted(baseline_by_id)]
    repeat_sets = []
    max_repeats = max((len(value) for value in repeats_by_id.values()), default=0)
    for index in range(max_repeats):
        repeat_sets.append([
            repeats_by_id[key][index]
            for key in sorted(repeats_by_id)
            if len(repeats_by_id[key]) > index
        ])
    return baseline, repeat_sets


def build_repeatability_report(
    groups: Iterable[Mapping[str, Any]],
    reuse_stats: Mapping[str, Any] | None = None,
    baseline_ranking: Iterable[Any] | None = None,
    candidate_ranking: Iterable[Any] | None = None,
    thresholds: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Build an acceptance report from repeated runs grouped by fingerprint.

    Each group is ``{"fingerprint": ..., "runs": [assessment, ...]}`` where
    the first occurrence of each application is the baseline and later
    occurrences are forced reruns of the same input.
    """
    limits = {**DEFAULT_THRESHOLDS, **dict(thresholds or {})}
    group_reports: list[dict[str, Any]] = []
    total_flips = total_criteria = 0
    all_drifts: list[float] = []

    for group in groups:
        runs = [run for run in group.get("runs", []) if isinstance(run, Mapping)]
        baseline, repeat_sets = _split_repeats(runs)
        comparisons = [compare_assessments(baseline, repeat) for repeat in repeat_sets]
        group_drifts: list[float] = []
        group_flips = group_criteria = 0
        for comparison in comparisons:
            group_flips += comparison["criterion_flips"]
            group_criteria += comparison["criterion_compared"]
            group_drifts.extend(
                detail["score_drift"] for detail in comparison["details"]
                if detail["score_drift"] is not None
            )
        total_flips += group_flips
        total_criteria += group_criteria
        all_drifts.extend(group_drifts)
        group_reports.append({
            "fingerprint": group.get("fingerprint"),
            "runs": len(runs),
            "baseline_applications": len(baseline),
            "repeat_sets": len(repeat_sets),
            "mean_score_drift": round(sum(group_drifts) / len(group_drifts), 4) if group_drifts else None,
            "max_score_drift": max(group_drifts) if group_drifts else None,
            "p95_score_drift": percentile(group_drifts, 95),
            "criterion_compared": group_criteria,
            "criterion_flips": group_flips,
            "criterion_flip_rate": round(group_flips / group_criteria, 6) if group_criteria else None,
            "comparisons": comparisons,
        })

    ranking = None
    if baseline_ranking is not None and candidate_ranking is not None:
        ranking = compare_rankings(baseline_ranking, candidate_ranking)

    reuse_rate = None
    if reuse_stats:
        eligible = reuse_stats.get("eligible", reuse_stats.get("eligible_reuse_count", reuse_stats.get("total")))
        reused = reuse_stats.get("reused", reuse_stats.get("reused_count"))
        try:
            if eligible not in (None, 0) and reused is not None:
                reuse_rate = round(float(reused) / float(eligible), 6)
        except (TypeError, ValueError):
            reuse_rate = None

    aggregate = {
        "mean_score_drift": round(sum(all_drifts) / len(all_drifts), 4) if all_drifts else None,
        "max_score_drift": max(all_drifts) if all_drifts else None,
        "p95_score_drift": percentile(all_drifts, 95),
        "criterion_compared": total_criteria,
        "criterion_flips": total_flips,
        "criterion_flip_rate": round(total_flips / total_criteria, 6) if total_criteria else None,
    }
    checks = {
        "has_repeat_data": bool(all_drifts or total_criteria),
        "p95_score_drift_within_limit": (
            aggregate["p95_score_drift"] is not None
            and aggregate["p95_score_drift"] <= limits["max_p95_score_drift"]
        ),
        "criterion_flip_rate_within_limit": (
            aggregate["criterion_flip_rate"] is not None
            and aggregate["criterion_flip_rate"] <= limits["max_criterion_flip_rate"]
        ),
        "fingerprint_reuse_complete": (
            reuse_rate is not None and reuse_rate >= limits["required_fingerprint_reuse_rate"]
        ),
        "ranking_stable": True if ranking is None else bool(
            (ranking["kendall_tau"] is None or ranking["kendall_tau"] >= limits["min_ranking_kendall"])
            and (ranking["top_k_overlap"].get("10") is None
                 or ranking["top_k_overlap"]["10"] >= limits["min_top10_overlap"])
        ),
    }
    passed = all(value for key, value in checks.items() if key != "fingerprint_reuse_complete" or reuse_stats)
    if reuse_stats:
        passed = passed and checks["fingerprint_reuse_complete"]

    return {
        "thresholds": limits,
        "groups": group_reports,
        "aggregate": aggregate,
        "ranking": ranking,
        "fingerprint_reuse_rate": reuse_rate,
        "checks": checks,
        "passed": passed,
    }
