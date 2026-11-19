import io

import pytest
from docx import Document

from app.core.exceptions import FileValidationError
from app.services.document_processor import document_processor
from app.services.matching import matching_engine


def test_matching_uses_weights_confidence_and_coverage():
    criteria = [
        {"criterion_id": "must", "category": "MUST_HAVE", "weight_in_group": 100},
        {"criterion_id": "nice", "category": "NICE_TO_HAVE", "weight_in_group": 100},
    ]
    findings = [
        {"criterion_id": "must", "outcome": "STRONG_MATCH", "confidence": .9, "confidence_band": "HIGH"},
        {"criterion_id": "nice", "outcome": "MATCH", "confidence": .8, "confidence_band": "HIGH"},
    ]
    score, coverage, status, _, review = matching_engine.calculate_assessment_scores(criteria, findings)
    assert (score, coverage, status, review) == (94.0, 1.0, "MEETS_MANDATORY", False)
    score, coverage, status, _, review = matching_engine.calculate_assessment_scores(criteria, findings[1:])
    assert (score, coverage, status, review) == (80.0, 0.3, "NEEDS_HR_VERIFICATION", True)
    findings[0]["outcome"] = "NO_MATCH"
    assert matching_engine.calculate_assessment_scores(criteria, findings)[2] == "POSSIBLE_MISMATCH"


def test_unclear_is_excluded_from_score_but_counts_against_coverage():
    criteria = [
        {"criterion_id": "must", "category": "MUST_HAVE", "weight_in_group": 100},
        {"criterion_id": "nice", "category": "NICE_TO_HAVE", "weight_in_group": 100},
    ]
    group_weights = {"MUST_HAVE": .5, "NICE_TO_HAVE": .5}
    findings = [
        {"criterion_id": "must", "outcome": "STRONG_MATCH", "confidence": .9,
         "confidence_band": "HIGH"},
    ]
    score, coverage, status, augmented, review = matching_engine.calculate_assessment_scores(
        criteria, findings, group_weights)
    assert score == 100.0
    assert coverage == 0.5
    assert status == "NEEDS_HR_VERIFICATION"
    assert review is True
    assert augmented[1]["outcome"] == "UNCLEAR"
    assert augmented[1]["score"] is None


def test_no_scored_criteria_has_no_score_and_scored_no_match_is_zero():
    criteria = [
        {"criterion_id": "must", "category": "MUST_HAVE", "weight_in_group": 100},
        {"criterion_id": "nice", "category": "NICE_TO_HAVE", "weight_in_group": 100},
    ]
    score, coverage, status, _, _ = matching_engine.calculate_assessment_scores(criteria, [])
    assert score is None
    assert coverage == 0
    assert status == "NEEDS_HR_VERIFICATION"

    findings = [
        {"criterion_id": "must", "outcome": "NO_MATCH", "confidence": .9,
         "confidence_band": "HIGH"},
    ]
    score, coverage, status, _, _ = matching_engine.calculate_assessment_scores(criteria, findings)
    assert score == 0.0
    assert coverage == 0.7
    assert status == "POSSIBLE_MISMATCH"


def test_unverified_quotes_and_duplicates_are_not_authoritative():
    text = "Developed Python systems for five years."
    assert matching_engine.verify_verbatim_quote("Python systems for five years", text)
    assert not matching_engine.verify_verbatim_quote("Managed a completely imaginary team", text)
    pages = "--- Page 1 ---\nOther content\n--- Page 2 ---\nDeveloped Python systems for five years."
    assert matching_engine.quote_pages("Python systems for five years", pages) == [2]
    assert matching_engine.quote_pages("Python systems for five years", text) == []
    apps = [{"application_id": "a", "identity": {"email": "TEST@example.com"}},
            {"application_id": "b", "identity": {"email": "test@example.com"}},
            {"application_id": "c", "identity": {}}]
    assert matching_engine.detect_duplicates(apps) == [("a", "b", .98, "EMAIL_MATCH")]


def test_quote_span_tolerates_accents_punctuation_and_spacing():
    text = "--- Page 1 ---\nKinh nghiệm: xây dựng Python, FastAPI cho 5 năm."
    quote = "xay dung python fastapi cho 5 nam"
    span = matching_engine.find_quote_span(quote, text)
    assert span is not None
    assert "Python, FastAPI" in text[span[0]:span[1]]
    assert matching_engine.quote_pages(quote, text) == [1]


