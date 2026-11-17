"""Offline MIME routing demonstration. Never contacts a mailbox or persists content."""
import re
from email import policy
from email.parser import BytesParser

MAX_MESSAGE_BYTES = 15_000_000
MAX_ATTACHMENT_BYTES = 10_000_000


def inspect_synthetic_email(raw: bytes, eligible_codes: set[str]) -> dict:
    """Return only metadata, not sender, body or attachments. Codes must be supplied by caller.

    This is not a spam filter, malware scanner, or a production ingestion service.
    """
    if not raw or len(raw) > MAX_MESSAGE_BYTES:
        return {'status': 'REVIEW', 'reason': 'MESSAGE_SIZE'}
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
        if message.defects:
            return {'status': 'REVIEW', 'reason': 'MALFORMED'}
        subject = str(message.get('Subject', ''))
        matches = [code for code in eligible_codes if re.search(r'(?<![\w-])' + re.escape(code) + r'(?![\w-])', subject, re.IGNORECASE)]
        if len(matches) != 1:
            return {'status': 'REVIEW', 'reason': 'POSITION_AMBIGUOUS'}
        attachments = [part for part in message.walk() if part.get_content_disposition() == 'attachment']
        if len(attachments) != 1:
            return {'status': 'REVIEW', 'reason': 'ATTACHMENT_COUNT'}
        part = attachments[0]
        if part.defects:
            return {'status': 'REVIEW', 'reason': 'MALFORMED'}
        name = (part.get_filename() or '').lower()
        content = part.get_payload(decode=True)
        if not isinstance(content, bytes) or not 0 < len(content) <= MAX_ATTACHMENT_BYTES or not name.endswith(('.pdf', '.docx')):
            return {'status': 'REVIEW', 'reason': 'ATTACHMENT_INVALID'}
        return {'status': 'CANDIDATE', 'position_code': matches[0], 'attachment_size': len(content)}
    except (ValueError, TypeError, LookupError):
        return {'status': 'REVIEW', 'reason': 'MALFORMED'}
