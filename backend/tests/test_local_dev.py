"""Running without Supabase (AUTH_BACKEND=local) and without AI Core (LLM_PROVIDER=mock)."""
import asyncio
import os
from uuid import uuid4

import jwt
import pytest
from pydantic import ValidationError
from sqlalchemy import text

from app.core.config import Settings, settings
from app.services import local_auth, mock_ai
from app.services.llm_client import LLMClient

SECRET = "x" * 48

JD = """We are hiring a Backend Python Engineer.
Requirements: 3+ years of Python experience building REST APIs with FastAPI or Django.
Solid PostgreSQL and SQL skills are required.
Nice to have: Docker and CI/CD pipelines."""

CV = """Senior developer.
Built REST APIs with FastAPI and Python for 5 years at Acme (2019-2024).
Designed PostgreSQL schemas and tuned SQL queries.
Bachelor of Computer Science, Hanoi University."""


# ---------------------------------------------------------------- unit tests

def test_password_hash_roundtrip_and_format():
    stored = local_auth.hash_password("correct horse battery")
    assert stored.startswith("scrypt$") and "correct" not in stored
    assert local_auth.verify_password("correct horse battery", stored)
    assert not local_auth.verify_password("wrong password!!", stored)
    assert not local_auth.verify_password("x", "not-a-hash")
    assert local_auth.hash_password("same") != local_auth.hash_password("same")  # salted


def test_local_tokens_are_accepted_by_the_existing_verifier(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", SECRET)
    token, expires_in = local_auth.issue_token("00000000-0000-0000-0000-000000000001", "a@example.org")
    payload = jwt.decode(token, SECRET, algorithms=["HS256"], audience="authenticated")
    assert payload["sub"].endswith("1") and expires_in == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def test_config_guards_development_shortcuts():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, APP_ENV="production", LLM_PROVIDER="mock")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, AUTH_BACKEND="local", SUPABASE_JWT_SECRET="short")
    assert Settings(_env_file=None, APP_ENV="development", LLM_PROVIDER="mock", AUTH_BACKEND="local",
                    SUPABASE_JWT_SECRET=SECRET).AUTH_BACKEND == "local"


