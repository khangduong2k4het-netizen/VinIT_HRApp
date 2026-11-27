"""Password-reset requests: a person asks with a reason, an Admin approves, a one-time link goes to the account's own
email. Disposable local *_test database only."""
import os
import re
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.db.database import SessionLocal, engine
from app.main import app
from app.services import local_auth, mailer
from app.services.accounts import provision_user

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                reason="Requires a disposable local migrated *_test database")
PASSWORD = "first-password-for-tests-123"
NEW_PASSWORD = "reset-by-link-password-456"
REASON = "Em quên mật khẩu sau kỳ nghỉ, cần vào hệ thống để xử lý hồ sơ."


@pytest.fixture()
def box(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_BACKEND", "local")
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "synthetic-jwt-secret-not-for-production-0123456789")
    monkeypatch.setattr(settings, "AUTH_PUBLIC_MAX_PER_IP_HOUR", 0)
    monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "SMTP_FROM", "tuyendung@vinuni.test")
    sent = []
    monkeypatch.setattr(mailer, "send_email", lambda to, subject, body, **kw: sent.append((to, subject, body)))
    from app.api import reset_requests
    monkeypatch.setattr(reset_requests, "send_email", lambda to, subject, body, **kw: sent.append((to, subject, body)))
    return TestClient(app), sent


def _member(roles):
    email = f"user{uuid4().hex[:10]}@vinuni.edu.vn"
    db = SessionLocal()
    try:
        user_id = provision_user(db, email=email, password=PASSWORD, display_name="Người Quên Mật Khẩu", roles=roles,
                                 actor_id=None, bootstrap=True)
    finally:
        db.close()
    return email, user_id


def _bearer(user_id, email):
    return {"Authorization": f"Bearer {local_auth.issue_token(user_id, email)[0]}"}


def _ask(client, email, reason=REASON):
    return client.post("/v1/auth/password-reset-requests", json={"email": email, "reason": reason})


def _pending(user_id=None):
    with engine.connect() as conn:
        return conn.execute(text("""SELECT request_id::text, status FROM app_private.password_reset_requests
            WHERE (CAST(:u AS uuid) IS NULL OR user_id = CAST(:u AS uuid))"""), {"u": user_id}).all()


def test_answer_is_identical_for_known_and_unknown_emails_and_only_real_accounts_get_a_request(box):
    client, _ = box
    email, user_id = _member(["HR_RECRUITER"])
    known = _ask(client, email)
    unknown = _ask(client, f"nobody{uuid4().hex[:6]}@vinuni.edu.vn")
    assert known.status_code == unknown.status_code == 202 and known.json() == unknown.json()
    rows = _pending(user_id)
    assert len(rows) == 1 and rows[0][1] == "PENDING"
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.password_reset_requests WHERE email LIKE 'nobody%'")).scalar_one() == 0


def test_one_open_request_per_account_reason_rules_and_daily_cap(box):
    client, _ = box
    email, user_id = _member(["VIEWER"])
    assert _ask(client, "not-an-email").status_code == 422
    assert _ask(client, email, "ngắn").status_code == 422
    assert _ask(client, email, "x" * 501).status_code == 422
    _ask(client, email)
    _ask(client, email)  # same answer, no second open request
    assert len(_pending(user_id)) == 1
    admin_email, admin_id = _member(["ADMIN"])
    rid = _pending(user_id)[0][0]
    assert client.post(f"/v1/admin/reset-requests/{rid}/reject", headers=_bearer(admin_id, admin_email), json={"note": "chưa xác minh"}).status_code == 200
    for _ in range(4):
        _ask(client, email)
        pending = [r for r in _pending(user_id) if r[1] == "PENDING"]
        if pending:
            client.post(f"/v1/admin/reset-requests/{pending[0][0]}/reject", headers=_bearer(admin_id, admin_email), json={})
    assert len(_pending(user_id)) == 3  # at most 3 requests per day


def test_only_an_admin_can_list_and_decide(box):
    client, _ = box
    email, user_id = _member(["HR_RECRUITER"])
    _ask(client, email)
    rid = _pending(user_id)[0][0]
    hr = _bearer(user_id, email)
    assert client.get("/v1/admin/reset-requests", headers=hr).status_code == 403
    assert client.post(f"/v1/admin/reset-requests/{rid}/approve", headers=hr).status_code == 403
    assert client.get("/v1/admin/reset-requests").status_code in (401, 403)


