"""F2.06 image OCR / DOCX images and F2.07 retention automation.

Unit tests use synthetic images and documents only. Tests that need the
Tesseract binary are skipped when it is not installed. Integration tests use
the disposable PostgreSQL database from TEST_DATABASE_URL (see README).
"""
import asyncio
import io
import os
import shutil
from datetime import date, datetime, timedelta, timezone

import pytest
from docx import Document
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.core.config import settings
from app.core.exceptions import FileValidationError
from app.services import document_processor as dp

HAS_TESSERACT = shutil.which("tesseract") is not None
needs_tesseract = pytest.mark.skipif(not HAS_TESSERACT, reason="Tesseract binary is not installed")
LINES = [
    "Synthetic Candidate CV",
    "Experience: Senior Accountant, 5 years general ledger and IFRS reporting",
    "Skills: Python, SQL, Excel, financial reporting, procurement, budgeting",
    "Education: Bachelor of Accounting 2018",
    "Certifications: ACCA member, CPA candidate",
]


def _font(size):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def synthetic_page(width=2480, height=3508, size=48):
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font, y = _font(size), 200
    for _ in range(4):
        for line in LINES:
            draw.text((150, y), line, fill="black", font=font)
            y += int(size * 1.6)
    return image


def to_bytes(image, fmt="PNG"):
    buffer = io.BytesIO()
    image.save(buffer, fmt)
    return buffer.getvalue()


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- F2.06 unit


def test_validate_accepts_png_and_jpeg_by_magic_bytes():
    page = synthetic_page(600, 800)
    assert run(dp.document_processor.validate_file(to_bytes(page), "cv.png", "image/png")) == "image/png"
    assert run(dp.document_processor.validate_file(to_bytes(page, "JPEG"), "cv.JPG", "image/jpeg")) == "image/jpeg"
    assert run(dp.document_processor.validate_file(to_bytes(page, "JPEG"), "cv.jpeg", "x")) == "image/jpeg"


@pytest.mark.parametrize("name,payload", [
    ("cv.png", b"\xff\xd8\xff" + b"0" * 100),        # JPEG bytes with a PNG name
    ("cv.jpg", b"\x89PNG\r\n\x1a\n" + b"0" * 100),    # PNG bytes with a JPG name
    ("cv.gif", b"GIF89a" + b"0" * 100),
])
def test_validate_rejects_mismatched_or_unsupported_images(name, payload):
    with pytest.raises(FileValidationError):
        run(dp.document_processor.validate_file(payload, name, "image/png"))


def test_validate_rejects_images_over_pixel_limit(monkeypatch):
    monkeypatch.setattr(settings, "OCR_MAX_IMAGE_PIXELS", 100_000)
    with pytest.raises(FileValidationError):
        run(dp.document_processor.validate_file(to_bytes(synthetic_page(600, 800)), "cv.png", "image/png"))


def test_mime_extensions_cover_images():
    assert dp.MIME_EXTENSIONS["image/jpeg"] == ".jpg" and dp.MIME_EXTENSIONS["image/png"] == ".png"


def test_low_resolution_image_goes_to_manual_queue_before_ocr(monkeypatch):
    monkeypatch.setattr(dp, "_ocr", lambda image: pytest.fail("OCR must not run on a low-resolution image"))
    with pytest.raises(dp.DocumentQualityError) as error:
        run(dp.document_processor.extract_text_from_image(to_bytes(synthetic_page().resize((827, 1170)))))
    assert error.value.code == "IMAGE_LOW_RESOLUTION"
    assert error.value.quality["estimated_dpi"] < settings.OCR_MIN_DPI
    assert "Synthetic" not in error.value.message


def test_a4_at_150_dpi_is_not_low_resolution():
    assert dp.estimate_dpi(Image.new("L", (1240, 1754), 255)) >= 150


def test_blurry_image_goes_to_manual_queue_before_ocr(monkeypatch):
    monkeypatch.setattr(dp, "_ocr", lambda image: pytest.fail("OCR must not run on a blurry image"))
    blurry = synthetic_page().filter(ImageFilter.GaussianBlur(8))
    with pytest.raises(dp.DocumentQualityError) as error:
        run(dp.document_processor.extract_text_from_image(to_bytes(blurry)))
    assert error.value.code == "IMAGE_BLURRY"


