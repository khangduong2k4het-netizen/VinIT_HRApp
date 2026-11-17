"""Interactive, read-only Gmail connection smoke for a dedicated test mailbox.

Never stores tokens or imports CVs. Run manually on the VPS using an SSH
loopback tunnel; do not paste credentials or the authorization URL into chat.
"""
import argparse
import json
import logging
import os
from pathlib import Path
import stat
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'
GMAIL_URL = 'https://gmail.googleapis.com/gmail/v1/users/me/messages'


def validate_client_file(filename: str) -> Path:
    path = Path(filename).expanduser()
    if path.is_symlink():
        raise ValueError('The OAuth client file must not be a symlink')
    path = path.resolve(strict=True)
    if path == REPO_ROOT or REPO_ROOT in path.parents:
        raise ValueError('The OAuth client file must be outside the repository')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError('The OAuth client file must be owned by this user and be mode 0600 or stricter')
    with path.open(encoding='utf-8') as stream:
        config = json.load(stream)
    installed = config.get('installed', {}) if isinstance(config, dict) else {}
    if (not installed.get('client_id') or not installed.get('client_secret')
            or installed.get('auth_uri') != 'https://accounts.google.com/o/oauth2/auth'
            or installed.get('token_uri') != 'https://oauth2.googleapis.com/token'):
        raise ValueError('Expected an official Google Desktop OAuth client file')
    return path


def run_smoke(client_file: Path, port: int, flow_factory, session_factory) -> int:
    # Avoid leaking the callback URL (including authorization code) to logs.
    logging.getLogger('google_auth_oauthlib.flow').disabled = True
    flow = flow_factory.from_client_secrets_file(str(client_file), [SCOPE], autogenerate_code_verifier=True)
    credentials = flow.run_local_server(host='localhost', bind_addr='127.0.0.1', port=port,
        open_browser=False, timeout_seconds=300, access_type='online',
        authorization_prompt_message='Mở URL sau trên máy của anh, không gửi URL này vào chat: {url}',
        success_message='Xong kiểm tra OAuth. Có thể đóng tab này.')
    session = session_factory(credentials)
    try:
        response = session.get(GMAIL_URL, params={'q': 'label:HRA_TEST', 'maxResults': 5}, timeout=20)
        response.raise_for_status()
        data = response.json()
        messages = data.get('messages', [])
        if not isinstance(messages, list):
            raise ValueError('Unexpected Gmail response')
        # Do not print message IDs, snippets, headers or bodies.
        return len(messages)
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description='Kiểm tra OAuth Gmail chỉ đọc, không nhập CV hay lưu token.')
    parser.add_argument('--client-file', required=True, help='Đường dẫn client OAuth Desktop, ngoài repo, mode 0600')
    parser.add_argument('--port', type=int, default=8765, help='Cổng loopback callback đã SSH forward')
    parser.add_argument('--confirm-test-mailbox', action='store_true', help='Xác nhận chỉ dùng hộp thư thử nghiệm')
    args = parser.parse_args()
    if not args.confirm_test_mailbox or not 1024 <= args.port <= 65535:
        print('Cần xác nhận hộp thư thử nghiệm và cổng hợp lệ.', file=sys.stderr)
        return 2
    try:
        path = validate_client_file(args.client_file)
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import AuthorizedSession
        count = run_smoke(path, args.port, InstalledAppFlow, AuthorizedSession)
    except Exception as exc:
        # Exceptions can contain secrets, URLs, authorization codes or bodies.
        print(f'Kiểm tra thất bại ({type(exc).__name__}); xem runbook, không gửi log/token.', file=sys.stderr)
        return 1
    print(f'Gmail OAuth chỉ đọc: thành công; tìm thấy {count} email trong label HRA_TEST (tối đa 5).')
    print('Không tải CV, tạo hồ sơ, sửa/xóa email hay lưu token. Chưa phải tích hợp ingestion.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
