"""F2.07 — automated retention cycle, reminders and purge one-time codes.

The cycle never deletes candidate data. Each run:

1. cancels open cases whose position was reopened (or re-closed with a new
   ``closed_at``): the 12-month period restarts from the new closure;
2. creates PENDING cases for closed positions that are due or within the
   reminder window (largest of ``RETENTION_NOTICE_DAYS``);
3. records reminders for the HR recruiters/leads of the position and every
   global HR Lead at the 30/15/7-day milestones (in-app, plus email when
   SMTP is configured).

Physical deletion stays the explicit per-case flow in ``retention``: confirm
after the due date, then execute with a one-time code.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import SessionLocal
from app.services.mailer import MailError, email_enabled, send_email
from app.services.retention import (
    OPEN_CASE_STATUSES,
    RetentionError,
    _as_utc,
    _audit,
    _now,
    approved_policy,
    assert_position_still_closed,
    days_until,
    earliest_retention_months,
    generate_retention_cases,
    get_case,
    notice_window_days,
)

logger = get_logger(__name__)

# pg_try_advisory_lock key: only one retention cycle runs at a time.
RETENTION_CYCLE_LOCK_KEY = 70_207


def cancel_cases_of_reopened_positions(db, *, position_id: str | None = None,
                                       actor_user_id: str | None = None) -> int:
    """Cancel open cases that belong to a closure that no longer exists."""
    rows = db.execute(text("""
        UPDATE app_private.application_retention_cases c
        SET status = 'CANCELLED', cancel_reason = 'POSITION_REOPENED', cancelled_at = NOW()
        FROM app_private.positions p
        WHERE p.position_id = c.position_id
          AND c.status IN ('PENDING', 'SCHEDULED_FOR_DELETION', 'ON_HOLD')
          AND (CAST(:position_id AS uuid) IS NULL OR c.position_id = CAST(:position_id AS uuid))
          AND (p.status <> 'CLOSED' OR p.closed_at IS NULL OR p.closed_at <> c.position_closed_at)
        RETURNING c.retention_case_id, c.position_id, c.application_opaque_id, c.policy_version
    """), {"position_id": position_id}).mappings().all()
    if not rows:
        return 0
    case_ids = [str(row["retention_case_id"]) for row in rows]
    db.execute(text("""
        UPDATE app_private.deletion_jobs
        SET status = 'FAILED', error = 'CANCELLED_POSITION_REOPENED', completed_at = NOW()
        WHERE retention_case_id = ANY(CAST(:ids AS uuid[])) AND status IN ('PENDING', 'PROCESSING')
    """), {"ids": case_ids})
    db.execute(text("""
        UPDATE app_private.retention_holds
        SET released_by = :actor, released_at = NOW(), release_reason = 'POSITION_REOPENED'
        WHERE retention_case_id = ANY(CAST(:ids AS uuid[])) AND released_at IS NULL
    """), {"ids": case_ids, "actor": actor_user_id})
    by_position: dict[str, list[dict]] = {}
    for row in rows:
        by_position.setdefault(str(row["position_id"]), []).append(dict(row))
    for pid, cases in by_position.items():
        _audit(db, actor_user_id=actor_user_id, action="CANCEL_RETENTION_CASES_POSITION_REOPENED",
               case={"retention_case_id": cases[0]["retention_case_id"], "position_id": pid},
               outcome="CANCELLED", metadata={"position_id": pid, "cancelled_count": len(cases)})
    return len(rows)


def cancel_cases_of_superseded_policy(db, *, actor_user_id: str | None = None) -> int:
    """Cancel open cases whose policy was replaced by a longer one.

    A case stores the due date computed under the policy in force when it was
    created. When the approved policy gives that application a later due date
    (12 months -> 5 years with an active Talent Pool consent), the case would
    delete data too early, so it is cancelled and re-created later with the new
    due date. Legal holds (ON_HOLD) are kept: once released they come back as
    PENDING and are cancelled here.
    """
    policy = approved_policy(db)
    if not policy:
        return 0
    use_consent = policy["base_months"] is not None
    # Same rule as retention_due_date, per case.
    rows = db.execute(text("""
        UPDATE app_private.application_retention_cases c
        SET status = 'CANCELLED', cancel_reason = 'POLICY_EXTENDED', cancelled_at = NOW()
        WHERE c.status IN ('PENDING', 'SCHEDULED_FOR_DELETION')
          AND c.policy_version <> :policy_version
          AND GREATEST(
                c.position_closed_at + make_interval(months => :base_months),
                CASE WHEN :use_consent THEN (
                    SELECT k.granted_at + make_interval(months => :months)
                    FROM app_private.application_data_consents k
                    WHERE k.application_id = c.application_id
                      AND k.purpose = 'TALENT_POOL' AND k.withdrawn_at IS NULL) END
              ) > c.due_date
        RETURNING c.retention_case_id, c.position_id
    """), {"policy_version": policy["policy_version"], "months": policy["months"],
           "base_months": earliest_retention_months(policy), "use_consent": use_consent}).mappings().all()
    if not rows:
        return 0
    case_ids = [str(row["retention_case_id"]) for row in rows]
    db.execute(text("""
        UPDATE app_private.deletion_jobs
        SET status = 'FAILED', error = 'CANCELLED_POLICY_EXTENDED', completed_at = NOW()
        WHERE retention_case_id = ANY(CAST(:ids AS uuid[])) AND status IN ('PENDING', 'PROCESSING')
    """), {"ids": case_ids})
    by_position: dict[str, list[dict]] = {}
    for row in rows:
        by_position.setdefault(str(row["position_id"]), []).append(dict(row))
    for pid, cases in by_position.items():
        _audit(db, actor_user_id=actor_user_id, action="CANCEL_RETENTION_CASES_POLICY_EXTENDED",
               case={"retention_case_id": cases[0]["retention_case_id"], "position_id": pid},
               outcome="CANCELLED", metadata={"position_id": pid, "cancelled_count": len(cases),
                                              "policy_version": policy["policy_version"]})
    return len(rows)


def sync_due_cases(db) -> int:
    """Create cases for every closed position that is due or nearly due."""
    policy = approved_policy(db)
    if not policy:
        return 0
    # Shortest period: applications without an active Talent Pool consent.
    months = earliest_retention_months(policy)
    # Coarse SQL pre-filter; generate_retention_cases applies the exact rule
    # (including the later due date of applications with consent).
    horizon = _now() + timedelta(days=notice_window_days() + 1)
    positions = db.execute(text("""
        SELECT p.position_id FROM app_private.positions p
        WHERE p.status = 'CLOSED' AND p.closed_at IS NOT NULL
          AND p.closed_at + make_interval(months => :months) <= :horizon
          AND EXISTS (
              SELECT 1 FROM app_private.applications a
              WHERE a.position_id = p.position_id
                AND NOT EXISTS (
                    SELECT 1 FROM app_private.application_retention_cases c
                    WHERE c.application_id = a.application_id
                      AND c.status IN ('PENDING', 'SCHEDULED_FOR_DELETION', 'ON_HOLD', 'DELETED')))
        ORDER BY p.closed_at
    """), {"months": months, "horizon": horizon}).scalars().all()
    created = 0
    for position_id in positions:
        result = generate_retention_cases(db, position_id=str(position_id), actor_user_id=None)
        created += int(result["created_count"])
    return created


def _recipients(db, position_id: str) -> list[dict]:
    """HR recruiters/leads of the position plus every global HR Lead (active)."""
    return [dict(row) for row in db.execute(text("""
        SELECT DISTINCT u.id AS user_id, u.email
        FROM auth.users u
        JOIN app_private.user_profiles up ON up.user_id = u.id AND COALESCE(up.account_status, 'ACTIVE') = 'ACTIVE'
        WHERE EXISTS (
                SELECT 1 FROM app_private.position_assignments pa
                WHERE pa.position_id = :position_id AND pa.user_id = u.id AND pa.revoked_at IS NULL
                  AND pa.position_role IN ('HR_RECRUITER', 'HR_LEAD'))
           OR EXISTS (
                SELECT 1 FROM app_private.user_role_assignments ur
                WHERE ur.user_id = u.id AND ur.revoked_at IS NULL AND ur.role_code = 'HR_LEAD')
        ORDER BY u.id
    """), {"position_id": position_id}).mappings().all()]


def record_due_reminders(db, now: datetime | None = None) -> dict[str, Any]:
    """Record reminders at the configured milestones.

    Returns ``{"in_app_sent": n, "email_ids": [...]}``; EMAIL rows are sent
    by ``deliver_email_reminders`` after the transaction commits.

    Only the most urgent milestone reached is sent: if the cycle was off
    and a position is already 5 days from due, the 30/15-day reminders are
    stored as SKIPPED instead of sending three emails at once.
    """
    now = now or _now()
    milestones = sorted({int(day) for day in settings.RETENTION_NOTICE_DAYS})
    groups = db.execute(text("""
        SELECT c.position_id, c.position_closed_at,
               (c.due_date AT TIME ZONE 'UTC')::date AS due_on,
               MIN(c.due_date) AS due_date,
               COUNT(*) AS open_case_count
        FROM app_private.application_retention_cases c
        JOIN app_private.positions p ON p.position_id = c.position_id
        WHERE c.status IN ('PENDING', 'SCHEDULED_FOR_DELETION')
          AND p.status = 'CLOSED' AND p.closed_at = c.position_closed_at
        GROUP BY c.position_id, c.position_closed_at, (c.due_date AT TIME ZONE 'UTC')::date
    """)).mappings().all()
    email_ids: list[str] = []
    in_app_sent = 0
    send_email_channel = email_enabled()
    for group in groups:
        left = days_until(group["due_date"], now)
        if left is None or left <= 0:
            continue  # already due: the console shows it, no more countdown reminders
        reached = [day for day in milestones if left <= day]
        if not reached:
            continue
        target = min(reached)
        position_id = str(group["position_id"])
        for recipient in _recipients(db, position_id):
            for day in reached:
                status = "SENT" if day == target else "SKIPPED"
                inserted = db.execute(text("""
                    INSERT INTO app_private.retention_notifications
                        (position_id, position_closed_at, due_date, due_on, milestone_days, recipient_user_id,
                         channel, status, open_case_count, sent_at)
                    VALUES (:position_id, :closed_at, :due_date, :due_on, :day, :user_id, 'IN_APP', :status,
                            :count, CASE WHEN :status = 'SENT' THEN NOW() END)
                    ON CONFLICT (position_id, position_closed_at, due_on, milestone_days, recipient_user_id, channel)
                    DO NOTHING
                    RETURNING notification_id
                """), {"position_id": position_id, "closed_at": group["position_closed_at"],
                       "due_date": group["due_date"], "due_on": group["due_on"], "day": day,
                       "user_id": recipient["user_id"],
                       "status": status, "count": int(group["open_case_count"])}).scalar_one_or_none()
                if inserted and status == "SENT":
                    in_app_sent += 1
            if send_email_channel and recipient.get("email"):
                row = db.execute(text("""
                    INSERT INTO app_private.retention_notifications
                        (position_id, position_closed_at, due_date, due_on, milestone_days, recipient_user_id,
                         channel, status, open_case_count)
                    VALUES (:position_id, :closed_at, :due_date, :due_on, :day, :user_id, 'EMAIL', 'PENDING', :count)
                    ON CONFLICT (position_id, position_closed_at, due_on, milestone_days, recipient_user_id, channel)
                    DO NOTHING
                    RETURNING notification_id
                """), {"position_id": position_id, "closed_at": group["position_closed_at"],
                       "due_date": group["due_date"], "due_on": group["due_on"], "day": target,
                       "user_id": recipient["user_id"],
                       "count": int(group["open_case_count"])}).scalar_one_or_none()
                if row:
                    email_ids.append(str(row))
    return {"in_app_sent": in_app_sent, "email_ids": email_ids}


def deliver_email_reminders(notification_ids: list[str]) -> dict[str, int]:
    """Send committed EMAIL reminders one by one; each result is committed."""
    sent = failed = 0
    for notification_id in notification_ids:
        db = SessionLocal()
        try:
            row = db.execute(text("""
                SELECT n.notification_id, n.milestone_days, n.due_date, n.open_case_count,
                       u.email, p.title, p.position_code
                FROM app_private.retention_notifications n
                JOIN auth.users u ON u.id = n.recipient_user_id
                JOIN app_private.positions p ON p.position_id = n.position_id
                WHERE n.notification_id = :id AND n.status = 'PENDING' AND n.channel = 'EMAIL'
                FOR UPDATE OF n SKIP LOCKED
            """), {"id": notification_id}).mappings().first()
            if not row:
                db.rollback()
                continue
            due = _as_utc(row["due_date"]).date().isoformat()
            subject = f"[VinUni HRA] Hồ sơ vị trí {row['position_code']} đến hạn retention sau {row['milestone_days']} ngày"
            body = (
                f"Vị trí: {row['title']} ({row['position_code']})\n"
                f"Số hồ sơ chờ xử lý retention: {row['open_case_count']}\n"
                f"Ngày đến hạn: {due}\n\n"
                "Vui lòng mở Lưu trữ & xóa dữ liệu để xác nhận xóa hoặc tạm hoãn có văn bản Pháp chế:\n"
                f"{settings.APP_PUBLIC_URL.rstrip('/')}/retention\n\n"
                "Hệ thống không tự xóa dữ liệu. Email này không chứa thông tin ứng viên."
            )
            try:
                send_email(row["email"], subject, body)
                db.execute(text("""
                    UPDATE app_private.retention_notifications SET status = 'SENT', sent_at = NOW(), error_code = NULL
                    WHERE notification_id = :id
                """), {"id": notification_id})
                sent += 1
            except MailError as exc:
                db.execute(text("""
                    UPDATE app_private.retention_notifications SET status = 'FAILED', error_code = :error
                    WHERE notification_id = :id
                """), {"id": notification_id, "error": str(exc)[:80]})
                failed += 1
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    return {"emails_sent": sent, "emails_failed": failed}


def run_retention_cycle(now: datetime | None = None) -> dict[str, Any]:
    """One idempotent pass. Returns counts; ``skipped`` when another runs."""
    db = SessionLocal()
    try:
        # Transaction-scoped lock: released by the commit/rollback below.
        locked = db.execute(text("SELECT pg_try_advisory_xact_lock(:key)"),
                            {"key": RETENTION_CYCLE_LOCK_KEY}).scalar_one()
        if not locked:
            db.rollback()
            return {"skipped": True}
        cancelled = cancel_cases_of_reopened_positions(db)
        cancelled_policy = cancel_cases_of_superseded_policy(db)
        created = sync_due_cases(db)
        reminders = record_due_reminders(db, now)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    delivery = deliver_email_reminders(reminders["email_ids"])
    summary = {"skipped": False, "cases_cancelled_reopened": cancelled,
               "cases_cancelled_policy_extended": cancelled_policy, "cases_created": created,
               "in_app_reminders_sent": reminders["in_app_sent"], **delivery}
    logger.info("Retention cycle finished", **summary)
    return summary


# ----------------------------------------------------------------------
# One-time code before physical purge
# ----------------------------------------------------------------------

def _code_hash(challenge_id: str, code: str) -> str:
    key = (settings.SUPABASE_JWT_SECRET or "vinuni-hra-retention-otp").encode("utf-8")
    return hmac.new(key, f"{challenge_id}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


def create_purge_challenge(db, *, case_id: str, user_id: str) -> dict:
    """Issue a 6-digit code for one case and one user (F2.07 OTP).

    The code goes to the user's email. Without SMTP, development/testing can
    echo it in the response (``RETENTION_OTP_DEV_ECHO``); production refuses.
    """
    case = get_case(db, case_id, for_update=True)
    if case["status"] != "SCHEDULED_FOR_DELETION":
        raise RetentionError("Case cần được xác nhận xóa trước khi lấy mã", status_code=409)
    if _as_utc(case["due_date"]) > _now():
        raise RetentionError("Retention case chưa đến hạn xóa", status_code=409)
    assert_position_still_closed(db, case)
    recent = db.execute(text("""
        SELECT COUNT(*) FROM app_private.retention_purge_challenges
        WHERE user_id = :user_id AND created_at > NOW() - INTERVAL '10 minutes'
    """), {"user_id": user_id}).scalar_one()
    if int(recent) >= 5:
        raise RetentionError("Đã yêu cầu quá nhiều mã; vui lòng thử lại sau ít phút", status_code=429)

    email = db.execute(text("SELECT email FROM auth.users WHERE id = :id"), {"id": user_id}).scalar_one_or_none()
    if email_enabled() and email:
        channel = "EMAIL"
    elif settings.RETENTION_OTP_DEV_ECHO and settings.APP_ENV in ("development", "testing"):
        channel = "DEV_ECHO"
    else:
        raise RetentionError("Chưa cấu hình kênh gửi mã OTP (SMTP); không thể thực hiện xóa vật lý", status_code=503)

    db.execute(text("""
        UPDATE app_private.retention_purge_challenges SET expires_at = NOW()
        WHERE retention_case_id = :case_id AND user_id = :user_id
          AND consumed_at IS NULL AND expires_at > NOW()
    """), {"case_id": case_id, "user_id": user_id})
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge_id = db.execute(text("""
        INSERT INTO app_private.retention_purge_challenges
            (retention_case_id, user_id, code_hash, channel, expires_at)
        VALUES (:case_id, :user_id, 'pending', :channel, NOW() + make_interval(mins => :ttl))
        RETURNING challenge_id
    """), {"case_id": case_id, "user_id": user_id, "channel": channel,
           "ttl": settings.RETENTION_OTP_TTL_MINUTES}).scalar_one()
    challenge_id = str(challenge_id)
    db.execute(text("""
        UPDATE app_private.retention_purge_challenges SET code_hash = :hash WHERE challenge_id = :id
    """), {"hash": _code_hash(challenge_id, code), "id": challenge_id})
    if channel == "EMAIL":
        try:
            send_email(
                email,
                "[VinUni HRA] Mã xác nhận xóa dữ liệu ứng viên",
                f"Mã xác nhận: {code}\nHiệu lực {settings.RETENTION_OTP_TTL_MINUTES} phút, dùng một lần.\n"
                f"Hồ sơ (mã ẩn danh): {(case.get('application_opaque_id') or '')[:12]}\n"
                "Nếu bạn không yêu cầu xóa, hãy bỏ qua email này và báo Admin.",
            )
        except MailError as exc:
            raise RetentionError("Không gửi được mã OTP qua email", status_code=502) from exc
    _audit(db, actor_user_id=user_id, action="REQUEST_RETENTION_PURGE_OTP", case=case,
           outcome="ISSUED", metadata={"application_opaque_id": case.get("application_opaque_id"),
                                       "channel": channel})
    result = {"challenge_id": challenge_id, "channel": channel,
              "expires_in_minutes": settings.RETENTION_OTP_TTL_MINUTES}
    if channel == "DEV_ECHO":
        result["dev_code"] = code
    return result


def verify_purge_challenge(db, *, case_id: str, user_id: str, challenge_id: str, code: str) -> None:
    """Consume a valid code or raise. Failed attempts are counted.

    The caller must commit even when this raises, so attempts persist.
    """
    row = db.execute(text("""
        SELECT challenge_id, retention_case_id, user_id, code_hash, attempts, expires_at, consumed_at
        FROM app_private.retention_purge_challenges
        WHERE challenge_id = :id FOR UPDATE
    """), {"id": challenge_id}).mappings().first()
    if (not row or str(row["retention_case_id"]) != str(case_id) or str(row["user_id"]) != str(user_id)):
        raise RetentionError("Mã OTP không hợp lệ", status_code=400)
    if row["consumed_at"] is not None or _as_utc(row["expires_at"]) <= datetime.now(timezone.utc):
        raise RetentionError("Mã OTP đã hết hạn hoặc đã được dùng; vui lòng lấy mã mới", status_code=400)
    if int(row["attempts"]) >= settings.RETENTION_OTP_MAX_ATTEMPTS:
        raise RetentionError("Đã nhập sai quá số lần cho phép; vui lòng lấy mã mới", status_code=429)
    if not hmac.compare_digest(row["code_hash"], _code_hash(str(row["challenge_id"]), (code or "").strip())):
        db.execute(text("""
            UPDATE app_private.retention_purge_challenges SET attempts = attempts + 1 WHERE challenge_id = :id
        """), {"id": challenge_id})
        raise RetentionError("Mã OTP không đúng", status_code=400)
    db.execute(text("""
        UPDATE app_private.retention_purge_challenges SET consumed_at = NOW() WHERE challenge_id = :id
    """), {"id": challenge_id})


def notification_rows(db, *, user_id: str, unread_only: bool, limit: int = 50) -> list[dict]:
    rows = db.execute(text("""
        SELECT n.notification_id, n.position_id, n.due_date, n.milestone_days, n.open_case_count,
               n.created_at, n.read_at, p.title AS position_title, p.position_code
        FROM app_private.retention_notifications n
        JOIN app_private.positions p ON p.position_id = n.position_id
        WHERE n.recipient_user_id = :user_id AND n.channel = 'IN_APP' AND n.status = 'SENT'
          AND (NOT :unread_only OR n.read_at IS NULL)
        ORDER BY n.created_at DESC
        LIMIT :limit
    """), {"user_id": user_id, "unread_only": unread_only, "limit": limit}).mappings().all()
    return [{**dict(row), "notification_id": str(row["notification_id"]), "position_id": str(row["position_id"]),
             "days_until_due": days_until(row["due_date"])} for row in rows]


__all__ = [
    "OPEN_CASE_STATUSES",
    "cancel_cases_of_reopened_positions",
    "create_purge_challenge",
    "deliver_email_reminders",
    "notification_rows",
    "record_due_reminders",
    "run_retention_cycle",
    "sync_due_cases",
    "verify_purge_challenge",
]
