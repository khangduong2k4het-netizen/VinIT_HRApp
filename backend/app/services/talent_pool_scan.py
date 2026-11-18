"""P3-1 phase 2: scan the Talent Pool against a new position's approved rubric.

Each eligible pool application (see talent_pool.eligible_pool) is scored in
place with the deterministic rule engine only. No CV text leaves the system:
criteria the rules cannot decide stay UNCLEAR and are counted, so HR knows to
check them by hand. The LLM fallback is left out until DEP-05 allows sending
real CV content to a provider.

Results keep scores and redacted evidence quotes, never names or contact data.
Eligibility is checked again every time results are read; a result whose
application left the pool (consent withdrawn, expired, queued for deletion,
unmarked) is deleted before anything is shown.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime
from typing import Callable, Optional

from sqlalchemy import text

from app.core.config import settings
from app.services.deterministic_matching import deterministic_matcher
from app.services.matching import matching_engine
from app.services.redaction import redact_text
from app.services.talent_pool import eligible_pool, pool_expiry

DECISIONS = ("CONTACT", "SKIP", "LATER")
QUOTE_LIMIT = 300


class ScanError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def load_extracted_text(path: str) -> str:
    if not path:
        raise FileNotFoundError("No extracted text path is recorded")
    if settings.STORAGE_BACKEND == "local":
        with open(os.path.join(settings.LOCAL_STORAGE_PATH, settings.SUPABASE_STORAGE_BUCKET_EXTRACTED, path),
                  encoding="utf-8") as f:
            return f.read()
    if settings.STORAGE_BACKEND == "supabase":
        from app.db.supabase import get_supabase_client
        client = get_supabase_client()
        if not client:
            raise RuntimeError("Supabase storage is not configured")
        return client.storage.from_(settings.SUPABASE_STORAGE_BUCKET_EXTRACTED).download(path).decode("utf-8")
    raise ValueError(f"Unknown storage backend: {settings.STORAGE_BACKEND}")


def approved_rubric(db, position_id: str) -> tuple[dict, list[dict]]:
    """Approved criteria of the latest JD of an OPEN position, as the assessment worker reads them."""
    pos = db.execute(text("SELECT status FROM app_private.positions WHERE position_id = :p"), {"p": position_id}).first()
    if pos is None:
        raise ScanError("Không tìm thấy vị trí", 404)
    if pos[0] != "OPEN":
        raise ScanError("Chỉ quét Talent Pool cho vị trí đang mở", 409)
    cv = db.execute(text("""
        SELECT criteria_version_id, mandatory_weight_total, nice_to_have_weight_total
        FROM app_private.criteria_versions WHERE position_id = :p AND status = 'APPROVED'
          AND jd_version_id = (SELECT jd_version_id FROM app_private.jd_versions WHERE position_id = :p
                               ORDER BY version_number DESC LIMIT 1)
        ORDER BY version_number DESC LIMIT 1
    """), {"p": position_id}).mappings().first()
    if not cv:
        raise ScanError("Tiêu chí của vị trí cần được HR và Hiring Manager duyệt trước khi quét", 409)
    rows = db.execute(text("""
        SELECT criterion_id, name, description, category, weight_in_group, expected_evidence_keywords, requirement_spec
        FROM app_private.criteria_items WHERE criteria_version_id = :c ORDER BY display_order
    """), {"c": str(cv["criteria_version_id"])}).mappings().all()
    items = []
    for row in rows:
        item = {**dict(row), "criterion_id": str(row["criterion_id"]), "weight_in_group": float(row["weight_in_group"])}
        if isinstance(item.get("requirement_spec"), str):
            try:
                item["requirement_spec"] = json.loads(item["requirement_spec"])
            except (TypeError, ValueError):
                item["requirement_spec"] = None
        items.append(item)
    if not items:
        raise ScanError("Bộ tiêu chí đã duyệt không có tiêu chí nào", 409)
    return dict(cv), items


def _cv_material(db, application_id: str) -> Optional[dict]:
    row = db.execute(text("""
        SELECT pr.extracted_text_storage_path,
               (SELECT pv.profile_version_id FROM app_private.profile_versions pv
                WHERE pv.application_id = :a AND pv.status = 'COMPLETED' ORDER BY pv.version_number DESC LIMIT 1) AS profile_version_id
        FROM app_private.application_documents d
        JOIN app_private.document_processing_runs pr ON pr.document_id = d.document_id AND pr.status = 'COMPLETED'
        WHERE d.application_id = :a AND d.document_type = 'CV' AND d.file_processing_status = 'COMPLETED'
          AND pr.extracted_text_storage_path IS NOT NULL
        ORDER BY d.created_at DESC, pr.created_at DESC LIMIT 1
    """), {"a": application_id}).mappings().first()
    return dict(row) if row else None


def _candidate_profile(db, application_id: str, profile_version_id) -> dict:
    facts = db.execute(text("""SELECT fact_type, fact_value FROM app_private.profile_facts
        WHERE profile_version_id = :v"""), {"v": str(profile_version_id)}).mappings().all() if profile_version_id else []
    return {
        "candidate_identifier": application_id,
        "total_years_experience": 0,
        "education": [f["fact_value"] for f in facts if f["fact_type"] == "EDUCATION"],
        "work_history": [f["fact_value"] for f in facts if f["fact_type"] == "WORK_EXPERIENCE"],
        "skills": [(f["fact_value"] or {}).get("name") for f in facts if f["fact_type"] == "SKILL"],
        "certifications": [f["fact_value"] for f in facts if f["fact_type"] == "CERTIFICATION"],
        "languages": [f["fact_value"] for f in facts if f["fact_type"] == "LANGUAGE"],
        "projects": [f["fact_value"] for f in facts if f["fact_type"] == "PROJECT"],
    }


def score_cv(cv_text: str, criteria: list[dict], candidate_profile: dict, group_weights: dict) -> dict:
    """Rules-only scoring of one CV. Quotes are verified against the (redacted) text."""
    result = deterministic_matcher.evaluate_criteria(cv_text, criteria, candidate_profile)
    if result.get("candidate_years_experience"):
        candidate_profile["total_years_experience"] = result["candidate_years_experience"]
    validated = []
    for finding in matching_engine.canonicalize_findings(criteria, list(result.get("findings", []))):
        evidence = finding.get("evidence") or {}
        quote = evidence.get("verbatim_quote") or ""
        span = matching_engine.find_quote_span(quote, cv_text) if quote else None
        if span is not None:
            evidence["verbatim_quote"] = cv_text[span[0]:span[1]]
        elif finding.get("outcome") != "UNCLEAR":
            finding["outcome"] = "UNCLEAR"
            finding["requires_verification"] = True
        finding["evidence"] = evidence
        validated.append(finding)
    score, coverage, status, results, _ = matching_engine.calculate_assessment_scores(
        criteria, validated, group_weights=group_weights)
    names = {c["criterion_id"]: (c.get("name"), c.get("category")) for c in criteria}
    criterion_results = [{
        "criterion_id": r["criterion_id"],
        "name": names.get(r["criterion_id"], (None, None))[0],
        "category": names.get(r["criterion_id"], (None, None))[1],
        "outcome": r["outcome"],
        "quote": ((r.get("evidence") or {}).get("verbatim_quote") or "")[:QUOTE_LIMIT] or None,
    } for r in results]
    return {"score": score, "coverage": coverage, "status": status, "criterion_results": criterion_results,
            "unresolved_count": sum(1 for r in results if r["outcome"] == "UNCLEAR")}


def run_scan(db, *, position_id: str, user_id: str,
             read_text: Callable[[str], str] = load_extracted_text) -> dict:
    """Score every eligible pool application for the position. Caller commits."""
    cv, criteria = approved_rubric(db, position_id)
    group_weights = {"MUST_HAVE": float(cv["mandatory_weight_total"]) / 100,
                     "NICE_TO_HAVE": float(cv["nice_to_have_weight_total"]) / 100}
    pool = [row for row in eligible_pool(db) if str(row["position_id"]) != position_id]
    skipped: Counter = Counter()
    if len(pool) > settings.TALENT_POOL_SCAN_MAX:
        skipped["OVER_LIMIT"] = len(pool) - settings.TALENT_POOL_SCAN_MAX
        pool = sorted(pool, key=lambda r: r["consented_at"], reverse=True)[:settings.TALENT_POOL_SCAN_MAX]
    scan_id = str(db.execute(text("""INSERT INTO app_private.talent_pool_scans(position_id, criteria_version_id, requested_by, eligible_count)
        VALUES (:p, :c, :u, :n) RETURNING scan_id"""),
        {"p": position_id, "c": str(cv["criteria_version_id"]), "u": user_id, "n": len(pool)}).scalar_one())
    scored = 0
    for row in pool:
        application_id = str(row["application_id"])
        material = _cv_material(db, application_id)
        if not material:
            skipped["NO_EXTRACTED_TEXT"] += 1
            continue
        try:
            cv_text = redact_text(read_text(material["extracted_text_storage_path"]), detect_first_line_name=True)
        except Exception:
            skipped["TEXT_UNAVAILABLE"] += 1
            continue
        result = score_cv(cv_text, criteria, _candidate_profile(db, application_id, material["profile_version_id"]),
                          group_weights)
        db.execute(text("""INSERT INTO app_private.talent_pool_scan_results(scan_id, application_id, matching_score,
                evidence_coverage, matching_status, unresolved_count, criterion_results)
            VALUES (:s, :a, :score, :cov, :st, :u, CAST(:cr AS jsonb))"""),
                   {"s": scan_id, "a": application_id, "score": result["score"], "cov": result["coverage"],
                    "st": result["status"], "u": result["unresolved_count"],
                    "cr": json.dumps(result["criterion_results"], ensure_ascii=False)})
        scored += 1
    db.execute(text("UPDATE app_private.talent_pool_scans SET scored_count = :n, skipped_counts = CAST(:k AS jsonb) WHERE scan_id = :s"),
               {"n": scored, "k": json.dumps(dict(skipped)), "s": scan_id})
    db.execute(text("""INSERT INTO app_private.audit_events(actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
        VALUES (:u, 'SCAN_TALENT_POOL', 'TALENT_POOL_SCAN', :s, :p, 'SUCCESS', CAST(:m AS jsonb))"""),
               {"u": user_id, "s": scan_id, "p": position_id,
                "m": json.dumps({"eligible_count": len(pool), "scored_count": scored, "skipped": dict(skipped),
                                 "criteria_version_id": str(cv["criteria_version_id"]), "method": "RULES_ONLY"})})
    return {"scan_id": scan_id, "eligible_count": len(pool), "scored_count": scored, "skipped": dict(skipped)}


def scan_header(db, scan_id: str) -> Optional[dict]:
    row = db.execute(text("""SELECT s.scan_id, s.position_id, s.criteria_version_id, s.requested_by, s.created_at,
            s.eligible_count, s.scored_count, s.skipped_counts, s.method
        FROM app_private.talent_pool_scans s WHERE s.scan_id = :s"""), {"s": scan_id}).mappings().first()
    return dict(row) if row else None


def scan_results(db, scan_id: str, now: Optional[datetime] = None) -> list[dict]:
    """Ranked results still eligible right now. Results that left the pool are deleted first."""
    still = {str(r["application_id"]): r for r in eligible_pool(db, now)}
    db.execute(text("""DELETE FROM app_private.talent_pool_scan_results
        WHERE scan_id = :s AND NOT (application_id = ANY(CAST(:ids AS uuid[]))) """),
               {"s": scan_id, "ids": list(still)})
    rows = db.execute(text("""
        SELECT r.application_id, r.matching_score, r.evidence_coverage, r.matching_status, r.unresolved_count,
               r.criterion_results, r.hr_decision, r.decided_at, a.position_id AS source_position_id,
               p.title AS source_position_title, p.position_code AS source_position_code, m.reason_code AS mark_reason
        FROM app_private.talent_pool_scan_results r
        JOIN app_private.applications a ON a.application_id = r.application_id
        JOIN app_private.positions p ON p.position_id = a.position_id
        LEFT JOIN app_private.talent_pool_marks m ON m.application_id = r.application_id AND m.removed_at IS NULL
        WHERE r.scan_id = :s
        ORDER BY (r.matching_status = 'POSSIBLE_MISMATCH'), r.matching_score DESC NULLS LAST,
                 r.evidence_coverage DESC, r.application_id
    """), {"s": scan_id}).mappings().all()
    out = []
    for rank, r in enumerate(rows, start=1):
        item = dict(r)
        consented_at = still[str(r["application_id"])]["consented_at"]
        item.update({
            "rank": rank,
            "application_id": str(r["application_id"]),
            "source_position_id": str(r["source_position_id"]),
            "matching_score": float(r["matching_score"]) if r["matching_score"] is not None else None,
            "evidence_coverage": float(r["evidence_coverage"]),
            "pool_expires_on": pool_expiry(consented_at).date().isoformat(),
        })
        out.append(item)
    return out


def record_decision(db, *, scan_id: str, application_id: str, decision: str, user_id: str) -> bool:
    if decision not in DECISIONS:
        raise ScanError("Quyết định không hợp lệ", 400)
    still = {str(r["application_id"]) for r in eligible_pool(db)}
    if application_id not in still:
        db.execute(text("DELETE FROM app_private.talent_pool_scan_results WHERE scan_id = :s AND application_id = :a"),
                   {"s": scan_id, "a": application_id})
        raise ScanError("Hồ sơ không còn trong Talent Pool", 409)
    done = db.execute(text("""UPDATE app_private.talent_pool_scan_results
        SET hr_decision = :d, decided_by = :u, decided_at = NOW() WHERE scan_id = :s AND application_id = :a"""),
                      {"d": decision, "u": user_id, "s": scan_id, "a": application_id}).rowcount
    return bool(done)

