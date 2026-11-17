"""Synthetic-only eligibility model; no database access and no real candidate search."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SyntheticEligibility:
    opted_in: bool
    withdrawn: bool
    consent_expires_at: datetime | None
    retention_expires_at: datetime | None
    deletion_pending: bool


def eligible_for_synthetic_scan(record: SyntheticEligibility, now: datetime) -> bool:
    if now.utcoffset() is None:
        raise ValueError('timezone-aware timestamp required')
    deadlines = (record.consent_expires_at, record.retention_expires_at)
    return (record.opted_in and not record.withdrawn and not record.deletion_pending
            and all(d is not None and d.utcoffset() is not None and d > now for d in deadlines))
