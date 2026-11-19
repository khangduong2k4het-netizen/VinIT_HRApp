import json

import pytest
from pydantic import ValidationError

from app.services.ai_config import sanitize_provider_snapshot
from app.services.evaluation import build_repeatability_report, compare_rankings
from app.services.matching import matching_engine


def test_provider_snapshot_is_reduced_without_operations_access():
    snapshot = {
        "runtime": {
            "source": "database",
            "config_id": "config-1",
            "provider": "compatible",
            "provider_name": "Provider",
            "model_name": "model-1",
            "api_base": "https://provider.example/v1",
            "api_key_configured": True,
            "api_key_hint": "sk-...1234",
        },
        "provider_returned_model": "model-1",
        "system_fingerprint": "fp-1",
    }

    reduced = sanitize_provider_snapshot(snapshot)

    assert reduced == {
        "model_name": "model-1",
        "provider_returned_model": "model-1",
        "system_fingerprint": "fp-1",
    }
    assert "api_key_hint" not in str(reduced)
    assert "api_base" not in str(reduced)

    operations = sanitize_provider_snapshot(snapshot, operations_access=True)
    assert operations["runtime"]["model_name"] == "model-1"
    assert "api_key" not in operations["runtime"]


def test_quote_span_prefers_suggested_page_for_repeated_quote():
    quote = "Built Python services for five years."
    cv_text = f"--- Page 1 ---\n{quote}\n\n--- Page 2 ---\n{quote}"

    first = matching_engine.find_quote_span(quote, cv_text)
    second = matching_engine.find_quote_span(quote, cv_text, preferred_page=2)

    assert first is not None and second is not None
    assert second[0] > first[0]
    assert matching_engine.quote_pages(quote, cv_text, second) == [2]


def test_kendall_uses_tau_b_tie_correction():
    baseline = [
        {"application_id": "a", "rank_number": 1},
        {"application_id": "b", "rank_number": 1},
        {"application_id": "c", "rank_number": 2},
    ]
    candidate = [
        {"application_id": "a", "rank_number": 1},
        {"application_id": "b", "rank_number": 2},
        {"application_id": "c", "rank_number": 2},
    ]

    result = compare_rankings(baseline, candidate)

    assert result["kendall_tau_b"] == 0.5
    assert result["kendall_tau"] == 0.5


def test_repeatability_uses_explicit_run_order_not_file_order():
    runs = [
        {"application_id": "a", "matching_score": 80, "run_index": 2,
         "criterion_results": [{"criterion_id": "c1", "outcome": "MATCH"}]},
        {"application_id": "a", "matching_score": 90, "run_index": 1,
         "criterion_results": [{"criterion_id": "c1", "outcome": "MATCH"}]},
    ]

    report = build_repeatability_report([{"fingerprint": "fp", "runs": runs}])

    assert report["aggregate"]["max_score_drift"] == 10


@pytest.mark.asyncio
async def test_llm_fallback_uses_chunks_and_isolates_invalid_findings(monkeypatch):
    from app.services.llm_client import LLMClient

    captured = {}

    async def fake_call(self, *, system_prompt, user_prompt, **kwargs):
        captured["system_prompt"] = system_prompt
        captured["user_prompt"] = user_prompt
        return {
            "candidate_identifier": "candidate",
            "rubric_version": "rubric",
            "findings": [
                {"criterion_id": "valid", "outcome": "MATCH", "confidence": 0.9,
                 "confidence_band": "HIGH", "reasoning": "Evidence supplied",
                 "evidence": {"verbatim_quote": "Built Python services for five years.",
                              "page_number": 1, "chunk_id": "chunk-0001"},
                 "requires_verification": False},
                {"criterion_id": "invalid", "outcome": "PERFECT", "confidence": 0.9,
                 "confidence_band": "HIGH", "reasoning": "Bad enum",
                 "evidence": {"verbatim_quote": "Invented", "page_number": 1},
                 "requires_verification": False},
            ],
        }

    monkeypatch.setattr(LLMClient, "_call_llm", fake_call)
    rubric = [
        {"criterion_id": "valid", "name": "Python", "description": "Python"},
        {"criterion_id": "invalid", "name": "Rust", "description": "Rust"},
    ]
    chunks = {
        "valid": [{"chunk_id": "chunk-0001", "page_number": 1, "section": "WORK",
                   "text": "Built Python services for five years."}],
        "invalid": [{"chunk_id": "chunk-0002", "page_number": 1, "section": "WORK",
                     "text": "Built Python services for five years."}],
    }

    result = await LLMClient().match_criterion_evidence(
        cv_text="FULL CV SECRET SENTENCE should not be sent when chunks are supplied.",
        candidate_profile={},
        rubric=rubric,
        candidate_identifier="candidate",
        rubric_version="rubric",
        candidate_chunks=chunks,
    )

    payload = json.loads(captured["user_prompt"])
    assert "untrusted_redacted_cv" not in payload
    assert "SECRET SENTENCE" not in captured["user_prompt"]
    assert payload["untrusted_candidate_chunks_by_criterion"]["valid"][0]["chunk_id"] == "chunk-0001"

    outcomes = {finding["criterion_id"]: finding["outcome"] for finding in result["findings"]}
    assert outcomes == {"valid": "MATCH", "invalid": "UNCLEAR"}
    invalid = next(f for f in result["findings"] if f["criterion_id"] == "invalid")
    assert invalid["requires_verification"] is True


@pytest.mark.asyncio
async def test_strict_json_schema_is_opt_in(monkeypatch):
    from app.core.config import settings
    from app.services.llm_client import LLMClient

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '{"ok":true}'}}]}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            captured.update(kwargs["json"])
            return FakeResponse()

    monkeypatch.setattr("app.services.llm_client.httpx.AsyncClient", FakeClient)
    monkeypatch.setattr(settings, "ALLOW_EXTERNAL_API", False)
    monkeypatch.setattr(settings, "LLM_API_BASE", "http://127.0.0.1:11434/v1")
    monkeypatch.setattr(settings, "LLM_STRICT_JSON_SCHEMA", True)
    monkeypatch.setattr("app.services.llm_client.get_active_runtime", lambda db: {
        "provider": "local", "model_name": settings.LLM_MODEL_NAME,
        "api_base": settings.LLM_API_BASE, "temperature_default": 0.1,
    })

    result = await LLMClient()._call_llm(
        "system", "user", json_schema={"type": "object"})

    assert result == {"ok": True}
    assert captured["response_format"]["type"] == "json_schema"
    assert captured["response_format"]["json_schema"]["strict"] is True


def test_requirement_spec_schema_rejects_missing_threshold():
    from app.schemas.criteria import CriterionCreate

    with pytest.raises(ValidationError):
        CriterionCreate(
            name="Python",
            description="Python experience",
            category="MUST_HAVE",
            weight_in_group=100,
            requirement_spec={"kind": "YEARS", "terms": ["Python"]},
        )
