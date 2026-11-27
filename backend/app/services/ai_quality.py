"""P3-2 — AI quality trends (read-only; never changes assessments or decisions).

Metric dictionary. Everything is limited to the caller's positions and to the
date range [date_from, date_to], both inclusive, grouped by week or month.

* overrides — screening decisions (into SHORTLIST or REJECTED_SCREENING) made
  while an AI conclusion existed, and how many of them contradicted it. This
  measures how often HR *disagrees* with the AI, not whether the AI was right.
  Decisions recorded before tracking existed have no AI snapshot and are
  excluded rather than guessed.
* qa_random_sample — completed QA inspections whose reasons include
  RANDOM_SAMPLE, and how many found issues. Random selection is the only
  group that gives an unbiased error-rate estimate, so it is the headline
  QA figure.
* qa_risk_group — completed inspections that were selected because of a risk
  rule (single mandatory miss, borderline evidence coverage). These are chosen
  *because* they are suspicious, so their error rate is expected to be higher
  and must never be pooled with the random sample. A case can belong to both
  groups (a risk case that was also drawn at random).
* assessments — completed assessment runs: average evidence coverage, share
  that need HR verification and share of UNCLEAR criterion results.

Rates are withheld (``rate`` is null, ``insufficient`` true) when the
denominator is below MIN_SAMPLE_SIZE; counts are always returned. Nothing is
broken down by individual recruiter.
"""
from __future__ import annotations

import csv
import hashlib
import io
import math
from datetime import date, timedelta
from typing import Any, Optional

from sqlalchemy import text

from app.services.analytics import has_global_scope
from app.services.redaction import redact_text
from app.services.retention import application_opaque_id

MIN_SAMPLE_SIZE = 20
GRAINS = ("week", "month")
RISK_REASONS = ("SINGLE_MANDATORY_MISS", "BORDERLINE_COVERAGE")
BREAKDOWN_DIMENSIONS = (
    "job_family", "department", "override_reason", "flag_category",
    "matching_policy_version", "file_type", "criterion_type",
)
MARKER_TITLE_MAX = 200
MARKER_NOTE_MAX = 1000
GOLDEN_SET_MAX_ROWS = 2000
QUOTE_LIMIT = 300

_SCOPE = """
    scope AS (
        SELECT p.position_id, p.job_family_id, p.department_id FROM app_private.positions p
        WHERE (:global_scope OR EXISTS (
                SELECT 1 FROM app_private.position_assignments pa
                WHERE pa.position_id = p.position_id AND pa.user_id = :user_id AND pa.revoked_at IS NULL
                  AND pa.position_role IN ('HR_RECRUITER', 'HR_LEAD')))
          AND (CAST(:position_id AS uuid) IS NULL OR p.position_id = CAST(:position_id AS uuid))
          AND (CAST(:department_id AS uuid) IS NULL OR p.department_id = CAST(:department_id AS uuid))
          AND (CAST(:job_family_id AS uuid) IS NULL OR p.job_family_id = CAST(:job_family_id AS uuid))
    )
"""


class QualityError(ValueError):
    pass


def wilson_interval(successes: int, total: int, z: float = 1.96) -> Optional[tuple[float, float]]:
    """95% Wilson score interval for a proportion; None when there is no data."""
    if total <= 0:
        return None
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def proportion(count: int, total: int, min_sample: Optional[int] = None) -> dict[str, Any]:
    count, total = int(count or 0), int(total or 0)
    min_sample = MIN_SAMPLE_SIZE if min_sample is None else min_sample
    enough = total >= min_sample
    interval = wilson_interval(count, total) if enough else None
    return {
        "count": count,
        "total": total,
        "rate": round(count / total, 4) if enough else None,
        "ci_low": round(interval[0], 4) if interval else None,
        "ci_high": round(interval[1], 4) if interval else None,
        "insufficient": not enough,
    }


