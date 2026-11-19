"""F2.03 — operational analytics (pilot report).

Metric dictionary (all limited to the caller's position scope and the
date range [date_from, date_to], both inclusive):

* applications_received — applications created in the range.
* funnel — of those applications, how many EVER reached each stage
  (from application_status_events; a later step back does not undo it).
* time_to_shortlist — hours from application creation (CV upload) to its
  first SHORTLIST decision, for applications in the cohort that reached it.
* cv_processing — CV_PROCESSING operations created in the range:
  seconds from worker start to completion.
* overrides — screening decisions made in the range (into SHORTLIST or
  REJECTED_SCREENING) where an AI conclusion existed at decision time; an
  override is one that contradicts it (see app.services.override_rules).
  Decisions recorded before tracking existed have no AI snapshot and are
  excluded rather than guessed.
* technical_errors — files uploaded in the range that were rejected at upload
  or ended up needing HR review, plus processing error codes.

No metric is broken down by individual recruiter: the roadmap forbids using
these numbers as a personal KPI.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from sqlalchemy import text

from app.services.override_rules import REASON_CODES

FUNNEL_STAGES = ("IN_REVIEW", "SHORTLIST", "INTERVIEW", "OFFERED", "ACCEPTED")
MAX_RANGE_DAYS = 366


class AnalyticsError(ValueError):
    pass


def resolve_range(date_from: Optional[str], date_to: Optional[str], today: Optional[date] = None) -> tuple[date, date]:
    today = today or date.today()
    try:
        end = date.fromisoformat(date_to) if date_to else today
        start = date.fromisoformat(date_from) if date_from else end - timedelta(days=89)
    except ValueError:
        raise AnalyticsError("Ngày phải theo định dạng YYYY-MM-DD") from None
    if start > end:
        raise AnalyticsError("Ngày bắt đầu phải trước ngày kết thúc")
    if (end - start).days > MAX_RANGE_DAYS:
        raise AnalyticsError(f"Khoảng thời gian tối đa {MAX_RANGE_DAYS} ngày")
    return start, end


def has_global_scope(db, user_id: str) -> bool:
    return bool(db.execute(text("""
        SELECT 1 FROM app_private.user_role_assignments
        WHERE user_id = :u AND revoked_at IS NULL AND role_code IN ('ADMIN', 'HR_LEAD') LIMIT 1
    """), {"u": user_id}).first())


def has_any_hr_scope(db, user_id: str) -> bool:
    return has_global_scope(db, user_id) or bool(db.execute(text("""
        SELECT 1 FROM app_private.position_assignments
        WHERE user_id = :u AND revoked_at IS NULL AND position_role IN ('HR_RECRUITER', 'HR_LEAD') LIMIT 1
    """), {"u": user_id}).first())


# Positions the caller may analyse, optionally narrowed by position/department.
_SCOPE = """
    scope AS (
        SELECT p.position_id FROM app_private.positions p
        WHERE (:global_scope OR EXISTS (
                SELECT 1 FROM app_private.position_assignments pa
                WHERE pa.position_id = p.position_id AND pa.user_id = :user_id AND pa.revoked_at IS NULL
                  AND pa.position_role IN ('HR_RECRUITER', 'HR_LEAD')))
          AND (CAST(:position_id AS uuid) IS NULL OR p.position_id = CAST(:position_id AS uuid))
          AND (CAST(:department_id AS uuid) IS NULL OR p.department_id = CAST(:department_id AS uuid))
    )
