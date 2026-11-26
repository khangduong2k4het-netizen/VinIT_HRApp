"""Self-registration and forgot-password (AUTH_BACKEND=local). Disposable local *_test database only."""
import os
import time
from uuid import uuid4
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine
from app.main import app

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                reason="Requires a disposable local migrated *_test database")
PASSWORD = "first-password-for-tests-123"
NEW_PASSWORD = "second-password-for-tests-456"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_BACKEND", "local")
    monkeypatch.setattr(settings, "SELF_REGISTRATION_ENABLED", True)
    monkeypatch.setattr(settings, "SELF_REGISTRATION_ALLOWED_DOMAINS", "vinuni.edu.vn")
    monkeypatch.setattr(settings, "PASSWORD_RESET_DEV_ECHO", True)
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "synthetic-jwt-secret-not-for-production-0123456789")
    return TestClient(app)


def _email():
    return f"user{uuid4().hex[:10]}@vinuni.edu.vn"


def _register(client, email, password=PASSWORD):
    return client.post("/v1/auth/register", json={"email": email, "display_name": "Người Dùng Thử", "password": password})


def _login(client, email, password):
    return client.post("/v1/auth/login", json={"email": email, "password": password})


def _activate(email):
    with engine.begin() as conn:
        conn.execute(text("""UPDATE app_private.user_profiles SET account_status = 'ACTIVE'
            WHERE user_id = (SELECT id FROM auth.users WHERE email = :e)"""), {"e": email})
        conn.execute(text("""INSERT INTO app_private.user_role_assignments(user_id, role_code)
            SELECT id, 'VIEWER' FROM auth.users WHERE email = :e"""), {"e": email})


def test_public_config_reports_flags(client):
    config = client.get("/v1/auth/public-config").json()
    assert config["self_registration"] is True and config["registration_domains"] == ["vinuni.edu.vn"]


def test_registration_is_pending_until_admin_activates(client):
    email = _email()
    assert _register(client, email).status_code == 201
    with engine.connect() as conn:
        row = conn.execute(text("""SELECT p.account_status, p.must_change_password,
            (SELECT COUNT(*) FROM app_private.user_role_assignments r WHERE r.user_id = p.user_id)
            FROM app_private.user_profiles p JOIN auth.users u ON u.id = p.user_id WHERE u.email = :e"""), {"e": email}).one()
    assert row == ("INACTIVE", False, 0)
    blocked = _login(client, email, PASSWORD)
    assert blocked.status_code == 403 and "chờ Admin duyệt" in blocked.json()["detail"]
    _activate(email)
    assert _login(client, email, PASSWORD).status_code == 200


def test_duplicate_email_gets_the_same_answer_and_does_not_replace_the_account(client):
    email = _email()
    first = _register(client, email)
    second = _register(client, email, "another-password-for-tests-789")
    assert first.status_code == second.status_code == 201 and first.json() == second.json()
    _activate(email)
    assert _login(client, email, PASSWORD).status_code == 200
    assert _login(client, email, "another-password-for-tests-789").status_code == 401


def test_registration_rejects_other_domains_weak_passwords_and_can_be_disabled(client, monkeypatch):
    assert _register(client, f"x{uuid4().hex[:8]}@gmail.com").status_code == 400
    assert _register(client, _email(), "short").status_code == 422
    monkeypatch.setattr(settings, "SELF_REGISTRATION_ENABLED", False)
    assert _register(client, _email()).status_code == 404
    assert client.get("/v1/auth/public-config").json()["self_registration"] is False


def _forgot(client, email):
    return client.post("/v1/auth/forgot-password", json={"email": email})


def _token(response):
    return parse_qs(urlparse(response.json()["dev_reset_link"]).query)["token"][0]


def test_forgot_password_is_generic_and_only_active_accounts_get_a_link(client):
    unknown = _forgot(client, _email())
    pending = _email()
    _register(client, pending)
    inactive = _forgot(client, pending)
    active = _email()
    _register(client, active)
    _activate(active)
    known = _forgot(client, active)
    assert unknown.status_code == inactive.status_code == known.status_code == 202
    assert unknown.json()["message"] == known.json()["message"]
    assert "dev_reset_link" not in unknown.json() and "dev_reset_link" not in inactive.json()
    assert "/reset-password?token=" in known.json()["dev_reset_link"]


