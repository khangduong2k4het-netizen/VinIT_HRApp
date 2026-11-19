from uuid import uuid4

import pytest
from app.schemas.positions import PositionCreate
from app.services.departments import (
    DepartmentError,
    next_position_code,
    normalize_code_format,
    normalize_department_name,
    render_position_code,
)


class _Result:
    def __init__(self, exists):
        self._exists = exists

    def first(self):
        return (1,) if self._exists else None


class _FakeDb:
    def __init__(self, existing_codes):
        self.existing_codes = set(existing_codes)

    def execute(self, _statement, params):
        return _Result(params["code"] in self.existing_codes)


def test_department_name_and_code_format_are_normalized():
    assert normalize_department_name("  Phòng   Công nghệ  ") == "Phòng Công nghệ"
    assert normalize_code_format(" req-it-{seq:000} ") == "REQ-IT-{SEQ:000}"
    assert render_position_code("REQ-IT-{SEQ:000}", 1) == "REQ-IT-001"
    assert render_position_code("REQ-HR-{SEQ}", 12) == "REQ-HR-12"


@pytest.mark.parametrize("value", [
    "REQ-IT-001",
    "REQ-IT-{SEQ:000}-{SEQ}",
    "REQ IT {SEQ:000}",
    "REQ-IT-{SEQ:0000000}",
    "REQ-IT-{SEQ:00A}",
])
def test_invalid_code_formats_are_rejected(value):
    with pytest.raises(DepartmentError):
        normalize_code_format(value)


def test_next_position_code_skips_existing_legacy_codes():
    department = {"code_format": "REQ-IT-{SEQ:000}", "next_sequence": 1}
    code, sequence = next_position_code(_FakeDb({"REQ-IT-001", "REQ-IT-002"}), department)
    assert (code, sequence) == ("REQ-IT-003", 3)


def test_position_create_uses_department_instead_of_manual_code():
    payload = PositionCreate(
        department_id=uuid4(),
        title="Engineer",
        jd_content="Job description",
        hiring_manager_user_id=uuid4(),
    )
    assert payload.position_code is None
    assert payload.department_id is not None
