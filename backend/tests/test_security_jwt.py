import asyncio
import time
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

from app.core import security
from app.core.config import settings


class FakeRequest:
    def __init__(self, token):
        self.headers = {"Authorization": f"Bearer {token}"}


class FakeJWKClient:
    def __init__(self, key):
        self.key = key

    def get_signing_key_from_jwt(self, token):
        return SimpleNamespace(key=self.key)


def verify(token):
    return asyncio.run(security.verify_supabase_jwt(FakeRequest(token)))


def claims(**overrides):
    now = int(time.time())
    payload = {
        "sub": str(uuid4()),
        "aud": "authenticated",
        "role": "authenticated",
        "email": "admin@example.org",
        "iss": "https://project.example/auth/v1",
        "iat": now,
        "exp": now + 3600,
    }
    payload.update(overrides)
    return payload


def configure_jwks(monkeypatch, public_key):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://project.example")
    monkeypatch.setattr(settings, "SUPABASE_JWT_ISSUER", None)
    monkeypatch.setattr(settings, "SUPABASE_JWKS_URL", None)
    monkeypatch.setattr(settings, "SUPABASE_JWKS_CACHE_SECONDS", 300)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "")
    monkeypatch.setattr(
        security,
        "_get_jwk_client",
        lambda url, cache_seconds: FakeJWKClient(public_key),
    )


def test_es256_token_is_verified_through_jwks(monkeypatch):
    private_key = ec.generate_private_key(ec.SECP256R1())
    configure_jwks(monkeypatch, private_key.public_key())
    payload = claims()
    token = jwt.encode(
        payload,
        private_key,
        algorithm="ES256",
        headers={"kid": "test-es256-key"},
    )

    verified = verify(token)

    assert verified["sub"] == payload["sub"]
    assert verified["email"] == payload["email"]


def test_es256_token_with_wrong_key_or_issuer_is_rejected(monkeypatch):
    signing_key = ec.generate_private_key(ec.SECP256R1())
    other_key = ec.generate_private_key(ec.SECP256R1())
    configure_jwks(monkeypatch, other_key.public_key())
    token = jwt.encode(claims(), signing_key, algorithm="ES256")

    with pytest.raises(HTTPException) as wrong_key:
        verify(token)
    assert wrong_key.value.status_code == 401

    configure_jwks(monkeypatch, signing_key.public_key())
    wrong_issuer = jwt.encode(
        claims(iss="https://attacker.example/auth/v1"),
        signing_key,
        algorithm="ES256",
    )
    with pytest.raises(HTTPException) as issuer_error:
        verify(wrong_issuer)
    assert issuer_error.value.status_code == 401


def test_legacy_hs256_token_still_works(monkeypatch):
    secret = "legacy-test-secret"
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", secret)
    payload = claims()
    payload.pop("iss")
    token = jwt.encode(payload, secret, algorithm="HS256")

    verified = verify(token)

    assert verified["sub"] == payload["sub"]


def test_es256_without_jwks_configuration_is_service_unavailable(monkeypatch):
    private_key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(settings, "SUPABASE_URL", None)
    monkeypatch.setattr(settings, "SUPABASE_JWT_ISSUER", None)
    monkeypatch.setattr(settings, "SUPABASE_JWKS_URL", None)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "")
    token = jwt.encode(claims(), private_key, algorithm="ES256")

    with pytest.raises(HTTPException) as error:
        verify(token)
    assert error.value.status_code == 503


def test_non_hs256_hmac_algorithm_is_rejected(monkeypatch):
    secret = "legacy-test-secret"
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", secret)
    token = jwt.encode(claims(), secret, algorithm="HS384")

    with pytest.raises(HTTPException) as error:
        verify(token)
    assert error.value.status_code == 401