def resolve_period(date_from: Optional[str], date_to: Optional[str], grain: str,
                   today: Optional[date] = None) -> tuple[date, date, str]:
    if grain not in GRAINS:
        raise QualityError("Hạt thời gian phải là week hoặc month")
    today = today or date.today()
    try:
        end = date.fromisoformat(date_to) if date_to else today
        start = date.fromisoformat(date_from) if date_from else end - timedelta(days=179)
    except ValueError:
        raise QualityError("Ngày phải theo định dạng YYYY-MM-DD") from None
    if start > end:
        raise QualityError("Ngày bắt đầu phải trước ngày kết thúc")
    if (end - start).days > 731:
        raise QualityError("Khoảng thời gian tối đa 731 ngày")
    return start, end, grain


def _params(db, user_id: str, start: date, end: date, position_id, department_id, job_family_id) -> dict:
    return {"user_id": user_id, "global_scope": has_global_scope(db, user_id), "position_id": position_id,
            "department_id": department_id, "job_family_id": job_family_id,
            "start": start, "end_excl": end + timedelta(days=1), "risk": list(RISK_REASONS)}


def _rows(db, sql: str, params: dict) -> list[dict]:
    return [dict(r) for r in db.execute(text("WITH " + _SCOPE + " " + sql), params).mappings().all()]


def _num(value) -> Optional[float]:
    return round(float(value), 4) if value is not None else None


