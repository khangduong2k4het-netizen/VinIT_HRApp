"""Generate synthetic DOCX CV fixtures for Phase 1 staging E2E.

The source pack lives in ``staging/synthetic`` and is intentionally fake:
all identities use ``example.test`` and synthetic phone numbers.  Generated
DOCX files are written outside the source pack (default
``staging/generated``) so operators can upload them to a staging environment
without editing the reviewed source text.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from docx import Document

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "staging" / "synthetic" / "manifest.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "staging" / "generated"
ALLOWED_OUTCOMES = {"STRONG_MATCH", "MATCH", "UNCLEAR", "NO_MATCH"}


def load_manifest(manifest_path: Path = DEFAULT_MANIFEST) -> dict:
    return json.loads(Path(manifest_path).read_text(encoding="utf-8"))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_manifest(manifest: dict, *, manifest_path: Path = DEFAULT_MANIFEST) -> list[Path]:
    """Validate the synthetic pack and return candidate source paths."""
    _require(manifest.get("data_classification") == "SYNTHETIC_ONLY",
             "staging fixture manifest must be SYNTHETIC_ONLY")
    allowed_domains = set(manifest.get("allowed_email_domains") or [])
    _require("example.test" in allowed_domains, "example.test must be an allowed staging domain")

    base_dir = Path(manifest_path).resolve().parent

    def check_identity(owner: str, identity: dict) -> None:
        email = str(identity.get("email") or "")
        _require("@" in email, f"{owner} is missing an email")
        domain = email.rsplit("@", 1)[1]
        _require(domain in allowed_domains, f"{owner} uses non-synthetic email domain: {domain}")
        phone = str(identity.get("phone") or "")
        if phone:
            _require("000" in phone, f"{owner} phone does not look synthetic: {phone}")

    for user in manifest.get("users", []):
        check_identity(f"user {user.get('key')}", user)

    position_keys = {position.get("key") for position in manifest.get("positions", [])}
    source_paths: list[Path] = []
    candidate_keys: set[str] = set()
    for candidate in manifest.get("candidates", []):
        key = candidate.get("key")
        _require(key and key not in candidate_keys, f"duplicate or missing candidate key: {key}")
        candidate_keys.add(key)
        _require(candidate.get("position_key") in position_keys,
                 f"candidate {key} references unknown position {candidate.get('position_key')}")
        check_identity(f"candidate {key}", candidate.get("identity") or {})
        source = base_dir / str(candidate.get("source_file") or "")
        _require(source.is_file(), f"candidate {key} source file is missing: {source}")
        source_paths.append(source)
        for criterion, outcome in (candidate.get("expected_criteria") or {}).items():
            _require(outcome in ALLOWED_OUTCOMES,
                     f"candidate {key} criterion {criterion} has invalid expected outcome {outcome}")

    for fixture in manifest.get("special_fixtures", []):
        source = base_dir / str(fixture.get("source_file") or "")
        _require(source.is_file(), f"special fixture {fixture.get('key')} source file is missing: {source}")
        source_paths.append(source)

    return source_paths


def _write_docx(source_text: str, output_path: Path) -> None:
    document = Document()
    lines = [line.rstrip() for line in source_text.splitlines()]
    non_empty = [line for line in lines if line.strip()]
    if non_empty:
        document.add_heading(non_empty[0], level=1)
        for line in non_empty[1:]:
            document.add_paragraph(line)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)


def generate_docx_fixtures(
    manifest: dict,
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> list[Path]:
    validate_manifest(manifest, manifest_path=manifest_path)
    base_dir = Path(manifest_path).resolve().parent
    output_dir = Path(output_dir)
    generated: list[Path] = []
    for candidate in manifest.get("candidates", []):
        source = base_dir / str(candidate["source_file"])
        target = output_dir / str(candidate["generated_docx"])
        _write_docx(source.read_text(encoding="utf-8"), target)
        generated.append(target)
    return generated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic staging DOCX fixtures")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--check", action="store_true", help="Validate only; do not write DOCX files")
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest)
    if args.check:
        validate_manifest(manifest, manifest_path=args.manifest)
        print(f"OK: {args.manifest} is a valid synthetic staging pack")
        return 0

    generated = generate_docx_fixtures(
        manifest, manifest_path=args.manifest, output_dir=args.output_dir
    )
    for path in generated:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
