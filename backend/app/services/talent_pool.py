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
      AND c.granted_at > CAST(:now AS timestamptz) - make_interval(months => :months)
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