def quality_trends(db, *, user_id: str, start: date, end: date, grain: str = "week",
                   position_id: Optional[str] = None, department_id: Optional[str] = None,
                   job_family_id: Optional[str] = None) -> dict[str, Any]:
    params = _params(db, user_id, start, end, position_id, department_id, job_family_id)
    params["grain"] = grain

    override_rows = _rows(db, """
        SELECT date_trunc(:grain, e.changed_at)::date AS period,
               COUNT(*) AS decisions_with_ai,
               COUNT(*) FILTER (WHERE e.override_direction IS NOT NULL) AS overrides,
               COUNT(*) FILTER (WHERE e.override_direction = 'ADVANCED_DESPITE_AI') AS advanced_despite_ai,
               COUNT(*) FILTER (WHERE e.override_direction = 'REJECTED_DESPITE_AI') AS rejected_despite_ai
        FROM app_private.application_status_events e
        JOIN app_private.applications a ON a.application_id = e.application_id
        WHERE a.position_id IN (SELECT position_id FROM scope)
          AND e.changed_at >= :start AND e.changed_at < :end_excl
          AND e.new_status IN ('SHORTLIST', 'REJECTED_SCREENING')
          AND e.ai_matching_status IN ('NEEDS_HR_VERIFICATION', 'POSSIBLE_MISMATCH', 'MEETS_MANDATORY')
        GROUP BY 1
    """, params)

    qa_rows = _rows(db, """
        SELECT date_trunc(:grain, qi.completed_at)::date AS period,
               COUNT(*) AS completed,
               COUNT(*) FILTER (WHERE qi.verdict = 'ISSUES_FOUND') AS issues,
               COUNT(*) FILTER (WHERE qi.reasons ? 'RANDOM_SAMPLE') AS random_completed,
               COUNT(*) FILTER (WHERE qi.reasons ? 'RANDOM_SAMPLE' AND qi.verdict = 'ISSUES_FOUND') AS random_issues,
               COUNT(*) FILTER (WHERE qi.reasons ?| CAST(:risk AS text[])) AS risk_completed,
               COUNT(*) FILTER (WHERE qi.reasons ?| CAST(:risk AS text[]) AND qi.verdict = 'ISSUES_FOUND') AS risk_issues
        FROM app_private.quality_inspections qi
        WHERE qi.position_id IN (SELECT position_id FROM scope) AND qi.status = 'COMPLETED'
          AND qi.completed_at >= :start AND qi.completed_at < :end_excl
        GROUP BY 1
    """, params)

    flag_rows = _rows(db, """
        SELECT date_trunc(:grain, qi.completed_at)::date AS period, f.category, COUNT(*) AS count
        FROM app_private.quality_flags f
        JOIN app_private.quality_inspections qi ON qi.inspection_id = f.inspection_id
        WHERE qi.position_id IN (SELECT position_id FROM scope) AND qi.status = 'COMPLETED'
          AND qi.completed_at >= :start AND qi.completed_at < :end_excl
        GROUP BY 1, 2
    """, params)

    assessment_rows = _rows(db, """
        SELECT date_trunc(:grain, ar.completed_at)::date AS period,
               COUNT(*) AS completed,
               AVG(ar.evidence_coverage) AS average_evidence_coverage,
               COUNT(*) FILTER (WHERE ar.matching_status = 'NEEDS_HR_VERIFICATION') AS needs_verification
        FROM app_private.assessment_runs ar
        WHERE ar.position_id IN (SELECT position_id FROM scope) AND ar.status = 'COMPLETED'
          AND ar.completed_at >= :start AND ar.completed_at < :end_excl
        GROUP BY 1
    """, params)

    criterion_rows = _rows(db, """
        SELECT date_trunc(:grain, ar.completed_at)::date AS period,
               COUNT(*) AS results,
               COUNT(*) FILTER (WHERE r.outcome = 'UNCLEAR') AS unclear
        FROM app_private.criterion_assessment_results r
        JOIN app_private.assessment_runs ar ON ar.assessment_id = r.assessment_id
        WHERE ar.position_id IN (SELECT position_id FROM scope) AND ar.status = 'COMPLETED'
          AND ar.completed_at >= :start AND ar.completed_at < :end_excl
        GROUP BY 1
    """, params)

    backlog = _rows(db, """
        SELECT COUNT(*) AS open_cases, MIN(qi.created_at) AS oldest_created_at
        FROM app_private.quality_inspections qi
        WHERE qi.position_id IN (SELECT position_id FROM scope) AND qi.status IN ('PENDING', 'IN_REVIEW')
    """, params)[0]

    by = lambda rows: {r["period"]: r for r in rows}  # noqa: E731
    overrides, qa, assess, crit = by(override_rows), by(qa_rows), by(assessment_rows), by(criterion_rows)
    flags: dict[date, dict[str, int]] = {}
    for row in flag_rows:
        flags.setdefault(row["period"], {})[row["category"]] = int(row["count"])

    periods = sorted(set(overrides) | set(qa) | set(assess) | set(crit))
    series = []
    for period in periods:
        o, q, a, c = overrides.get(period), qa.get(period), assess.get(period), crit.get(period)
        series.append({
            "period": period.isoformat(),
            "overrides": {
                **proportion(o["overrides"] if o else 0, o["decisions_with_ai"] if o else 0),
                "advanced_despite_ai": int(o["advanced_despite_ai"]) if o else 0,
                "rejected_despite_ai": int(o["rejected_despite_ai"]) if o else 0,
            },
            "qa_random_sample": proportion(q["random_issues"] if q else 0, q["random_completed"] if q else 0),
            "qa_risk_group": proportion(q["risk_issues"] if q else 0, q["risk_completed"] if q else 0),
            "qa_completed": int(q["completed"]) if q else 0,
            "qa_flags_by_category": flags.get(period, {}),
            "assessments": {
                "completed": int(a["completed"]) if a else 0,
                "average_evidence_coverage": _num(a["average_evidence_coverage"]) if a else None,
                "needs_verification": proportion(a["needs_verification"] if a else 0, a["completed"] if a else 0),
                "unclear_criteria": proportion(c["unclear"] if c else 0, c["results"] if c else 0),
            },
        })
    return {
        "range": {"date_from": start.isoformat(), "date_to": end.isoformat(), "grain": grain},
        "min_sample": MIN_SAMPLE_SIZE,
        "series": series,
        "qa_backlog": {"open_cases": int(backlog["open_cases"]),
                       "oldest_created_at": backlog["oldest_created_at"]},
    }