def test_matching_canonicalizes_findings_and_has_no_confidence_cliff():
    criteria = [
        {"criterion_id": "must", "category": "MUST_HAVE", "weight_in_group": 100},
        {"criterion_id": "nice", "category": "NICE_TO_HAVE", "weight_in_group": 100},
    ]
    low = [{"criterion_id": "must", "outcome": "MATCH", "confidence": .59, "confidence_band": "LOW"}]
    high = [{"criterion_id": "must", "outcome": "MATCH", "confidence": .61, "confidence_band": "MEDIUM"}]
    low_result = matching_engine.calculate_assessment_scores(criteria, low)
    high_result = matching_engine.calculate_assessment_scores(criteria, high)
    assert low_result[3][0]["outcome"] == high_result[3][0]["outcome"] == "MATCH"
    assert low_result[0] == high_result[0] == 80.0
    assert [item["criterion_id"] for item in low_result[3]] == ["must", "nice"]
    assert low_result[3][1]["outcome"] == "UNCLEAR"


@pytest.mark.asyncio
async def test_validates_file_signature_and_does_not_trust_filename():
    doc = Document(); doc.add_paragraph("Candidate experience with Python")
    out = io.BytesIO(); doc.save(out)
    mime = await document_processor.validate_file(out.getvalue(), "candidate.docx", "application/octet-stream")
    assert "wordprocessingml" in mime
    with pytest.raises(FileValidationError):
        await document_processor.validate_file(b"not a pdf", "candidate.pdf", "application/pdf")
    with pytest.raises(FileValidationError):
        await document_processor.validate_file(b"<html>bad</html>", "candidate.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def test_llm_external_endpoint_policy_fails_closed(monkeypatch):
    from app.core.config import settings
    from app.services.llm_client import LLMClient, LLMError
    instance = LLMClient()
    monkeypatch.setattr(settings, "ALLOW_EXTERNAL_API", False)
    instance.base_url = "http://127.0.0.1:11434/v1"
    instance._check_endpoint_policy()
    instance.base_url = "https://8.8.8.8/v1"
    with pytest.raises(LLMError, match="External"):
        instance._check_endpoint_policy()
    instance.base_url = None
    with pytest.raises(LLMError, match="not configured"):
        instance._check_endpoint_policy()
    instance.base_url = "https://8.8.8.8/v1"
    monkeypatch.setattr(settings, "ALLOW_EXTERNAL_API", True)
    instance._check_endpoint_policy()
    instance.base_url = "http://8.8.8.8/v1"
    with pytest.raises(LLMError, match="HTTPS"):
        instance._check_endpoint_policy()
    instance.base_url = "http://127.0.0.1:11434/v1"
    instance._check_endpoint_policy()


@pytest.mark.asyncio
async def test_blank_scanned_pdf_page_markers_do_not_count_as_cv_text(monkeypatch):
    from app.services.document_processor import DocumentType
    async def validate(*args):
        return "application/pdf"
    async def detect(*args):
        return DocumentType.PDF_SCANNED
    async def extract(*args):
        return ("\n".join(f"--- Page {i} ---" for i in range(1, 10)),
                [{"page_number": i, "content": ""} for i in range(1, 10)])
    monkeypatch.setattr(document_processor, "validate_file", validate)
    monkeypatch.setattr(document_processor, "detect_document_type", detect)
    monkeypatch.setattr(document_processor, "extract_text_from_pdf_scan", extract)
    with pytest.raises(FileValidationError, match="sufficient text"):
        await document_processor.process_document(b"%PDF-", "blank.pdf", "application/pdf")


def test_versioned_group_weights_are_used_and_invalid_confidence_is_unclear():
    criteria = [
        {"criterion_id": "must", "category": "MUST_HAVE", "weight_in_group": 100},
        {"criterion_id": "nice", "category": "NICE_TO_HAVE", "weight_in_group": 100},
    ]
    findings = [
        {"criterion_id": "must", "outcome": "STRONG_MATCH", "confidence": .9, "confidence_band": "HIGH"},
        {"criterion_id": "nice", "outcome": "MATCH", "confidence": .8, "confidence_band": "MEDIUM"},
    ]
    result = matching_engine.calculate_assessment_scores(criteria, findings, {"MUST_HAVE": .5, "NICE_TO_HAVE": .5})
    assert result[:3] == (90.0, 1.0, "MEETS_MANDATORY")
    findings[0]["confidence_band"] = "not a real band"
    result = matching_engine.calculate_assessment_scores(criteria, findings, {"MUST_HAVE": .5, "NICE_TO_HAVE": .5})
    assert result[2] == "MEETS_MANDATORY"
    assert result[3][0]["outcome"] == "STRONG_MATCH" and not result[3][0]["requires_verification"]
    findings[0].update(confidence=5, confidence_band="HIGH")
    assert matching_engine.calculate_assessment_scores(criteria, findings)[3][0]["outcome"] == "UNCLEAR"


def test_integration_database_guard_rejects_libpq_overrides():
    import os
    import subprocess
    import sys
    from pathlib import Path
    conftest = Path(__file__).with_name("conftest.py")
    for url in (
        "postgresql://postgres@localhost/hra_test?hostaddr=8.8.8.8",
        "postgresql://postgres@localhost/hra_test?dbname=production",
        "postgresql://postgres@localhost/hra_test?host=evil.example",
        "postgresql://postgres@/hra_test",  # PGHOST may be remote
    ):
        result = subprocess.run([sys.executable, str(conftest)], env={**os.environ, "TEST_DATABASE_URL": url},
                                capture_output=True, text=True, timeout=5)
        assert result.returncode != 0
        assert "explicit local disposable" in result.stderr


@pytest.mark.asyncio
async def test_llm_client_does_not_route_cv_through_environment_proxy(monkeypatch):
    from app.services.llm_client import LLMClient
    from app.core.config import settings
    captured = {}
    class FakeResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": [{"message": {"content": '{"ok":true}'}}]}
    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, *args, **kwargs):
            return FakeResponse()
    monkeypatch.setattr("app.services.llm_client.httpx.AsyncClient", FakeClient)
    monkeypatch.setattr(settings, "ALLOW_EXTERNAL_API", False)
    monkeypatch.setattr(settings, "LLM_API_BASE", "http://127.0.0.1:11434/v1")
    monkeypatch.setattr("app.services.llm_client.get_active_runtime", lambda db: {
        "provider": "local", "model_name": settings.LLM_MODEL_NAME, "api_base": settings.LLM_API_BASE, "temperature_default": .1})
    llm = LLMClient(); llm.base_url = "http://127.0.0.1:11434/v1"
    assert await llm._call_llm("system", "test") == {"ok": True}
    assert captured["trust_env"] is False


