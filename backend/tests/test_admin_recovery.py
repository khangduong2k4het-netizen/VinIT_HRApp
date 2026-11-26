"""Admin recovery by the server-held recovery key (/auth/recovery). Disposable local *_test database only."""
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api import admin_recovery
from app.core.config import settings
from app.db.database import SessionLocal, engine
from app.main import app
from app.services import local_auth
from app.services.accounts import provision_user

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                reason="Requires a disposable local migrated *_test database")
KEY = "k" * 8 + "-recovery-key-for-tests-" + "0123456789abcdef"
PASSWORD = "first-password-for-tests-123"
NEW_PASSWORD = "chosen-after-recovery-456"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_BACKEND", "local")
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "synthetic-jwt-secret-not-for-production-0123456789")
    monkeypatch.setattr(settings, "ADMIN_RECOVERY_KEY", KEY)
    admin_recovery._failures_by_ip.clear()
    admin_recovery._failures_overall.clear()
    yield TestClient(app)
    admin_recovery._failures_by_ip.clear()
    admin_recovery._failures_overall.clear()


def _member(roles, status="ACTIVE"):
    email = f"user{uuid4().hex[:10]}@vinuni.edu.vn"
    db = SessionLocal()
    try:
        user_id = provision_user(db, email=email, password=PASSWORD, display_name="Quản Trị Thử", roles=roles,
                                 actor_id=None, bootstrap=True, account_status=status)
    finally:
        db.close()
    return email, user_id


def _bearer(user_id, email):
    return {"Authorization": f"Bearer {local_auth.issue_token(user_id, email)[0]}"}


def test_page_is_off_without_a_long_key(client, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    for value in (None, "", "short-key"):
        monkeypatch.setattr(settings, "ADMIN_RECOVERY_KEY", value)
        assert client.post("/v1/auth/recovery/admins", json={"key": "anything"}).status_code == 404
        assert client.get("/v1/auth/public-config").json()["admin_recovery"] is False
    monkeypatch.setattr(settings, "ADMIN_RECOVERY_KEY", KEY)
    assert client.get("/v1/auth/public-config").json()["admin_recovery"] is True


def test_key_lists_only_admins_and_a_wrong_key_reveals_nothing(client):
    admin_email, _ = _member(["ADMIN"])
    hr_email, _ = _member(["HR_RECRUITER"])
    wrong = client.post("/v1/auth/recovery/admins", json={"key": "w" * 40})
    assert wrong.status_code == 401 and admin_email not in wrong.text
    ok = client.post("/v1/auth/recovery/admins", json={"key": KEY})
    emails = {i["email"] for i in ok.json()["items"]}
    assert ok.status_code == 200 and admin_email in emails and hr_email not in emails
    assert all(set(i) == {"user_id", "email", "display_name", "account_status"} for i in ok.json()["items"])


def test_reset_sets_a_new_password_revokes_sessions_unlocks_and_audits_without_secrets(client):
    email, user_id = _member(["ADMIN"])
    old_session = _bearer(user_id, email)
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.local_credentials SET failed_attempts = 4, locked_until = NOW() + INTERVAL '10 minutes' "
                          "WHERE user_id = :u"), {"u": user_id})
        conn.execute(text("UPDATE app_private.user_profiles SET tokens_valid_after = NOW() - INTERVAL '1 hour' WHERE user_id = :u"), {"u": user_id})
    assert client.get("/v1/auth/me", headers=old_session).status_code == 200
    done = client.post("/v1/auth/recovery/reset", json={"key": KEY, "user_id": user_id, "new_password": NEW_PASSWORD})
    assert done.status_code == 200
    assert client.get("/v1/auth/me", headers=old_session).status_code == 401
    import time
    time.sleep(1.2)
    login = client.post("/v1/auth/login", json={"email": email, "password": NEW_PASSWORD})
    assert login.status_code == 200 and login.json()["user"]["must_change_password"] is False
    assert client.post("/v1/auth/login", json={"email": email, "password": PASSWORD}).status_code == 401
    with engine.connect() as conn:
        audit = conn.execute(text("""SELECT metadata::text, actor_user_id FROM app_private.audit_events
            WHERE object_id = :u AND action_type = 'ADMIN_RECOVERY_RESET_PASSWORD'"""), {"u": user_id}).one()
    assert audit[1] is None and "recovery_page" in audit[0]
    assert KEY not in audit[0] and NEW_PASSWORD not in audit[0]


