"""P3-1 Talent Pool: who may be scanned. Pure rules plus the eligibility query.

A received application may be reused for another position only when it has a
TALENT_POOL consent that is not withdrawn, is still inside the retention window
counted from the moment the candidate ticked that consent (not from the day the
CV was received), is not queued for deletion, and was
marked by HR. The same query is used before every scan and before showing results.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

from app.core.config import settings
from app.services.retention import add_months

MARK_REASONS = ("STRONG_FIT", "NEAR_MISS", "OTHER_ROLE_FIT")
MARKABLE_STATUSES = ("SHORTLIST", "INTERVIEW", "REJECTED_INTERVIEW")


class PoolError(ValueError):
    pass


def pool_expiry(consented_at: datetime, months: Optional[int] = None) -> datetime:
    """End of the pool window, counted from when the TALENT_POOL consent was ticked."""
    return add_months(consented_at, months if months is not None else settings.TALENT_POOL_RETENTION_MONTHS)


def ineligibility_reason(*, status: str, consent_present: bool, consent_withdrawn: bool, consented_at: Optional[datetime],
                         open_retention_status: Optional[str], now: Optional[datetime] = None) -> Optional[str]:
    """First reason the application cannot enter or stay in the pool, else None."""
    now = now or datetime.now(timezone.utc)
    if not consent_present:
        return "NO_CONSENT"
    if consent_withdrawn:
        return "CONSENT_WITHDRAWN"
    if consented_at is None or pool_expiry(consented_at) <= now:
        return "RETENTION_EXPIRED"
    if open_retention_status in ("SCHEDULED_FOR_DELETION", "ON_HOLD", "DELETED"):
        return "DELETION_PENDING"
    if status not in MARKABLE_STATUSES:
        return "STATUS_NOT_ELIGIBLE"
    return None


ELIGIBLE_POOL_SQL = """
    SELECT a.application_id, a.position_id, a.created_at AS received_at, c.granted_at AS consented_at
    FROM app_private.talent_pool_marks m
    JOIN app_private.applications a ON a.application_id = m.application_id
    JOIN app_private.application_data_consents c
      ON c.application_id = a.application_id AND c.purpose = 'TALENT_POOL' AND c.withdrawn_at IS NULL
    WHERE m.removed_at IS NULL
      AND c.granted_at + make_interval(months => :months) > CAST(:now AS timestamptz)
      AND a.application_status IN ('SHORTLIST', 'INTERVIEW', 'REJECTED_INTERVIEW')
      AND NOT EXISTS (
          SELECT 1 FROM app_private.application_retention_cases rc
          WHERE rc.application_id = a.application_id AND rc.status IN ('SCHEDULED_FOR_DELETION', 'ON_HOLD'))
"""


def eligible_pool(db, now: Optional[datetime] = None) -> list:
    """Applications that may be scanned right now (unscoped; callers add position access)."""
    rows = db.execute(text(ELIGIBLE_POOL_SQL), {"now": now or datetime.now(timezone.utc),
                                                "months": settings.TALENT_POOL_RETENTION_MONTHS})
    return [dict(r._mapping) for r in rows]


def application_pool_state(db, application_id: str, now: Optional[datetime] = None) -> Optional[dict]:
    row = db.execute(text("""
        SELECT a.position_id, a.application_status, a.created_at,
               c.consent_id IS NOT NULL AS consent_present, c.withdrawn_at IS NOT NULL AS consent_withdrawn,
               c.granted_at AS consented_at,
               (SELECT rc.status FROM app_private.application_retention_cases rc
                 WHERE rc.application_id = a.application_id AND rc.status IN ('SCHEDULED_FOR_DELETION', 'ON_HOLD')
                 LIMIT 1) AS retention_status
        FROM app_private.applications a
        LEFT JOIN app_private.application_data_consents c
          ON c.application_id = a.application_id AND c.purpose = 'TALENT_POOL'
        WHERE a.application_id = :id
    """), {"id": application_id}).first()
    if row is None:
        return None
    r = row._mapping
    reason = ineligibility_reason(
        status=r["application_status"], consent_present=bool(r["consent_present"]),
        consent_withdrawn=bool(r["consent_withdrawn"]), consented_at=r["consented_at"],
        open_retention_status=r["retention_status"], now=now)
    return {"position_id": str(r["position_id"]), "eligible": reason is None, "reason": reason,
            "expires_on": (pool_expiry(r["consented_at"]).date().isoformat()
                           if r["consented_at"] is not None else None)}


SCAN_CANDIDATES_SQL = """
    WITH pool AS (""" + ELIGIBLE_POOL_SQL + """),
    target AS (
        SELECT lower(btrim(i.email)) AS email, regexp_replace(coalesce(i.phone, ''), '[^0-9]', '', 'g') AS phone
        FROM app_private.applications a
        JOIN app_private.application_identities i ON i.application_id = a.application_id
        WHERE a.position_id = :target
    ),
    candidates AS (
        SELECT pool.application_id, pool.position_id, pool.consented_at,
               lower(btrim(i.email)) AS email, regexp_replace(coalesce(i.phone, ''), '[^0-9]', '', 'g') AS phone
        FROM pool
        LEFT JOIN app_private.application_identities i ON i.application_id = pool.application_id
        WHERE pool.position_id <> :target
    ),
    fresh AS (
        SELECT c.* FROM candidates c
        WHERE NOT EXISTS (SELECT 1 FROM target t WHERE (c.email <> '' AND t.email = c.email)
                                                   OR (length(c.phone) >= 9 AND t.phone = c.phone))
    ),
    -- One row per person: the most recent consent wins when the same email is pooled twice.
    deduped AS (
        SELECT DISTINCT ON (coalesce(nullif(email, ''), application_id::text)) *
        FROM fresh ORDER BY coalesce(nullif(email, ''), application_id::text), consented_at DESC
    )
    SELECT d.application_id, d.position_id AS source_position_id, processing.extracted_text_storage_path,
           profile.profile_version_id
    FROM deduped d
    LEFT JOIN LATERAL (
        SELECT r.extracted_text_storage_path FROM app_private.application_documents doc
        JOIN app_private.document_processing_runs r ON r.document_id = doc.document_id AND r.status = 'COMPLETED'
        WHERE doc.application_id = d.application_id AND doc.document_type = 'CV'
        ORDER BY r.created_at DESC LIMIT 1
    ) processing ON TRUE
    LEFT JOIN LATERAL (
        SELECT profile_version_id FROM app_private.profile_versions
        WHERE application_id = d.application_id AND status = 'COMPLETED'
        ORDER BY version_number DESC LIMIT 1
    ) profile ON TRUE
    ORDER BY d.consented_at DESC
    LIMIT :limit
"""


def scan_candidates(db, target_position_id: str, now: Optional[datetime] = None) -> list:
    """Eligible pooled applications to score for a position.

    Excludes applications of the target position itself and people who already
    applied to it (same email or phone), and keeps one application per email.
    """
    rows = db.execute(text(SCAN_CANDIDATES_SQL), {
        "now": now or datetime.now(timezone.utc), "months": settings.TALENT_POOL_RETENTION_MONTHS,
        "target": target_position_id, "limit": settings.TALENT_POOL_SCAN_MAX_CANDIDATES})
    return [dict(r._mapping) for r in rows]


def eligible_application_ids(db, now: Optional[datetime] = None) -> set:
    return {str(row["application_id"]) for row in eligible_pool(db, now)}
