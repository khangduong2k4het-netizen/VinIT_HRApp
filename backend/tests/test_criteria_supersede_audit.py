"""Duyệt bộ tiêu chí thứ hai phải ghi được audit mà không nổ 500.

Lỗi thật (phát hiện khi job integration chạy lại sau 11 ngày đỏ):
`approve_criteria` ghi `superseded_by_version` bằng `cv["version_number"]`,
nhưng truy vấn nạp `cv` chỉ SELECT position_id, jd_version_id, status,
mandatory_weight_total, nice_to_have_weight_total, approved_by_hr — thiếu
version_number. Khi vị trí đã có một bộ APPROVED, nhánh supersede chạy và
câu INSERT audit ném KeyError → 500. Vị trí chưa từng duyệt bộ nào thì
không vào nhánh đó, nên lỗi chỉ lộ ra khi duyệt bộ thứ hai.

Test này đọc mã nguồn thay vì dựng DB, để nó chạy được ở cả job unit.
"""
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def _declared_columns(sql: str) -> set[str]:
    """Cột trong SELECT, bỏ dòng comment để không bắt nhầm chữ trong giải thích."""
    head = sql.split("FROM")[0]
    columns = set()
    for part in head.replace("SELECT", "", 1).split(","):
        name = part.strip().split()[-1] if part.strip() else ""
        if name and name != "*":
            columns.add(name.strip('`"'))
    return columns


def _approve_query_block() -> str:
    src = (BACKEND / "app" / "api" / "criteria.py").read_text(encoding="utf-8")
    start = src.index("def approve_criteria")
    end = src.index("\ndef ", start + 1) if "\ndef " in src[start + 1:] else len(src)
    block = src[start:end]
    marker = "SELECT position_id, jd_version_id, status"
    at = block.index(marker)
    return block[at:block.index("FOR UPDATE", at)]


def test_approve_reads_version_number_it_later_writes_to_audit():
    """Cột nào ghi vào audit metadata thì phải có trong SELECT nạp `cv`."""
    columns = _declared_columns(_approve_query_block())
    assert "version_number" in columns, (
        "approve_criteria đọc cv['version_number'] khi ghi audit supersede; "
        "thiếu cột này trong SELECT là 500 ngay lần duyệt bộ thứ hai"
    )


def test_supersede_audit_still_uses_version_number():
    """Nếu ai bỏ cách đọc này khỏi audit thì test trên không còn nghĩa — báo để rà lại."""
    src = (BACKEND / "app" / "api" / "criteria.py").read_text(encoding="utf-8")
    start = src.index("def approve_criteria")
    block = src[start:start + 12000]
    assert 'cv["version_number"]' in block
