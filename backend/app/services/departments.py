"""Department master-data helpers.

A department's ``code_format`` is the template used to generate position
codes. It must contain exactly one sequence placeholder, for example
``REQ-IT-{SEQ:000}`` -> ``REQ-IT-001``, ``REQ-IT-002``.
"""
import re
from typing import Any

from sqlalchemy import text


class DepartmentError(ValueError):
    pass


_SEQUENCE_PLACEHOLDER = re.compile(r"\{SEQ(?::(0+))?\}")
_ALLOWED_FORMAT_CHARS = re.compile(r"^[A-Z0-9\-_/{}:]+$")


def normalize_department_name(value: Any) -> str:
    if not isinstance(value, str):
        raise DepartmentError("Tên phòng ban không hợp lệ")
    name = " ".join(value.strip().split())
    if not name or len(name) > 160 or any(ord(char) < 32 or ord(char) == 127 for char in name):
        raise DepartmentError("Tên phòng ban phải có từ 1 đến 160 ký tự")
    return name


def normalize_code_format(value: Any) -> str:
    if not isinstance(value, str):
        raise DepartmentError("Mã định dạng phòng ban không hợp lệ")
    code_format = value.strip().upper()
    placeholders = list(_SEQUENCE_PLACEHOLDER.finditer(code_format))
    if (
        not 3 <= len(code_format) <= 80
        or any(char.isspace() for char in code_format)
        or not _ALLOWED_FORMAT_CHARS.fullmatch(code_format)
        or len(placeholders) != 1
    ):
        raise DepartmentError(
            "Mã định dạng phải chứa đúng một {SEQ} hoặc {SEQ:000}, ví dụ REQ-IT-{SEQ:000}"
        )
    width = placeholders[0].group(1)
    if width and len(width) > 6:
        raise DepartmentError("Số chữ số trong {SEQ:000} tối đa là 6")
    return code_format


def render_position_code(code_format: str, sequence: int) -> str:
    if sequence < 1:
        raise DepartmentError("Số thứ tự mã vị trí phải lớn hơn 0")
    normalized = normalize_code_format(code_format)

    def replace(match: re.Match[str]) -> str:
        width = len(match.group(1) or "") or 1
        return str(sequence).zfill(width)

    return _SEQUENCE_PLACEHOLDER.sub(replace, normalized, count=1)


def next_position_code(db, department: dict[str, Any]) -> tuple[str, int]:
    """Return the next free code for a department row locked by the caller."""
    sequence = int(department["next_sequence"] or 1)
    for _ in range(1000):
        code = render_position_code(department["code_format"], sequence)
        exists = db.execute(
            text("SELECT 1 FROM app_private.positions WHERE position_code = :code"),
            {"code": code},
        ).first()
        if not exists:
            return code, sequence
        sequence += 1
    raise DepartmentError("Không thể sinh mã vị trí duy nhất cho phòng ban này")
