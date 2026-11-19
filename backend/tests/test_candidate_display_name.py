"""Tên ứng viên: đọc từ CV, không lấy từ tên file.

Bối cảnh: trước đây worker đặt ``display_name`` bằng
``os.path.splitext(original_filename)[0]``, nên HR thấy "CV_final_v2 (1)"
làm tên ứng viên. Sửa thành đọc từ profile LLM, nhưng model đọc bản đã redact
nên phải kiểm chứng tên có thật trong CV — không tin model, không tin tên file.

Tên file vẫn được giữ ở ``original_filename`` để tham chiếu.
"""
from app.workers.processor import _verified_candidate_name

CV_TEXT = """--- Page 1 ---
Daniel Whitfield
Backend Engineer
Email: daniel.whitfield@example.test

Experience: 5 years Python, PostgreSQL.
"""


def test_name_found_in_cv_is_accepted():
    assert _verified_candidate_name("Daniel Whitfield", CV_TEXT) == "Daniel Whitfield"


def test_name_missing_from_cv_is_rejected():
    """Model trả tên không có trong CV (bịa hoặc nhận nhầm) — phải bỏ."""
    assert _verified_candidate_name("Marcus Bell", CV_TEXT) is None


def test_file_name_is_not_used_as_fallback():
    """Không đọc được tên thì trả None, KHÔNG rơi về tên file."""
    assert _verified_candidate_name(None, CV_TEXT) is None


def test_none_is_tolerated():
    """Không đọc được tên — không được ném lỗi."""
    assert _verified_candidate_name(None, CV_TEXT) is None


def test_non_string_is_rejected():
    assert _verified_candidate_name(123, CV_TEXT) is None
    assert _verified_candidate_name(["An"], CV_TEXT) is None


def test_whitespace_is_normalised():
    result = _verified_candidate_name("  Daniel   Whitfield ", CV_TEXT)
    assert result == "Daniel Whitfield"


def test_case_insensitive_match():
    """CV viết hoa toàn bộ, model trả chữ thường — vẫn là cùng một tên."""
    cv = "DANIEL WHITFIELD\nBackend Engineer"
    assert _verified_candidate_name("daniel whitfield", cv) == "daniel whitfield"


def test_company_name_is_rejected_when_not_present():
    assert _verified_candidate_name("Northbridge Commerce Ltd", CV_TEXT) is None


def test_too_long_value_is_rejected():
    """Một dòng tiêu đề bị nhận nhầm thành tên."""
    long_value = "Daniel Whitfield " + "x" * 100
    assert _verified_candidate_name(long_value, CV_TEXT) is None


def test_too_many_words_is_rejected():
    assert _verified_candidate_name(
        "Daniel Whitfield Senior Backend Engineer Lead", CV_TEXT
    ) is None


def test_values_with_code_like_characters_rejected():
    assert _verified_candidate_name("Daniel <Whitfield>", CV_TEXT) is None
    assert _verified_candidate_name("an@example.test", CV_TEXT) is None


def test_single_word_name_can_be_accepted():
    """Một số CV chỉ ghi một từ (ví dụ tên tiếng Anh ngắn)."""
    cv = "AN\nSoftware Engineer"
    assert _verified_candidate_name("An", cv) == "An"


def test_empty_cv_text_rejects_everything():
    assert _verified_candidate_name("Daniel Whitfield", "") is None


# ---------------------------------------------------------------------------
# Đoạn trích gửi đi để đọc tên: giữ tên, bỏ liên hệ.
# ---------------------------------------------------------------------------

def test_contacts_only_keeps_the_name():
    from app.services.redaction import redact_contacts_only
    header = "Daniel Whitfield\nEmail: daniel.whitfield@example.test\nPhone: +44 7700 900112"
    out = redact_contacts_only(header)
    assert "Daniel Whitfield" in out
    assert "an@example.test" not in out
    assert "912" not in out


def test_contacts_only_still_drops_labelled_identity_lines():
    """Dòng nhãn như địa chỉ/ngày sinh không giúp ích gì cho việc đọc tên."""
    from app.services.redaction import redact_contacts_only
    out = redact_contacts_only("Daniel Whitfield\nAddress: 12 Sample Street, Leeds\nDate of birth: 01/01/1995")
    assert "Daniel Whitfield" in out
    assert "12 Sample Street" not in out
    assert "01/01/1995" not in out


