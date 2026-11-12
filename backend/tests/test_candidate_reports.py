"""F2.09: side-by-side comparison and custom Excel/PDF export."""
import io
import os

import pytest
from sqlalchemy import text

from app.services.candidate_report import _fact_label, best_by_criterion, safe_cell


# ------------------------------------------------------------------ unit
def test_best_per_criterion_ignores_unclear_and_ties():
    criteria = [{"criterion_id": c} for c in ("a", "b", "c", "d")]
    cands = [
        {"application_id": "x", "results": {"a": {"outcome": "STRONG_MATCH"}, "b": {"outcome": "MATCH"},
                                            "c": {"outcome": "UNCLEAR"}, "d": {"outcome": "NO_MATCH"}}},
        {"application_id": "y", "results": {"a": {"outcome": "MATCH"}, "b": {"outcome": "MATCH"},
                                            "c": {"outcome": "UNCLEAR"}, "d": {"outcome": "NO_MATCH"}}},
    ]
    # a: x is better; b: everyone ties -> nobody; c: only unknowns; d: best known is "not met" -> nobody.
    assert best_by_criterion(criteria, cands) == {"a": ["x"]}


def test_spreadsheet_formula_injection_is_neutralised():
    assert safe_cell('=HYPERLINK("http://evil","x")') == '\'=HYPERLINK("http://evil","x")'
    for value in ("+1", "-1", "@SUM(A1)", "\tx"):
        assert safe_cell(value).startswith("'")
    assert safe_cell("Python") == "Python" and safe_cell(3.5) == 3.5 and safe_cell(None) is None


def test_profile_labels_use_whitelisted_keys_only():
    work = {"job_title": "Data Engineer", "company": "Acme", "start_date": "2020", "end_date": "2023",
            "email": "secret@example.test", "phone": "0901234567", "address": "1 Secret St"}
    label = _fact_label("WORK_EXPERIENCE", work)
    assert label == "Data Engineer, Acme (2020 – 2023)"
    assert "secret" not in _fact_label("CERTIFICATION", {"name": "AWS SAA", "email": "secret@example.test"})
    assert _fact_label("EDUCATION", {"degree": "BSc", "institution": "VinUni", "year": "2024"}) == "BSc, VinUni (2024)"


# ----------------------------------------------------------- integration
integration = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                 reason="Requires disposable local *_test PostgreSQL")
if os.environ.get("TEST_DATABASE_URL"):
    from app.db.database import engine
    from test_phase1_integration import client, headers, seed, uid  # noqa: F401 (pytest fixtures)


