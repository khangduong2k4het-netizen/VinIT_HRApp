"""Restricted readonly Gmail test mailbox client; never log mailbox or contents."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from app.core.config import settings

SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'
BASE = 'https://gmail.googleapis.com/gmail/v1/users/me'
REPO = Path(__file__).resolve().parents[3]
MAX_RAW_BYTES = 15_000_000
MAX_JSON_BYTES = 22_000_000
ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,200}$')


def _token_path() -> Path:
    path = Path(settings.GMAIL_TEST_TOKEN_FILE).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise ValueError('Invalid token location')
    path = path.resolve(strict=True)
    info = path.stat()
    if (path == REPO or REPO in path.parents or not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077):
        raise ValueError('Invalid token permissions')
    return path


def open_session():
    path = _token_path()
    with path.open(encoding='utf-8') as stream:
        doc = json.load(stream)
    if (not isinstance(doc, dict) or doc.get('token_uri') != 'https://oauth2.googleapis.com/token'
            or not doc.get('refresh_token') or not doc.get('client_id') or not doc.get('client_secret')
            or set(doc.get('scopes', [])) != {SCOPE}):
        raise ValueError('Invalid OAuth credentials')
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import AuthorizedSession
    return AuthorizedSession(Credentials.from_authorized_user_info(doc, scopes=[SCOPE]))


def _get_json(session, url: str, params: dict, *, limit: int) -> dict:
    response = session.get(url, params=params, timeout=30, stream=True)
    try:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            data.extend(chunk)
            if len(data) > limit:
                raise ValueError('Gmail response exceeds size limit')
        result = json.loads(data)
        if not isinstance(result, dict):
            raise ValueError('Malformed Gmail response')
        return result
    finally:
        response.close()


def mailbox_hash(session) -> str:
    profile = _get_json(session, BASE + '/profile', {'fields': 'emailAddress'}, limit=32768)
    email = profile.get('emailAddress')
    if not isinstance(email, str) or not 3 <= len(email) <= 254 or '@' not in email:
        raise ValueError('Invalid mailbox identity')
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def list_messages(session, page_token: str | None = None) -> tuple[list[str], str | None]:
    params = {'q': 'label:HRA_TEST', 'maxResults': 5, 'includeSpamTrash': 'false', 'fields': 'messages(id),nextPageToken'}
    if page_token:
        if not re.fullmatch(r'[A-Za-z0-9_=/+.-]{1,1000}', page_token):
            raise ValueError('Invalid page token')
        params['pageToken'] = page_token
    body = _get_json(session, BASE + '/messages', params, limit=65536)
    messages = body.get('messages', [])
    if not isinstance(messages, list) or len(messages) > 5:
        raise ValueError('Invalid message list')
    ids = [item.get('id') for item in messages if isinstance(item, dict)]
    if len(ids) != len(messages) or any(not isinstance(i, str) or not ID_PATTERN.fullmatch(i) for i in ids):
        raise ValueError('Invalid message id')
    next_page = body.get('nextPageToken')
    if next_page is not None and (not isinstance(next_page, str) or not re.fullmatch(r'[A-Za-z0-9_=/+.-]{1,1000}', next_page)):
        raise ValueError('Invalid next page token')
    return ids, next_page


def fetch_message(session, message_id: str) -> tuple[list[str], bytes | None]:
    if not ID_PATTERN.fullmatch(message_id):
        raise ValueError('Invalid message id')
    url = BASE + '/messages/' + message_id
    meta = _get_json(session, url, {'format': 'metadata', 'fields': 'id,labelIds,sizeEstimate'}, limit=65536)
    labels, size = meta.get('labelIds', []), meta.get('sizeEstimate')
    if (meta.get('id') != message_id or not isinstance(labels, list) or any(not isinstance(x, str) for x in labels)
            or not isinstance(size, int) or isinstance(size, bool) or size <= 0):
        raise ValueError('Invalid Gmail metadata')
    if 'SPAM' in labels or 'TRASH' in labels or size > MAX_RAW_BYTES:
        return labels, None
    response = _get_json(session, url, {'format': 'raw', 'fields': 'id,raw,labelIds'}, limit=MAX_JSON_BYTES)
    labels = response.get('labelIds', [])
    raw = response.get('raw')
    if (response.get('id') != message_id or not isinstance(labels, list) or any(not isinstance(x, str) for x in labels)
            or not isinstance(raw, str) or len(raw) > ((MAX_RAW_BYTES + 2) // 3) * 4):
        raise ValueError('Invalid Gmail content')
    if 'SPAM' in labels or 'TRASH' in labels:
        return labels, None
    result = base64.b64decode(raw + '=' * (-len(raw) % 4), altchars=b'-_', validate=True)
    if not result or len(result) > MAX_RAW_BYTES:
        raise ValueError('Gmail message too large')
    return labels, result