def test_database_does_not_log_cv_parameters():
    from app.db.database import engine
    assert engine.hide_parameters is True
    assert engine.echo is False


def test_coverage_rounding_cannot_promote_a_below_threshold_candidate():
    criteria = [
        {"criterion_id": "covered", "category": "MUST_HAVE", "weight_in_group": 99.9},
        {"criterion_id": "missing", "category": "MUST_HAVE", "weight_in_group": .1},
        {"criterion_id": "optional", "category": "NICE_TO_HAVE", "weight_in_group": 100},
    ]
    findings = [{"criterion_id": "covered", "outcome": "MATCH", "confidence": .9, "confidence_band": "HIGH"}]
    _, coverage, status, _, _ = matching_engine.calculate_assessment_scores(criteria, findings)
    assert coverage == .69 and status == "NEEDS_HR_VERIFICATION"
    ranked = matching_engine.rank_applications([{"latest_assessment": {"matching_status": status, "evidence_coverage": coverage}}], criteria)
    assert ranked[0]["rank_number"] is None


def test_zero_score_sorts_above_missing_score():
    rows = [
        {"id": "missing", "latest_assessment": {"matching_status": "NEEDS_HR_VERIFICATION", "matching_score": None, "evidence_coverage": .9}},
        {"id": "zero", "latest_assessment": {"matching_status": "NEEDS_HR_VERIFICATION", "matching_score": 0, "evidence_coverage": .7}},
    ]
    assert [row["id"] for row in matching_engine.rank_applications(rows, [])] == ["zero", "missing"]


