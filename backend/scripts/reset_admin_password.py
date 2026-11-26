"""Emergency password reset for an Admin who forgot their password. Run on the server by the operator.

For the case nobody can sign in to reset a password in the app: the only Admin forgot theirs and there is no
email (SMTP). It sets a temporary password for ONE account, forces a change at the next sign-in, revokes the
sessions issued before, clears a temporary lock-out and writes an audit event (actor = operator-cli, no
password in it). Only works with AUTH_BACKEND=local; with Supabase reset it in Supabase instead.
By default only accounts with the ADMIN role; other accounts need --force (normally an Admin resets those
in the app: Quản lý tài khoản -> Đặt lại mật khẩu).

Usage (from backend/, uses DATABASE_URL from the environment/.env):
    python scripts/reset_admin_password.py --email admin@vinuni.edu.vn
    python scripts/reset_admin_password.py --email admin@vinuni.edu.vn --password "A-12+char-temporary-pass"
    python scripts/reset_admin_password.py --email hr@vinuni.edu.vn --force
    python scripts/reset_admin_password.py --list-admins      # forgot which email the Admin used

Without --password a random temporary password is generated and printed once. Give it to the person through a
trusted channel; they must change it on first sign-in.
"""
from __future__ import annotations

import argparse
import secrets
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.services import local_auth  # noqa: E402


def generate_password() -> str:
    alphabet = string.ascii_letters + string.digits
    core = "".join(secrets.choice(alphabet) for _ in range(14))
    return f"{core[:7]}-{core[7:]}-{secrets.randbelow(90) + 10}!"


def password_problem(password: str) -> str | None:
    if len(password) < 12 or len(password.encode("utf-8")) > 72 or not password.strip():
        return "Mật khẩu cần ít nhất 12 ký tự và tối đa 72 byte UTF-8."
    return None


def list_admins() -> list[tuple[str, str, str]]:
    """(email, display name, account status) of every account that holds the ADMIN role, for an operator who forgot the email."""
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT u.email, p.display_name, p.account_status FROM auth.users u
            JOIN app_private.user_profiles p ON p.user_id = u.id
            WHERE EXISTS (SELECT 1 FROM app_private.user_role_assignments r
                          WHERE r.user_id = u.id AND r.role_code = 'ADMIN' AND r.revoked_at IS NULL)
            ORDER BY p.account_status, u.email
        """)).all()
        return [(r[0], r[1], r[2]) for r in rows]
    finally:
        db.close()


def reset(email: str, password: str | None = None, force: bool = False) -> tuple[str, str]:
    """Returns (user_id, temporary password). Raises ValueError with a message for the operator."""
    if settings.AUTH_BACKEND != "local":
        raise ValueError("Chỉ dùng được khi AUTH_BACKEND=local. Với Supabase hãy đặt lại mật khẩu trong Supabase.")
    chosen = password or generate_password()
    problem = password_problem(chosen)
    if problem:
        raise ValueError(problem)
    db = SessionLocal()
    try:
        row = db.execute(text("""
            SELECT u.id AS user_id, p.account_status,
                   EXISTS (SELECT 1 FROM app_private.user_role_assignments r
                           WHERE r.user_id = u.id AND r.role_code = 'ADMIN' AND r.revoked_at IS NULL) AS is_admin
            FROM auth.users u JOIN app_private.user_profiles p ON p.user_id = u.id
            WHERE lower(u.email) = lower(:email) FOR UPDATE OF p
        """), {"email": email.strip()}).mappings().first()
        if not row:
            raise ValueError("Không tìm thấy tài khoản với email này.")
        if row["account_status"] != "ACTIVE":
            raise ValueError(f"Tài khoản đang ở trạng thái {row['account_status']}; chỉ đặt lại cho tài khoản ACTIVE.")
        if not row["is_admin"] and not force:
            raise ValueError("Tài khoản này không phải Admin. Admin đặt lại trong app (Quản lý tài khoản), "
                             "hoặc thêm --force nếu thật sự cần.")
        user_id = str(row["user_id"])
        local_auth.set_password(db, user_id, chosen)  # also clears failed attempts and the temporary lock
        db.execute(text("""
            UPDATE app_private.user_profiles SET must_change_password = TRUE,
                tokens_valid_after = clock_timestamp(), updated_at = NOW() WHERE user_id = :id
        """), {"id": user_id})
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome, metadata)
            VALUES (NULL, 'EMERGENCY_RESET_PASSWORD', 'USER', :id, 'SUCCESS',
                    CAST('{"actor": "operator-cli", "via": "server_script"}' AS jsonb))
        """), {"id": user_id})
        db.commit()
        return user_id, chosen
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Emergency password reset for an Admin (AUTH_BACKEND=local).")
    parser.add_argument("--email")
    parser.add_argument("--list-admins", action="store_true", help="list the Admin accounts (email, name, status) and exit")
    parser.add_argument("--password", help="temporary password (12+ characters); generated when omitted")
    parser.add_argument("--force", action="store_true", help="also allow an account that is not an Admin")
    args = parser.parse_args()
    if args.list_admins:
        for email, name, status in list_admins():
            print(f"{email}	{name}	{status}")
        return 0
    if not args.email:
        parser.error("cần --email (hoặc --list-admins để xem danh sách Admin)")
    try:
        _, temporary = reset(args.email, args.password, args.force)
    except ValueError as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1
    print(f"Đã đặt mật khẩu tạm cho {args.email.strip()}: {temporary}")
    print("Người dùng phải đổi mật khẩu ngay ở lần đăng nhập đầu; các phiên đăng nhập cũ đã bị thu hồi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
