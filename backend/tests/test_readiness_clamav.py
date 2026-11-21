"""`/health/ready` báo trạng thái ClamAV, nhưng không biến nó thành 503.

Vì sao cần: trước đây `/health/ready` chỉ kiểm DB. Máy quét chết thì đường nhận
CV hỏng (`careers_intake.py` fail-closed 503) trong khi health vẫn báo `ready` —
không có tín hiệu nào cho giám sát. Đó là mục HANG-01/HANG-03.

Vì sao **không** trả 503 khi máy quét chết: máy quét chỉ ảnh hưởng đường nộp CV;
xem vị trí, chấm hồ sơ đã nhận, duyệt rubric vẫn chạy. Trả 503 sẽ khiến load
balancer rút backend khỏi vòng phục vụ và biến "thiếu máy quét" thành "sập toàn
hệ thống" — đổi một lỗi im lặng lấy một lỗi to hơn.
"""
import socket
from pathlib import Path

import pytest

from app import main as main_module
from app.core.config import settings

BACKEND = Path(__file__).resolve().parents[1]
SOURCE = (BACKEND / "app" / "main.py").read_text()


# ---------------------------------------------------------------------------
# Ba trạng thái, không gộp
# ---------------------------------------------------------------------------

def test_state_is_disabled_when_not_configured(monkeypatch):
    """Chưa cấu hình socket là chủ ý, khác với đã cấu hình mà hỏng."""
    monkeypatch.setattr(settings, "CLAMAV_UNIX_SOCKET", "")
    assert main_module._clamav_state() == "disabled"


def test_state_is_unavailable_when_socket_path_does_not_exist(monkeypatch, tmp_path):
    """Đã cấu hình nhưng không kết nối được — đây là trạng thái cần cảnh báo."""
    monkeypatch.setattr(settings, "CLAMAV_UNIX_SOCKET", str(tmp_path / "clamd.ctl"))
    assert main_module._clamav_state() == "unavailable"


def test_state_is_connected_when_socket_accepts(monkeypatch, tmp_path):
    """Có tiến trình đang nghe trên socket thì là `connected`.

    Dùng một Unix socket thật trong tmp_path thay vì mock: điều đang kiểm chính
    là "mở được socket này không", nên mock `socket.socket` sẽ kiểm chính cái
    mock chứ không kiểm được gì.
    """
    path = str(tmp_path / "clamd.ctl")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(path)
        server.listen(1)
        monkeypatch.setattr(settings, "CLAMAV_UNIX_SOCKET", path)
        assert main_module._clamav_state() == "connected"
    finally:
        server.close()


def test_probe_never_raises(monkeypatch):
    """Health probe hỏng thì chính health check thành nguồn sự cố."""
    monkeypatch.setattr(settings, "CLAMAV_UNIX_SOCKET", "/nonexistent/definitely/not/here.ctl")
    assert main_module._clamav_state() == "unavailable"


def test_probe_only_connects(monkeypatch):
    """Chỉ mở rồi đóng socket, không ghi dữ liệu nào.

    Kiểm bằng mã nguồn chứ không bằng socket thật: Unix socket không phát EOF rõ
    ràng khi client đóng im lặng, nên một test dựng server rồi `recv` sẽ kiểm
    hành vi của kernel chứ không kiểm được code có gửi gì hay không.
    """
    body = SOURCE[SOURCE.index("def _clamav_state"):SOURCE.index("def create_app")]
    assert "conn.connect(" in body
    assert ".send" not in body and ".sendall" not in body


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

def test_readiness_reports_clamav_field():
    assert '"clamav": clamav_status' in SOURCE


def test_readiness_does_not_fail_on_missing_scanner_by_default():
    """Cờ mặc định TẮT: thiếu máy quét vẫn trả 200."""
    assert "READINESS_REQUIRE_CLAMAV: bool = False" in (
        BACKEND / "app" / "core" / "config.py").read_text()
    assert 'if settings.READINESS_REQUIRE_CLAMAV and clamav_status != "connected":' in SOURCE


def test_readiness_still_fails_when_database_is_down():
    """Cờ ClamAV không được làm mất chốt DB — DB chết vẫn phải 503."""
    ready_body = SOURCE[SOURCE.index('health/ready'):]
    assert 'status_code=503, content={"status": "unhealthy", "database": "unavailable"}' in ready_body