def test_login_distinguishes_invalid_credentials_from_unavailable_service(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.config import settings
    from app.api import auth
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://example.test")
    monkeypatch.setattr(settings, "SUPABASE_ANON_KEY", "example")
    class AuthFailure(Exception):
        status = 400
    class FakeAuth:
        failure = AuthFailure()
        def sign_in_with_password(self, *_):
            raise self.failure
    fake = FakeAuth()
    monkeypatch.setattr(auth, "create_client", lambda *_: type("Client", (), {"auth": fake})())
    with TestClient(app) as client:
        credentials = {"email": "demo@example.test", "password": "not-a-real-password"}
        assert client.post("/v1/auth/login", json=credentials).status_code == 401
        fake.failure = RuntimeError("network failure")
        response = client.post("/v1/auth/login", json=credentials)
        assert response.status_code == 503 and "không khả dụng" in response.json()["detail"]


def test_redaction_minimises_common_vietnamese_and_english_identifiers():
    from app.services.redaction import redact_text, redact_payload, redact_professional_profile
    raw = """--- Page 1 ---
Nguyễn Văn An
Email: an.synthetic@example.test
Điện thoại: +84 912 345 678
Ngày sinh: 01/01/1990
Địa chỉ: 123 Phố Ví Dụ, Hà Nội
Giới tính: Nam
Nguyễn Văn An built Python services for five years.
Portfolio https://example.test/person
--- Page 2 ---
Professional experience: 2015 - 2024.
"""
    redacted = redact_text(raw, detect_first_line_name=True)
    for secret in ("Nguyễn Văn An", "an.synthetic@example.test", "912 345 678", "01/01/1990", "123 Phố", "Nam", "example.test/person"):
        assert secret not in redacted
    assert "built Python services for five years" in redacted
    assert "--- Page 2 ---" in redacted and "2015 - 2024" in redacted
    assert redact_text(redacted, detect_first_line_name=True) == redacted
    clean = redact_payload({"email": "x@example.test", "skills": ["Python"], "work_history": [{"phone": "123456789", "description": "Contact x@example.test"}]})
    assert "email" not in clean and "phone" not in clean["work_history"][0]
    assert "x@example.test" not in str(clean) and clean["skills"] == ["Python"]
    structured = redact_professional_profile({
        "name": "Synthetic Candidate", "email": "x@example.test", "skills": ["Python"],
        "certifications": [{"name": "Cloud Practitioner", "email": "x@example.test"}],
        "languages": [{"name": "English", "level": "Professional", "gender": "X"}],
        "projects": [{"name": "Search Platform", "description": "Built a service"}],
        "work_history": [{"name": "Synthetic Candidate", "role": "Developer"}],
    })
    assert "name" not in structured and "email" not in str(structured) and "gender" not in str(structured)
    assert structured["certifications"][0]["name"] == "Cloud Practitioner"
    assert structured["languages"][0]["name"] == "English"
    assert structured["projects"][0]["name"] == "Search Platform"
    assert "name" not in structured["work_history"][0]


def test_profile_page_numbers_are_sanitized_before_database_insert():
    from app.services.llm_client import normalize_profile_page_number, sanitize_profile_page_numbers

    assert normalize_profile_page_number(1) == 1
    assert normalize_profile_page_number("2") == 2
    assert normalize_profile_page_number(3.0) == 3
    assert normalize_profile_page_number("Page 1") is None
    assert normalize_profile_page_number(["1"]) is None
    assert normalize_profile_page_number(True) is None
    assert normalize_profile_page_number(0) is None

    profile = sanitize_profile_page_numbers({
        "education": [{"page_number": "Page 1"}],
        "work_history": [{"page_number": "2"}],
        "certifications": [{"page_number": 1.0}],
        "languages": [{"page_number": {"page": 1}}],
        "projects": ["Synthetic project"],
    })
    assert profile["education"][0]["page_number"] is None
    assert profile["work_history"][0]["page_number"] == 2
    assert profile["certifications"][0]["page_number"] == 1
    assert profile["languages"][0]["page_number"] is None


def test_criteria_direct_approval_roles():
    from fastapi import HTTPException

    from app.api.criteria import criteria_decision
    from app.schemas.criteria import ApprovalAction

    # The original HR -> HM workflow remains unchanged.
    assert criteria_decision("DRAFT", ApprovalAction.APPROVE, {"HR_RECRUITER"}, set()) == (
        "PENDING_HM_APPROVAL", "HR_RECRUITER")
    assert criteria_decision("PENDING_HM_APPROVAL", ApprovalAction.APPROVE, {"HIRING_MANAGER"}, set()) == (
        "APPROVED", "HIRING_MANAGER")

    # The supplementary path is available to Admin/HR Lead and to the assigned
    # HR Recruiter (who must also accept responsibility, checked by the endpoint)
    # from every non-final approval state, but never to an HM or an outsider.
    for status in ("DRAFT", "PENDING_HR_REVIEW", "PENDING_HM_APPROVAL"):
        assert criteria_decision(status, ApprovalAction.DIRECT_APPROVE, {"HR_RECRUITER"}, set()) == (
            "APPROVED", "HR_RECRUITER")
        # Someone who is both HR Lead and the assigned recruiter acts as HR Lead.
        assert criteria_decision(status, ApprovalAction.DIRECT_APPROVE, {"HR_RECRUITER"}, {"HR_LEAD"}) == (
            "APPROVED", "HR_LEAD")
        assert criteria_decision(status, ApprovalAction.DIRECT_APPROVE, set(), {"ADMIN"}) == (
            "APPROVED", "ADMIN")
        assert criteria_decision(status, ApprovalAction.DIRECT_APPROVE, {"HR_LEAD"}, set()) == (
            "APPROVED", "HR_LEAD")
        assert criteria_decision(status, ApprovalAction.DIRECT_APPROVE, set(), {"HR_LEAD"}) == (
            "APPROVED", "HR_LEAD")
        for position_roles, system_roles in (({"HIRING_MANAGER"}, set()), (set(), {"HR_RECRUITER"}), (set(), set())):
            with pytest.raises(HTTPException) as exc:
                criteria_decision(status, ApprovalAction.DIRECT_APPROVE, position_roles, system_roles)
            assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_profile_accepts_certifications_returned_as_plain_names(monkeypatch):
    """gpt-4o-mini lists certifications as strings; that must not fail the CV."""
    from app.services.llm_client import LLMClient
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": __import__("json").dumps({
            "candidate_identifier": "fake", "total_years_experience": 3, "education": [], "work_history": [],
            "skills": ["Python"], "certifications": ["AWS Solutions Architect", {"name": "CCNA"}],
            "languages": [], "projects": []})}}]}
    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs): return FakeResponse()
    monkeypatch.setattr("app.services.llm_client.httpx.AsyncClient", FakeClient)
    from app.core.config import settings
    monkeypatch.setattr(settings, "LLM_API_BASE", "http://127.0.0.1:11434/v1")
    monkeypatch.setattr("app.services.llm_client.get_active_runtime", lambda db: {
        "provider": "local", "model_name": settings.LLM_MODEL_NAME, "api_base": settings.LLM_API_BASE, "temperature_default": .1})
    llm = LLMClient(); llm.base_url = "http://127.0.0.1:11434/v1"
    profile = await llm.extract_candidate_profile("Synthetic CV with AWS and CCNA certificates.", "synthetic-id")
    assert [c["name"] for c in profile["certifications"]] == ["AWS Solutions Architect", "CCNA"]


