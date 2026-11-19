"""Import a JD draft from a public job-posting link: URL safety, page extraction and the API."""
import json
import os
import socket

import httpx
import pytest
from sqlalchemy import text

from app.services import jd_import
from app.services.jd_import import JDImportError, extract_job_page, fetch_page, validate_url

PUBLIC_IP = "93.184.216.34"

LD_PAGE = """<html><head><title>Ignored</title>
<script type="application/ld+json">{"@context":"http://schema.org","@type":"JobPosting",
"title":"Engineer (QA/QC and Standardization)",
"description":"&lt;p&gt;ABOUT US&lt;/p&gt;&lt;p&gt;KEY RESPONSIBILITIES&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Maintain ISO 13485 records
and procedures&lt;/li&gt;&lt;li&gt;Lead root cause analysis&lt;/li&gt;&lt;/ul&gt;&lt;p&gt;REQUIREMENTS&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Bachelor in Engineering&lt;/li&gt;&lt;li&gt;3+ years in medical device quality&lt;/li&gt;&lt;/ul&gt;",
"employmentType":"Full-time","validThrough":"2026-12-16","identifier":{"@type":"PropertyValue","value":"11227"},
"jobLocation":{"@type":"Place","address":{"@type":"PostalAddress","streetAddress":"Gia Lam","addressCountry":"VN"}}}
</script ></head><body><nav>Menu</nav></body></html>"""


@pytest.fixture
def public_dns(monkeypatch):
    """Every hostname resolves to a public address unless a test overrides it."""
    table = {}

    def fake_getaddrinfo(host, *args, **kwargs):
        ip = table.get(host, PUBLIC_IP)
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 6, "", (ip, 0))]

    monkeypatch.setattr(jd_import.socket, "getaddrinfo", fake_getaddrinfo)
    return table


# ------------------------------------------------------------------ URL safety

@pytest.mark.parametrize("url", [
    "ftp://example.com/job", "javascript:alert(1)", "https://user:pw@example.com/job",
    "https://example.com:8080/job", "example.com/job",
])
def test_rejects_unsupported_urls(url, public_dns):
    with pytest.raises(JDImportError) as exc:
        validate_url(url)
    assert exc.value.code == "INVALID_URL"


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "192.168.1.10", "169.254.169.254", "::1", "100.64.0.1"])
def test_rejects_hosts_that_resolve_to_private_addresses(ip, public_dns):
    public_dns["internal.example"] = ip
    with pytest.raises(JDImportError) as exc:
        validate_url("https://internal.example/job")
    assert exc.value.code == "PRIVATE_ADDRESS"


def test_allowlist_limits_hosts(public_dns, monkeypatch):
    monkeypatch.setattr(jd_import.settings, "JD_IMPORT_ALLOWED_HOSTS", ["talent.vn"])
    assert validate_url("https://vinuni.talent.vn/job/1")
    with pytest.raises(JDImportError) as exc:
        validate_url("https://evil.example/job")
    assert exc.value.code == "HOST_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_redirect_to_private_address_is_refused(public_dns):
    public_dns["internal.example"] = "127.0.0.1"

    def handler(request):
        return httpx.Response(302, headers={"location": "http://internal.example/admin"})

    with pytest.raises(JDImportError) as exc:
        await fetch_page("https://jobs.example/job", transport=httpx.MockTransport(handler))
    assert exc.value.code == "PRIVATE_ADDRESS"


@pytest.mark.asyncio
async def test_fetch_follows_safe_redirect_and_checks_type_and_size(public_dns, monkeypatch):
    def handler(request):
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "/new"})
        if request.url.path == "/new":
            return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=LD_PAGE)
        if request.url.path == "/pdf":
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"x" * 5000)

    transport = httpx.MockTransport(handler)
    final_url, page = await fetch_page("https://jobs.example/old", transport=transport)
    assert final_url == "https://jobs.example/new" and "JobPosting" in page
    with pytest.raises(JDImportError) as exc:
        await fetch_page("https://jobs.example/pdf", transport=transport)
    assert exc.value.code == "NOT_HTML"
    monkeypatch.setattr(jd_import.settings, "JD_IMPORT_MAX_BYTES", 1000)
    with pytest.raises(JDImportError) as exc:
        await fetch_page("https://jobs.example/big", transport=transport)
    assert exc.value.code == "TOO_LARGE"


# -------------------------------------------------------------- extraction

def test_extracts_json_ld_job_posting_despite_raw_newlines_and_trailing_junk():
    job = extract_job_page(LD_PAGE, "https://jobs.example/new")
    assert job.source == "JSON_LD"
    assert job.title == "Engineer (QA/QC and Standardization)"
    assert "- Maintain ISO 13485 records and procedures" in job.text
    assert "- 3+ years in medical device quality" in job.text
    assert job.metadata["posting_id"] == "11227" and job.metadata["valid_through"] == "2026-12-16"
    assert "Menu" not in job.text


