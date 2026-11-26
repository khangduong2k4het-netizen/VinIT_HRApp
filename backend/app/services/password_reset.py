"""Self-service password reset tokens. Never log tokens or passwords."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.core.config import settings


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_token(db, user_id: str) -> str | None:
    """Create a fresh token for an ACTIVE account, or None when the hourly cap is reached.

    Older unused tokens are invalidated. The caller commits.
    """
    recent = db.execute(text("""
        SELECT COUNT(*) FROM app_private.password_reset_tokens
        WHERE user_id = :id AND created_at > NOW() - INTERVAL '1 hour'
    """), {"id": user_id}).scalar_one()
    if recent >= settings.PASSWORD_RESET_MAX_PER_HOUR:
        return None
    db.execute(text("""
        UPDATE app_private.password_reset_tokens SET used_at = NOW()
        WHERE user_id = :id AND used_at IS NULL
    """), {"id": user_id})
    token = secrets.token_urlsafe(32)
    db.execute(text("""
        INSERT INTO app_private.password_reset_tokens (token_hash, user_id, expires_at)
        VALUES (:h, :id, :exp)
    """), {"h": hash_token(token), "id": user_id,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES)})
    return token


def consume_token(db, token: str) -> str | None:
    """Return the user id and mark the token used, or None if invalid/expired/used. Caller commits."""
    row = db.execute(text("""
        UPDATE app_private.password_reset_tokens SET used_at = NOW()
        WHERE token_hash = :h AND used_at IS NULL AND expires_at > NOW()
        RETURNING user_id
    """), {"h": hash_token(token)}).first()
    return str(row[0]) if row else None


def allowed_registration_domain(email: str) -> bool:
    domains = [d.strip().lower().lstrip("@") for d in settings.SELF_REGISTRATION_ALLOWED_DOMAINS.split(",") if d.strip()]
    if not domains:
        return True
    return email.rsplit("@", 1)[-1].strip().lower() in domains