def test_deskew_estimate_recovers_small_rotation():
    gray = synthetic_page().convert("L").rotate(4, expand=True, fillcolor=255)
    assert abs(dp.estimate_skew_angle(gray) + 4) <= 1.0


def test_docx_reads_tables_in_body_order_and_skips_small_images():
    document = Document()
    document.add_paragraph("Synthetic Candidate summary paragraph")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Skill", "Level"
    table.cell(1, 0).text, table.cell(1, 1).text = "IFRS reporting", "Advanced"
    document.add_paragraph("Closing paragraph after the table")
    logo = io.BytesIO(to_bytes(Image.new("RGB", (60, 60), "navy")))
    document.add_picture(logo)
    buffer = io.BytesIO()
    document.save(buffer)

    text, pages = run(dp.document_processor.extract_text_from_docx(buffer.getvalue()))
    assert text.splitlines() == ["Synthetic Candidate summary paragraph", "Skill | Level",
                                 "IFRS reporting | Advanced", "Closing paragraph after the table"]
    assert len(pages) == 1
    assert pages[0]["docx_stats"]["embedded_images"] == 1 and pages[0]["docx_stats"]["skipped_small"] == 1
    summary = dp.document_quality_summary(pages)
    assert summary["docx"]["skipped_small"] == 1 and summary["images"] == []


def test_image_only_docx_with_blurry_scan_needs_hr_review():
    document = Document()
    blurry = synthetic_page().filter(ImageFilter.GaussianBlur(8))
    document.add_picture(io.BytesIO(to_bytes(blurry, "JPEG")))
    buffer = io.BytesIO()
    document.save(buffer)
    with pytest.raises(dp.DocumentQualityError) as error:
        run(dp.document_processor.extract_text_from_docx(buffer.getvalue()))
    assert error.value.code == "DOCX_IMAGES_LOW_QUALITY"


def test_quality_summary_is_numeric_only():
    pages = [{"page_number": 1, "content": "Synthetic secret text", "ocr_confidence": {"conf": [90]},
              "image_quality": {"source": "IMAGE", "width": 10, "height": 20, "estimated_dpi": 300.0,
                                "sharpness": 50.0, "orientation_rotation": 0, "deskew_degrees": 0.0}}]
    summary = dp.document_quality_summary(pages)
    assert "Synthetic" not in str(summary) and summary["images"][0]["estimated_dpi"] == 300.0


@needs_tesseract
def test_image_cv_is_ocred_after_rotation_and_skew():
    page = synthetic_page().rotate(90, expand=True).rotate(3, expand=True, fillcolor="white")
    text, pages, doc_type = run(dp.document_processor.process_document(to_bytes(page, "JPEG"), "cv.jpg", "image/jpeg"))
    assert doc_type == dp.DocumentType.IMAGE
    assert "ACCA" in text and "Accountant" in text
    assert pages[0]["image_quality"]["orientation_rotation"] in (90, 270)
    assert pages[0]["ocr_confidence"]["conf"]


@needs_tesseract
def test_docx_embedded_scan_becomes_an_extra_page():
    document = Document()
    document.add_paragraph("Synthetic Candidate cover text for the DOCX body")
    document.add_picture(io.BytesIO(to_bytes(synthetic_page(), "PNG")))
    buffer = io.BytesIO()
    document.save(buffer)
    text, pages, doc_type = run(dp.document_processor.process_document(buffer.getvalue(), "cv.docx", "x"))
    assert doc_type == dp.DocumentType.DOCX and len(pages) == 2
    assert pages[1]["page_number"] == 2 and "ACCA" in pages[1]["content"]
    assert "--- Embedded image 1 ---" in text
    assert pages[0]["docx_stats"]["ocr_images"] == 1


# ------------------------------------------------------- F2.07 integration

integration = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                 reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")

if os.environ.get("TEST_DATABASE_URL"):
    from sqlalchemy import text

    from app.db.database import engine
    from app.services import retention_automation as automation
    from test_phase1_integration import client, headers, purge_with_otp, seed, uid  # noqa: F401


