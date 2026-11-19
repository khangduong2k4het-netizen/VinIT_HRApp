"""Local authentication (AUTH_BACKEND=local): passwords and tokens without Supabase.

Passwords are hashed with scrypt (stdlib, memory-hard). Tokens are HS256 JWTs
with the same claims the verifier in app.core.security already accepts, signed
with SUPABASE_JWT_SECRET. Never log passwords, hashes or tokens.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings

_N, _R, _P = 2 ** 14, 8, 1
_SALT_BYTES, _KEY_BYTES = 16, 32
_MAXMEM = 64 * 1024 * 1024


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_KEY_BYTES, maxmem=_MAXMEM)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                                dklen=len(expected), maxmem=_MAXMEM)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, UnicodeError):
        return False


# Verified against when the email is unknown, so response time does not reveal
# whether an account exists.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def issue_token(user_id: str, email: Optional[str]) -> tuple[str, int]:
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    now = int(time.time())
    token = jwt.encode({"sub": user_id, "aud": "authenticated", "role": "authenticated", "email": email,
                        "iss": "hra-local-auth", "iat": now, "exp": now + expires_in},
                       settings.SUPABASE_JWT_SECRET, algorithm="HS256")
    return token, expires_in


class LocalAuthLocked(Exception):
    """Too many failed attempts; the account is temporarily locked."""


def authenticate(db, email: str, password: str) -> Optional[dict]:
    """Return {user_id, email} on success, None on bad credentials. Commits attempt counters."""
    row = db.execute(text("""
        SELECT u.id AS user_id, u.email, c.password_hash, c.failed_attempts, c.locked_until
        FROM auth.users u JOIN app_private.local_credentials c ON c.user_id = u.id
        WHERE lower(u.email) = lower(:email)
        FOR UPDATE OF c
    """), {"email": email.strip()}).mappings().first()
    if not row:
        verify_password(password, _DUMMY_HASH)
        db.rollback()
        return None
    now = datetime.now(timezone.utc)
    if row["locked_until"] is not None and row["locked_until"] > now:
        db.rollback()
        raise LocalAuthLocked()
    if not verify_password(password, row["password_hash"]):
        attempts = row["failed_attempts"] + 1
        locked = attempts >= settings.LOCAL_AUTH_MAX_FAILED_ATTEMPTS
        db.execute(text("""
            UPDATE app_private.local_credentials
            SET failed_attempts = :attempts, locked_until = :locked_until WHERE user_id = :id
        """), {"attempts": 0 if locked else attempts, "id": str(row["user_id"]),
                "locked_until": now + timedelta(minutes=settings.LOCAL_AUTH_LOCKOUT_MINUTES) if locked else None})
        db.commit()
        return None
    if row["failed_attempts"] or row["locked_until"] is not None:
        db.execute(text("UPDATE app_private.local_credentials SET failed_attempts = 0, locked_until = NULL WHERE user_id = :id"),
                   {"id": str(row["user_id"])})
    db.commit()
    return {"user_id": str(row["user_id"]), "email": row["email"]}


def verify_user_password(db, user_id: str, password: str) -> bool:
    stored = db.execute(text("SELECT password_hash FROM app_private.local_credentials WHERE user_id = :id"),
                        {"id": user_id}).scalar_one_or_none()
    return verify_password(password, stored or _DUMMY_HASH) and stored is not None


def set_password(db, user_id: str, password: str) -> None:
    """Caller commits."""
    db.execute(text("""
        UPDATE app_private.local_credentials
        SET password_hash = :hash, password_updated_at = NOW(), failed_attempts = 0, locked_until = NULL
        WHERE user_id = :id
    """), {"hash": hash_password(password), "id": user_id})


class LocalIdentityExists(Exception):
    pass


def create_identity(db, user_id: str, email: str, password: str) -> None:
    """Create auth.users + credentials in the caller's transaction (caller commits)."""
    exists = db.execute(text("SELECT 1 FROM auth.users WHERE lower(email) = lower(:email)"), {"email": email}).first()
    if exists:
        raise LocalIdentityExists()
    try:
        with db.begin_nested():
            db.execute(text("INSERT INTO auth.users (id, email) VALUES (:id, :email)"), {"id": user_id, "email": email.strip().lower()})
    except IntegrityError:
        raise LocalIdentityExists() from None
    db.execute(text("INSERT INTO app_private.local_credentials (user_id, password_hash) VALUES (:id, :hash)"),
               {"id": user_id, "hash": hash_password(password)})