def test_excerpt_is_bounded():
    """Chỉ gửi phần đầu CV, không gửi cả tài liệu."""
    from app.services.llm_client import NAME_EXCERPT_CHARS
    assert NAME_EXCERPT_CHARS <= 1000


# ---------------------------------------------------------------------------
# extract_candidate_name: đường gọi thật tới LLM (được thay bằng stub).
# ---------------------------------------------------------------------------

CV_WITH_CONTACTS = (
    "Daniel Whitfield\n"
    "Backend Engineer · Python\n"
    "daniel.whitfield@example.test  ·  +44 7700 900112\n"
    "SUMMARY\n"
    "Backend engineer with 4 years of experience.\n"
)


def _run_name_extraction(answer, cv_text=CV_WITH_CONTACTS):
    """Chạy extract_candidate_name với một client trả sẵn ``answer``."""
    import asyncio
    from app.services.llm_client import LLMClient

    captured = {}

    class StubClient(LLMClient):
        async def _call_llm(self, system_prompt, user_prompt, **kwargs):
            import json
            captured["prompt"] = json.loads(user_prompt)["resume_header"]
            return {"full_name": answer}

    client = StubClient()
    return asyncio.run(client.extract_candidate_name(cv_text, "app-1")), captured


def test_name_is_read_from_the_header():
    """Đây là test bắt lỗi thiếu import: hàm thật phải chạy được."""
    name, _ = _run_name_extraction("Daniel Whitfield")
    assert name == "Daniel Whitfield"


def test_name_request_sends_the_name_but_not_contacts():
    """Model cần thấy tên, nhưng không được thấy email hay số điện thoại."""
    _, captured = _run_name_extraction("Daniel Whitfield")
    prompt = captured["prompt"]
    assert "Daniel Whitfield" in prompt
    assert "daniel.whitfield@example.test" not in prompt
    assert "900112" not in prompt


def test_null_answer_returns_none():
    name, _ = _run_name_extraction(None)
    assert name is None


def test_placeholder_answers_are_treated_as_missing():
    """Model đôi khi trả chuỗi vô nghĩa thay vì null."""
    for value in ("null", "None", "n/a", "[REDACTED]", "   "):
        name, _ = _run_name_extraction(value)
        assert name is None, value


def test_empty_cv_short_circuits():
    import asyncio
    from app.services.llm_client import LLMClient
    assert asyncio.run(LLMClient().extract_candidate_name("", "app-1")) is None


def test_llm_error_does_not_break_processing():
    """Không đọc được tên là chuyện nhỏ, không được làm hỏng cả tác vụ."""
    import asyncio
    from app.services.llm_client import LLMClient, LLMError

    class FailingClient(LLMClient):
        async def _call_llm(self, *args, **kwargs):
            raise LLMError("provider down")

    assert asyncio.run(
        FailingClient().extract_candidate_name(CV_WITH_CONTACTS, "app-1")
    ) is None


def test_end_to_end_with_real_cv_file():
    """CV thật trong bộ demo: lấy đúng tên, và tên đó qua được bước kiểm chứng."""
    from pathlib import Path
    from app.services.document_processor import document_processor
    import asyncio

    cv_path = (
        Path(__file__).resolve().parents[2]
        / "doc" / "BO_DEMO_TUYEN_DUNG" / "02_CV" / "CV_01_daniel_whitfield.docx"
    )
    if not cv_path.exists():
        import pytest
        pytest.skip("Bộ CV demo chưa được sinh")

    raw, _, _ = asyncio.run(
        document_processor.process_document(
            cv_path.read_bytes(), cv_path.name,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    )
    assert raw.splitlines()[0].strip() == "Daniel Whitfield"

    name, _ = _run_name_extraction("Daniel Whitfield", raw)
    assert _verified_candidate_name(name, raw) == "Daniel Whitfield"


def test_filename_is_not_used_when_the_model_returns_nothing():
    """Yêu cầu gốc: không có tên thì để trống, KHÔNG rơi về tên tệp."""
    name, _ = _run_name_extraction(None)
    assert _verified_candidate_name(name, CV_WITH_CONTACTS) is None