@pytest.fixture(autouse=True)
def _twelve_month_policy():
    """These scenarios are written for a 12-month policy; pin it, then restore what was approved."""
    if not os.environ.get("TEST_DATABASE_URL"):
        yield
        return
    with engine.begin() as conn:
        approved = list(conn.execute(text(
            "SELECT policy_version FROM app_private.retention_policy_versions WHERE status = 'APPROVED'")).scalars())
        conn.execute(text("""INSERT INTO app_private.retention_policy_versions (policy_version, retention_months, trigger_event, status)
            VALUES ('v1.0-12month', 12, 'POSITION_CLOSED', 'APPROVED') ON CONFLICT (policy_version) DO NOTHING"""))
        conn.execute(text("UPDATE app_private.retention_policy_versions SET status = 'SUPERSEDED' WHERE status = 'APPROVED'"))
        conn.execute(text("UPDATE app_private.retention_policy_versions SET status = 'APPROVED' WHERE policy_version = 'v1.0-12month'"))
    yield
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.retention_policy_versions SET status = 'SUPERSEDED' WHERE status = 'APPROVED'"))
        conn.execute(text("UPDATE app_private.retention_policy_versions SET status = 'APPROVED' WHERE policy_version = ANY(:v)"),
                     {"v": approved or ["v1.0-12month"]})


def _close(seed, *, months_ago=None, days_until_due=None, position="pos"):
    """Close a position so that its 12-month due date lands where requested."""
    now = datetime.now(timezone.utc)
    if days_until_due is not None:
        due = now + timedelta(days=days_until_due, hours=1)
        # add_months(closed_at, 12) == due for these synthetic dates
        closed_at = due.replace(year=due.year - 1)
    else:
        closed_at = now.replace(year=now.year - 1) - timedelta(days=30 * (months_ago - 12))
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE app_private.positions SET status = 'CLOSED', closed_at = :closed WHERE position_id = :p
        """), {"closed": closed_at, "p": seed[position]})
    return closed_at


def _grant_lead(seed, user="hr", position="pos"):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO app_private.position_access_grants (position_id, user_id, permission_code)
            VALUES (:p, :u, 'CONFIRM_DELETION') ON CONFLICT DO NOTHING
        """), {"p": seed[position], "u": seed[user]})


def _make_global_lead(seed, user="other"):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id, role_code) VALUES (:u, 'HR_LEAD')"),
                     {"u": seed[user]})


@integration
def test_cycle_creates_upcoming_cases_and_one_reminder_per_milestone(client, seed):
    _close(seed, days_until_due=20)
    _make_global_lead(seed)
    first = automation.run_retention_cycle()
    assert first["skipped"] is False and first["cases_created"] == 1
    # HR of the position + global HR Leads (earlier tests may leave other
    # synthetic HR Leads in auth.users); the 30-day milestone is reached.
    assert first["in_app_reminders_sent"] >= 2
    lead_notes = client.get("/v1/retention/notifications", headers=headers(seed["other"])).json()
    assert [n["milestone_days"] for n in lead_notes] == [30]
    second = automation.run_retention_cycle()
    assert second["cases_created"] == 0 and second["in_app_reminders_sent"] == 0

    queue = client.get("/v1/retention/queue", headers=headers(seed["hr"])).json()
    case = queue["cases"][0]
    assert case["status"] == "PENDING" and case["is_due"] is False and case["days_until_due"] == 21
    assert queue["settings"]["notice_window_days"] == 30

    notes = client.get("/v1/retention/notifications", headers=headers(seed["hr"])).json()
    assert [(n["milestone_days"], n["open_case_count"]) for n in notes] == [(30, 1)]
    assert "Candidate" not in str(notes)
    assert client.get("/v1/retention/notifications", headers=headers(seed["hm"])).json() == []
    read = client.post(f"/v1/retention/notifications/{notes[0]['notification_id']}/read", headers=headers(seed["hr"]))
    assert read.status_code == 200
    assert client.get("/v1/retention/notifications", headers=headers(seed["hr"]),
                      params={"unread_only": True}).json() == []
    # Not due yet: confirmation is still refused.
    _grant_lead(seed)
    assert client.post(f"/v1/retention/cases/{case['retention_case_id']}/confirm",
                       headers=headers(seed["hr"]), json={}).status_code == 422


