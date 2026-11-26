"""F3.03 email channel: turn CVs sent to the connected Gmail mailbox into applications.

Position routing, most certain first (the first rule that finds exactly one
existing position code wins):

1. plus address: mail sent to ``mailbox+REQ-IT-043@gmail.com``
2. a position code in the subject
3. a position code in the message text
4. a position code in an attachment file name

The position must be open with approved criteria for its latest JD (it does not
have to be published on /apply). Anything else - no code, an unknown code, two
different codes, a closed position - goes to the HR triage list, with title-based
suggestions. HRA never guesses a position on its own.

A CV received by email is recorded with consent for that position only
(channel EMAIL, no Talent Pool) and follows the general retention period.

Logs and audit metadata never carry addresses, subjects, file names or content.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import threading
import unicodedata
from datetime import datetime, timezone
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text

from app.api.public_intake import _commit_application, _remove_cv, _write_cv
from app.core.config import settings
from app.core.exceptions import FileValidationError
from app.core.logging import get_logger
from app.db.database import SessionLocal
from app.db.supabase import get_supabase_client
from app.services import gmail_client as gmail
from app.services.document_processor import MIME_EXTENSIONS, document_processor
from app.services.malware_scan import ScanRejected, ScanUnavailable, scan_upload

logger = get_logger(__name__)

EMAIL_OPEN_POSITION_SQL = """
    SELECT p.position_id, p.position_code, p.title, p.org_unit, p.work_location, p.employment_type
    FROM app_private.positions p
    WHERE p.status = 'OPEN'
      AND EXISTS (SELECT 1 FROM app_private.criteria_versions cv
                  WHERE cv.position_id = p.position_id AND cv.status = 'APPROVED'
                    AND cv.jd_version_id = (SELECT jd_version_id FROM app_private.jd_versions
                                            WHERE position_id = p.position_id ORDER BY version_number DESC LIMIT 1))
