"""Consent primitives. Not exposed as a free-standing opt-in API.

Only a future intake may call create_consent after explicit separate opt-in,
with approved policy values chosen by the server in the same DB transaction.
"""
from datetime import datetime
import hashlib
import secrets
import re

from sqlalchemy import text


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('ascii')).hexdigest()


def create_consent(db, *, application_id: str, notice_version: str,
                   consent_expires_at: datetime, retention_expires_at: datetime,
                   withdrawal_token: str | None = None) -> str:
    """Insert evidence and return a one-time 256-bit bearer withdrawal token.

    The caller owns the transaction and must return the token only after commit.
    Never log or persist the token itself. A recovery/reissue workflow is not yet
    implemented, so do not use this with real candidates until it is approved.
    """
    if (not notice_version or len(notice_version) > 100
            or consent_expires_at.utcoffset() is None or retention_expires_at.utcoffset() is None):
        raise ValueError('Invalid consent policy')
    token = withdrawal_token if withdrawal_token is not None else secrets.token_hex(32)
    if not re.fullmatch(r'[0-9a-f]{64}', token):
        raise ValueError('Invalid withdrawal token')
    db.execute(text("""INSERT INTO app_private.talent_pool_consents
        (application_id,notice_version,token_hash,consent_expires_at,retention_expires_at)
        VALUES (:app,:notice,:token,:consent_expiry,:retention_expiry)"""),
        {'app': application_id, 'notice': notice_version, 'token': hash_token(token),
         'consent_expiry': consent_expires_at, 'retention_expiry': retention_expires_at})
    db.execute(text("""INSERT INTO app_private.audit_events(action_type, object_type, object_id, outcome, metadata)
        VALUES ('TALENT_POOL_CONSENT','APPLICATION',:app,'SUCCESS',jsonb_build_object('notice_version',CAST(:notice AS text)))"""),
        {'app': application_id, 'notice': notice_version})
    return token