def test_reset_refuses_non_admins_inactive_admins_weak_passwords_and_wrong_keys(client):
    hr_email, hr_id = _member(["HR_RECRUITER"])
    _, off_id = _member(["ADMIN"], status="INACTIVE")
    _, admin_id = _member(["ADMIN"])
    body = {"key": KEY, "new_password": NEW_PASSWORD}
    assert client.post("/v1/auth/recovery/reset", json={**body, "user_id": hr_id}).status_code == 404
    assert client.post("/v1/auth/recovery/reset", json={**body, "user_id": off_id}).status_code == 409
    assert client.post("/v1/auth/recovery/reset", json={**body, "user_id": admin_id, "new_password": "short"}).status_code == 422
    assert client.post("/v1/auth/recovery/reset", json={**body, "user_id": admin_id, "key": "x" * 40}).status_code == 401
    assert client.post("/v1/auth/login", json={"email": hr_email, "password": PASSWORD}).status_code == 200  # untouched


def test_wrong_keys_lock_the_address_then_everyone_for_a_while(client):
    for _ in range(admin_recovery.MAX_FAILURES_PER_IP):
        assert client.post("/v1/auth/recovery/admins", json={"key": "w" * 40}).status_code == 401
    blocked = client.post("/v1/auth/recovery/admins", json={"key": KEY})
    assert blocked.status_code == 429  # even the right key while locked
    admin_recovery._failures_by_ip.clear()
    for _ in range(admin_recovery.MAX_FAILURES_OVERALL):
        admin_recovery._failures_overall.append(__import__("time").time())
    assert client.post("/v1/auth/recovery/admins", json={"key": KEY}).status_code == 429


def test_admin_count_summary_is_for_admins_only(client):
    admin_email, admin_id = _member(["ADMIN"])
    hr_email, hr_id = _member(["HR_RECRUITER"])
    ok = client.get("/v1/admin/users/summary", headers=_bearer(admin_id, admin_email))
    assert ok.status_code == 200 and ok.json()["active_admins"] >= 1
    assert client.get("/v1/admin/users/summary", headers=_bearer(hr_id, hr_email)).status_code == 403


@pytest.fixture()
def mailbox(monkeypatch):
    from app.api import admin_recovery as module
    from app.api import auth as auth_api
    sent = []
    monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "SMTP_FROM", "tuyendung@vinuni.test")
    monkeypatch.setattr(settings, "AUTH_PUBLIC_MAX_PER_IP_HOUR", 0)
    monkeypatch.setattr(module, "send_email", lambda to, subject, body, **kw: sent.append((to, subject, body)))
    auth_api._public_hits.clear()
    return sent


def _code_from(mail):
    import re
    return re.search(r"\b([A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4})\b", mail[2]).group(1)


def _ask(client, email):
    return client.post("/v1/auth/recovery/email-code", json={"email": email})


def _reset(client, email, code, password=NEW_PASSWORD):
    return client.post("/v1/auth/recovery/email-code/reset", json={"email": email, "code": code, "new_password": password})


def test_step_one_is_generic_and_only_an_active_admin_gets_a_code(client, mailbox):
    admin_email, _ = _member(["ADMIN"])
    hr_email, _ = _member(["HR_RECRUITER"])
    _member(["ADMIN"], status="INACTIVE")
    answers = [_ask(client, e) for e in (admin_email, hr_email, f"nobody{uuid4().hex[:6]}@vinuni.edu.vn")]
    assert {a.status_code for a in answers} == {202} and len({a.text for a in answers}) == 1
    assert [m[0] for m in mailbox] == [admin_email]
    code = _code_from(mailbox[0])
    assert len(code) == 14 and code not in answers[0].text and "15 phút" in mailbox[0][2]


def test_the_code_plays_the_old_password_once_then_revokes_sessions_and_audits_without_secrets(client, mailbox):
    import time
    email, user_id = _member(["ADMIN"])
    old_session = _bearer(user_id, email)
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.user_profiles SET tokens_valid_after = NOW() - INTERVAL '1 hour' WHERE user_id = :u"), {"u": user_id})
        conn.execute(text("UPDATE app_private.local_credentials SET failed_attempts = 3, locked_until = NOW() + INTERVAL '10 minutes' WHERE user_id = :u"), {"u": user_id})
    _ask(client, email)
    code = _code_from(mailbox[0])
    assert _reset(client, email, code.lower().replace("-", " ")).status_code == 200  # case / spacing do not matter
    assert _reset(client, email, code, "another-password-789!").status_code == 400  # one use
    assert client.get("/v1/auth/me", headers=old_session).status_code == 401
    time.sleep(1.2)
    assert client.post("/v1/auth/login", json={"email": email, "password": NEW_PASSWORD}).status_code == 200
    with engine.connect() as conn:
        audits = {r[0]: r[1] for r in conn.execute(text("""SELECT action_type, COALESCE(metadata::text, '') FROM app_private.audit_events
            WHERE object_id = :u AND action_type IN ('ADMIN_RECOVERY_EMAIL_CODE_SENT', 'ADMIN_RECOVERY_EMAIL_CODE_USED')"""), {"u": user_id})}
        stored = conn.execute(text("SELECT code_hash FROM app_private.admin_recovery_codes WHERE user_id = :u"), {"u": user_id}).scalars().all()
    assert set(audits) == {"ADMIN_RECOVERY_EMAIL_CODE_SENT", "ADMIN_RECOVERY_EMAIL_CODE_USED"}
    assert not any(code in v or NEW_PASSWORD in v for v in audits.values())
    assert stored and all(code not in h and len(h) == 64 for h in stored)


