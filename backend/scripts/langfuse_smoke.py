#!/usr/bin/env python3
"""Send one synthetic Langfuse trace, or only report safe configuration.

This script never reads a CV, JD, database record or provider secret. It is
intended for an approved dev/staging Langfuse project after LF-2 environment
mapping. Run from ``backend/`` so the local ``.env`` is loaded by settings:

    .venv/bin/python scripts/langfuse_smoke.py
    .venv/bin/python scripts/langfuse_smoke.py --send
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import langfuse_observability as observability


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true", help="Send one synthetic trace and score")
    args = parser.parse_args()

    status = observability.get_observability_status()
    print(json.dumps({"langfuse_status": status}, ensure_ascii=False, indent=2))
    if not args.send:
        return 0
    if not status["configured"]:
        print("Langfuse is not configured; set LANGFUSE_ENABLED=true and project keys first.", file=sys.stderr)
        return 2

    with observability.span(
        "hra.langfuse.smoke",
        metadata={"synthetic": True, "smoke_test": True},
        input_data={"synthetic": True},
    ) as smoke:
        smoke.update(output={"status": "COMPLETED", "synthetic": True})
        smoke.score(name="smoke_test", value=True, data_type="BOOLEAN", metadata={"synthetic": True})
    observability.flush()
    print("Synthetic Langfuse trace sent. Check the configured project/environment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