def _candidate(seed, name, outcome, *, status="MEETS_MANDATORY", score=80.0, coverage=0.9, quote="Built Python APIs"):
    """Application with identity contacts, a profile and a completed assessment on seed['cv']."""
    app_id = uid()
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"), {"id": seed["cv"]})
        conn.execute(text("INSERT INTO app_private.applications(application_id,position_id,created_by,application_status) VALUES (:a,:p,:u,'IN_REVIEW')"),
                     {"a": app_id, "p": seed["pos"], "u": seed["hr"]})
        conn.execute(text("INSERT INTO app_private.application_identities(application_id,display_name,email,phone) VALUES (:a,:n,:e,'0901234567')"),
                     {"a": app_id, "n": name, "e": name.replace(" ", ".").lower() + "@contact.example"})
        doc = conn.execute(text("""INSERT INTO app_private.application_documents(application_id,bucket,storage_path,original_filename,mime_type,size_bytes,file_processing_status)
            VALUES (:a,'cv','x','cv.pdf','application/pdf',10,'COMPLETED') RETURNING document_id"""), {"a": app_id}).scalar_one()
        profile = conn.execute(text("""INSERT INTO app_private.profile_versions(application_id,source_document_id,version_number,status)
            VALUES (:a,:d,1,'COMPLETED') RETURNING profile_version_id"""), {"a": app_id, "d": doc}).scalar_one()
        conn.execute(text("""INSERT INTO app_private.profile_facts(profile_version_id,fact_type,fact_value)
            VALUES (:p,'WORK_EXPERIENCE',CAST(:v AS jsonb))"""),
                     {"p": profile, "v": '{"job_title":"Engineer","company":"Acme","email":"leak@example.test"}'})
        assessment = conn.execute(text("""INSERT INTO app_private.assessment_runs(position_id,application_id,jd_version_id,criteria_version_id,profile_version_id,status,matching_status,matching_score,evidence_coverage,completed_at)
            VALUES (:p,:a,:jd,:cv,:pv,'COMPLETED',:ms,:sc,:cov,NOW()) RETURNING assessment_id"""),
                     {"p": seed["pos"], "a": app_id, "jd": seed["jd"], "cv": seed["cv"], "pv": profile,
                      "ms": status, "sc": score, "cov": coverage}).scalar_one()
        result = conn.execute(text("""INSERT INTO app_private.criterion_assessment_results(assessment_id,criterion_id,outcome,score,confidence,requires_hr_verification)
            VALUES (:a,:c,:o,1,0.8,false) RETURNING result_id"""), {"a": assessment, "c": seed["criterion"], "o": outcome}).scalar_one()
        conn.execute(text("""INSERT INTO app_private.evidence_items(criterion_result_id,source_document_id,verbatim_quote,page_number,verification_status)
            VALUES (:r,:d,:q,1,'VERIFIED')"""), {"r": result, "d": doc, "q": quote})
    return app_id


@integration
def test_comparison_matrix_rules_and_access(client, seed):
    hr = headers(seed["hr"])
    a = _candidate(seed, "Strong One", "STRONG_MATCH")
    b = _candidate(seed, "Plain Two", "MATCH", status="NEEDS_HR_VERIFICATION", score=60.0, coverage=0.4)
    route = f"/v1/candidate-reports/positions/{seed['pos']}/comparison"
    data = client.get(route, headers=hr, params={"application_ids": [a, b]})
    assert data.status_code == 200, data.text
    body = data.json()
    assert [c["candidate_name"] for c in body["candidates"]] == ["Strong One", "Plain Two"]  # selection order
    assert body["best_by_criterion"] == {seed["criterion"]: [a]}
    assert body["candidates"][0]["strengths"] == ["Python"] and body["candidates"][1]["needs_verification"]
    assert body["candidates"][0]["results"][seed["criterion"]]["evidence"][0]["quote"] == "Built Python APIs"
    assert body["candidates"][0]["profile"]["work"] == ["Engineer, Acme"]
    assert "contact.example" not in data.text and "0901234567" not in data.text and "leak@" not in data.text

    assert client.get(route, headers=hr, params={"application_ids": [a]}).status_code == 422          # fewer than 2
    five = [a, b] + [_candidate(seed, f"C{i}", "MATCH") for i in range(3)]
    assert client.get(route, headers=hr, params={"application_ids": five}).status_code == 422          # more than 4
    assert client.get(route, headers=headers(seed["hm"]), params={"application_ids": [a, b]}).status_code == 403
    assert client.get(route, headers=headers(seed["hr2"]), params={"application_ids": [a, b]}).status_code == 403
    # An application of another position is never compared here.
    assert client.get(route, headers=hr, params={"application_ids": [a, seed["app2"]]}).status_code == 404
    # A candidate without a current assessment cannot be mixed in.
    assert client.get(route, headers=hr, params={"application_ids": [a, seed["app"]]}).status_code == 409


