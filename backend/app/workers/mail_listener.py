"""Background listener for the connected Gmail mailbox (F3.03 email channel).

Gmail publishes a notification to Google Cloud Pub/Sub as soon as mail arrives.
This thread pulls that subscription (so HRA needs no public URL), then reads the
new mail. It also re-syncs every GMAIL_FALLBACK_SYNC_MINUTES in case a
notification was missed, and keeps the Gmail watch renewed (it lasts ~7 days).
Without a Pub/Sub subscription configured it simply checks every minute.
"""
from __future__ import annotations

import threading
import time

from app.core.config import settings
from app.core.logging import get_logger
from app.services import gmail_client
from app.services.mail_intake import pull_notifications, sync_mailbox

logger = get_logger(__name__)


class MailListener:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="mail-listener", daemon=True)
        self._thread.start()
        logger.info("Mail listener started", pubsub=bool(settings.GMAIL_PUBSUB_SUBSCRIPTION))

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    def _run(self) -> None:
        last_sync = 0.0
        notified = None
        while not self._stop.is_set():
            if not gmail_client.configured():
                self._stop.wait(60)
                continue
            try:
                notified = pull_notifications()
                # Pub/Sub working: rely on it and re-check rarely. Not configured or failing: check every minute.
                fallback = max(1, int(settings.GMAIL_FALLBACK_SYNC_MINUTES)) * 60 if notified is not None else 60
                if notified or time.monotonic() - last_sync >= fallback:
                    counts = sync_mailbox()
                    last_sync = time.monotonic()
                    if any(counts.values()):
                        logger.info("Mailbox synced", **{k.lower(): v for k, v in counts.items()})
            except Exception as exc:
                logger.error("Mail listener cycle failed", error_type=type(exc).__name__)
                self._stop.wait(30)
            # Pull returns at once when idle on some setups; do not spin.
            self._stop.wait(2 if notified is not None else 15)


mail_listener = MailListener()