"""

CODE_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{2,10}-[A-Za-z0-9]{1,10}-\d{1,6})(?![A-Za-z0-9])")
CV_NAME_RE = re.compile(r"(cv|resume|r[eé]sum[eé]|so[ _-]?yeu|ly[ _-]?lich|curriculum)", re.I)
LABELS = {"MATCHED": "HRA/Đã nhận", "NEEDS_TRIAGE": "HRA/Chờ phân loại", "IGNORED": "HRA/Bỏ qua"}
INLINE_IMAGE_MIN_BYTES = 20_000  # smaller images are signatures / logos, not CVs
MAX_EMAIL_ATTACHMENTS = 10
NOTICE_VERSION = "email-v1"
_sync_lock = threading.Lock()


# ---- small helpers -------------------------------------------------------------------

def fold(value: str) -> str:
    """Lower case without Vietnamese accents, for title matching."""
    value = unicodedata.normalize("NFD", value or "").replace("đ", "d").replace("Đ", "D")
    return "".join(ch for ch in value if unicodedata.category(ch) != "Mn").lower()


def _codes(value: str) -> list[str]:
    seen: list[str] = []
    for match in CODE_RE.finditer(value or ""):
        code = match.group(1).upper()
        if code not in seen:
            seen.append(code)
    return seen


def _local_key(address: str) -> tuple[str, str, str]:
    """(local part without +tag and dots, domain, tag) of an address, lower case."""
    local, _, domain = (address or "").strip().lower().partition("@")
    base, _, tag = local.partition("+")
    return base.replace(".", ""), domain, tag


def plus_tags(addresses: list[str], mailbox: str) -> list[str]:
    """Tags of addresses that are the mailbox itself with a +tag."""
    base, domain, _ = _local_key(mailbox)
    tags = []
    for addr in addresses:
        b, d, tag = _local_key(addr)
        if tag and b == base and d == domain:
            tags.append(tag)
    return tags


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    return unescape(re.sub(r"(?s)<[^>]+>", " ", html))


def parse_message(message: dict) -> dict:
    """Headers, plain text and attachment descriptors of a Gmail 'full' message."""
    h = gmail.headers_of(message)
    from_name, from_address = parseaddr((h.get("from") or [""])[0])
    recipients = [addr for _, addr in getaddresses(h.get("to", []) + h.get("cc", []) + h.get("delivered-to", [])
                                                  + h.get("x-original-to", [])) if addr]
    received_at = None
    if h.get("date"):
        try:
            received_at = parsedate_to_datetime(h["date"][0])
        except (TypeError, ValueError):
            received_at = None
    if received_at is None and message.get("internalDate"):
        received_at = datetime.fromtimestamp(int(message["internalDate"]) / 1000, tz=timezone.utc)
    plain, html, attachments = [], [], []
    for part in gmail.walk_parts(message.get("payload", {})):
        body = part.get("body", {}) or {}
        mime = (part.get("mimeType") or "").lower()
        filename = part.get("filename") or ""
        if filename and (body.get("attachmentId") or body.get("data")):
            part_headers = {x.get("name", "").lower(): x.get("value", "") for x in part.get("headers", [])}
            disposition = part_headers.get("content-disposition", "").lower()
            attachments.append({
                "filename": os.path.basename(filename)[:255], "mime": mime, "size": int(body.get("size") or 0),
                "attachment_id": body.get("attachmentId"), "data": body.get("data"),
                "inline": disposition.startswith("inline") or "content-id" in part_headers,
            })
        elif mime == "text/plain" and body.get("data"):
            plain.append(gmail.b64url(body["data"]).decode("utf-8", "replace"))
        elif mime == "text/html" and body.get("data"):
            html.append(_html_to_text(gmail.b64url(body["data"]).decode("utf-8", "replace")))
    text_body = ("\n".join(plain) or "\n".join(html))[:20000]
    auto = (h.get("auto-submitted") or ["no"])[0].lower() != "no" or \
        (h.get("precedence") or [""])[0].lower() in ("bulk", "junk", "list", "auto_reply")
    return {
        "from_name": (from_name or "").strip()[:200] or None, "from_address": (from_address or "").strip().lower() or None,
        "recipients": recipients, "subject": (h.get("subject") or [""])[0][:500],
        "internet_message_id": (h.get("message-id") or [None])[0], "thread_id": message.get("threadId"),
        "received_at": received_at, "text": text_body, "attachments": attachments, "auto_reply": auto,
    }


# ---- position routing ----------------------------------------------------------------

def route(db, parsed: dict, mailbox: str, filenames: list[str]) -> dict:
    """{'position': row|None, 'method': str|None, 'reason': str|None, 'suggestions': [...]}"""
    sources = [
        ("PLUS_ADDRESS", [t.upper() for t in plus_tags(parsed["recipients"], mailbox) if CODE_RE.fullmatch(t)]),
        ("SUBJECT_CODE", _codes(parsed["subject"])),
        ("BODY_CODE", _codes(parsed["text"])),
        ("FILENAME_CODE", _codes(" ".join(filenames))),
    ]
    reason = "NO_CODE"
    for method, codes in sources:
        if not codes:
            continue
        known = db.execute(text("""SELECT position_id, upper(position_code) AS code FROM app_private.positions
            WHERE upper(position_code) = ANY(:codes)"""), {"codes": codes}).mappings().all()
        if not known:
            reason = "UNKNOWN_CODE"
            continue
        if len({row["position_id"] for row in known}) > 1:
            return {"position": None, "method": None, "reason": "MULTIPLE_CODES", "suggestions": _suggest(db, parsed, filenames)}
        pos = db.execute(text(EMAIL_OPEN_POSITION_SQL + " AND p.position_id = :p"), {"p": known[0]["position_id"]}).first()
        if not pos:
            return {"position": None, "method": None, "reason": "POSITION_NOT_OPEN", "suggestions": _suggest(db, parsed, filenames)}
        return {"position": pos, "method": method, "reason": None, "suggestions": []}
    return {"position": None, "method": None, "reason": reason, "suggestions": _suggest(db, parsed, filenames)}


def _suggest(db, parsed: dict, filenames: list[str]) -> list[dict]:
    """Open positions whose title appears in the subject, text or file names (at most 3)."""
    haystack = fold(" ".join([parsed["subject"], parsed["text"][:5000], " ".join(filenames)]))
    out = []
    for row in db.execute(text(EMAIL_OPEN_POSITION_SQL + " ORDER BY p.created_at DESC")).mappings().all():
        title = fold(re.sub(r"\[[^\]]*\]", " ", row["title"] or "")).strip()
        title = re.sub(r"\s+", " ", re.sub(r"[()]", " ", title)).strip()
        if len(title) >= 4 and title in haystack:
            out.append({"position_id": str(row["position_id"]), "position_code": row["position_code"],
                        "title": row["title"], "why": "TITLE_IN_MAIL"})
        if len(out) == 3:
            break
    return out


# ---- attachments ----------------------------------------------------------------------

def _validated(filename: str, content: bytes, declared: str) -> tuple[Optional[str], Optional[str]]:
    """(mime, None) for an acceptable CV file, else (None, reason code)."""
    if not content:
        return None, "EMPTY"
    if len(content) > settings.MAX_FILE_SIZE_BYTES:
        return None, "TOO_LARGE"
    try:
        mime = asyncio.run(document_processor.validate_file(content, filename, declared or "application/octet-stream"))
    except FileValidationError:
        return None, "NOT_A_CV_FILE"
    try:
        scan_upload(content)
    except ScanRejected:
        return None, "MALWARE"
    except ScanUnavailable:
        return None, "SCAN_UNAVAILABLE"
    return mime, None


def _pick_cv(files: list[dict]) -> dict:
    named = [f for f in files if CV_NAME_RE.search(f["filename"])]
    pool = named or files
    docs = [f for f in pool if not f["mime"].startswith("image/")]
    return max(docs or pool, key=lambda f: f["size"])


def _storage():
    if settings.STORAGE_BACKEND == "supabase":
        client = get_supabase_client()
        if not client:
            raise gmail.GmailError("STORAGE_UNAVAILABLE")
        return client
    return None


def read_stored(storage_path: str) -> bytes:
    if settings.STORAGE_BACKEND == "local":
        base = Path(settings.LOCAL_STORAGE_PATH).expanduser().resolve()
        bucket_dir = (base / settings.SUPABASE_STORAGE_BUCKET_CV).resolve()
        candidate = (bucket_dir / storage_path).resolve()
        if candidate != bucket_dir and bucket_dir not in candidate.parents:
            raise HTTPException(status_code=400, detail="Đường dẫn tệp không hợp lệ")
        with open(candidate, "rb") as f:
            return f.read()
    return _storage().storage.from_(settings.SUPABASE_STORAGE_BUCKET_CV).download(storage_path)


def remove_stored(storage_path: str) -> None:
    _remove_cv(_storage() if settings.STORAGE_BACKEND == "supabase" else None, storage_path)


# ---- creating the application ----------------------------------------------------------

def _is_hra_user(db, address: Optional[str]) -> bool:
    if not address:
        return False
    return db.execute(text("SELECT 1 FROM auth.users WHERE lower(email) = :e"), {"e": address.lower()}).first() is not None


def create_application(db, pos, cv: dict, *, message_id: str, method: str, sender: dict) -> Optional[str]:
    """Create the application for one CV. Returns the application id, or None for a duplicate CV."""
    receipt = _commit_application(
        pos, filename=cv["filename"], content=cv["content"], mime=cv["mime"], declared_type=cv.get("declared"),
        size=len(cv["content"]), sha=hashlib.sha256(cv["content"]).hexdigest(),
        consent_talent_pool=False, ip_hash=f"mail:{message_id}", channel="EMAIL", source_code="EMAIL",
        notice_version=NOTICE_VERSION, evidence_extra={"mailbox_message_id": message_id, "match": method},
        audit_action="RECEIVE_EMAIL_CV", audit_extra={"match": method, "mailbox_message_id": message_id},
        receipt_extra=True, open_sql=EMAIL_OPEN_POSITION_SQL)
    if receipt.get("status") == "duplicate":
        return None
    app_id = receipt["receipt_id"]
    # The sender is the candidate unless HR forwarded the CV from their own account.
    if sender.get("address") and not _is_hra_user(db, sender["address"]):
        db.execute(text("""UPDATE app_private.application_identities
            SET email = :e, display_name = COALESCE(:n, display_name), updated_at = NOW() WHERE application_id = :a"""),
                   {"e": sender["address"], "n": sender.get("name"), "a": app_id})
        db.commit()
    return app_id


# ---- processing one message -------------------------------------------------------------

def _finish(db, message_id: str, status: str, **fields) -> None:
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    db.execute(text(f"UPDATE app_private.mailbox_messages SET status = :status{', ' + sets if sets else ''} WHERE message_id = :id"),
               {"status": status, "id": message_id, **fields})
    db.commit()


def process_message(account: dict, token: str, gmail_id: str, labels: dict[str, str]) -> Optional[str]:
    """Handle one Gmail message once. Returns the final status, or None if another run took it."""
    db = SessionLocal()
    try:
        message_id = db.execute(text("""INSERT INTO app_private.mailbox_messages(account_id, provider_message_id)
            VALUES (:acc, :gid) ON CONFLICT (account_id, provider_message_id) DO NOTHING RETURNING message_id"""),
                                {"acc": account["account_id"], "gid": gmail_id}).scalar_one_or_none()
        db.commit()
        if not message_id:
            return None
        message_id = str(message_id)
        status = _process(db, account, token, gmail_id, message_id)
        label = LABELS.get(status)
        if label and labels.get(label):
            try:
                gmail.add_label(token, gmail_id, labels[label])
            except gmail.GmailError as exc:
                logger.warning("Could not label message", error=exc.code)
        return status
    except Exception as exc:
        db.rollback()
        logger.error("Mail intake failed for one message", error_type=type(exc).__name__)
        try:
            db.execute(text("""UPDATE app_private.mailbox_messages SET status = 'FAILED', reason = :r
                WHERE account_id = :acc AND provider_message_id = :gid AND status = 'NEW'"""),
                       {"r": getattr(exc, "code", type(exc).__name__)[:60], "acc": account["account_id"], "gid": gmail_id})
            db.commit()
        except Exception:
            db.rollback()
        return "FAILED"
    finally:
        db.close()


def _process(db, account: dict, token: str, gmail_id: str, message_id: str) -> str:
    parsed = parse_message(gmail.get_message(token, gmail_id))
    db.execute(text("""UPDATE app_private.mailbox_messages SET internet_message_id = :imid, thread_id = :tid,
            from_address = :fa, from_name = :fn, to_addresses = :to, subject = :sub, received_at = :rcv
        WHERE message_id = :id"""),
               {"imid": parsed["internet_message_id"], "tid": parsed["thread_id"], "fa": parsed["from_address"],
                "fn": parsed["from_name"], "to": ", ".join(parsed["recipients"])[:2000], "sub": parsed["subject"],
                "rcv": parsed["received_at"], "id": message_id})
    db.commit()

    mailbox = account["email_address"]
    if parsed["from_address"] and _local_key(parsed["from_address"])[:2] == _local_key(mailbox)[:2]:
        _finish(db, message_id, "IGNORED", reason="OWN_MESSAGE")
        return "IGNORED"
    if parsed["auto_reply"]:
        _finish(db, message_id, "IGNORED", reason="AUTO_REPLY")
        return "IGNORED"
    if parsed["internet_message_id"] and db.execute(text("""SELECT 1 FROM app_private.mailbox_messages
            WHERE internet_message_id = :imid AND message_id <> :id AND status IN ('MATCHED', 'NEEDS_TRIAGE') LIMIT 1"""),
                                                     {"imid": parsed["internet_message_id"], "id": message_id}).first():
        _finish(db, message_id, "IGNORED", reason="DUPLICATE_MESSAGE")
        return "IGNORED"

    accepted, rejected = [], []
    downloaded = 0
    for att in parsed["attachments"]:
        is_image = att["mime"].startswith("image/")
        if is_image and (att["inline"] or att["size"] < INLINE_IMAGE_MIN_BYTES):
            continue  # signatures, logos
        if att["size"] > settings.MAX_FILE_SIZE_BYTES:
            rejected.append((att, "TOO_LARGE", att["size"]))
            continue
        if downloaded >= MAX_EMAIL_ATTACHMENTS:
            rejected.append((att, "TOO_MANY_ATTACHMENTS", att["size"]))
            continue
        downloaded += 1
        content = gmail.b64url(att["data"]) if att.get("data") else gmail.get_attachment(token, gmail_id, att["attachment_id"])
        mime, why = _validated(att["filename"], content, att["mime"])
        if mime:
            accepted.append({"filename": att["filename"], "mime": mime, "declared": att["mime"], "content": content,
                             "size": len(content)})
        else:
            rejected.append((att, why, len(content)))
    for att, why, size in rejected:
        db.execute(text("""INSERT INTO app_private.mailbox_attachments(message_id, filename, mime_type, size_bytes, status, reject_reason)
            VALUES (:m, :f, :t, :s, 'REJECTED', :r)"""), {"m": message_id, "f": att["filename"], "t": att["mime"], "s": size, "r": why})
    db.commit()
    if not accepted:
        reason = "SCAN_UNAVAILABLE" if any(r[1] == "SCAN_UNAVAILABLE" for r in rejected) else "NO_CV_ATTACHMENT"
        status = "FAILED" if reason == "SCAN_UNAVAILABLE" else "IGNORED"
        _finish(db, message_id, status, reason=reason)
        return status

    filenames = [f["filename"] for f in accepted]
    decision = route(db, parsed, mailbox, filenames)
    cv = _pick_cv(accepted)
    if decision["position"] is not None:
        try:
            app_id = create_application(db, decision["position"], cv, message_id=message_id, method=decision["method"],
                                        sender={"address": parsed["from_address"], "name": parsed["from_name"]})
        except HTTPException as exc:
            decision = {"position": None, "method": None, "reason": "POSITION_BUSY" if exc.status_code == 503 else "POSITION_NOT_OPEN",
                        "suggestions": _suggest(db, parsed, filenames)}
        else:
            for f in accepted:
                used = f is cv and app_id is not None
                db.execute(text("""INSERT INTO app_private.mailbox_attachments(message_id, filename, mime_type, size_bytes,
                        content_sha256, status, reject_reason, application_id)
                    VALUES (:m, :f, :t, :s, :sha, :st, :r, :a)"""),
                           {"m": message_id, "f": f["filename"], "t": f["mime"], "s": f["size"],
                            "sha": hashlib.sha256(f["content"]).hexdigest(), "st": "USED" if used else "DISCARDED",
                            "r": None if used else ("DUPLICATE_CV" if f is cv else "NOT_MAIN_CV"), "a": app_id if used else None})
            db.commit()
            if app_id is None:
                _finish(db, message_id, "IGNORED", reason="DUPLICATE_CV", position_id=str(decision["position"].position_id),
                        match_method=decision["method"])
                return "IGNORED"
            _finish(db, message_id, "MATCHED", position_id=str(decision["position"].position_id), match_method=decision["method"])
            return "MATCHED"

    # Triage: keep the files so HR can open them and pick the position.
    storage = _storage()
    for f in accepted:
        path = f"mailbox/{message_id}/{uuid4()}{MIME_EXTENSIONS[f['mime']]}"
        _write_cv(storage, path, f["content"], f["mime"])
        db.execute(text("""INSERT INTO app_private.mailbox_attachments(message_id, filename, mime_type, size_bytes,
                content_sha256, storage_path, status) VALUES (:m, :f, :t, :s, :sha, :p, 'STORED')"""),
                   {"m": message_id, "f": f["filename"], "t": f["mime"], "s": f["size"],
                    "sha": hashlib.sha256(f["content"]).hexdigest(), "p": path})
    db.execute(text("""UPDATE app_private.mailbox_messages SET suggestions = CAST(:s AS jsonb) WHERE message_id = :id"""),
               {"s": json.dumps(decision["suggestions"]), "id": message_id})
    db.execute(text("""INSERT INTO app_private.audit_events(action_type, object_type, object_id, outcome, metadata)
        VALUES ('QUEUE_EMAIL_CV_TRIAGE', 'MAILBOX_MESSAGE', :id, 'SUCCESS', CAST(:m AS jsonb))"""),
               {"id": message_id, "m": json.dumps({"reason": decision["reason"], "files": len(accepted)})})
    db.commit()
    _finish(db, message_id, "NEEDS_TRIAGE", reason=decision["reason"])
    return "NEEDS_TRIAGE"


def sync_triage_label(account_id: str, gmail_id: str, target_status: str) -> None:
    """Best-effort update of Gmail labels after HR triages a message. Never raises: the HR decision is already saved."""
    try:
        if not gmail.configured() or target_status not in LABELS:
            return
        db = SessionLocal()
        try:
            account = db.execute(text("""SELECT * FROM app_private.mailbox_accounts
                WHERE account_id = :id AND status = 'ACTIVE'"""), {"id": account_id}).mappings().first()
        finally:
            db.close()
        if not account:
            return
        token = gmail.access_token(gmail.decrypt_token(account["refresh_token_ciphertext"]))
        labels = gmail.ensure_labels(token, list(LABELS.values()))
        add_id = labels.get(LABELS[target_status])
        remove_id = labels.get(LABELS["NEEDS_TRIAGE"])
        if add_id:
            gmail.replace_label(token, gmail_id, add_id, remove_id)
    except Exception as exc:  # noqa: BLE001 - a label is cosmetic; log and move on
        logger.warning("Could not update triage Gmail label", error_type=type(exc).__name__,
                       error=getattr(exc, "code", None))


def schedule_triage_label_sync(account_id: str, gmail_id: str, target_status: str) -> None:
    """Run the Gmail label update in the background so HR's request is not held up by Google."""
    threading.Thread(target=sync_triage_label, args=(account_id, gmail_id, target_status),
                     daemon=True, name="triage-label-sync").start()


