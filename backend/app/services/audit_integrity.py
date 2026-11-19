"""Tamper-evidence checks for the append-only audit hash chain.

Migration 00012 makes ``app_private.audit_events`` append-only for
UPDATE/DELETE and fills a SHA-256 hash chain on insert.  This module only
verifies the stored chain; it never returns audit metadata or candidate data.
"""
from __future__ import annotations

from sqlalchemy import text


def verify_audit_chain(db) -> dict:
    """Return aggregate integrity status for the audit hash chain.

    ``valid`` is true only when every event links to the previous stored hash
    and every stored hash recomputes to the migration's canonical payload.
    A database superuser who disables triggers or rewrites history outside the
    application remains an operational risk; this check detects accidental or
    application-level tampering and broken backfills.
    """
    row = db.execute(text("""
        WITH ordered AS (
            SELECT
                e.chain_sequence,
                e.event_id,
                e.event_hash,
                e.previous_event_hash,
                LAG(e.event_hash) OVER (ORDER BY e.chain_sequence) AS expected_previous,
                app_private.compute_audit_event_hash(e.previous_event_hash, e) AS expected_hash
            FROM app_private.audit_events e
        ), broken AS (
            SELECT chain_sequence, event_id
            FROM ordered
            WHERE COALESCE(previous_event_hash, '') <> COALESCE(expected_previous, '')
               OR COALESCE(event_hash, '') <> COALESCE(expected_hash, '')
        )
        SELECT
            (SELECT COUNT(*) FROM app_private.audit_events) AS checked_events,
            (SELECT COUNT(*) FROM broken) AS broken_events,
            (SELECT event_id::text FROM broken ORDER BY chain_sequence LIMIT 1) AS first_broken_event_id
    """)).mappings().one()
    broken = int(row["broken_events"] or 0)
    return {
        "valid": broken == 0,
        "checked_events": int(row["checked_events"] or 0),
        "broken_events": broken,
        "first_broken_event_id": row["first_broken_event_id"],
        "algorithm": "sha256-hash-chain",
    }
