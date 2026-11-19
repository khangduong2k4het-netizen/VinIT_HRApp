#!/usr/bin/env python3
"""Register a trained LTR artifact as a DRAFT model version.

Registration never approves or activates a model.  An authorized reviewer
must explicitly approve the exact artifact hash through the admin review
endpoint before the worker may use it in ACTIVE mode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.services.ltr import LTRModel, artifact_sha256  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", help="LTR artifact JSON written by train_ltr.py")
    args = parser.parse_args()

    raw = Path(args.artifact).read_bytes()
    artifact = json.loads(raw.decode("utf-8"))
    model = LTRModel.from_artifact(artifact)
    training = artifact.get("training") or {}
    data_sha256 = training.get("data_sha256") or hashlib.sha256(raw).hexdigest()
    db = SessionLocal()
    try:
        existing = db.execute(text("""
            SELECT artifact, artifact_sha256
            FROM app_private.ltr_model_versions
            WHERE model_version = :model_version
        """), {"model_version": model.model_version}).mappings().first()
        if existing:
            existing_artifact = existing["artifact"]
            if isinstance(existing_artifact, str):
                existing_artifact = json.loads(existing_artifact)
            existing_hash = existing["artifact_sha256"] or artifact_sha256(existing_artifact)
            if existing_hash != model.artifact_sha256:
                print(
                    "Model version already exists with a different artifact; "
                    "refusing to overwrite it", file=sys.stderr)
                return 1
            if not existing["artifact_sha256"]:
                db.execute(text("""
                    UPDATE app_private.ltr_model_versions
                    SET artifact_sha256 = :artifact_sha256
                    WHERE model_version = :model_version
                """), {
                    "model_version": model.model_version,
                    "artifact_sha256": model.artifact_sha256,
                })
                db.commit()
            print(f"LTR model {model.model_version} is already registered as DRAFT/APPROVED/REJECTED")
            return 0

        db.execute(text("""
            INSERT INTO app_private.ltr_model_versions
                (model_version, artifact, metrics, feature_names, training_examples,
                 training_groups, data_sha256, artifact_sha256, status)
            VALUES (:model_version, CAST(:artifact AS jsonb), CAST(:metrics AS jsonb),
                    CAST(:feature_names AS jsonb), :training_examples, :training_groups,
                    :data_sha256, :artifact_sha256, 'DRAFT')
        """), {
            "model_version": model.model_version,
            "artifact": json.dumps(artifact, ensure_ascii=False),
            "metrics": json.dumps(artifact.get("metrics") or {}, ensure_ascii=False),
            "feature_names": json.dumps(artifact.get("feature_names") or [], ensure_ascii=False),
            "training_examples": int(training.get("examples") or 0),
            "training_groups": int(training.get("groups") or 0),
            "data_sha256": data_sha256,
            "artifact_sha256": model.artifact_sha256,
        })
        db.execute(text("""
            INSERT INTO app_private.ltr_model_review_events
                (model_version, artifact_sha256, action, from_status, to_status,
                 metrics, data_sha256)
            VALUES (:model_version, :artifact_sha256, 'REGISTERED', NULL, 'DRAFT',
                    CAST(:metrics AS jsonb), :data_sha256)
        """), {
            "model_version": model.model_version,
            "artifact_sha256": model.artifact_sha256,
            "metrics": json.dumps(artifact.get("metrics") or {}, ensure_ascii=False),
            "data_sha256": data_sha256,
        })
        db.commit()
    finally:
        db.close()
    print(f"Registered LTR model {model.model_version} as DRAFT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
