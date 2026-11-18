"""P3-1 phase 2: score pooled applications against another position's rubric.

The scoring path is the one the worker uses for a position's own applicants:
deterministic rules decide measurable criteria first, the LLM only sees the
criteria the rules could not decide, every quote must be found verbatim in the
CV (otherwise the finding becomes UNCLEAR), and matching_engine computes score,
coverage and matching status. Semantic (BGE) retrieval is not used here; the
LLM gets the deterministic fallback chunks.

Nothing is written to the target position's applicants, assessments or
ranking: results live in talent_pool_scan_results and HR decides whom to
contact. Quotes are kept only when verified, and at most QUOTE_LIMIT chars.
"""
from __future__ import annotations

from typing import Any

from app.services.deterministic_matching import deterministic_matcher
from app.services.llm_client import llm_client
from app.services.matching import matching_engine

QUOTE_LIMIT = 300
STATUS_ORDER = {"MEETS_MANDATORY": 0, "NEEDS_HR_VERIFICATION": 1, "POSSIBLE_MISMATCH": 2, "NOT_ASSESSED": 3}


def score_against_rubric(loop, *, cv_text: str, candidate_profile: dict[str, Any], criteria_items: list[dict],
                         group_weights: dict[str, float], candidate_identifier: str, rubric_version: str) -> dict:
    """Return {score, coverage, matching_status, results} for one CV and one rubric."""
    deterministic = deterministic_matcher.evaluate_criteria(cv_text, criteria_items, candidate_profile)
    if deterministic.get("candidate_years_experience"):
        candidate_profile["total_years_experience"] = deterministic["candidate_years_experience"]
    raw_findings = list(deterministic.get("findings", []))
    unresolved_ids = set(deterministic.get("unresolved_criterion_ids", []))
    unresolved = [c for c in criteria_items if str(c.get("criterion_id")) in unresolved_ids]
    if unresolved:
        findings = loop.run_until_complete(llm_client.match_criterion_evidence(
            cv_text=cv_text, candidate_profile=candidate_profile, rubric=unresolved,
            candidate_identifier=candidate_identifier, rubric_version=rubric_version,
            candidate_chunks=deterministic.get("fallback_chunks", {})))
        if isinstance(findings, dict):
            findings.pop("_provider_metadata", None)
            findings.pop("_prompt_version", None)
            raw_findings.extend(findings.get("findings", []))

    chunk_by_id = {str(c.get("chunk_id")): c for c in deterministic.get("chunks", [])
                   if isinstance(c, dict) and c.get("chunk_id")}
    validated = []
    for finding in matching_engine.canonicalize_findings(criteria_items, raw_findings):
        evidence = finding.get("evidence") or {}
        quote = evidence.get("verbatim_quote") or ""
        chunk_id = evidence.get("chunk_id") or evidence.get("evidence_chunk_id") or finding.get("evidence_chunk_id")
        chunk = chunk_by_id.get(str(chunk_id)) if chunk_id else None
        if chunk is not None and not quote:
            quote = str(chunk.get("text") or "")
        span = matching_engine.find_quote_span(
            quote, cv_text, preferred_page=evidence.get("page_number"),
            preferred_start=(chunk or {}).get("char_start", evidence.get("char_start")),
            preferred_end=(chunk or {}).get("char_end", evidence.get("char_end")))
        verified = span is not None
        finding["evidence_verified"] = verified
        if verified:
            evidence["verbatim_quote"] = cv_text[span[0]:span[1]]
        finding["evidence"] = evidence
        if not verified and finding.get("outcome") != "UNCLEAR":
            finding["outcome"] = "UNCLEAR"
            finding["requires_verification"] = True
        validated.append(finding)
    score, coverage, status, results, _needs_verification = matching_engine.calculate_assessment_scores(
        criteria_items, validated, group_weights=group_weights)
    return {"score": score, "coverage": coverage, "matching_status": status, "results": results}


def criteria_summary(results: list[dict], criteria_items: list[dict]) -> list[dict]:
    """Per-criterion outcome for HR, with a verified quote only."""
    by_id = {str(c["criterion_id"]): c for c in criteria_items}
    out = []
    for result in results:
        criterion = by_id.get(str(result.get("criterion_id")), {})
        evidence = result.get("evidence") or {}
        quote = evidence.get("verbatim_quote") if result.get("evidence_verified") else None
        out.append({
            "criterion_id": str(result.get("criterion_id")),
            "name": criterion.get("name"),
            "category": criterion.get("category"),
            "outcome": result.get("outcome"),
            "quote": (quote or "")[:QUOTE_LIMIT] or None,
        })
    return out


def rank_key(row: dict) -> tuple:
    """Same priorities as the position ranking (LTR off): status, score, coverage."""
    score = row.get("matching_score")
    return (STATUS_ORDER.get(row.get("matching_status") or "NOT_ASSESSED", 99),
            -(float(score) if score is not None else -1.0),
            -float(row.get("evidence_coverage") or 0),
            str(row.get("application_id")))
