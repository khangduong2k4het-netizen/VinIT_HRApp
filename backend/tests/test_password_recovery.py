"""Password recovery without email: Admin resets a member's password, and the server-side emergency script
for an Admin who locked themselves out (AUTH_BACKEND=local). Disposable local *_test database only."""
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.db.database import SessionLocal, engine
from app.main import app
from app.services import local_auth
from app.services.accounts import provision_user

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import reset_admin_password  # noqa: E402

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                reason="Requires a disposable local migrated *_test database")
PASSWORD = "first-password-for-tests-123"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_BACKEND", "local")
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "synthetic-jwt-secret-not-for-production-0123456789")
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    return TestClient(app)


def _member(roles, status="ACTIVE"):
    email = f"member{uuid4().hex[:10]}@vinuni.edu.vn"
    db = SessionLocal()
    try:
        user_id = provision_user(db, email=email, password=PASSWORD, display_name="Thành Viên Thử", roles=roles,
                                 actor_id=None, bootstrap=True, account_status=status)
    finally:
        db.close()
    return email, user_id


def _bearer(user_id, email):
    token, _ = local_auth.issue_token(user_id, email)
    return {"Authorization": f"Bearer {token}"}


def _login(client, email, password):
    return client.post("/v1/auth/login", json={"email": email, "password": password})


def test_admin_resets_a_hr_password_in_local_mode_and_forces_a_change(client):
    admin_email, admin_id = _member(["ADMIN"])
    hr_email, hr_id = _member(["HR_RECRUITER"])
    done = client.post(f"/v1/admin/users/{hr_id}/reset-password", headers=_bearer(admin_id, admin_email),
                       json={"new_password": "temporary-hr-password-456"})
    assert done.status_code == 200 and done.json()["must_change_password"] is True
    assert _login(client, hr_email, PASSWORD).status_code == 401
    ok = _login(client, hr_email, "temporary-hr-password-456")
    assert ok.status_code == 200 and ok.json()["user"]["must_change_password"] is True
    with engine.connect() as conn:
        action = conn.execute(text("""SELECT action_type FROM app_private.audit_events WHERE object_id = :u
            AND action_type = 'RESET_USER_PASSWORD'"""), {"u": hr_id}).scalar_one()
    assert action == "RESET_USER_PASSWORD"


def test_emergency_script_resets_a_locked_admin_and_leaves_no_password_in_the_audit(client):
    email, user_id = _member(["ADMIN"])
    with engine.begin() as conn:  # a temporary lock-out after too many wrong passwords
        conn.execute(text("UPDATE app_private.local_credentials SET failed_attempts = 3, locked_until = NOW() + INTERVAL '30 minutes' "
                          "WHERE user_id = :u"), {"u": user_id})
    returned_id, temporary = reset_admin_password.reset(email)
    assert returned_id == user_id and len(temporary) >= 12
    login = _login(client, email, temporary)
    assert login.status_code == 200 and login.json()["user"]["must_change_password"] is True
    assert _login(client, email, PASSWORD).status_code == 401
    with engine.connect() as conn:
        audit = conn.execute(text("""SELECT metadata::text FROM app_private.audit_events WHERE object_id = :u
            AND action_type = 'EMERGENCY_RESET_PASSWORD'"""), {"u": user_id}).scalar_one()
    assert temporary not in audit and "server_script" in audit


def test_emergency_script_refuses_bad_input(client):
    email, _ = _member(["ADMIN"])
    inactive, _ = _member(["VIEWER"], status="INACTIVE")
    viewer, _ = _member(["HR_RECRUITER"])
    for args, message in (((f"nobody{uuid4().hex[:6]}@vinuni.edu.vn",), "Không tìm thấy"), ((inactive,), "INACTIVE"),
                          ((email, "short"), "12 ký tự"), ((viewer,), "không phải Admin")):
        with pytest.raises(ValueError, match=message):
            reset_admin_password.reset(*args)


def test_emergency_script_can_force_a_non_admin_and_records_the_operator(client):
    email, user_id = _member(["HR_RECRUITER"])
    _, temporary = reset_admin_password.reset(email, force=True)
    assert _login(client, email, temporary).status_code == 200
    with engine.connect() as conn:
        row = conn.execute(text("""SELECT actor_user_id, metadata->>'actor' FROM app_private.audit_events WHERE object_id = :u
            AND action_type = 'EMERGENCY_RESET_PASSWORD'"""), {"u": user_id}).one()
    assert tuple(row) == (None, "operator-cli")


def test_emergency_script_only_for_local_auth(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_BACKEND", "supabase")
    with pytest.raises(ValueError, match="AUTH_BACKEND=local"):
        reset_admin_password.reset("someone@vinuni.edu.vn")


def test_forgot_password_is_not_offered_without_an_email_channel(client, monkeypatch):
    monkeypatch.setattr(settings, "PASSWORD_RESET_DEV_ECHO", False)
    assert client.get("/v1/auth/public-config").json()["password_reset"] is False
    monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "SMTP_FROM", "tuyendung@vinuni.test")
    assert client.get("/v1/auth/public-config").json()["password_reset"] is True