def quality_breakdown(db, *, user_id: str, start: date, end: date, dimension: str,
                      position_id: Optional[str] = None, department_id: Optional[str] = None,
                      job_family_id: Optional[str] = None) -> dict[str, Any]:
    if dimension not in BREAKDOWN_DIMENSIONS:
        raise QualityError("Chiều phân rã không hợp lệ")
    params = _params(db, user_id, start, end, position_id, department_id, job_family_id)
    rows: list[dict[str, Any]]

    if dimension in ("job_family", "department"):
        key_sql, name_join = (
            ("s.job_family_id", "LEFT JOIN app_private.job_families d ON d.job_family_id = s.job_family_id")
            if dimension == "job_family" else
            ("s.department_id", "LEFT JOIN app_private.departments d ON d.department_id = s.department_id"))
        label_sql = "d.code" if dimension == "job_family" else "d.name"
        override = {str(r["key"]): r for r in _rows(db, f"""
            SELECT {key_sql}::text AS key, {label_sql} AS label,
                   COUNT(*) AS decisions_with_ai,
                   COUNT(*) FILTER (WHERE e.override_direction IS NOT NULL) AS overrides
            FROM app_private.application_status_events e
            JOIN app_private.applications a ON a.application_id = e.application_id
            JOIN scope s ON s.position_id = a.position_id {name_join}
            WHERE e.changed_at >= :start AND e.changed_at < :end_excl
              AND e.new_status IN ('SHORTLIST', 'REJECTED_SCREENING')
              AND e.ai_matching_status IN ('NEEDS_HR_VERIFICATION', 'POSSIBLE_MISMATCH', 'MEETS_MANDATORY')
            GROUP BY 1, 2""", params)}
        qa = {str(r["key"]): r for r in _rows(db, f"""
            SELECT {key_sql}::text AS key, {label_sql} AS label,
                   COUNT(*) FILTER (WHERE qi.reasons ? 'RANDOM_SAMPLE') AS random_completed,
                   COUNT(*) FILTER (WHERE qi.reasons ? 'RANDOM_SAMPLE' AND qi.verdict = 'ISSUES_FOUND') AS random_issues
            FROM app_private.quality_inspections qi
            JOIN scope s ON s.position_id = qi.position_id {name_join}
            WHERE qi.status = 'COMPLETED' AND qi.completed_at >= :start AND qi.completed_at < :end_excl
            GROUP BY 1, 2""", params)}
        rows = []
        for key in sorted(set(override) | set(qa), key=lambda k: str((override.get(k) or qa.get(k))["label"] or "")):
            o, q = override.get(key), qa.get(key)
            rows.append({"key": key if key != "None" else None, "label": (o or q)["label"],
                         "overrides": proportion(o["overrides"] if o else 0, o["decisions_with_ai"] if o else 0),
                         "qa_random_sample": proportion(q["random_issues"] if q else 0, q["random_completed"] if q else 0)})

    elif dimension == "override_reason":
        data = _rows(db, """
            SELECT e.override_reason_code AS key, COUNT(*) AS count
            FROM app_private.application_status_events e
            JOIN app_private.applications a ON a.application_id = e.application_id
            WHERE a.position_id IN (SELECT position_id FROM scope)
              AND e.changed_at >= :start AND e.changed_at < :end_excl AND e.override_direction IS NOT NULL
            GROUP BY 1 ORDER BY count DESC, key""", params)
        total = sum(int(r["count"]) for r in data)
        rows = [{"key": r["key"], "count": int(r["count"]), "share": round(int(r["count"]) / total, 4) if total >= MIN_SAMPLE_SIZE else None}
                for r in data]

    elif dimension == "flag_category":
        data = _rows(db, """
            SELECT f.category AS key, COUNT(*) AS count
            FROM app_private.quality_flags f
            JOIN app_private.quality_inspections qi ON qi.inspection_id = f.inspection_id
            WHERE qi.position_id IN (SELECT position_id FROM scope) AND qi.status = 'COMPLETED'
              AND qi.completed_at >= :start AND qi.completed_at < :end_excl
            GROUP BY 1 ORDER BY count DESC, key""", params)
        total = sum(int(r["count"]) for r in data)
        rows = [{"key": r["key"], "count": int(r["count"]), "share": round(int(r["count"]) / total, 4) if total >= MIN_SAMPLE_SIZE else None}
                for r in data]

    elif dimension == "file_type":
        data = _rows(db, """
            SELECT CASE
                     WHEN d.mime_type = 'application/pdf' THEN 'PDF'
                     WHEN d.mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' THEN 'DOCX'
                     WHEN d.mime_type LIKE 'image/%' THEN 'IMAGE'
                     ELSE 'OTHER'
                   END AS key,
                   COUNT(*) AS uploaded,
                   COUNT(*) FILTER (WHERE d.file_processing_status = 'NEEDS_HR_REVIEW') AS needs_review
            FROM app_private.application_documents d
            JOIN app_private.applications a ON a.application_id = d.application_id
            WHERE a.position_id IN (SELECT position_id FROM scope)
              AND d.document_type = 'CV'
              AND d.created_at >= :start AND d.created_at < :end_excl
            GROUP BY 1 ORDER BY uploaded DESC, key""", params)
        rows = [{"key": r["key"], "completed": int(r["uploaded"]),
                 "needs_verification": proportion(r["needs_review"], r["uploaded"])} for r in data]

    elif dimension == "criterion_type":
        data = _rows(db, """
            SELECT COALESCE(ci.category, 'UNKNOWN') AS key,
                   COUNT(*) AS results,
                   COUNT(*) FILTER (WHERE r.outcome = 'UNCLEAR') AS unclear
            FROM app_private.criterion_assessment_results r
            JOIN app_private.assessment_runs ar ON ar.assessment_id = r.assessment_id
            LEFT JOIN app_private.criteria_items ci ON ci.criterion_id = r.criterion_id
            WHERE ar.position_id IN (SELECT position_id FROM scope) AND ar.status = 'COMPLETED'
              AND ar.completed_at >= :start AND ar.completed_at < :end_excl
            GROUP BY 1 ORDER BY 1""", params)
        rows = [{"key": r["key"], "completed": int(r["results"]),
                 "needs_verification": proportion(r["unclear"], r["results"])} for r in data]

    else:  # matching_policy_version
        # Pre-aggregate QA per assessment_id so multiple inspections on one assessment
        # can never double-count completed assessments or skew average coverage.
        data = _rows(db, """
            SELECT COALESCE(ar.matching_policy_version, 'unknown') AS key,
                   COUNT(*) AS completed,
                   AVG(ar.evidence_coverage) AS average_evidence_coverage,
                   COUNT(*) FILTER (WHERE ar.matching_status = 'NEEDS_HR_VERIFICATION') AS needs_verification,
                   COALESCE(SUM(qa.random_completed), 0) AS random_completed,
                   COALESCE(SUM(qa.random_issues), 0) AS random_issues
            FROM app_private.assessment_runs ar
            LEFT JOIN (
                SELECT qi.assessment_id,
                       COUNT(*) FILTER (WHERE qi.reasons ? 'RANDOM_SAMPLE') AS random_completed,
                       COUNT(*) FILTER (WHERE qi.reasons ? 'RANDOM_SAMPLE' AND qi.verdict = 'ISSUES_FOUND') AS random_issues
                FROM app_private.quality_inspections qi
                WHERE qi.status = 'COMPLETED'
                GROUP BY qi.assessment_id
            ) qa ON qa.assessment_id = ar.assessment_id
            WHERE ar.position_id IN (SELECT position_id FROM scope) AND ar.status = 'COMPLETED'
              AND ar.completed_at >= :start AND ar.completed_at < :end_excl
            GROUP BY 1 ORDER BY 1""", params)
        rows = [{"key": r["key"], "completed": int(r["completed"]),
                 "average_evidence_coverage": _num(r["average_evidence_coverage"]),
                 "needs_verification": proportion(r["needs_verification"], r["completed"]),
                 "qa_random_sample": proportion(r["random_issues"], r["random_completed"])} for r in data]

    return {"range": {"date_from": start.isoformat(), "date_to": end.isoformat()},
            "dimension": dimension, "min_sample": MIN_SAMPLE_SIZE, "rows": rows}