@integration
def test_late_cycle_sends_only_the_most_urgent_milestone(seed):
    _close(seed, days_until_due=5)
    automation.run_retention_cycle()
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT milestone_days, status FROM app_private.retention_notifications
            WHERE recipient_user_id = :u ORDER BY milestone_days
        """), {"u": seed["hr"]}).all()
    assert [tuple(row) for row in rows] == [(7, "SENT"), (15, "SKIPPED"), (30, "SKIPPED")]


@integration
def test_reopening_position_cancels_open_cases_and_restarts_cycle(client, seed):
    _close(seed, months_ago=13)
    _grant_lead(seed)
    generated = client.post(f"/v1/retention/positions/{seed['pos']}/cases/generate", headers=headers(seed["hr"]))
    case_id = generated.json()["cases"][0]["retention_case_id"]
    assert client.post(f"/v1/retention/cases/{case_id}/confirm", headers=headers(seed["hr"]), json={}).status_code == 200

    reopened = client.patch(f"/v1/positions/{seed['pos']}", headers=headers(seed["hr"]), json={"status": "OPEN"})
    assert reopened.status_code == 200, reopened.text
    listed = client.get(f"/v1/retention/positions/{seed['pos']}/cases", headers=headers(seed["hr"])).json()
    assert [(c["status"], c["cancel_reason"]) for c in listed] == [("CANCELLED", "POSITION_REOPENED")]
    with engine.connect() as conn:
        job = conn.execute(text("SELECT status, error FROM app_private.deletion_jobs WHERE retention_case_id = :c"),
                           {"c": case_id}).mappings().one()
    assert job["status"] == "FAILED" and job["error"] == "CANCELLED_POSITION_REOPENED"

    # Closing again starts a new 12-month period: nothing is due now.
    closed = client.patch(f"/v1/positions/{seed['pos']}", headers=headers(seed["hr"]), json={"status": "CLOSED"})
    assert closed.status_code == 200, closed.text
    regenerated = client.post(f"/v1/retention/positions/{seed['pos']}/cases/generate", headers=headers(seed["hr"]))
    assert regenerated.json()["created_count"] == 0


@integration
def test_extending_retention_to_five_years_cancels_cases_of_the_old_policy(client, seed):
    """Cases created under the 12-month policy must not delete data once 5 years is approved."""
    _close(seed, months_ago=13)
    _grant_lead(seed)
    generated = client.post(f"/v1/retention/positions/{seed['pos']}/cases/generate", headers=headers(seed["hr"]))
    case_id = generated.json()["cases"][0]["retention_case_id"]
    assert client.post(f"/v1/retention/cases/{case_id}/confirm", headers=headers(seed["hr"]), json={}).status_code == 200
    with engine.begin() as conn:
        old = conn.execute(text("""SELECT policy_version FROM app_private.retention_policy_versions
            WHERE status = 'APPROVED' ORDER BY created_at DESC LIMIT 1""")).scalar_one()
        conn.execute(text("UPDATE app_private.retention_policy_versions SET status = 'SUPERSEDED' WHERE policy_version = :v"), {"v": old})
        conn.execute(text("""INSERT INTO app_private.retention_policy_versions (policy_version, retention_months, trigger_event, status)
            VALUES ('test-60month', 60, 'POSITION_CLOSED', 'APPROVED')"""))
    try:
        summary = automation.run_retention_cycle()
        assert summary["cases_cancelled_policy_extended"] == 1 and summary["cases_created"] == 0
        listed = client.get(f"/v1/retention/positions/{seed['pos']}/cases", headers=headers(seed["hr"])).json()
        assert [(c["status"], c["cancel_reason"]) for c in listed] == [("CANCELLED", "POLICY_EXTENDED")]
        with engine.connect() as conn:
            job = conn.execute(text("SELECT status, error FROM app_private.deletion_jobs WHERE retention_case_id = :c"),
                               {"c": case_id}).mappings().one()
            audited = conn.execute(text("""SELECT COUNT(*) FROM app_private.audit_events
                WHERE action_type = 'CANCEL_RETENTION_CASES_POLICY_EXTENDED'""")).scalar_one()
        assert job["status"] == "FAILED" and job["error"] == "CANCELLED_POLICY_EXTENDED" and audited == 1
        # 13 months after closing is far from the 5-year due date: nothing new, and a rerun is a no-op.
        regenerated = client.post(f"/v1/retention/positions/{seed['pos']}/cases/generate", headers=headers(seed["hr"]))
        assert regenerated.json()["created_count"] == 0 and regenerated.json()["retention_months"] == 60
        assert automation.run_retention_cycle()["cases_cancelled_policy_extended"] == 0
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE app_private.retention_policy_versions SET status = 'APPROVED' WHERE policy_version = :v"), {"v": old})
            conn.execute(text("UPDATE app_private.application_retention_cases SET policy_version = :v WHERE policy_version = 'test-60month'"),
                         {"v": old})
            conn.execute(text("DELETE FROM app_private.retention_policy_versions WHERE policy_version = 'test-60month'"))


@integration
def test_stale_case_of_an_earlier_closure_cannot_be_purged(client, seed):
    _close(seed, months_ago=13)
    _grant_lead(seed)
    case_id = client.post(f"/v1/retention/positions/{seed['pos']}/cases/generate",
                          headers=headers(seed["hr"])).json()["cases"][0]["retention_case_id"]
    client.post(f"/v1/retention/cases/{case_id}/confirm", headers=headers(seed["hr"]), json={})
    # Reopened and re-closed outside the API (e.g. a data fix): the guard still holds.
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET closed_at = NOW() WHERE position_id = :p"), {"p": seed["pos"]})
    settings.RETENTION_OTP_DEV_ECHO = True
    try:
        response = client.post(f"/v1/retention/cases/{case_id}/purge-otp", headers=headers(seed["hr"]))
    finally:
        settings.RETENTION_OTP_DEV_ECHO = False
    assert response.status_code == 409
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.applications WHERE application_id = :a"),
                            {"a": seed["app"]}).scalar_one() == 1


@integration
def test_hold_blocks_deletion_until_released(client, seed):
    _close(seed, months_ago=13)
    _grant_lead(seed)
    case_id = client.post(f"/v1/retention/positions/{seed['pos']}/cases/generate",
                          headers=headers(seed["hr"])).json()["cases"][0]["retention_case_id"]
    client.post(f"/v1/retention/cases/{case_id}/confirm", headers=headers(seed["hr"]), json={})

    bad = client.post(f"/v1/retention/cases/{case_id}/hold", headers=headers(seed["hr"]),
                      json={"reason_code": "COMPLAINT", "legal_approval_reference": "Nguyen Van A complained!"})
    assert bad.status_code == 422  # free text with punctuation is refused
    assert client.post(f"/v1/retention/cases/{case_id}/hold", headers=headers(seed["hm"]),
                       json={"reason_code": "COMPLAINT", "legal_approval_reference": "PC-2026/015"}).status_code == 403
    held = client.post(f"/v1/retention/cases/{case_id}/hold", headers=headers(seed["hr"]), json={
        "reason_code": "COMPLAINT", "legal_approval_reference": "PC-2026/015",
        "hold_until": (date.today() + timedelta(days=60)).isoformat()})
    assert held.status_code == 200, held.text
    assert held.json()["status"] == "ON_HOLD" and held.json()["hold"]["legal_approval_reference"] == "PC-2026/015"

    assert client.post(f"/v1/retention/cases/{case_id}/confirm", headers=headers(seed["hr"]), json={}).status_code == 409
    settings.RETENTION_OTP_DEV_ECHO = True
    try:
        assert client.post(f"/v1/retention/cases/{case_id}/purge-otp", headers=headers(seed["hr"])).status_code == 409
    finally:
        settings.RETENTION_OTP_DEV_ECHO = False
    # The cycle must not recreate a case for a held application.
    assert automation.run_retention_cycle()["cases_created"] == 0

    released = client.post(f"/v1/retention/cases/{case_id}/release-hold", headers=headers(seed["hr"]))
    assert released.status_code == 200 and released.json()["status"] == "PENDING"
    with engine.connect() as conn:
        actions = conn.execute(text("""
            SELECT action_type FROM app_private.audit_events WHERE object_id = :c ORDER BY chain_sequence
        """), {"c": case_id}).scalars().all()
    assert "PLACE_RETENTION_HOLD" in actions and "RELEASE_RETENTION_HOLD" in actions


@integration
def test_purge_otp_is_single_use_and_limits_attempts(client, seed, monkeypatch):
    _close(seed, months_ago=13)
    _grant_lead(seed)
    case_id = client.post(f"/v1/retention/positions/{seed['pos']}/cases/generate",
                          headers=headers(seed["hr"])).json()["cases"][0]["retention_case_id"]
    client.post(f"/v1/retention/cases/{case_id}/confirm", headers=headers(seed["hr"]), json={})

    # Production without SMTP: no channel to send the code, purge is refused.
    assert client.post(f"/v1/retention/cases/{case_id}/purge-otp", headers=headers(seed["hr"])).status_code == 503

    monkeypatch.setattr(settings, "RETENTION_OTP_DEV_ECHO", True)
    monkeypatch.setattr(settings, "RETENTION_OTP_MAX_ATTEMPTS", 2)
    challenge = client.post(f"/v1/retention/cases/{case_id}/purge-otp", headers=headers(seed["hr"])).json()
    wrong = "000000" if challenge["dev_code"] != "000000" else "111111"
    url = f"/v1/retention/cases/{case_id}/execute"
    body = {"challenge_id": challenge["challenge_id"], "otp": wrong}
    assert client.post(url, headers=headers(seed["hr"]), json=body).status_code == 400
    assert client.post(url, headers=headers(seed["hr"]), json=body).status_code == 400
    # Attempts exhausted: even the right code is refused now.
    body["otp"] = challenge["dev_code"]
    assert client.post(url, headers=headers(seed["hr"]), json=body).status_code == 429
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.applications WHERE application_id = :a"),
                            {"a": seed["app"]}).scalar_one() == 1

    executed = purge_with_otp(client, case_id, seed["hr"])
    assert executed.status_code == 200 and executed.json()["status"] == "DELETED"
    # A consumed code cannot be replayed.
    replay = client.post(url, headers=headers(seed["hr"]), json=body)
    assert replay.status_code == 400


@integration
def test_cycle_endpoint_is_limited_to_admin_and_hr_lead(client, seed):
    assert client.post("/v1/retention/cycle/run", headers=headers(seed["hr"])).status_code == 403
    _make_global_lead(seed)
    response = client.post("/v1/retention/cycle/run", headers=headers(seed["other"]))
    assert response.status_code == 200 and response.json()["skipped"] is False


@integration
def test_low_resolution_image_upload_lands_in_manual_queue(client, seed, tmp_path, monkeypatch):
    from app.workers.processor import worker
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"),
                     {"id": seed["cv"]})
    small = to_bytes(synthetic_page().resize((827, 1170)))
    response = client.post(f"/v1/applications/upload-batch/{seed['pos']}", headers=headers(seed["hr"]),
                           files={"files": ("candidate.png", small, "image/png")})
    assert response.status_code == 202, response.text
    worker._process_pending_operations()
    with engine.connect() as conn:
        document = conn.execute(text("""
            SELECT d.mime_type, d.storage_path, d.file_processing_status, d.processing_error,
                   r.error_code, r.image_quality
            FROM app_private.application_documents d
            JOIN app_private.document_processing_runs r ON r.document_id = d.document_id
            WHERE d.original_filename = 'candidate.png'
        """)).mappings().one()
    assert document["mime_type"] == "image/png" and document["storage_path"].endswith(".png")
    assert document["file_processing_status"] == "NEEDS_HR_REVIEW"
    assert document["error_code"] == "IMAGE_LOW_RESOLUTION"
    assert document["image_quality"]["estimated_dpi"] == 100.0
    assert "Synthetic" not in (document["processing_error"] or "")