@integration
def test_export_excel_and_pdf_without_contacts_with_audit(client, seed):
    from openpyxl import load_workbook
    hr = headers(seed["hr"])
    a = _candidate(seed, "Strong One", "STRONG_MATCH", quote='=HYPERLINK("http://evil.example","click")')
    _candidate(seed, "Plain Two", "MATCH", status="NEEDS_HR_VERIFICATION", score=60.0, coverage=0.4)
    route = f"/v1/candidate-reports/positions/{seed['pos']}/export"
    every = ["candidate", "rank", "application_status", "matching_status", "score", "coverage", "criteria", "evidence", "profile"]
    response = client.post(route, headers=hr, json={"format": "xlsx", "columns": every})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert response.headers["cache-control"] == "no-store"
    workbook = load_workbook(io.BytesIO(response.content))
    cells = [str(c.value) for ws in workbook.worksheets for row in ws.iter_rows() for c in row if c.value is not None]
    joined = "\n".join(cells)
    assert "Strong One" in joined and "Đáp ứng rõ" in joined and "Engineer, Acme" in joined
    assert "contact.example" not in joined and "0901234567" not in joined and "leak@" not in joined
    assert not any(c.startswith("=") for c in cells)  # CV text never becomes a formula
    assert any(c.startswith("'\"=HYPERLINK") or "=HYPERLINK" in c for c in cells)

    # Columns are optional: without "candidate" names are replaced by the application reference.
    lite = client.post(route, headers=hr, json={"format": "xlsx", "columns": ["score"], "application_ids": [a]})
    sheet = load_workbook(io.BytesIO(lite.content)).worksheets[0]
    assert [c.value for c in sheet[1]] == ["Mã hồ sơ", "Điểm"] and sheet.max_row == 2
    assert "Strong One" not in str([c.value for row in sheet.iter_rows() for c in row])

    pdf = client.post(route, headers=hr, json={"format": "pdf", "columns": every, "language": "en"})
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF") and b"contact.example" not in pdf.content

    assert client.post(route, headers=hr, json={"format": "xlsx", "columns": ["email"]}).status_code == 422
    assert client.post(route, headers=hr, json={"format": "csv"}).status_code == 422
    assert client.post(route, headers=headers(seed["hm"]), json={"format": "xlsx"}).status_code == 403
    with engine.connect() as conn:
        events = conn.execute(text("""SELECT metadata FROM app_private.audit_events
            WHERE action_type='EXPORT_CANDIDATE_REPORT' AND position_id=:p ORDER BY chain_sequence"""), {"p": seed["pos"]}).scalars().all()
    assert len(events) == 3
    assert events[0]["format"] == "xlsx" and events[0]["row_count"] == 2 and events[0]["columns"] == every
    assert events[1]["selected"] is True and events[2]["format"] == "pdf"
    assert "Strong One" not in str(events)


@integration
def test_export_needs_assessed_rows_and_respects_limit(client, seed, monkeypatch):
    from app.core.config import settings
    hr = headers(seed["hr"])
    route = f"/v1/candidate-reports/positions/{seed['pos']}/export"
    assert client.post(route, headers=hr, json={"format": "xlsx"}).status_code == 409  # criteria not approved yet
    _candidate(seed, "One", "MATCH")
    _candidate(seed, "Two", "MATCH")
    monkeypatch.setattr(settings, "EXPORT_MAX_ROWS", 1)
    assert client.post(route, headers=hr, json={"format": "xlsx"}).status_code == 413


@integration
def test_unverified_quotes_are_never_shown_or_exported(client, seed):
    hr = headers(seed["hr"])
    a = _candidate(seed, "Strong One", "STRONG_MATCH")
    b = _candidate(seed, "Plain Two", "MATCH", quote='"total_years_experience": 0')
    with engine.begin() as conn:
        conn.execute(text("""UPDATE app_private.evidence_items SET verification_status='FAILED'
            WHERE verbatim_quote LIKE '%total_years_experience%'"""))
    body = client.get(f"/v1/candidate-reports/positions/{seed['pos']}/comparison", headers=hr,
                      params={"application_ids": [a, b]}).json()
    assert body["candidates"][1]["results"][seed["criterion"]]["evidence"] == []
    exported = client.post(f"/v1/candidate-reports/positions/{seed['pos']}/export", headers=hr,
                           json={"format": "pdf", "columns": ["criteria", "evidence"]})
    assert exported.status_code == 200 and b"total_years_experience" not in exported.content
