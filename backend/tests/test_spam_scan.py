"""Fake local spamd socket only, no email provider or real messages."""
import socket
import threading

import pytest

from app.services.spam_scan import SpamVerdict, scan_message


@pytest.mark.parametrize(('response', 'expected'), [
    (b'SPAMD/1.1 0 EX_OK\r\nSpam: False ; 2.0 / 5.0\r\n\r\n', SpamVerdict.HAM),
    (b'SPAMD/1.5 0 EX_OK\r\nSpam: Yes ; 5 / 5\r\n\r\n', SpamVerdict.SPAM),
    (b'SPAMD/1.5 75 EX_TEMPFAIL\r\n\r\n', SpamVerdict.UNAVAILABLE),
    (b'SPAMD/1.5 0 EX_OK\r\nSpam: False ; 8 / 5\r\n\r\n', SpamVerdict.UNAVAILABLE),
    (b'SPAMD/1.5 0 EX_OK\r\nSpam: False ; 1 / 5\r\nSpam: True ; 8 / 5\r\n\r\n', SpamVerdict.UNAVAILABLE),
    (b'SPAMD/1.5 0 EX_OK\r\nSpam: False ; nan / 5\r\n\r\n', SpamVerdict.UNAVAILABLE),
    (b'SPAMD/1.5 0 EX_OK\r\nSpam: False ; 1 / 5\r\n', SpamVerdict.UNAVAILABLE),
])
def test_spam_protocol(tmp_path, response, expected):
    path = str(tmp_path / 'spamd.sock')
    raw = b'Subject: synthetic\r\n\r\nSynthetic test email.'
    captured = []
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(path); server.listen(1)
        def serve():
            with server.accept()[0] as conn:
                while True:
                    part = conn.recv(65536)
                    if not part: break
                    captured.append(part)
                conn.sendall(response)
        thread = threading.Thread(target=serve)
        thread.start()
        result = scan_message(raw, socket_path=path, max_bytes=1024, timeout_seconds=2)
        thread.join(timeout=3)
        assert not thread.is_alive()
    assert b''.join(captured) == f'CHECK SPAMC/1.5\r\nContent-length: {len(raw)}\r\n\r\n'.encode() + raw
    assert result == expected


def test_invalid_parameters_and_timeout_fail_closed(tmp_path):
    path = str(tmp_path / 'spamd.sock')
    assert scan_message(b'', socket_path=path, max_bytes=100) == SpamVerdict.UNAVAILABLE
    assert scan_message(b'x', socket_path=path, max_bytes=0) == SpamVerdict.UNAVAILABLE
    assert scan_message(b'x', socket_path='relative', max_bytes=10) == SpamVerdict.UNAVAILABLE
    assert scan_message(b'x', socket_path=path, max_bytes=10, timeout_seconds=float('nan')) == SpamVerdict.UNAVAILABLE
    stop = threading.Event()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(path); server.listen(1)
        def serve():
            with server.accept()[0]: stop.wait(2)
        thread = threading.Thread(target=serve); thread.start()
        try:
            assert scan_message(b'x', socket_path=path, max_bytes=10, timeout_seconds=0.05) == SpamVerdict.UNAVAILABLE
        finally:
            stop.set(); thread.join(timeout=2)
        assert not thread.is_alive()