def version_markers(db, *, user_id: str, start: date, end: date) -> list[dict[str, Any]]:
    """Change points: first completed assessment using each rules/policy/prompt version,
    plus markers written by an Admin (for changes the data cannot reveal, e.g. a dictionary update)."""
    params = _params(db, user_id, start, end, None, None, None)
    first_seen = _rows(db, """
        SELECT kind, value, MIN(seen_at) AS seen_at FROM (
            SELECT 'MATCHING_POLICY' AS kind, ar.matching_policy_version AS value, ar.completed_at AS seen_at
              FROM app_private.assessment_runs ar WHERE ar.status = 'COMPLETED' AND ar.matching_policy_version IS NOT NULL
                AND ar.position_id IN (SELECT position_id FROM scope)
            UNION ALL
            SELECT 'PROMPT', ar.prompt_version, ar.completed_at
              FROM app_private.assessment_runs ar WHERE ar.status = 'COMPLETED' AND ar.prompt_version IS NOT NULL
                AND ar.position_id IN (SELECT position_id FROM scope)
            UNION ALL
            SELECT 'RULES', r.rule_version, ar.completed_at
              FROM app_private.criterion_assessment_results r
              JOIN app_private.assessment_runs ar ON ar.assessment_id = r.assessment_id
              WHERE ar.status = 'COMPLETED' AND r.rule_version IS NOT NULL
                AND ar.position_id IN (SELECT position_id FROM scope)
        ) v GROUP BY kind, value
    """, params)
    markers = [{"date": r["seen_at"].date().isoformat(), "kind": "VERSION", "source": r["kind"],
                "title": f"{r['kind']} {r['value']}", "note": None}
               for r in first_seen if start <= r["seen_at"].date() <= end]
    manual = db.execute(text("""
        SELECT marker_id::text AS marker_id, occurred_on, title, note FROM app_private.quality_markers
        WHERE occurred_on BETWEEN :start AND :end"""), {"start": start, "end": end}).mappings().all()
    markers += [{"date": r["occurred_on"].isoformat(), "kind": "MANUAL", "source": "ADMIN",
                 "title": r["title"], "note": r["note"], "marker_id": r["marker_id"]} for r in manual]
    return sorted(markers, key=lambda m: (m["date"], m["kind"], m["title"]))