def test_falls_back_to_visible_article_text_without_scripts():
    body = "<p>Requirements: 5 years of Python and PostgreSQL.</p>" * 10
    page = (f"<html><head><title>Backend Engineer</title><script>steal()</script></head><body>"
            f"<nav>Home Jobs</nav><article><h1>Backend Engineer</h1>{body}</article><footer>Copyright</footer></body></html>")
    job = extract_job_page(page, "https://jobs.example/b")
    assert job.source == "HTML_TEXT" and job.title == "Backend Engineer"
    assert "5 years of Python" in job.text
    assert "steal()" not in job.text and "Home Jobs" not in job.text and "Copyright" not in job.text


def test_page_without_job_content_is_refused():
    with pytest.raises(JDImportError) as exc:
        extract_job_page("<html><title>Login</title><body><form>Sign in</form></body></html>", "https://x.example")
    assert exc.value.code == "NO_CONTENT"


# -------------------------------------------------------------------- API

integration = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                 reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")

if os.environ.get("TEST_DATABASE_URL"):
    from app.db.database import engine
    from test_phase1_integration import client, headers, seed  # noqa: F401 (pytest fixtures)


@integration
def test_api_returns_a_reviewable_draft_and_audits_only_metadata(client, seed, monkeypatch):
    from app.services.llm_client import LLMError, llm_client

    async def fake_fetch(url):
        return "https://vinuni.talent.vn/job/11227", LD_PAGE

    calls = {}

    async def fake_ai(page_text, title_hint, *, source_host):
        calls["host"] = source_host
        return {"is_job_posting": True, "title": "QA/QC Engineer", "language_code": "en",
                "jd_content": "Requirements\n- 3+ years in medical device quality", "notes": ["No salary listed"],
                "posting_content": "Benefits\n- Health insurance"}

    monkeypatch.setattr(jd_import, "fetch_page", fake_fetch)
    monkeypatch.setattr(llm_client, "extract_jd_from_page", fake_ai)
    route = "/v1/positions/jd-import"
    body = {"url": "https://vinuni.talent.vn/job/engineer-qaqc-and-standardization-11227"}

    assert client.post(route, headers=headers(seed["hm"]), json=body).status_code == 403
    ok = client.post(route, headers=headers(seed["hr"]), json=body)
    assert ok.status_code == 200, ok.text
    data = ok.json()
    assert data["ai_used"] is True and data["extraction"] == "JSON_LD" and data["title"] == "QA/QC Engineer"
    assert data["jd_content"].startswith("Requirements") and data["metadata"]["posting_id"] == "11227"
    assert calls["host"] == "vinuni.talent.vn"
    assert data["posting_content"] == "Benefits\n- Health insurance"  # candidate-facing text, kept apart from the JD
    with engine.connect() as conn:
        meta = conn.execute(text("""
            SELECT metadata FROM app_private.audit_events WHERE action_type = 'IMPORT_JD_FROM_URL'
            ORDER BY created_at DESC LIMIT 1
        """)).scalar_one()
    assert meta["host"] == "vinuni.talent.vn" and meta["ai_used"] is True
    assert "medical device" not in json.dumps(meta)  # page content is never audited

    # AI unavailable: HR still gets the page text, with a note to review it.
    async def broken_ai(*args, **kwargs):
        raise LLMError("down")

    monkeypatch.setattr(llm_client, "extract_jd_from_page", broken_ai)
    fallback = client.post(route, headers=headers(seed["hr"]), json=body).json()
    assert fallback["ai_used"] is False and "3+ years in medical device quality" in fallback["jd_content"]
    assert fallback["notes"] and fallback["posting_content"] == ""

    # Not a job posting according to the AI.
    async def not_a_job(*args, **kwargs):
        return {"is_job_posting": False, "title": "", "jd_content": "", "language_code": "en", "notes": []}

    monkeypatch.setattr(llm_client, "extract_jd_from_page", not_a_job)
    assert client.post(route, headers=headers(seed["hr"]), json=body).status_code == 422

    # Unsafe links are refused before any request is made.
    monkeypatch.undo()
    refused = client.post(route, headers=headers(seed["hr"]), json={"url": "http://127.0.0.1:8000/v1/admin/users"})
    assert refused.status_code == 400


def test_sectioned_ai_output_is_flattened_to_plain_text():
    from app.services.llm_client import _jd_sections_to_text
    text = _jd_sections_to_text({"Summary": "QA engineer for 3D medical devices",
                                 "Requirements": ["Bachelor in Engineering", "ISO 13485 knowledge"]})
    assert text == "Summary\nQA engineer for 3D medical devices\n\nRequirements\n- Bachelor in Engineering\n- ISO 13485 knowledge"
    assert _jd_sections_to_text(None) == "" and _jd_sections_to_text("plain") == "plain"