def test_wrong_code_five_times_cancels_it_and_all_failures_look_the_same(client, mailbox):
    email, _ = _member(["ADMIN"])
    other_email, _ = _member(["ADMIN"])
    _ask(client, email)
    code = _code_from(mailbox[0])
    answers = [_reset(client, email, "AAAA-BBBB-CCCC") for _ in range(5)]
    assert {a.status_code for a in answers} == {400} and len({a.text for a in answers}) == 1
    admin_recovery._failures_by_ip.clear()
    late = _reset(client, email, code)  # the right code arrives after the 5th wrong try: cancelled
    assert late.status_code == 400 and late.text == answers[0].text
    unknown = _reset(client, f"nobody{uuid4().hex[:6]}@vinuni.edu.vn", code)
    no_code = _reset(client, other_email, code)
    assert unknown.text == no_code.text == answers[0].text
    _ask(client, email)  # a new request replaces the cancelled code
    assert _reset(client, email, _code_from(mailbox[1])).status_code == 200


def test_expired_code_and_a_new_request_replaces_the_old_code(client, mailbox):
    email, user_id = _member(["ADMIN"])
    _ask(client, email)
    first = _code_from(mailbox[0])
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.admin_recovery_codes SET expires_at = NOW() - INTERVAL '1 minute' WHERE user_id = :u"), {"u": user_id})
    assert _reset(client, email, first).status_code == 400
    _ask(client, email)
    _ask(client, email)
    second, third = _code_from(mailbox[1]), _code_from(mailbox[2])
    assert _reset(client, email, second).status_code == 400  # replaced by the third
    assert _reset(client, email, third).status_code == 200


def test_new_password_rules_and_the_per_account_and_per_address_limits(client, mailbox, monkeypatch):
    email, _ = _member(["ADMIN"])
    for _ in range(6):
        assert _ask(client, email).status_code == 202
    assert len(mailbox) == admin_recovery.MAX_CODES_PER_HOUR  # the rest are silently ignored
    code = _code_from(mailbox[-1])
    assert _reset(client, email, code, "short").status_code == 422
    from app.api import auth as auth_api
    auth_api._public_hits.clear()
    monkeypatch.setattr(settings, "AUTH_PUBLIC_MAX_PER_IP_HOUR", 2)
    codes = [_ask(client, f"x{i}@vinuni.edu.vn").status_code for i in range(4)]
    assert codes[:2] == [202, 202] and 429 in codes[2:]
    auth_api._public_hits.clear()


def test_without_email_both_steps_say_so_and_send_nothing(client, mailbox, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    email, _ = _member(["ADMIN"])
    for response in (_ask(client, email), _reset(client, email, "AAAA-BBBB-CCCC")):
        assert response.status_code == 409 and "Chưa cấu hình email" in response.json()["detail"]
    assert mailbox == []


def test_admin_recovery_is_offered_when_either_the_key_or_email_exists(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_RECOVERY_KEY", None)
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    assert client.get("/v1/auth/public-config").json()["admin_recovery"] is False
    monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "SMTP_FROM", "tuyendung@vinuni.test")
    assert client.get("/v1/auth/public-config").json()["admin_recovery"] is True
    monkeypatch.setattr(settings, "AUTH_BACKEND", "supabase")
    assert client.get("/v1/auth/public-config").json()["admin_recovery"] is False
    assert client.post("/v1/auth/recovery/email-code", json={"email": "admin@vinuni.edu.vn"}).status_code == 404
    assert client.post("/v1/auth/recovery/email-code/reset", json={"email": "admin@vinuni.edu.vn", "code": "AAAA-BBBB-CCCC", "new_password": NEW_PASSWORD}).status_code == 404
