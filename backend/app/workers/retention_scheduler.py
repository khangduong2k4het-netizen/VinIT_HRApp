"""Periodic F2.07 retention cycle (case sync, reopen guard, reminders).

Started by the API process only when ``RETENTION_SCHEDULER_ENABLED`` is true.
Several API replicas are safe: the cycle takes a PostgreSQL advisory lock.
For hosts that prefer cron, ``scripts/run_retention_cycle.py`` runs one pass.
The cycle never deletes candidate data.
"""
from __future__ import annotations

import threading

from app.core.config import settings
from app.core.logging import get_logger
from app.services.retention_automation import run_retention_cycle

logger = get_logger(__name__)


class RetentionScheduler:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="retention-scheduler", daemon=True)
        self._thread.start()
        logger.info("Retention scheduler started", interval_minutes=settings.RETENTION_SCHEDULER_INTERVAL_MINUTES)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    def _run(self) -> None:
        interval = max(1, int(settings.RETENTION_SCHEDULER_INTERVAL_MINUTES)) * 60
        while not self._stop.is_set():
            try:
                run_retention_cycle()
            except Exception as exc:
                logger.error("Retention cycle failed", error_type=type(exc).__name__)
            self._stop.wait(interval)


retention_scheduler = RetentionScheduler()