def _assessment_opaque_id(assessment_id: Any) -> Optional[str]:
    if not assessment_id:
        return None
    return hashlib.sha256(f"vinuni-hra:assessment:{str(assessment_id).lower()}".encode("utf-8")).hexdigest()


def _safe_quote(quote: Optional[str]) -> Optional[str]:
    if not quote:
        return None
    cleaned = redact_text(str(quote), detect_first_line_name=False).strip()
    return cleaned[:QUOTE_LIMIT] or None


def golden_set_rows(db, *, user_id: str, start: date, end: date,
                    position_id: Optional[str] = None, department_id: Optional[str] = None,
                    job_family_id: Optional[str] = None) -> list[dict[str, Any]]:
    """P3-2 §5: anonymized label set built from QA inspections and clear HR overrides.

    Never includes candidate names, emails, phones, filenames or full CV text.
    """
    params = _params(db, user_id, start, end, position_id, department_id, job_family_id)
    params["limit"] = GOLDEN_SET_MAX_ROWS

    qa_rows = _rows(db, """
        SELECT qi.inspection_id, qi.assessment_id, ar.application_id, p.position_code,
               jf.code AS job_family_code, ar.matching_policy_version, ar.matching_status,
               ar.evidence_coverage, qi.verdict, qi.reasons, qi.completed_at,
               COALESCE(
                   (SELECT json_agg(f.category ORDER BY f.category)
                    FROM app_private.quality_flags f WHERE f.inspection_id = qi.inspection_id),
                   '[]'::json
               ) AS flags,
               COALESCE(
                   (SELECT json_agg(e.verbatim_quote ORDER BY e.created_at)
                    FROM app_private.evidence_items e
                    JOIN app_private.criterion_assessment_results r ON r.result_id = e.criterion_result_id
                    WHERE r.assessment_id = ar.assessment_id),
                   '[]'::json
               ) AS quotes
        FROM app_private.quality_inspections qi
        JOIN app_private.assessment_runs ar ON ar.assessment_id = qi.assessment_id
        JOIN app_private.positions p ON p.position_id = qi.position_id
        LEFT JOIN app_private.job_families jf ON jf.job_family_id = p.job_family_id
        WHERE qi.position_id IN (SELECT position_id FROM scope)
          AND qi.status = 'COMPLETED'
          AND qi.completed_at >= :start AND qi.completed_at < :end_excl
          AND (qi.verdict = 'ISSUES_FOUND' OR (qi.verdict = 'CORRECT' AND qi.reasons ? 'RANDOM_SAMPLE'))
        ORDER BY qi.completed_at DESC
        LIMIT :limit
    """, params)

    override_rows = _rows(db, """
        SELECT e.application_id, p.position_code, jf.code AS job_family_code,
               e.ai_matching_status, e.new_status, e.override_direction, e.override_reason_code, e.changed_at
        FROM app_private.application_status_events e
        JOIN app_private.applications a ON a.application_id = e.application_id
        JOIN app_private.positions p ON p.position_id = a.position_id
        LEFT JOIN app_private.job_families jf ON jf.job_family_id = p.job_family_id
        WHERE a.position_id IN (SELECT position_id FROM scope)
          AND e.changed_at >= :start AND e.changed_at < :end_excl
          AND e.override_direction IS NOT NULL
          AND e.override_reason_code IS NOT NULL
          AND e.override_reason_code <> 'OTHER'
        ORDER BY e.changed_at DESC
        LIMIT :limit
    """, params)

    items: list[dict[str, Any]] = []
    for r in qa_rows:
        reasons = list(r["reasons"] or [])
        is_random = "RANDOM_SAMPLE" in reasons
        raw_quotes = list(r["quotes"] or [])
        quotes = [q for q in (_safe_quote(item) for item in raw_quotes[:5]) if q]
        items.append({
            "source": "QA_ISSUES_FOUND" if r["verdict"] == "ISSUES_FOUND" else "QA_RANDOM_CORRECT",
            "confidence": "HIGH",
            "label_note": "QA_VERIFIED",
            "recorded_at": r["completed_at"].isoformat() if r["completed_at"] else None,
            "application_opaque_id": application_opaque_id(str(r["application_id"])),
            "assessment_opaque_id": _assessment_opaque_id(r["assessment_id"]),
            "position_code": r["position_code"],
            "job_family_code": r["job_family_code"],
            "matching_policy_version": r["matching_policy_version"],
            "ai_matching_status": r["matching_status"],
            "evidence_coverage": _num(r["evidence_coverage"]),
            "sample_group": "RANDOM_SAMPLE" if is_random else "RISK_GROUP",
            "qa_verdict": r["verdict"],
            "qa_flags": list(r["flags"] or []),
            "override_direction": None,
            "override_reason_code": None,
            "hr_status": None,
            "redacted_evidence_quotes": quotes,
        })

    for r in override_rows:
        items.append({
            "source": "HR_OVERRIDE",
            "confidence": "MEDIUM",
            "label_note": "HR_OPINION",
            "recorded_at": r["changed_at"].isoformat() if r["changed_at"] else None,
            "application_opaque_id": application_opaque_id(str(r["application_id"])),
            "assessment_opaque_id": None,
            "position_code": r["position_code"],
            "job_family_code": r["job_family_code"],
            "matching_policy_version": None,
            "ai_matching_status": r["ai_matching_status"],
            "evidence_coverage": None,
            "sample_group": None,
            "qa_verdict": None,
            "qa_flags": [],
            "override_direction": r["override_direction"],
            "override_reason_code": r["override_reason_code"],
            "hr_status": r["new_status"],
            "redacted_evidence_quotes": [],
        })
    return items[:GOLDEN_SET_MAX_ROWS]


