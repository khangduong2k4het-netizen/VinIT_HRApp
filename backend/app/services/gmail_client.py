"""Small Gmail API + Cloud Pub/Sub client for the recruiting mailbox (F3.03 email channel).

Plain HTTPS calls with httpx; no Google SDK. Only the scopes HRA needs are asked
for: read mail and change its labels (gmail.modify) and pull the Pub/Sub
subscription Gmail publishes to (pubsub). HRA never sends mail through Gmail.

Errors carry a short code only; message content, tokens and addresses are never
put into exception text or logs.
"""
from __future__ import annotations

import base64
import hashlib
import threading
import time
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

SCOPES = ["https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/pubsub"]
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
PUBSUB = "https://pubsub.googleapis.com/v1"


class GmailError(Exception):
    """A Gmail / Pub/Sub call failed. ``code`` is safe to store and show."""

    def __init__(self, code: str, status: int | None = None):
        super().__init__(code)
        self.code = code
        self.status = status


def configured() -> bool:
    return bool(settings.GMAIL_INTAKE_ENABLED and settings.GMAIL_CLIENT_ID and settings.GMAIL_CLIENT_SECRET)


# ---- token storage ----------------------------------------------------------------

def _fernet() -> Fernet:
    key = (settings.MAILBOX_ENCRYPTION_KEY or settings.AI_CONFIG_ENCRYPTION_KEY or "").strip()
    if not key:
        raise GmailError("ENCRYPTION_KEY_MISSING")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise GmailError("ENCRYPTION_KEY_INVALID") from None


