import json
from pathlib import Path

from app.services.deterministic_matching import deterministic_matcher
from app.services.evaluation import (
    build_repeatability_report,
    compare_assessments,
    compare_rankings,
)

FIXTURE = Path(__file__).parent / "fixtures" / "matching_golden.json"


def run(application_id, score, outcomes, fingerprint="fp-1"):
    return {
        "application_id": application_id,
        "matching_score": score,
        "assessment_fingerprint": fingerprint,
        "criterion_results": [
            {"criterion_id": criterion_id, "outcome": outcome}
            for criterion_id, outcome in outcomes.items()
        ],
    }


def test_identical_reruns_have_zero_drift_and_no_flips():
    baseline = [run("a", 90, {"c1": "MATCH", "c2": "STRONG_MATCH"})]
    report = compare_assessments(baseline, baseline)
    assert report["mean_score_drift"] == 0
    assert report["p95_score_drift"] == 0
    assert report["criterion_flip_rate"] == 0
    assert report["exact_application_agreement"] == 1.0


def test_score_drift_and_criterion_flips_are_measured():
    baseline = [run("a", 90, {"c1": "MATCH", "c2": "MATCH"})]
    candidate = [run("a", 93, {"c1": "STRONG_MATCH", "c2": "MATCH"})]
    report = compare_assessments(baseline, candidate)
    assert report["max_score_drift"] == 3
    assert report["criterion_compared"] == 2
    assert report["criterion_flips"] == 1
    assert report["criterion_flip_rate"] == 0.5


def test_ranking_metrics_for_identical_and_reversed_orders():
    identical = compare_rankings(["a", "b", "c", "d"], ["a", "b", "c", "d"])
    reversed_order = compare_rankings(["a", "b", "c", "d"], ["d", "c", "b", "a"])
    assert identical["spearman"] == 1.0
    assert identical["kendall_tau"] == 1.0
    assert identical["top_k_overlap"]["5"] == 1.0
    assert reversed_order["spearman"] == -1.0
    assert reversed_order["kendall_tau"] == -1.0


def test_repeatability_report_checks_reuse_and_thresholds():
    runs = [
        run("a", 90, {"c1": "MATCH"}),
        run("b", 80, {"c1": "STRONG_MATCH"}),
        run("a", 91, {"c1": "MATCH"}),
        run("b", 80, {"c1": "STRONG_MATCH"}),
    ]
    report = build_repeatability_report(
        [{"fingerprint": "fp-1", "runs": runs}],
        reuse_stats={"eligible": 4, "reused": 4},
        baseline_ranking=["a", "b"],
        candidate_ranking=["a", "b"],
    )
    assert report["fingerprint_reuse_rate"] == 1.0
    assert report["aggregate"]["p95_score_drift"] == 1
    assert report["passed"] is True


def test_repeatability_report_fails_when_thresholds_are_exceeded():
    runs = [
        run("a", 90, {"c1": "MATCH", "c2": "MATCH"}),
        run("a", 70, {"c1": "NO_MATCH", "c2": "MATCH"}),
    ]
    report = build_repeatability_report([{"fingerprint": "fp-1", "runs": runs}])
    assert report["aggregate"]["max_score_drift"] == 20
    assert report["checks"]["p95_score_drift_within_limit"] is False
    assert report["checks"]["criterion_flip_rate_within_limit"] is False
    assert report["passed"] is False


def test_golden_fixture_is_deterministic_across_three_runs():
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(cases) >= 10
    for case in cases:
        results = [
            deterministic_matcher.evaluate_criteria(
                case["cv_text"], [case["criterion"]], case.get("candidate_profile") or {})
            for _ in range(3)
        ]
        assert results[0] == results[1] == results[2], case["id"]
        findings = results[0]["findings"]
        if case["expected_outcome"] is None:
            assert findings == [], case["id"]
            assert results[0]["unresolved_criterion_ids"] == [case["criterion"]["criterion_id"]]
        else:
            assert len(findings) == 1, case["id"]
            assert findings[0]["outcome"] == case["expected_outcome"], case["id"]
            assert findings[0]["decision_source"] == "RULE", case["id"]