MAX_MESSAGE_RETRIES = 5
STALE_RETRY_MINUTES = 15


def retry_failed_message(message_id: str) -> dict:
    """Re-process one FAILED mailbox message (e.g. after ClamAV or transient Gmail error). At most
    MAX_MESSAGE_RETRIES times; a message left in NEW by a crashed retry may be retried after STALE_RETRY_MINUTES."""
    if not gmail.configured():
        raise HTTPException(status_code=409, detail="Chưa bật hoặc chưa cấu hình kết nối Gmail")
    leftovers: list[str] = []
    db = SessionLocal()
    try:
        row = db.execute(text("""SELECT m.message_id, m.account_id, m.provider_message_id, m.status, m.retry_count,
                (m.retry_started_at IS NOT NULL AND m.retry_started_at < NOW() - make_interval(mins => :stale)) AS retry_stale,
                a.email_address, a.refresh_token_ciphertext, a.status AS account_status
            FROM app_private.mailbox_messages m
            JOIN app_private.mailbox_accounts a ON a.account_id = m.account_id
            WHERE m.message_id = :id FOR UPDATE OF m"""), {"id": message_id, "stale": STALE_RETRY_MINUTES}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy thư")
        if not (row["status"] == "FAILED" or (row["status"] == "NEW" and row["retry_stale"])):
            raise HTTPException(status_code=409, detail="Chỉ có thể thử lại các thư đang ở trạng thái lỗi")
        if row["retry_count"] >= MAX_MESSAGE_RETRIES:
            raise HTTPException(status_code=409, detail=f"Đã hết lượt thử lại ({MAX_MESSAGE_RETRIES} lần). Hãy mở thư trong Gmail "
                                                        "để kiểm tra hoặc nhờ Admin xử lý.")
        if row["account_status"] != "ACTIVE":
            raise HTTPException(status_code=409, detail="Hộp thư Gmail chưa ở trạng thái hoạt động")
        account = {"account_id": row["account_id"], "email_address": row["email_address"]}
        gmail_id = row["provider_message_id"]
        ciphertext = row["refresh_token_ciphertext"]
        # A failed run may have left files and rows half done: clear them so the retry starts clean. Rows of a CV
        # already turned into an application (USED) stay; the application itself is protected by the duplicate check.
        leftovers = [r["storage_path"] for r in db.execute(text("""SELECT storage_path FROM app_private.mailbox_attachments
            WHERE message_id = :id AND status = 'STORED' AND storage_path IS NOT NULL"""), {"id": message_id}).mappings()]
        db.execute(text("""DELETE FROM app_private.mailbox_attachments
            WHERE message_id = :id AND status IN ('REJECTED', 'STORED', 'DISCARDED')"""), {"id": message_id})
        db.execute(text("""UPDATE app_private.mailbox_messages SET status = 'NEW', reason = NULL,
            retry_count = retry_count + 1, retry_started_at = NOW() WHERE message_id = :id"""), {"id": message_id})
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    for path in leftovers:
        remove_stored(path)

    db = SessionLocal()
    try:
        token = gmail.access_token(gmail.decrypt_token(ciphertext))
        labels = gmail.ensure_labels(token, list(LABELS.values()))
        status = _process(db, account, token, gmail_id, message_id)
        label = LABELS.get(status)
        if label and labels.get(label):
            try:
                gmail.add_label(token, gmail_id, labels[label])
            except gmail.GmailError as exc:
                logger.warning("Could not label retried message", error=exc.code)
        updated = db.execute(text("SELECT status, reason, position_id FROM app_private.mailbox_messages WHERE message_id = :id"),
                             {"id": message_id}).mappings().one()
        return {"status": updated["status"], "reason": updated["reason"],
                "position_id": str(updated["position_id"]) if updated["position_id"] else None}
    except Exception as exc:
        db.rollback()
        code = getattr(exc, "code", type(exc).__name__)[:60]
        db.execute(text("UPDATE app_private.mailbox_messages SET status = 'FAILED', reason = :r WHERE message_id = :id AND status = 'NEW'"),
                   {"r": code, "id": message_id})
        db.commit()
        raise HTTPException(status_code=502, detail=f"Không thể đọc lại thư lúc này ({code})") from None
    finally:
        db.close()


# ---- syncing the mailbox -----------------------------------------------------------------

def active_account(db) -> Optional[dict]:
    row = db.execute(text("""SELECT * FROM app_private.mailbox_accounts WHERE status <> 'DISCONNECTED'
        ORDER BY connected_at DESC LIMIT 1""")).mappings().first()
    return dict(row) if row else None


def _account_error(account_id: str, code: str, *, fatal: bool) -> None:
    db = SessionLocal()
    try:
        db.execute(text("""UPDATE app_private.mailbox_accounts SET last_error = :e, updated_at = NOW(),
            status = CASE WHEN :fatal THEN 'ERROR' ELSE status END WHERE account_id = :id"""),
                   {"e": code, "fatal": fatal, "id": account_id})
        db.commit()
    finally:
        db.close()


def ensure_watch(account: dict, token: str) -> None:
    """(Re)start the Gmail push watch when it is missing or expires within a day."""
    if not settings.GMAIL_PUBSUB_TOPIC:
        return
    expires = account.get("watch_expires_at")
    if expires and (expires - datetime.now(timezone.utc)).total_seconds() > 86400:
        return
    data = gmail.watch(token, settings.GMAIL_PUBSUB_TOPIC)
    expires_at = datetime.fromtimestamp(int(data["expiration"]) / 1000, tz=timezone.utc)
    db = SessionLocal()
    try:
        db.execute(text("""UPDATE app_private.mailbox_accounts SET watch_expires_at = :x,
            history_id = COALESCE(history_id, :h), updated_at = NOW() WHERE account_id = :id"""),
                   {"x": expires_at, "h": str(data.get("historyId")), "id": account["account_id"]})
        db.commit()
    finally:
        db.close()
    account["watch_expires_at"] = expires_at
    account["history_id"] = account.get("history_id") or str(data.get("historyId"))


def sync_mailbox() -> dict:
    """Process new INBOX mail of the connected mailbox once. Safe to call from several places."""
    counts = {"MATCHED": 0, "NEEDS_TRIAGE": 0, "IGNORED": 0, "FAILED": 0}
    if not gmail.configured() or not _sync_lock.acquire(blocking=False):
        return counts
    try:
        db = SessionLocal()
        try:
            account = active_account(db)
        finally:
            db.close()
        if not account or account["status"] != "ACTIVE":
            return counts
        account_id = str(account["account_id"])
        watch_error = None
        try:
            refresh = gmail.decrypt_token(account["refresh_token_ciphertext"])
            token = gmail.access_token(refresh)
            try:
                ensure_watch(account, token)
            except gmail.GmailError as exc:
                # Without push notifications HRA still reads the mailbox on its regular check.
                logger.warning("Gmail watch could not start", error=exc.code)
                watch_error = "WATCH_" + exc.code
            labels = gmail.ensure_labels(token, list(LABELS.values()))
            if account.get("history_id"):
                try:
                    ids, latest = gmail.history_message_ids(token, account["history_id"])
                except gmail.GmailError as exc:
                    if exc.code != "NOT_FOUND":
                        raise
                    ids, latest = gmail.recent_inbox_ids(token), gmail.get_profile(token).get("historyId")
            else:
                ids, latest = gmail.recent_inbox_ids(token, 1), gmail.get_profile(token).get("historyId")
            for gid in ids:
                status = process_message(account, token, gid, labels)
                if status:
                    counts[status] = counts.get(status, 0) + 1
            db = SessionLocal()
            try:
                db.execute(text("""UPDATE app_private.mailbox_accounts SET history_id = COALESCE(:h, history_id),
                    last_sync_at = NOW(), last_error = :e, updated_at = NOW() WHERE account_id = :id"""),
                           {"h": str(latest) if latest else None, "e": watch_error, "id": account_id})
                db.commit()
            finally:
                db.close()
        except gmail.GmailError as exc:
            logger.error("Mailbox sync failed", error=exc.code)
            _account_error(account_id, exc.code, fatal=exc.code in ("TOKEN_REVOKED", "TOKEN_UNREADABLE"))
        return counts
    finally:
        _sync_lock.release()


def pull_notifications() -> Optional[bool]:
    """Wait briefly for Gmail's Pub/Sub notifications.

    True when there was new mail, False when there was none, None when Pub/Sub is not
    usable (not configured, or the pull failed) and the caller should check the mailbox itself.
    """
    if not (gmail.configured() and settings.GMAIL_PUBSUB_SUBSCRIPTION):
        return None
    db = SessionLocal()
    try:
        account = active_account(db)
    finally:
        db.close()
    if not account or account["status"] != "ACTIVE":
        return None
    try:
        token = gmail.access_token(gmail.decrypt_token(account["refresh_token_ciphertext"]))
        received = gmail.pull(token, settings.GMAIL_PUBSUB_SUBSCRIPTION)
        gmail.ack(token, settings.GMAIL_PUBSUB_SUBSCRIPTION, [m["ackId"] for m in received if m.get("ackId")])
        return bool(received)
    except gmail.GmailError as exc:
        logger.warning("Pub/Sub pull failed", error=exc.code)
        _account_error(str(account["account_id"]), "PUBSUB_" + exc.code, fatal=False)
        return None
