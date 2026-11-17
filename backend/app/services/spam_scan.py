"""Fail-closed adapter for a local SpamAssassin spamd CHECK socket.

Standalone groundwork; this is not yet connected to Gmail ingestion. A HAM
verdict is not a guarantee that a message is safe or genuine.
"""
from enum import Enum
import math
import re
import socket
import time


class SpamVerdict(str, Enum):
    HAM = 'HAM'
    SPAM = 'SPAM'
    UNAVAILABLE = 'UNAVAILABLE'


_SCORE = rb'[-+]?(?:\d+(?:\.\d*)?|\.\d+)'
_SPAM_HEADER = re.compile(rb'^Spam:\s*(True|False|Yes|No)\s*;\s*(' + _SCORE + rb')\s*/\s*(' + _SCORE + rb')\s*$', re.IGNORECASE)
_STATUS = re.compile(rb'^SPAMD/1\.[1-5] 0 EX_OK$')


def scan_message(raw: bytes, *, socket_path: str, max_bytes: int,
                 timeout_seconds: float = 15.0) -> SpamVerdict:
    if (not isinstance(raw, bytes) or not raw or not isinstance(max_bytes, int)
            or isinstance(max_bytes, bool) or max_bytes <= 0 or len(raw) > max_bytes
            or not isinstance(socket_path, str) or not socket_path.startswith('/')
            or not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool)
            or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 120):
        return SpamVerdict.UNAVAILABLE
    deadline = time.monotonic() + timeout_seconds
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            def remaining():
                seconds = deadline - time.monotonic()
                if seconds <= 0:
                    raise TimeoutError
                conn.settimeout(seconds)
            remaining(); conn.connect(socket_path)
            remaining(); conn.sendall(f'CHECK SPAMC/1.5\r\nContent-length: {len(raw)}\r\n\r\n'.encode('ascii'))
            for offset in range(0, len(raw), 65536):
                remaining(); conn.sendall(raw[offset:offset + 65536])
            conn.shutdown(socket.SHUT_WR)
            reply = bytearray()
            while len(reply) < 8192 and b'\r\n\r\n' not in reply:
                remaining()
                chunk = conn.recv(8192 - len(reply))
                if not chunk:
                    return SpamVerdict.UNAVAILABLE
                reply.extend(chunk)
            if not reply.endswith(b'\r\n\r\n'):
                return SpamVerdict.UNAVAILABLE
            lines = bytes(reply[:-4]).split(b'\r\n')
            if not lines or not _STATUS.fullmatch(lines[0]):
                return SpamVerdict.UNAVAILABLE
            headers = [line for line in lines[1:] if line.lower().startswith(b'spam:')]
            if len(headers) != 1:
                return SpamVerdict.UNAVAILABLE
            match = _SPAM_HEADER.fullmatch(headers[0])
            if not match:
                return SpamVerdict.UNAVAILABLE
            score, threshold = float(match[2]), float(match[3])
            flagged = match[1].lower() in (b'true', b'yes')
            if not math.isfinite(score) or not math.isfinite(threshold) or flagged != (score >= threshold):
                return SpamVerdict.UNAVAILABLE
            return SpamVerdict.SPAM if flagged else SpamVerdict.HAM
    except (OSError, ValueError, OverflowError):
        return SpamVerdict.UNAVAILABLE