def test_reset_password_flow_token_is_single_use_and_stored_hashed(client):
    email = _email()
    _register(client, email)
    _activate(email)
    token = _token(_forgot(client, email))
    with engine.connect() as conn:
        stored = conn.execute(text("""SELECT token_hash FROM app_private.password_reset_tokens
            WHERE user_id = (SELECT id FROM auth.users WHERE email = :e)"""), {"e": email}).scalars().all()
    assert stored and token not in stored[0] and len(stored[0]) == 64
    old_token_login = _login(client, email, PASSWORD).json()["access_token"]
    ok = client.post("/v1/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD})
    assert ok.status_code == 200
    # No sleep here: logging in right after the reset waits out the reset second server-side.
    assert _login(client, email, NEW_PASSWORD).status_code == 200
    assert _login(client, email, PASSWORD).status_code == 401
    reused = client.post("/v1/auth/reset-password", json={"token": token, "new_password": "third-password-for-tests-000"})
    assert reused.status_code == 400
    assert _login(client, email, "third-password-for-tests-000").status_code == 401
    # A token issued before the reset no longer opens the API.
    assert client.get("/v1/auth/me", headers={"Authorization": f"Bearer {old_token_login}"}).status_code == 401


def test_new_request_invalidates_the_previous_link_and_garbage_is_rejected(client):
    email = _email()
    _register(client, email)
    _activate(email)
    first = _token(_forgot(client, email))
    second = _token(_forgot(client, email))
    assert client.post("/v1/auth/reset-password", json={"token": first, "new_password": NEW_PASSWORD}).status_code == 400
    assert client.post("/v1/auth/reset-password", json={"token": "x" * 43, "new_password": NEW_PASSWORD}).status_code == 400
    assert client.post("/v1/auth/reset-password", json={"token": second, "new_password": "short"}).status_code == 422
    assert client.post("/v1/auth/reset-password", json={"token": second, "new_password": NEW_PASSWORD}).status_code == 200


def test_expired_token_and_hourly_cap(client, monkeypatch):
    email = _email()
    _register(client, email)
    _activate(email)
    token = _token(_forgot(client, email))
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.password_reset_tokens SET expires_at = NOW() - INTERVAL '1 minute'"))
    assert client.post("/v1/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}).status_code == 400
    monkeypatch.setattr(settings, "PASSWORD_RESET_MAX_PER_HOUR", 2)
    assert "dev_reset_link" in _forgot(client, email).json()  # second request this hour
    capped = _forgot(client, email)
    assert capped.status_code == 202 and "dev_reset_link" not in capped.json()


def test_audit_records_ids_only(client):
    email = _email()
    _register(client, email)
    _activate(email)
    token = _token(_forgot(client, email))
    client.post("/v1/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD})
    with engine.connect() as conn:
        rows = conn.execute(text("""SELECT action_type, COALESCE(metadata::text, '') FROM app_private.audit_events
            WHERE object_id = (SELECT id FROM auth.users WHERE email = :e)
              AND action_type IN ('REGISTER_ACCOUNT', 'REQUEST_PASSWORD_RESET', 'RESET_PASSWORD_BY_TOKEN')"""), {"e": email}).all()
    assert {r[0] for r in rows} == {"REGISTER_ACCOUNT", "REQUEST_PASSWORD_RESET", "RESET_PASSWORD_BY_TOKEN"}
    assert not any(token in r[1] or NEW_PASSWORD in r[1] or PASSWORD in r[1] for r in rows)


def test_login_right_after_approval_waits_instead_of_returning_409(client):
    email = _email()
    _register(client, email)
    with engine.begin() as conn:  # approval stamps tokens_valid_after = now
        conn.execute(text("UPDATE app_private.user_profiles SET account_status = 'ACTIVE', tokens_valid_after = clock_timestamp() "
                          "WHERE user_id = (SELECT id FROM auth.users WHERE email = :e)"), {"e": email})
    started = time.time()
    assert _login(client, email, PASSWORD).status_code == 200
    assert time.time() - started < 3
