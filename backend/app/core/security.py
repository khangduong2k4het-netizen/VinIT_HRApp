import asyncio
from functools import lru_cache
from typing import Any, Dict, Optional
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import PyJWTError
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError

from .config import settings
from .logging import get_logger

logger = get_logger(__name__)

_ASYMMETRIC_ALGORITHMS = {
    "ES256",
    "ES384",
    "ES512",
    "RS256",
    "RS384",
    "RS512",
    "PS256",
    "PS384",
    "PS512",
    "EdDSA",
}


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _configuration_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication verification is not configured",
    )


def _jwks_url() -> Optional[str]:
    configured = (settings.SUPABASE_JWKS_URL or "").strip()
    if configured:
        return configured
    supabase_url = (settings.SUPABASE_URL or "").strip().rstrip("/")
    if not supabase_url:
        return None
    return f"{supabase_url}/auth/v1/.well-known/jwks.json"


def _jwt_issuer() -> Optional[str]:
    configured = (settings.SUPABASE_JWT_ISSUER or "").strip().rstrip("/")
    if configured:
        return configured
    supabase_url = (settings.SUPABASE_URL or "").strip().rstrip("/")
    if not supabase_url:
        return None
    return f"{supabase_url}/auth/v1"


@lru_cache(maxsize=8)
def _get_jwk_client(jwks_url: str, cache_seconds: int) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(
        jwks_url,
        cache_keys=True,
        cache_jwk_set=True,
        lifespan=max(30, cache_seconds),
        timeout=10,
    )


async def _decode_supabase_token(token: str) -> Dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
    except PyJWTError:
        raise _credentials_exception() from None

    algorithm = header.get("alg")
    if algorithm == "HS256":
        if not settings.SUPABASE_JWT_SECRET:
            raise _configuration_exception()
        try:
            return jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                options={"require": ["sub", "aud", "exp"]},
            )
        except PyJWTError:
            raise _credentials_exception() from None

    if algorithm not in _ASYMMETRIC_ALGORITHMS:
        raise _credentials_exception()

    jwks_url = _jwks_url()
    if not jwks_url:
        raise _configuration_exception()

    client = _get_jwk_client(jwks_url, settings.SUPABASE_JWKS_CACHE_SECONDS)
    try:
        signing_key = await asyncio.to_thread(client.get_signing_key_from_jwt, token)
    except PyJWKClientConnectionError:
        logger.warning("Unable to fetch Supabase JWKS", jwks_url=jwks_url)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication verification is temporarily unavailable",
        ) from None
    except PyJWKClientError:
        raise _credentials_exception() from None

    issuer = _jwt_issuer()
    decode_options = {"require": ["sub", "aud", "exp"]}
    decode_kwargs: Dict[str, Any] = {}
    if issuer:
        decode_options["require"].append("iss")
        decode_kwargs["issuer"] = issuer

    try:
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=[algorithm],
            audience="authenticated",
            options=decode_options,
            **decode_kwargs,
        )
    except PyJWTError:
        raise _credentials_exception() from None


async def verify_supabase_jwt(request: Request) -> Dict[str, Any]:
    """Verify a Supabase access token using HS256 legacy or JWKS signing keys."""
    auth_header = request.headers.get("Authorization", "")
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise _credentials_exception()

    payload = await _decode_supabase_token(parts[1])
    user_id: str = payload.get("sub")
    if user_id is None:
        raise _credentials_exception()
    try:
        # Compare canonical UUIDs in self-action and dual-approval guards.
        payload["sub"] = str(UUID(user_id))
    except (ValueError, TypeError, AttributeError):
        raise _credentials_exception() from None
    return payload


def ensure_token_is_current(user_payload: Dict[str, Any], valid_after) -> None:
    """Reject pre-reset app tokens even if an account is later re-enabled.

    Supabase uses integer-second iat values. Reject the cutoff second as well:
    a freshly issued token may need one second before it can be used.
    """
    if valid_after is None:
        return
    issued_at = user_payload.get("iat")
    if isinstance(issued_at, bool) or not isinstance(issued_at, (int, float)) or issued_at <= valid_after.timestamp():
        raise HTTPException(status_code=401, detail="Vui lòng đăng nhập lại.", headers={"WWW-Authenticate": "Bearer"})


async def get_active_user(user_payload: Dict[str, Any] = Depends(verify_supabase_jwt)) -> Dict[str, Any]:
    """Allow an active user to inspect their own account/change a temporary password."""
    user_id = user_payload.get("sub")
    from app.db.database import SessionLocal
    from sqlalchemy import text
    db = SessionLocal()
    try:
        profile = db.execute(text("""
            SELECT account_status, must_change_password, tokens_valid_after
            FROM app_private.user_profiles WHERE user_id = :id
        """), {"id": user_id}).mappings().first()
        if not profile or profile["account_status"] != "ACTIVE":
            raise HTTPException(status_code=403, detail="Tài khoản chưa được kích hoạt hoặc đã bị khóa")
        ensure_token_is_current(user_payload, profile["tokens_valid_after"])
        return {"user_id": user_id, "email": user_payload.get("email"),
                "role": user_payload.get("role", "authenticated"),
                "must_change_password": bool(profile["must_change_password"]),
                "token_payload": user_payload}
    finally:
        db.close()


async def get_current_user(user: Dict[str, Any] = Depends(get_active_user)) -> Dict[str, Any]:
    """Business routes are unavailable until a temporary password is changed."""
    if user["must_change_password"]:
        raise HTTPException(status_code=403, detail="Bạn cần đổi mật khẩu tạm thời trước khi sử dụng hệ thống.")
    return user


def require_role(allowed_roles: list[str]):
    """Dependency factory to require specific user roles"""
    async def role_checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        from app.db.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        try:
            found = db.execute(text("""
                SELECT 1 FROM app_private.user_role_assignments
                WHERE user_id = :id AND revoked_at IS NULL AND role_code = ANY(:roles) LIMIT 1
            """), {"id": user["user_id"], "roles": allowed_roles}).first()
            if not found:
                raise HTTPException(status_code=403, detail="Required role is not assigned")
            return user
        finally:
            db.close()
    return role_checker
