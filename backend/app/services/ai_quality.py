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

import math
from datetime import date, timedelta
from typing import Any, Optional

from sqlalchemy import text

from app.services.analytics import has_global_scope

MIN_SAMPLE_SIZE = 20
GRAINS = ("week", "month")
RISK_REASONS = ("SINGLE_MANDATORY_MISS", "BORDERLINE_COVERAGE")
BREAKDOWN_DIMENSIONS = ("job_family", "department", "override_reason", "flag_category", "matching_policy_version")
MARKER_TITLE_MAX = 200
MARKER_NOTE_MAX = 1000

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

    else:  # matching_policy_version
        data = _rows(db, """
            SELECT COALESCE(ar.matching_policy_version, 'unknown') AS key,
                   COUNT(*) AS completed,
                   AVG(ar.evidence_coverage) AS average_evidence_coverage,
                   COUNT(*) FILTER (WHERE ar.matching_status = 'NEEDS_HR_VERIFICATION') AS needs_verification,
                   COUNT(*) FILTER (WHERE qi.reasons ? 'RANDOM_SAMPLE' AND qi.status = 'COMPLETED') AS random_completed,
                   COUNT(*) FILTER (WHERE qi.reasons ? 'RANDOM_SAMPLE' AND qi.verdict = 'ISSUES_FOUND') AS random_issues
            FROM app_private.assessment_runs ar
            LEFT JOIN app_private.quality_inspections qi ON qi.assessment_id = ar.assessment_id
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