def test_approve_emails_a_one_time_link_to_the_account_and_never_returns_it(box):
    client, sent = box
    email, user_id = _member(["HR_RECRUITER"])
    admin_email, admin_id = _member(["ADMIN"])
    _ask(client, email)
    admin = _bearer(admin_id, admin_email)
    listed = client.get("/v1/admin/reset-requests", headers=admin).json()
    mine = [i for i in listed["items"] if i["email"] == email]
    assert mine and mine[0]["reason"] == REASON and listed["email_configured"] is True
    done = client.post(f"/v1/admin/reset-requests/{mine[0]['request_id']}/approve", headers=admin)
    assert done.status_code == 200 and "token" not in done.text and "http" not in done.text
    assert [s[0] for s in sent] == [email]
    token = re.search(r"token=([\w-]+)", sent[0][2]).group(1)
    assert client.post("/v1/admin/reset-requests/%s/approve" % mine[0]["request_id"], headers=admin).status_code == 409  # already decided
    ok = client.post("/v1/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD})
    assert ok.status_code == 200
    assert client.post("/v1/auth/reset-password", json={"token": token, "new_password": "another-password-789!"}).status_code == 400
    assert client.post("/v1/auth/login", json={"email": email, "password": NEW_PASSWORD}).status_code == 200
    with engine.connect() as conn:
        audits = {r[0]: r[1] for r in conn.execute(text("""SELECT action_type, COALESCE(metadata::text, '') FROM app_private.audit_events
            WHERE object_id = :u AND action_type IN ('REQUEST_PASSWORD_RESET_APPROVAL', 'APPROVE_PASSWORD_RESET_REQUEST')"""), {"u": user_id})}
    assert set(audits) == {"REQUEST_PASSWORD_RESET_APPROVAL", "APPROVE_PASSWORD_RESET_REQUEST"}
    assert not any(token in v or NEW_PASSWORD in v for v in audits.values())


def test_reject_sends_nothing(box):
    client, sent = box
    email, user_id = _member(["VIEWER"])
    admin_email, admin_id = _member(["ADMIN"])
    _ask(client, email)
    rid = _pending(user_id)[0][0]
    assert client.post(f"/v1/admin/reset-requests/{rid}/reject", headers=_bearer(admin_id, admin_email), json={"note": "không nhận ra người gửi"}).status_code == 200
    assert sent == [] and _pending(user_id)[0][1] == "REJECTED"


def test_without_email_the_admin_is_told_and_the_request_stays_open(box, monkeypatch):
    client, sent = box
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    email, user_id = _member(["VIEWER"])
    admin_email, admin_id = _member(["ADMIN"])
    _ask(client, email)
    rid = _pending(user_id)[0][0]
    answer = client.post(f"/v1/admin/reset-requests/{rid}/approve", headers=_bearer(admin_id, admin_email))
    assert answer.status_code == 409 and "Chưa cấu hình email" in answer.json()["detail"]
    assert sent == [] and _pending(user_id)[0][1] == "PENDING"


def test_an_admin_cannot_approve_their_own_request_and_old_requests_expire(box):
    client, sent = box
    first_email, first_id = _member(["ADMIN"])
    second_email, second_id = _member(["ADMIN"])
    _ask(client, first_email)
    rid = _pending(first_id)[0][0]
    own = client.post(f"/v1/admin/reset-requests/{rid}/approve", headers=_bearer(first_id, first_email))
    assert own.status_code == 403 and sent == []
    assert client.post(f"/v1/admin/reset-requests/{rid}/approve", headers=_bearer(second_id, second_email)).status_code == 200
    stale_email, stale_id = _member(["VIEWER"])
    _ask(client, stale_email)
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.password_reset_requests SET requested_at = NOW() - INTERVAL '8 days' WHERE user_id = :u"), {"u": stale_id})
    items = client.get("/v1/admin/reset-requests", headers=_bearer(second_id, second_email)).json()["items"]
    assert all(i["email"] != stale_email for i in items)
    assert _pending(stale_id)[0][1] == "EXPIRED"
    assert client.post(f"/v1/admin/reset-requests/{_pending(stale_id)[0][0]}/approve", headers=_bearer(second_id, second_email)).status_code == 409


def test_the_old_instant_link_is_off_by_default(box):
    client, sent = box
    email, _ = _member(["VIEWER"])
    answer = client.post("/v1/auth/forgot-password", json={"email": email})
    assert answer.status_code == 202 and sent == []