"""


def _rate(part: int, whole: int) -> Optional[float]:
    return round(part / whole, 4) if whole else None


def operational_report(db, *, user_id: str, start: date, end: date,
                       position_id: Optional[str] = None, department_id: Optional[str] = None) -> dict[str, Any]:
    params = {"user_id": user_id, "global_scope": has_global_scope(db, user_id), "position_id": position_id,
              "department_id": department_id, "start": start, "end_excl": end + timedelta(days=1)}

    def one(sql: str) -> dict:
        return dict(db.execute(text("WITH " + _SCOPE + ", " + sql), params).mappings().one())

    def many(sql: str) -> list[dict]:
        return [dict(r) for r in db.execute(text("WITH " + _SCOPE + ", " + sql), params).mappings().all()]

    cohort = """cohort AS (
        SELECT a.application_id, a.created_at FROM app_private.applications a
        WHERE a.position_id IN (SELECT position_id FROM scope)
          AND a.created_at >= :start AND a.created_at < :end_excl
    )"""

    volume = one(cohort + """
        SELECT (SELECT COUNT(*) FROM cohort) AS applications_received,
               (SELECT COUNT(DISTINCT a.position_id) FROM app_private.applications a
                 JOIN cohort c ON c.application_id = a.application_id) AS positions_with_applications,
               (SELECT COUNT(*) FROM scope) AS positions_in_scope
    """)

    reached = one(cohort + ", reached AS (SELECT DISTINCT e.application_id, e.new_status FROM app_private.application_status_events e "
                  "JOIN cohort c ON c.application_id = e.application_id) SELECT "
                  + ", ".join(f"COUNT(*) FILTER (WHERE new_status = '{stage}') AS {stage.lower()}" for stage in FUNNEL_STAGES)
                  + ", COUNT(*) FILTER (WHERE new_status = 'REJECTED_SCREENING') AS rejected_screening"
                  + ", COUNT(*) FILTER (WHERE new_status = 'REJECTED_INTERVIEW') AS rejected_interview FROM reached")
    received = volume["applications_received"]
    funnel, previous = [], received
    for stage in FUNNEL_STAGES:
        count = reached[stage.lower()]
        funnel.append({"stage": stage, "count": count, "rate_from_received": _rate(count, received),
                       "rate_from_previous": _rate(count, previous)})
        previous = count

    shortlist_time = one(cohort + """, firsts AS (
            SELECT c.application_id, EXTRACT(EPOCH FROM (MIN(e.changed_at) - c.created_at)) / 3600.0 AS hours
            FROM cohort c JOIN app_private.application_status_events e
              ON e.application_id = c.application_id AND e.new_status = 'SHORTLIST'
            GROUP BY c.application_id, c.created_at)
        SELECT COUNT(*) AS applications, AVG(hours) AS average_hours,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY hours) AS median_hours FROM firsts
    """)

    processing = one("""ops AS (
            SELECT EXTRACT(EPOCH FROM (o.completed_at - o.started_at)) AS seconds, o.status
            FROM app_private.operations o
            WHERE o.capability = 'CV_PROCESSING' AND o.position_id IN (SELECT position_id FROM scope)
              AND o.created_at >= :start AND o.created_at < :end_excl)
        SELECT COUNT(*) AS operations,
               COUNT(*) FILTER (WHERE status = 'FAILED') AS failed_operations,
               AVG(seconds) FILTER (WHERE status = 'COMPLETED' AND seconds IS NOT NULL) AS average_seconds
        FROM ops
    """)

    decisions = """decisions AS (
        SELECT e.*, a.position_id FROM app_private.application_status_events e
        JOIN app_private.applications a ON a.application_id = e.application_id
        WHERE a.position_id IN (SELECT position_id FROM scope)
          AND e.changed_at >= :start AND e.changed_at < :end_excl
          AND e.new_status IN ('SHORTLIST', 'REJECTED_SCREENING')
          AND e.ai_matching_status IN ('NEEDS_HR_VERIFICATION', 'POSSIBLE_MISMATCH', 'MEETS_MANDATORY'))"""
    totals = one(decisions + """
        SELECT COUNT(*) AS decisions_with_ai,
               COUNT(*) FILTER (WHERE override_direction IS NOT NULL) AS overrides,
               COUNT(*) FILTER (WHERE override_direction = 'ADVANCED_DESPITE_AI') AS advanced_despite_ai,
               COUNT(*) FILTER (WHERE override_direction = 'REJECTED_DESPITE_AI') AS rejected_despite_ai
        FROM decisions
    """)
    by_reason = {r["code"]: r["count"] for r in many(decisions + """
        SELECT override_reason_code AS code, COUNT(*) AS count FROM decisions
        WHERE override_direction IS NOT NULL GROUP BY override_reason_code""")}
    cases = many(decisions + """
        SELECT d.event_id, d.changed_at, d.application_id, d.position_id, d.previous_status, d.new_status,
               d.ai_matching_status, d.ai_matching_score, d.ai_evidence_coverage,
               d.override_direction, d.override_reason_code, d.note,
               p.title AS position_title, p.position_code, i.display_name AS candidate_name
        FROM decisions d
        JOIN app_private.positions p ON p.position_id = d.position_id
        LEFT JOIN app_private.application_identities i ON i.application_id = d.application_id
        WHERE d.override_direction IS NOT NULL
        ORDER BY d.changed_at DESC LIMIT 200
    """)
    tracking_since = db.execute(text("""
        SELECT MIN(changed_at) FROM app_private.application_status_events WHERE ai_matching_status IS NOT NULL
    """)).scalar_one_or_none()

    uploads = one("""items AS (
            SELECT bi.error_code, bi.detected_mime_type FROM app_private.cv_batch_items bi
            JOIN app_private.cv_batches b ON b.batch_id = bi.batch_id
            WHERE b.position_id IN (SELECT position_id FROM scope)
              AND bi.created_at >= :start AND bi.created_at < :end_excl)
        SELECT COUNT(*) AS files_uploaded,
               COUNT(*) FILTER (WHERE error_code = 'FILE_TOO_LARGE') AS rejected_too_large,
               COUNT(*) FILTER (WHERE error_code IS NOT NULL AND error_code <> 'FILE_TOO_LARGE') AS rejected_invalid_format
        FROM items
    """)
    documents = many("""docs AS (
            SELECT d.mime_type, d.file_processing_status FROM app_private.application_documents d
            JOIN app_private.applications a ON a.application_id = d.application_id
            WHERE a.position_id IN (SELECT position_id FROM scope)
              AND d.created_at >= :start AND d.created_at < :end_excl)
        SELECT mime_type, COUNT(*) AS total,
               COUNT(*) FILTER (WHERE file_processing_status IN ('NEEDS_HR_REVIEW', 'ERROR_UNSUPPORTED')) AS needs_review
        FROM docs GROUP BY mime_type ORDER BY total DESC
    """)
    run_errors = many("""runs AS (
            SELECT r.error_code FROM app_private.document_processing_runs r
            JOIN app_private.application_documents d ON d.document_id = r.document_id
            JOIN app_private.applications a ON a.application_id = d.application_id
            WHERE a.position_id IN (SELECT position_id FROM scope)
              AND r.created_at >= :start AND r.created_at < :end_excl AND r.error_code IS NOT NULL)
        SELECT error_code, COUNT(*) AS count FROM runs GROUP BY error_code ORDER BY count DESC
    """)
    needs_review = sum(d["needs_review"] for d in documents)
    rejected = uploads["rejected_too_large"] + uploads["rejected_invalid_format"]

    weekly = many(cohort + """, weeks AS (
            SELECT date_trunc('week', created_at)::date AS week, COUNT(*) AS applications FROM cohort GROUP BY 1),
        weekly_overrides AS (
            SELECT date_trunc('week', e.changed_at)::date AS week, COUNT(*) AS overrides
            FROM app_private.application_status_events e
            JOIN app_private.applications a ON a.application_id = e.application_id
            WHERE a.position_id IN (SELECT position_id FROM scope) AND e.override_direction IS NOT NULL
              AND e.changed_at >= :start AND e.changed_at < :end_excl GROUP BY 1)
        SELECT COALESCE(w.week, o.week) AS week, COALESCE(w.applications, 0) AS applications,
               COALESCE(o.overrides, 0) AS overrides
        FROM weeks w FULL OUTER JOIN weekly_overrides o ON o.week = w.week ORDER BY 1
    """)

    def num(value):
        return round(float(value), 2) if value is not None else None

    return {
        "range": {"date_from": start.isoformat(), "date_to": end.isoformat()},
        "scope": {"global": params["global_scope"], "positions": volume["positions_in_scope"]},
        "volume": {"applications_received": received, "positions_with_applications": volume["positions_with_applications"]},
        "funnel": funnel,
        "rejections": {"screening": reached["rejected_screening"], "interview": reached["rejected_interview"]},
        "time_to_shortlist": {"applications": shortlist_time["applications"],
                              "average_hours": num(shortlist_time["average_hours"]),
                              "median_hours": num(shortlist_time["median_hours"])},
        "cv_processing": {"operations": processing["operations"], "failed_operations": processing["failed_operations"],
                          "average_seconds": num(processing["average_seconds"])},
        "overrides": {
            **totals,
            "override_rate": _rate(totals["overrides"], totals["decisions_with_ai"]),
            "by_reason": [{"code": code, "label": label, "count": by_reason.get(code, 0)} for code, label in REASON_CODES.items()],
            "cases": cases,
            "tracking_since": tracking_since,
        },
        "technical_errors": {
            **uploads,
            "documents_needing_review": needs_review,
            "error_rate": _rate(rejected + needs_review, uploads["files_uploaded"]),
            "by_file_type": documents,
            "processing_error_codes": run_errors,
        },
        "weekly": weekly,
    }
