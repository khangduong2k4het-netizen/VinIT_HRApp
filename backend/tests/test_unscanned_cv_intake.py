"""Hồ sơ vào hệ thống khi máy quét virus không chạy — có cờ, có dấu vết.

Bối cảnh: đường nhận CV fail-closed khi ClamAV không trả lời. Đúng cho production,
nhưng ở vòng thử nghiệm nó làm tắc **toàn bộ** form ứng tuyển chỉ vì một dịch vụ
phụ, và người nộp không biết vì sao. Hướng đã thống nhất (HANG-01): vẫn nhận,
nhưng gắn dấu "chưa quét" và ghi audit.

Ba ranh giới phải giữ, mỗi ranh giới là một test ở đây:

1. Tệp **bẩn** thì luôn chặn — kể cả khi bật cờ.
2. Cờ **tắt** (mặc định) thì vẫn 503 như cũ.
3. Nhận vào hàng chờ thì bản ghi **phải** mang dấu, và phải tra được bằng audit.
   Không có dấu thì đây là mở lỗ, không phải mở đường.
"""
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SOURCE = (BACKEND / "app" / "api" / "careers_intake.py").read_text()
CONFIG = (BACKEND / "app" / "core" / "config.py").read_text()
MIGRATION = (BACKEND.parent / "supabase" / "migrations" / "00038_document_scan_state.sql").read_text()

APPLY = SOURCE[SOURCE.index('@router.post('):SOURCE.index("def _commit_intake")]
COMMIT = SOURCE[SOURCE.index("def _commit_intake"):]


# ---------------------------------------------------------------------------
# Ranh giới 1 — tệp bẩn luôn bị chặn
# ---------------------------------------------------------------------------

def test_infected_is_rejected_before_the_flag_is_even_checked():
    """Nhánh INFECTED phải đứng **trước** nhánh đọc cờ.

    Nếu đọc cờ trước rồi mới phân loại, một lần sửa thứ tự là đủ để tệp nhiễm
    độc đi qua cửa "nhận tệp chưa quét". Thứ tự trong mã là chốt chặn ở đây.
    """
    infected_at = APPLY.index("ScanVerdict.INFECTED")
    flag_at = APPLY.index("PUBLIC_CAREERS_UNSCANNED_FILES_ENABLED")
    assert infected_at < flag_at


def test_infected_returns_400_not_503():
    """Tệp bẩn là lỗi của tệp, không phải dịch vụ hỏng."""
    assert "raise HTTPException(400, 'Không thể tiếp nhận tệp')" in APPLY


# ---------------------------------------------------------------------------
# Ranh giới 2 — cờ tắt thì vẫn fail-closed
# ---------------------------------------------------------------------------

def test_flag_off_keeps_fail_closed():
    assert "if unscanned and not settings.PUBLIC_CAREERS_UNSCANNED_FILES_ENABLED:" in APPLY
    assert "raise HTTPException(503, 'Dịch vụ kiểm tra tệp chưa sẵn sàng')" in APPLY


def test_flag_defaults_to_false():
    assert "PUBLIC_CAREERS_UNSCANNED_FILES_ENABLED: bool = False" in CONFIG


def test_missing_socket_no_longer_rejects_before_scanning():
    """Chốt cũ `if not CLAMAV_UNIX_SOCKET.startswith('/'): 503` phải biến mất.

    Nếu còn, nó chặn trước cả bước quét, nên cờ không bao giờ có tác dụng — đúng
    kiểu lỗi "thêm cờ mà cờ không nối vào đâu".
    """
    assert "if not settings.CLAMAV_UNIX_SOCKET.startswith('/'):\n        raise HTTPException(503" not in SOURCE


def test_scan_still_runs_in_all_cases():
    """Không có nhánh nào nhận tệp mà bỏ qua bước quét."""
    assert APPLY.count("scan_bytes") == 1
    assert "verdict = await run_in_threadpool(scan_bytes" in APPLY


# ---------------------------------------------------------------------------
# Ranh giới 3 — nhận vào thì phải có dấu vết
# ---------------------------------------------------------------------------

def test_document_records_the_scan_state():
    assert "'scan_state': 'UNSCANNED' if unscanned else 'SCANNED'" in COMMIT
    assert "scan_state" in COMMIT


def test_flag_travels_from_the_endpoint_to_the_write():
    """Cờ được truyền xuống tầng ghi, không chỉ dùng để quyết định ở endpoint."""
    assert "'CAREERS', unscanned)" in APPLY
    assert "source=\"CAREERS\", unscanned=False)" in COMMIT


def test_default_is_scanned_for_callers_that_do_not_pass_the_flag():
    """`gmail_test.py` gọi hàm này mà không biết gì về cờ — mặc định phải an toàn.

    Mặc định `False` nghĩa là "coi như đã quét". Đúng cho đường Gmail vì ở đó
    `scan_bytes` chạy trước và kết quả UNAVAILABLE đã bị chặn thành REVIEW.
    """
    assert "unscanned=False" in COMMIT


def test_unscanned_write_emits_its_own_audit_action():
    """Phải tra được "hồ sơ nào vào lúc máy quét chết" bằng một action_type.

    Nhồi vào JSON của lần nhận hồ sơ thì phải đọc metadata của mọi bản ghi mới
    trả lời được câu đó.
    """
    assert "CAREERS_UNSCANNED_FILE_ACCEPTED" in COMMIT
    assert "'reason','SCANNER_UNAVAILABLE'" in COMMIT


def test_audit_only_written_when_unscanned():
    """Hồ sơ quét sạch không được sinh thêm dòng audit nhiễu."""
    audit_block = COMMIT[COMMIT.index("if unscanned:"):]
    assert audit_block.index("CAREERS_UNSCANNED_FILE_ACCEPTED") < audit_block.index("return")


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def test_migration_adds_the_column_with_a_default():
    """Có DEFAULT để hàng cũ không phải suy diễn NULL nghĩa là gì."""
    assert "ADD COLUMN scan_state TEXT NOT NULL DEFAULT 'SCANNED'" in MIGRATION


def test_migration_restricts_values():
    assert "CHECK (scan_state IN ('SCANNED', 'UNSCANNED', 'INFECTED'))" in MIGRATION


def test_migration_indexes_only_unscanned_rows():
    """Chỉ số bộ phận: hồ sơ chưa quét là thiểu số, đánh chỉ số toàn bảng là phí."""
    assert "WHERE scan_state <> 'SCANNED'" in MIGRATION