@pytest.mark.asyncio
async def test_real_llm_boundary_redacts_cv_profile_and_rubric_and_sets_guardrails(monkeypatch):
    from app.services.llm_client import LLMClient
    captured = []
    class FakeResponse:
        def __init__(self, payload): self.payload = payload
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": __import__("json").dumps(self.payload)}}]}
    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            captured.append(kwargs["json"])
            if len(captured) == 1:
                return FakeResponse({"candidate_identifier": "fake", "total_years_experience": 2,
                                     "education": [], "work_history": [], "skills": ["Python"],
                                     "certifications": [{"name": "Cloud Practitioner", "email": "x@example.test"}]})
            return FakeResponse({"candidate_identifier": "fake", "rubric_version": "fake", "findings": []})
    monkeypatch.setattr("app.services.llm_client.httpx.AsyncClient", FakeClient)
    from app.core.config import settings
    monkeypatch.setattr(settings, "LLM_API_BASE", "http://127.0.0.1:11434/v1")
    monkeypatch.setattr("app.services.llm_client.get_active_runtime", lambda db: {
        "provider": "local", "model_name": settings.LLM_MODEL_NAME, "api_base": settings.LLM_API_BASE, "temperature_default": .1})
    llm = LLMClient(); llm.base_url = "http://127.0.0.1:11434/v1"
    cv = "Nguyễn Văn An\nEmail: an.synthetic@example.test\nPhone: +84 912 345 678\nBuilt Python services for two years."
    profile = await llm.extract_candidate_profile(cv, "synthetic-id")
    assert profile["candidate_identifier"] == "synthetic-id"
    assert profile["certifications"][0]["name"] == "Cloud Practitioner"
    assert "email" not in profile["certifications"][0]
    await llm.match_criterion_evidence(cv, {"email": "an.synthetic@example.test", "skills": ["Python"],
        "languages": [{"name": "English", "phone": "123456789"}],
        "projects": [{"name": "Search Platform", "description": "Python services"}]},
        [{"criterion_id": "criterion", "name": "Python", "description": "Contact hr@example.test", "category": "MUST_HAVE"}],
        "synthetic-id", "synthetic-rubric")
    for payload in captured:
        sent = str(payload["messages"][1]["content"])
        assert "Nguyễn Văn An" not in sent and "an.synthetic@example.test" not in sent and "912 345 678" not in sent
        assert "Python" in sent and "REDACTED" in sent
        system = payload["messages"][0]["content"]
        assert "untrusted data" in system and "protected traits" in system and "human" in system
    assert "hr@example.test" not in str(captured[1])
    assert "English" in str(captured[1]) and "Search Platform" in str(captured[1])
    assert "123456789" not in str(captured[1])
