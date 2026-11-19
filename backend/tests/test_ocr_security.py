"""PII masking gaps, hidden PDF text and resource limits found in the OCR security review."""
import asyncio

import pytest
from fpdf import FPDF

from app.core.exceptions import FileValidationError
from app.services.document_processor import (DocumentQualityError, document_processor,
                                             document_quality_summary)
from app.services.mock_ai import _keywords
from app.services.redaction import REDACTED, redact_text

MASKED = [
    "SĐT: 0901 234 567",
    "Liên hệ 0901 234 567 nhé",
    "+84 (0) 901 234 567",
    "O9O1 234 567",               # OCR read 0 as O
    "09O1234567",
    "Zalo O9l2 345 678",          # 1 read as l
    "an.nguyen @ gmail . com",    # email split by OCR
    "an.nguyen(at)gmail(dot)com",
    "an.nguyen [at] gmail.com",
    "Sinh 01/01/1998 tại Hà Nội",
    "born on 1.1.1998",
    "Năm sinh 1998",
    "123 Nguyễn Trãi, Thanh Xuân, Hà Nội",
    "Số 12/3 ngõ 45 Láng Hạ, phường Láng Hạ, quận Đống Đa",
    "45 Le Loi Street, District 1, Ho Chi Minh",
    "12 Tran Hung Dao Street, Hanoi",
    "CCCD 001098012345",
]

KEPT = [
    "2019 - 2023 Software Engineer",
    "Jan 2019 - Dec 2021, Hanoi, Vietnam",
    "FPT Software, Hanoi, Vietnam",
    "3 years at VinFast, Hai Phong",
    "5 years experience, Python, Django, Vietnam",
    "Managed 12 people, 3 teams, Hanoi",
    "GPA 3.6/4.0 (2016 - 2020)",
    "Python 3.11, Django 4.2",
    "IELTS 7.5 (2023)",
    "Improved latency by 35% for 1200000 users",
    "Office 365, Illustrator, IntelliJ",
    "Born to code in Python",
    "Hotline 1900 1234",
    "Version 2.1.0.12345 released",
]


@pytest.mark.parametrize("text", MASKED)
def test_identifiers_are_masked_including_ocr_garbled_and_unlabelled(text):
    assert REDACTED in redact_text(text)


@pytest.mark.parametrize("text", KEPT)
def test_professional_text_is_not_masked(text):
    assert redact_text(text) == text


def test_birth_date_masks_only_the_date():
    assert redact_text("Sinh 01/01/1998 tại Hà Nội") == f"Sinh {REDACTED} tại Hà Nội"


def test_mock_ai_never_turns_the_placeholder_into_a_skill():
    assert "REDACTED" not in _keywords(f"Skills {REDACTED} Python Django {REDACTED}", limit=10)


# ------------------------------------------------------------ PDF content
SECRET = "Expert Python engineer with 10 years of Kubernetes and AWS experience."


def _pdf(mode: str = "none", pages: int = 1) -> bytes:
    pdf = FPDF()
    pdf.set_font("helvetica", size=12)
    for index in range(pages):
        pdf.add_page()
        pdf.multi_cell(0, 8, f"Junior Accountant at ABC Company, page {index + 1}.\n"
                             "Skills: Excel, bookkeeping, invoicing, reconciliation, payroll.",
                       new_x="LMARGIN", new_y="NEXT")
    if mode == "invisible":
        pdf.text_mode = 3
        pdf.multi_cell(0, 8, SECRET, new_x="LMARGIN", new_y="NEXT")
    elif mode == "tiny":
        pdf.set_font("helvetica", size=0.5)
        pdf.multi_cell(0, 1, SECRET, new_x="LMARGIN", new_y="NEXT")
    elif mode == "white":
        pdf.set_text_color(255, 255, 255)
        pdf.multi_cell(0, 8, SECRET, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def _process(data: bytes):
    return asyncio.run(document_processor.process_document(data, "cv.pdf", "application/pdf"))


@pytest.mark.parametrize("mode,counter", [("invisible", "invisible_chars"), ("tiny", "tiny_chars")])
def test_hidden_pdf_text_never_reaches_extraction(mode, counter):
    text, pages, _ = _process(_pdf(mode))
    assert "Kubernetes" not in text and "Accountant" in text
    hidden = document_quality_summary(pages)["pdf_hidden_text"]
    assert hidden[counter] >= len("Kubernetes")
    assert "Kubernetes" not in str(hidden)  # counts only, never the hidden words


def test_white_text_is_kept_but_reported():
    # White on a dark sidebar is common in CV templates, so it is flagged, not removed.
    text, pages, _ = _process(_pdf("white"))
    assert "Kubernetes" in text
    assert document_quality_summary(pages)["pdf_hidden_text"]["white_chars"] > 0


def test_ordinary_pdf_has_no_hidden_text_report():
    text, pages, _ = _process(_pdf("none"))
    assert "Accountant" in text and document_quality_summary(pages) is None


def test_pdf_page_limit_sends_long_documents_to_hr(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "MAX_DOCUMENT_PAGES", 3)
    with pytest.raises(DocumentQualityError) as error:
        _process(_pdf("none", pages=4))
    assert error.value.code == "PDF_TOO_MANY_PAGES" and "3" in str(error.value)
    assert _process(_pdf("none", pages=3))[2].value == "PDF_TEXT"


def test_docx_expanding_past_the_limit_is_rejected():
    import io
    import zipfile
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "a" * 101_000_000)  # compresses to ~100 KB
    with pytest.raises(FileValidationError):
        asyncio.run(document_processor.validate_file(
            buffer.getvalue(), "cv.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
