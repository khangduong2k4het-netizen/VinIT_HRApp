"""Minimal outbound email for retention reminders and purge one-time codes.

Disabled unless ``SMTP_HOST`` and ``SMTP_FROM`` are configured. Callers must
never put candidate data (names, contacts, CV text) in a message: retention
emails only carry position codes, dates, counts and one-time codes.
"""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings


class MailError(Exception):
    pass


def email_enabled() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_FROM)


def send_email(to_address: str, subject: str, body: str) -> None:
    if not email_enabled():
        raise MailError("EMAIL_NOT_CONFIGURED")
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as client:
            if settings.SMTP_STARTTLS:
                client.starttls(context=ssl.create_default_context())
            if settings.SMTP_USERNAME:
                client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
            client.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        # Provider messages can echo addresses; keep only the error type.
        raise MailError(type(exc).__name__) from exc