def _mock_client(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
    return LLMClient()


def test_mock_ai_drafts_valid_criteria_from_the_jd(monkeypatch):
    draft = asyncio.run(_mock_client(monkeypatch).extract_criteria_from_jd(JD, "REQ-1", "Backend"))
    categories = [c["category"] for c in draft["criteria"]]
    assert "MUST_HAVE" in categories and "NICE_TO_HAVE" in categories
    must = [c for c in draft["criteria"] if c["category"] == "MUST_HAVE"]
    assert round(sum(c["weight"] for c in must), 1) == 70.0
    assert all(c["jd_reference_text"] and c["expected_evidence_keywords"] for c in draft["criteria"])
    assert any("Docker" in c["description"] for c in draft["criteria"] if c["category"] == "NICE_TO_HAVE")


def test_mock_ai_profile_and_matching_quote_the_cv_verbatim(monkeypatch):
    client = _mock_client(monkeypatch)
    profile = asyncio.run(client.extract_candidate_profile(CV, "cand-1"))
    assert profile["total_years_experience"] == 5 and "FastAPI" in profile["skills"]
    rubric = [
        {"criterion_id": "c1", "name": "Python APIs", "description": "REST APIs in Python",
         "expected_evidence_keywords": ["Python", "FastAPI"]},
        {"criterion_id": "c2", "name": "Kubernetes", "description": "Operate clusters",
         "expected_evidence_keywords": ["Kubernetes"]},
    ]
    result = asyncio.run(client.match_criterion_evidence(CV, profile, rubric, "cand-1", "v1"))
    by_id = {f["criterion_id"]: f for f in result["findings"]}
    assert by_id["c1"]["outcome"] == "STRONG_MATCH"
    assert by_id["c1"]["evidence"]["verbatim_quote"] in " ".join(CV.split())
    assert by_id["c2"]["outcome"] == "UNCLEAR" and by_id["c2"]["evidence"]["verbatim_quote"] == ""
    assert all(f["reasoning"].startswith(mock_ai.MOCK_MARK) for f in result["findings"])


def test_mock_ai_never_contacts_a_network_endpoint(monkeypatch):
    client = _mock_client(monkeypatch)
    monkeypatch.setattr(settings, "LLM_API_BASE", None)

    def boom(*_args, **_kwargs):
        raise AssertionError("network must not be used in mock mode")
    monkeypatch.setattr("httpx.AsyncClient", boom)
    assert asyncio.run(client.extract_criteria_from_jd(JD, "REQ-1", "Backend"))["criteria"]


# ---------------------------------------------------------- integration tests

integration = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                  reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")


@pytest.fixture
def local_client(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db.database import engine
    monkeypatch.setattr(settings, "AUTH_BACKEND", "local")
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", SECRET)
    monkeypatch.setattr(settings, "ADMIN_BOOTSTRAP_TOKEN", "b" * 40)
    # TRUNCATE auth.users CASCADE also empties policy tables that reference
    # users; reuse the shared reset that restores them for later tests.
    from test_accounts import reset_disposable_database
    reset_disposable_database()
    client = TestClient(app)
    yield client, engine
    client.close()


@integration
def test_local_bootstrap_login_create_user_and_change_password(local_client):
    client, engine = local_client
    email, password = f"admin-{uuid4().hex[:6]}@example.org", "Admin-password-123"
    assert client.get("/v1/auth/bootstrap-status").json() == {"available": True}
    created = client.post("/v1/auth/bootstrap", json={"email": email, "display_name": "Admin", "password": password,
                                                       "setup_token": "b" * 40})
    assert created.status_code == 201, created.text
    with engine.connect() as conn:
        stored = conn.execute(text("SELECT password_hash FROM app_private.local_credentials")).scalar_one()
    assert stored.startswith("scrypt$") and password not in stored

    assert client.post("/v1/auth/login", json={"email": email, "password": "wrong-password-1"}).status_code == 401
    assert client.post("/v1/auth/login", json={"email": "nobody@example.org", "password": password}).status_code == 401
    login = client.post("/v1/auth/login", json={"email": email.upper(), "password": password})
    assert login.status_code == 200, login.text
    admin = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = client.get("/v1/auth/me", headers=admin).json()
    assert me["system_roles"] == ["ADMIN"] and me["must_change_password"] is False

    # Admin creates an HR user with a temporary password; it must be changed first.
    hr_email = f"hr-{uuid4().hex[:6]}@example.org"
    created = client.post("/v1/admin/users", headers=admin, json={"email": hr_email, "display_name": "HR",
                                                                  "password": "Temporary-pass-1", "roles": ["HR_RECRUITER"]})
    assert created.status_code == 201, created.text
    assert client.post("/v1/admin/users", headers=admin, json={"email": hr_email.upper(), "display_name": "Dup",
                                                               "password": "Temporary-pass-1", "roles": ["HR_RECRUITER"]}).status_code == 409
    hr = {"Authorization": "Bearer " + client.post("/v1/auth/login", json={"email": hr_email, "password": "Temporary-pass-1"}).json()["access_token"]}
    assert client.get("/v1/positions", headers=hr).status_code == 403  # must change the temporary password
    assert client.post("/v1/auth/change-password", headers=hr, json={"current_password": "nope-nope-nope",
                                                                    "new_password": "Brand-new-pass-1"}).status_code == 400
    changed = client.post("/v1/auth/change-password", headers=hr, json={"current_password": "Temporary-pass-1",
                                                                       "new_password": "Brand-new-pass-1"})
    assert changed.status_code == 200, changed.text
    assert client.get("/v1/auth/me", headers=hr).status_code == 401  # old token revoked
    assert client.post("/v1/auth/login", json={"email": hr_email, "password": "Temporary-pass-1"}).status_code == 401


@integration
def test_local_login_locks_after_repeated_failures(local_client, monkeypatch):
    client, engine = local_client
    monkeypatch.setattr(settings, "LOCAL_AUTH_MAX_FAILED_ATTEMPTS", 3)
    email, password = f"lock-{uuid4().hex[:6]}@example.org", "Admin-password-123"
    assert client.post("/v1/auth/bootstrap", json={"email": email, "display_name": "A", "password": password,
                                                   "setup_token": "b" * 40}).status_code == 201
    for _ in range(3):
        assert client.post("/v1/auth/login", json={"email": email, "password": "bad-password-x"}).status_code == 401
    assert client.post("/v1/auth/login", json={"email": email, "password": password}).status_code == 429
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.local_credentials SET locked_until = NOW() - INTERVAL '1 second'"))
    assert client.post("/v1/auth/login", json={"email": email, "password": password}).status_code == 200


@integration
def test_mock_ai_generates_a_criteria_draft_through_the_api(monkeypatch):
    """AI-backed endpoint works end to end with the mock (no AI Core needed)."""
    from fastapi.testclient import TestClient
    from app.core.security import get_current_user
    from app.db.database import engine
    from app.main import app
    from starlette.requests import Request
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
    hr = str(uuid4())
    pos = str(uuid4())
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE app_private.positions CASCADE"))
        conn.execute(text("INSERT INTO auth.users(id) VALUES (:id)"), {"id": hr})
        conn.execute(text("INSERT INTO app_private.user_profiles(user_id, display_name) VALUES (:id, 'HR')"), {"id": hr})
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id, role_code) VALUES (:id, 'HR_RECRUITER')"), {"id": hr})
        conn.execute(text("INSERT INTO app_private.positions(position_id, position_code, title, created_by) VALUES (:p, :p, 'Backend', :u)"), {"p": pos, "u": hr})
        conn.execute(text("INSERT INTO app_private.position_assignments(position_id, user_id, position_role) VALUES (:p, :u, 'HR_RECRUITER')"), {"p": pos, "u": hr})
        conn.execute(text("INSERT INTO app_private.jd_versions(position_id, version_number, content_text, created_by) VALUES (:p, 1, :jd, :u)"),
                     {"p": pos, "jd": JD, "u": hr})

    async def identity(request: Request):
        return {"user_id": request.headers["x-test-user"], "email": "t@example.org"}
    app.dependency_overrides[get_current_user] = identity
    try:
        client = TestClient(app)
        response = client.post(f"/v1/criteria/generate/{pos}", headers={"x-test-user": hr})
        assert response.status_code == 202, response.text
        body = response.json()
        assert body["origin"] == "AI_DRAFT" and body["status"] == "DRAFT"
        assert {c["category"] for c in body["criteria"]} == {"MUST_HAVE", "NICE_TO_HAVE"}
        assert all(c["jd_reference_text"] for c in body["criteria"])
    finally:
        app.dependency_overrides.clear()


def test_criterion_ids_survive_pii_redaction(monkeypatch):
    # "4727-4724-9556" inside a UUID looks like a phone number to the
    # redactor; the id must still reach the model so findings map back.
    client = _mock_client(monkeypatch)
    criterion_id = "889bd77e-4727-4724-9556-6cdcd13d1f2c"
    rubric = [{"criterion_id": criterion_id, "name": "Python APIs", "description": "REST APIs in Python",
               "expected_evidence_keywords": ["Python", "FastAPI"]}]
    result = asyncio.run(client.match_criterion_evidence(CV, {}, rubric, "cand-1", "v1"))
    assert [f["criterion_id"] for f in result["findings"]] == [criterion_id]
    assert result["findings"][0]["outcome"] != "UNCLEAR"