def _csv_cell(value: Any) -> str:
    text_val = "" if value is None else str(value)
    if text_val and text_val[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text_val
    return text_val


def golden_set_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "source", "confidence", "label_note", "recorded_at", "application_opaque_id", "assessment_opaque_id",
        "position_code", "job_family_code", "matching_policy_version", "ai_matching_status", "evidence_coverage",
        "sample_group", "qa_verdict", "qa_flags", "override_direction", "override_reason_code", "hr_status",
        "redacted_evidence_quotes",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        flat = {
            **row,
            "qa_flags": "; ".join(row.get("qa_flags") or []),
            "redacted_evidence_quotes": " | ".join(row.get("redacted_evidence_quotes") or []),
        }
        writer.writerow({k: _csv_cell(flat.get(k)) for k in fields})
    return buf.getvalue()


def evidence_calibration(
    db,
    *,
    user_id: str,
    start: date,
    end: date,
    position_id: Optional[str] = None,
    department_id: Optional[str] = None,
    job_family_id: Optional[str] = None,
) -> dict[str, Any]:
    """Closed-loop aggregate calibration from HR evidence sign-offs.

    Uses the latest sign-off per criterion result within the selected period so
    re-reviews never double-count. Aggregated only — never per recruiter.
    """
    params = _params(db, user_id, start, end, position_id, department_id, job_family_id)

    summary_rows = _rows(db, """,
        latest AS (
            SELECT DISTINCT ON (es.result_id)
                   es.result_id, es.criterion_id, es.verdict, es.reason_code
            FROM app_private.evidence_signoffs es
            WHERE es.position_id IN (SELECT position_id FROM scope)
              AND es.created_at >= :start AND es.created_at < :end_excl
            ORDER BY es.result_id, es.created_at DESC, es.signoff_id DESC
        )
        SELECT COUNT(*) AS total_reviewed,
               COUNT(*) FILTER (WHERE verdict = 'CONFIRMED') AS confirmed_count,
               COUNT(*) FILTER (WHERE verdict = 'DISPUTED') AS disputed_count
        FROM latest
    """, params)
    summary = summary_rows[0] if summary_rows else {"total_reviewed": 0, "confirmed_count": 0, "disputed_count": 0}
    total_reviewed = int(summary["total_reviewed"] or 0)
    confirmed_count = int(summary["confirmed_count"] or 0)
    disputed_count = int(summary["disputed_count"] or 0)
    dispute_rate = round(disputed_count / total_reviewed, 4) if total_reviewed > 0 else None

    reason_rows = _rows(db, """,
        latest AS (
            SELECT DISTINCT ON (es.result_id)
                   es.result_id, es.verdict, es.reason_code
            FROM app_private.evidence_signoffs es
            WHERE es.position_id IN (SELECT position_id FROM scope)
              AND es.created_at >= :start AND es.created_at < :end_excl
            ORDER BY es.result_id, es.created_at DESC, es.signoff_id DESC
        )
        SELECT reason_code, COUNT(*) AS count
        FROM latest
        WHERE verdict = 'DISPUTED' AND reason_code IS NOT NULL
        GROUP BY reason_code
        ORDER BY count DESC, reason_code ASC
    """, params)
    by_reason = [
        {
            "reason_code": r["reason_code"],
            "count": int(r["count"]),
            "share": round(int(r["count"]) / disputed_count, 4) if disputed_count > 0 else 0.0,
        }
        for r in reason_rows
    ]

    criteria_rows = _rows(db, """,
        latest AS (
            SELECT DISTINCT ON (es.result_id)
                   es.result_id, es.criterion_id, es.verdict
            FROM app_private.evidence_signoffs es
            WHERE es.position_id IN (SELECT position_id FROM scope)
              AND es.created_at >= :start AND es.created_at < :end_excl
            ORDER BY es.result_id, es.created_at DESC, es.signoff_id DESC
        )
        SELECT ci.name AS criterion_name,
               ci.category,
               COUNT(*) AS total_reviewed,
               COUNT(*) FILTER (WHERE l.verdict = 'DISPUTED') AS disputed_count
        FROM latest l
        JOIN app_private.criteria_items ci ON ci.criterion_id = l.criterion_id
        GROUP BY ci.name, ci.category
        HAVING COUNT(*) FILTER (WHERE l.verdict = 'DISPUTED') > 0
        ORDER BY disputed_count DESC, total_reviewed DESC, ci.name ASC
        LIMIT 10
    """, params)
    top_disputed_criteria = [
        {
            "criterion_name": r["criterion_name"],
            "category": r["category"],
            "total_reviewed": int(r["total_reviewed"]),
            "disputed_count": int(r["disputed_count"]),
            "dispute_rate": round(int(r["disputed_count"]) / int(r["total_reviewed"]), 4) if int(r["total_reviewed"]) > 0 else 0.0,
        }
        for r in criteria_rows
    ]

    return {
        "range": {"date_from": start.isoformat(), "date_to": end.isoformat()},
        "min_sample": MIN_SAMPLE_SIZE,
        "total_reviewed": total_reviewed,
        "confirmed_count": confirmed_count,
        "disputed_count": disputed_count,
        "dispute_rate": dispute_rate,
        "dispute_proportion": proportion(disputed_count, total_reviewed),
        "by_reason": by_reason,
        "top_disputed_criteria": top_disputed_criteria,
    }
