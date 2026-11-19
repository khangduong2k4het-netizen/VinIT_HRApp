import importlib.util
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "push_langfuse_evaluation.py"
_SPEC = importlib.util.spec_from_file_location("push_langfuse_evaluation", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
build_report = _MODULE.build_report
evaluation_scores = _MODULE.evaluation_scores


def test_push_langfuse_evaluation_builds_scores_from_snapshot_without_sending():
    payload = {
        "reuse": {"reused": 1, "total": 4},
        "runs": [
            {
                "application_id": "APP-1",
                "created_at": "2026-11-01T00:00:00Z",
                "assessment_fingerprint": "fp-a",
                "score": 80,
                "evidence_coverage": 100,
                "criteria": [{"criterion_id": "C1", "outcome": "MATCH", "mandatory": True}],
            },
            {
                "application_id": "APP-1",
                "created_at": "2026-11-02T00:00:00Z",
                "assessment_fingerprint": "fp-a",
                "score": 82,
                "evidence_coverage": 100,
                "criteria": [{"criterion_id": "C1", "outcome": "MATCH", "mandatory": True}],
            },
            {
                "application_id": "APP-2",
                "created_at": "2026-11-01T00:00:00Z",
                "assessment_fingerprint": "fp-b",
                "score": 40,
                "evidence_coverage": 50,
                "criteria": [{"criterion_id": "C1", "outcome": "NO_MATCH", "mandatory": True}],
            },
        ],
    }

    report = build_report(payload)
    scores = evaluation_scores(report, run_name="unit")

    assert report["passed"] is False  # score drift threshold is 1.0; repeated APP-1 drifts by 2.0
    assert scores
    names = {score["name"] for score in scores}
    assert "repeatability_mean_score_drift" in names
    assert "criterion_flip_rate" in names
    assert "fingerprint_reuse_rate" in names
    assert "repeatability_passed" in names
    assert all(score["metadata"] == {"run_name": "unit", "evaluation_type": "matching_repeatability"} for score in scores)
