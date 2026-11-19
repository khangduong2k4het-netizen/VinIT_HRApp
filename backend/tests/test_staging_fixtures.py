import importlib.util
from pathlib import Path

from docx import Document

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "backend" / "scripts" / "generate_staging_fixtures.py"
MANIFEST_PATH = REPO_ROOT / "staging" / "synthetic" / "manifest.json"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_staging_fixtures", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_staging_manifest_is_synthetic_and_complete():
    generator = _load_generator()
    manifest = generator.load_manifest(MANIFEST_PATH)

    sources = generator.validate_manifest(manifest, manifest_path=MANIFEST_PATH)

    assert manifest["dataset_id"] == "phase1-staging-synthetic-v1"
    assert len(sources) >= len(manifest["candidates"])
    assert {candidate["key"] for candidate in manifest["candidates"]} >= {
        "strong_backend",
        "partial_backend",
        "java_only",
        "vietnamese_backend",
        "retention_due_candidate",
        "retention_not_due_candidate",
    }
    assert all(
        user["email"].endswith("@example.test") for user in manifest["users"]
    )
    java_only = next(candidate for candidate in manifest["candidates"] if candidate["key"] == "java_only")
    # Conservative policy: explicit negative evidence is not an automatic
    # NO_MATCH; HR must verify before any rejection.
    assert java_only["expected_criteria"]["python_backend"] == "UNCLEAR"
    assert "remains UNCLEAR" in java_only["expected_gate"]
    partial = next(candidate for candidate in manifest["candidates"] if candidate["key"] == "partial_backend")
    # The Python rubric keeps its 4-year requirement; a stated 2 years is
    # therefore UNCLEAR for HR verification, not a MATCH or automatic NO_MATCH.
    assert partial["expected_criteria"]["python_backend"] == "UNCLEAR"
    assert partial["expected_criteria"]["docker"] == "UNCLEAR"


def test_generate_staging_docx_fixtures(tmp_path):
    generator = _load_generator()
    manifest = generator.load_manifest(MANIFEST_PATH)

    generated = generator.generate_docx_fixtures(
        manifest, manifest_path=MANIFEST_PATH, output_dir=tmp_path
    )

    assert len(generated) == len(manifest["candidates"])
    assert all(path.is_file() and path.suffix == ".docx" for path in generated)
    strong_text = "\n".join(
        paragraph.text for paragraph in Document(tmp_path / "strong_backend.docx").paragraphs
    )
    assert "candidate.strong@example.test" in strong_text
    assert "PostgreSQL" in strong_text