def encrypt_token(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_token(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken:
        raise GmailError("TOKEN_UNREADABLE") from None


# ---- OAuth ------------------------------------------------------------------------

def auth_url(state: str) -> str:
    return AUTH_URL + "?" + urlencode({
        "client_id": settings.GMAIL_CLIENT_ID, "redirect_uri": settings.GMAIL_REDIRECT_URI,
        "response_type": "code", "scope": " ".join(SCOPES), "access_type": "offline",
        # Always ask, so Google returns a refresh token even when the account consented before.
        "prompt": "consent", "state": state, "include_granted_scopes": "true",
    })


def exchange_code(code: str) -> dict:
    resp = httpx.post(TOKEN_URL, data={
        "code": code, "client_id": settings.GMAIL_CLIENT_ID, "client_secret": settings.GMAIL_CLIENT_SECRET,
        "redirect_uri": settings.GMAIL_REDIRECT_URI, "grant_type": "authorization_code",
    }, timeout=20)
    if resp.status_code != 200:
        raise GmailError("CODE_EXCHANGE_FAILED", resp.status_code)
    data = resp.json()
    if not data.get("refresh_token"):
        raise GmailError("NO_REFRESH_TOKEN")
    granted = set((data.get("scope") or "").split())
    if not set(SCOPES) <= granted:
        raise GmailError("SCOPES_NOT_GRANTED")
    return data


_token_cache: dict[str, tuple[str, float]] = {}
_token_lock = threading.Lock()


def access_token(refresh_token: str) -> str:
    """Short-lived access token for a refresh token, cached until shortly before expiry."""
    key = hashlib.sha256(refresh_token.encode()).hexdigest()
    with _token_lock:
        cached = _token_cache.get(key)
        if cached and cached[1] > time.time() + 60:
            return cached[0]
    resp = httpx.post(TOKEN_URL, data={
        "refresh_token": refresh_token, "client_id": settings.GMAIL_CLIENT_ID,
        "client_secret": settings.GMAIL_CLIENT_SECRET, "grant_type": "refresh_token",
    }, timeout=20)
    if resp.status_code != 200:
        error = ""
        try:
            error = resp.json().get("error", "")
        except ValueError:
            pass
        # invalid_grant: revoked, password changed, or 7-day expiry of an app in "Testing".
        raise GmailError("TOKEN_REVOKED" if error == "invalid_grant" else "TOKEN_REFRESH_FAILED", resp.status_code)
    data = resp.json()
    with _token_lock:
        _token_cache[key] = (data["access_token"], time.time() + int(data.get("expires_in", 3600)))
    return data["access_token"]


def forget_token(refresh_token: str) -> None:
    with _token_lock:
        _token_cache.pop(hashlib.sha256(refresh_token.encode()).hexdigest(), None)


# ---- Gmail ------------------------------------------------------------------------

def _call(method: str, url: str, token: str, *, params: dict | None = None, json: Any = None,
          timeout: float = 30) -> dict:
    resp = httpx.request(method, url, headers={"Authorization": f"Bearer {token}"}, params=params, json=json,
                         timeout=timeout)
    if resp.status_code == 404:
        raise GmailError("NOT_FOUND", 404)
    if resp.status_code == 429 or resp.status_code >= 500:
        raise GmailError("GOOGLE_BUSY", resp.status_code)
    if resp.status_code >= 400:
        raise GmailError("GOOGLE_REFUSED", resp.status_code)
    return resp.json() if resp.content else {}


def get_profile(token: str) -> dict:
    return _call("GET", f"{GMAIL}/profile", token)


def watch(token: str, topic: str) -> dict:
    """Ask Gmail to publish INBOX changes to the Pub/Sub topic (valid about 7 days)."""
    return _call("POST", f"{GMAIL}/watch", token,
                 json={"topicName": topic, "labelIds": ["INBOX"], "labelFilterBehavior": "include"})


def stop_watch(token: str) -> None:
    _call("POST", f"{GMAIL}/stop", token)


def history_message_ids(token: str, start_history_id: str) -> tuple[list[str], Optional[str]]:
    """Ids of messages added to INBOX since ``start_history_id`` and the newest history id.

    Raises GmailError('NOT_FOUND') when the history id is too old (Gmail keeps about a week).
    """
    ids: list[str] = []
    latest = None
    page = None
    while True:
        params = {"startHistoryId": start_history_id, "historyTypes": "messageAdded", "labelId": "INBOX",
                  "maxResults": 100}
        if page:
            params["pageToken"] = page
        data = _call("GET", f"{GMAIL}/history", token, params=params)
        latest = data.get("historyId", latest)
        for item in data.get("history", []):
            for added in item.get("messagesAdded", []):
                msg = added.get("message", {})
                if msg.get("id") and msg["id"] not in ids:
                    ids.append(msg["id"])
        page = data.get("nextPageToken")
        if not page:
            return ids, latest


def recent_inbox_ids(token: str, newer_than_days: int = 2) -> list[str]:
    data = _call("GET", f"{GMAIL}/messages", token, params={"q": f"in:inbox newer_than:{newer_than_days}d", "maxResults": 100})
    return [m["id"] for m in data.get("messages", [])]


def get_message(token: str, message_id: str) -> dict:
    return _call("GET", f"{GMAIL}/messages/{message_id}", token, params={"format": "full"})


def get_attachment(token: str, message_id: str, attachment_id: str) -> bytes:
    data = _call("GET", f"{GMAIL}/messages/{message_id}/attachments/{attachment_id}", token)
    return b64url(data.get("data", ""))


def ensure_labels(token: str, names: list[str]) -> dict[str, str]:
    existing = {item["name"]: item["id"] for item in _call("GET", f"{GMAIL}/labels", token).get("labels", [])}
    for name in names:
        if name not in existing:
            created = _call("POST", f"{GMAIL}/labels", token,
                            json={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"})
            existing[name] = created["id"]
    return {name: existing[name] for name in names}


def add_label(token: str, message_id: str, label_id: str) -> None:
    _call("POST", f"{GMAIL}/messages/{message_id}/modify", token, json={"addLabelIds": [label_id]})


# ---- Pub/Sub ----------------------------------------------------------------------

def pull(token: str, subscription: str, max_messages: int = 20) -> list[dict]:
    """Messages Gmail published since the last pull (waits briefly when there are none)."""
    data = _call("POST", f"{PUBSUB}/{subscription}:pull", token, json={"maxMessages": max_messages}, timeout=40)
    return data.get("receivedMessages", [])


def ack(token: str, subscription: str, ack_ids: list[str]) -> None:
    if ack_ids:
        _call("POST", f"{PUBSUB}/{subscription}:acknowledge", token, json={"ackIds": ack_ids})


# ---- message parsing ---------------------------------------------------------------

def b64url(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)) if data else b""


def headers_of(message: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for h in message.get("payload", {}).get("headers", []):
        out.setdefault(h.get("name", "").lower(), []).append(h.get("value", ""))
    return out


def walk_parts(part: dict):
    yield part
    for child in part.get("parts", []) or []:
        yield from walk_parts(child)
