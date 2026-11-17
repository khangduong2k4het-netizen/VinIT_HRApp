#!/usr/bin/env python3
"""Check clamd/spamd Unix sockets using standard synthetic test signatures.

Only in-memory test input. Does not read mailboxes, save signatures, alter
scanner state, or send messages. Run as the backend user, not with sudo.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.malware_scan import ScanVerdict, scan_bytes  # noqa: E402
from app.services.spam_scan import SpamVerdict, scan_message  # noqa: E402


def run_checks(clam_socket: str, spamd_socket: str) -> dict:
    # EICAR is a harmless standard antivirus test signature, assembled only in memory.
    eicar = b'X5O!P%@AP[4' + b'\\PZX54(P^)7CC)7}' + b'$EICAR-' + b'STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'
    gtube = b'XJS*C4JDBQADN1.NSBN3*2IDNEN*' + b'GTUBE-STANDARD-ANTI-UBE-TEST-EMAIL*C.34X'
    headers = (b'From: Synthetic Test <sender@example.test>\r\n'
               b'To: Test Mailbox <receiver@example.test>\r\n'
               b'Date: Tue, 17 Nov 2026 10:00:00 +0000\r\n'
               b'Message-ID: <synthetic-test@example.test>\r\n'
               b'Subject: Synthetic scanner verification\r\n'
               b'Content-Type: text/plain; charset=utf-8\r\n\r\n')
    clean = headers + b'This is a synthetic message for a private test.\r\n'
    virus = scan_bytes(eicar, socket_path=clam_socket, max_bytes=1024, timeout_seconds=30)
    clean_av = scan_bytes(clean, socket_path=clam_socket, max_bytes=1024 * 1024, timeout_seconds=30)
    spam = scan_message(headers + gtube + b'\r\n', socket_path=spamd_socket, max_bytes=1024 * 1024, timeout_seconds=40)
    clean_spam = scan_message(clean, socket_path=spamd_socket, max_bytes=1024 * 1024, timeout_seconds=40)
    return {'clamav_clean': clean_av.value, 'clamav_eicar': virus.value,
            'spamd_clean': clean_spam.value, 'spamd_gtube': spam.value,
            'pass': (clean_av == ScanVerdict.CLEAN and virus == ScanVerdict.INFECTED
                     and clean_spam == SpamVerdict.HAM and spam == SpamVerdict.SPAM)}


def main() -> int:
    parser = argparse.ArgumentParser(description='Kiểm tra socket scanner với dữ liệu giả; không thay đổi cấu hình.')
    parser.add_argument('--clam-socket', required=True)
    parser.add_argument('--spamd-socket', required=True)
    parser.add_argument('--confirm-synthetic', action='store_true')
    args = parser.parse_args()
    if not args.confirm_synthetic or not args.clam_socket.startswith('/') or not args.spamd_socket.startswith('/'):
        print('Cần xác nhận dữ liệu giả và đường dẫn socket tuyệt đối.', file=sys.stderr)
        return 2
    result = run_checks(args.clam_socket, args.spamd_socket)
    print(json.dumps(result))
    return 0 if result['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
