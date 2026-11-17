"""Authorize the dedicated test mailbox via SSH loopback; write tokens privately.

Run interactively on the VPS under the service account. Never paste the URL,
code, client JSON or token file into chat, logs or Git.
"""
import argparse
import logging
import os
from pathlib import Path
import stat
import sys

from gmail_readonly_smoke import REPO_ROOT, SCOPE, validate_client_file


def save_new_token(token_path: str, contents: str) -> None:
    path = Path(token_path).expanduser()
    parent = path.parent.resolve(strict=True)
    info = parent.stat()
    if (parent == REPO_ROOT or REPO_ROOT in parent.parents or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077):
        raise ValueError('Token directory must be owned by the current user, mode 0700, outside repo')
    target = parent / path.name
    if not path.name or path.name in ('.', '..'):
        raise ValueError('Invalid token file')
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            out.write(contents)
            out.flush()
            os.fsync(out.fileno())
    except Exception:
        os.unlink(target)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description='Cấp quyền Gmail thử nghiệm; lưu token ngoài repo với mode 0600.')
    parser.add_argument('--client-file', required=True)
    parser.add_argument('--token-file', required=True)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--confirm-test-mailbox', action='store_true')
    args = parser.parse_args()
    if not args.confirm_test_mailbox or not 1024 <= args.port <= 65535:
        print('Cần xác nhận hộp thư test và cổng hợp lệ.', file=sys.stderr)
        return 2
    try:
        client = validate_client_file(args.client_file)
        from google_auth_oauthlib.flow import InstalledAppFlow
        logging.getLogger('google_auth_oauthlib.flow').disabled = True
        flow = InstalledAppFlow.from_client_secrets_file(str(client), [SCOPE], autogenerate_code_verifier=True)
        credentials = flow.run_local_server(host='localhost', bind_addr='127.0.0.1', port=args.port,
            open_browser=False, timeout_seconds=300, access_type='offline', prompt='consent',
            authorization_prompt_message='Mở URL sau trên máy của anh, không gửi URL này vào chat: {url}',
            success_message='Đã cấp quyền. Có thể đóng tab này.')
        if not credentials.refresh_token:
            raise ValueError('No refresh token')
        save_new_token(args.token_file, credentials.to_json())
    except Exception as exc:
        print(f'Cấp quyền thất bại ({type(exc).__name__}); không gửi URL/token/log.', file=sys.stderr)
        return 1
    print('Đã lưu token cho Gmail thử nghiệm tại vị trí riêng; không gửi tệp hoặc nội dung vào chat.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
