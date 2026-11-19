#!/usr/bin/env python3
"""Train and gate an offline Learning-to-Rank artifact.

Input is a JSON list (or ``{"examples": [...]}``) where every example has
``group_id``/``position_id``, ``application_id``, ``label`` and
``features`` as produced by ``export_ltr_dataset.py`` or an HR-labelled
golden set.  Training fails closed when there are too few examples,
groups or relevance levels; no artifact is written in that case.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ltr import LTRError, train_ltr_model  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Labelled ranking examples JSON")
    parser.add_argument("--output", required=True, help="Write the model artifact JSON here")
    parser.add_argument("--report", help="Write the training report JSON here")
    parser.add_argument("--min-examples", type=int, default=200)
    parser.add_argument("--min-groups", type=int, default=10)
    parser.add_argument("--min-ndcg", type=float, default=0.70)
    parser.add_argument("--min-pairwise", type=float, default=0.65)
    parser.add_argument("--min-holdout-examples", type=int, default=20)
    parser.add_argument("--min-holdout-groups", type=int, default=2)
    parser.add_argument("--check", action="store_true",
                        help="Exit 2 when holdout metrics fail the gates")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    examples = payload.get("examples", []) if isinstance(payload, dict) else payload
    if not isinstance(examples, list):
        print("Input must be a JSON list or an object with an examples list", file=sys.stderr)
        return 1
    try:
        artifact = train_ltr_model(
            examples, min_examples=args.min_examples, min_groups=args.min_groups)
    except LTRError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    test_metrics = artifact["metrics"]["test"]
    training = artifact.get("training") or {}
    gates = {
        "ndcg_at_10": (test_metrics.get("ndcg_at_10") or 0) >= args.min_ndcg,
        "pairwise_accuracy": (test_metrics.get("pairwise_accuracy") or 0) >= args.min_pairwise,
        "holdout_examples": int(training.get("test_examples") or 0) >= args.min_holdout_examples,
        "holdout_groups": int(training.get("test_groups") or 0) >= args.min_holdout_groups,
    }
    artifact["gates"] = {
        "min_ndcg_at_10": args.min_ndcg,
        "min_pairwise_accuracy": args.min_pairwise,
        "min_holdout_examples": args.min_holdout_examples,
        "min_holdout_groups": args.min_holdout_groups,
        "passed": all(gates.values()),
        "checks": gates,
    }
    Path(args.output).write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "model_version": artifact["model_version"],
        "training": artifact["training"],
        "metrics": artifact["metrics"],
        "gates": artifact["gates"],
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 2 if args.check and not artifact["gates"]["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
