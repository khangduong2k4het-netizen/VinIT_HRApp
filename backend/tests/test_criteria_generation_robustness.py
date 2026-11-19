"""Sinh tiêu chí từ JD: chịu được các biến thể output thật của model.

Bối cảnh: một buổi tạo vị trí với JD tiếng Việt trả về
"AI trả về bộ tiêu chí không hợp lệ" (502). Lỗi không phải LLM hỏng — nó nằm ở
bước kiểm tra phía sau, và bước đó từ chối mọi khác biệt nhỏ so với khuôn lý
tưởng: nhãn nhóm bị dịch sang tiếng Việt, trọng số dạng chuỗi, từ khoá dạng
chuỗi, hay key `weight_in_group` thay cho `weight`.

Nguyên tắc ở đây: chỉ từ chối khi thật sự không dùng được. Tên tiêu chí và nhóm
là thứ HR duyệt và matching chấm điểm; hình thức trình bày thì nên nới.
"""
import pytest

from app.api.criteria import (
    _coerce_category,
    _coerce_keywords,
    _coerce_text,
    _coerce_weight,
)

# ---------------------------------------------------------------------------
# Nhãn nhóm: model hay dịch theo ngôn ngữ JD
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [
    "MUST_HAVE", "must_have", "Must Have", "must-have", "  MUST_HAVE  ",
    "MANDATORY", "Required",
    "BẮT BUỘC", "Bắt buộc", "bắt buộc", "bat buoc", "Yêu cầu bắt buộc",
])
def test_mandatory_labels_are_recognised(value):
    assert _coerce_category(value) == "MUST_HAVE"


@pytest.mark.parametrize("value", [
    "NICE_TO_HAVE", "nice_to_have", "Nice To Have", "nice-to-have",
    "PREFERRED", "Optional",
    "Ưu tiên", "ưu tiên", "UU TIEN", "Mong muốn",
])
def test_nice_labels_are_recognised(value):
    assert _coerce_category(value) == "NICE_TO_HAVE"


@pytest.mark.parametrize("value", [None, "", 123, [], {"a": 1}, "KHÔNG PHẢI NHÓM"])
def test_unknown_group_is_rejected_rather_than_guessed(value):
    """Đoán nhóm sai còn tệ hơn báo lỗi: nó đổi trọng số của cả rubric."""
    assert _coerce_category(value) is None


# ---------------------------------------------------------------------------
# Trọng số
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value,expected", [
    (60, 60.0),
    (60.0, 60.0),
    ("60", 60.0),
    ("60%", 60.0),
    (" 60 % ", 60.0),
    ("0.6", 0.6),          # không được nhân 100
    ("60,5", 60.5),        # dấu phẩy thập phân kiểu Việt Nam
])
def test_weight_formats_are_coerced(value, expected):
    assert _coerce_weight(value) == pytest.approx(expected)


@pytest.mark.parametrize("value", [None, True, False, "", "abc", "60%%", [], {}])
def test_unreadable_weight_returns_none(value):
    assert _coerce_weight(value) is None


def test_bool_is_not_treated_as_a_number():
    """`True` là 1 trong Python nhưng không phải trọng số hợp lệ."""
    assert _coerce_weight(True) is None


# ---------------------------------------------------------------------------
# Từ khoá bằng chứng
# ---------------------------------------------------------------------------


def test_keywords_as_comma_string_are_split():
    """Model đôi khi trả "Python, SQL" thay vì mảng."""
    assert _coerce_keywords("Python, SQL, FastAPI") == ["Python", "SQL", "FastAPI"]


def test_keywords_as_list_are_trimmed():
    assert _coerce_keywords([" Python ", "SQL", ""]) == ["Python", "SQL"]


@pytest.mark.parametrize("value", [None, 5, {"a": 1}])
def test_absent_keywords_become_empty_list(value):
    """Từ khoá chỉ là gợi ý, thiếu thì để trống chứ không chặn cả rubric."""
    assert _coerce_keywords(value) == []


# ---------------------------------------------------------------------------
# Văn bản
# ---------------------------------------------------------------------------


def test_text_is_stringified_and_trimmed():
    assert _coerce_text("  Python  ") == "Python"
    assert _coerce_text(None) == ""
    assert _coerce_text(123) == "123"
