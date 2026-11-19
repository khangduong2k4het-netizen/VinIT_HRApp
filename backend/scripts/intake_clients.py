"""F3.03: manage API keys for candidate websites that call /v1/intake.

Only a SHA-256 of each key is stored. The key is printed once, when created;
put it in the candidate website's server configuration (never in its pages).

Usage (from backend/, uses DATABASE_URL from the environment/.env):
    python scripts/intake_clients.py create "VinUni Careers"
    python scripts/intake_clients.py list
    python scripts/intake_clients.py revoke <client_id>
"""
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.api.partner_intake import key_hash  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402


def create(name: str) -> int:
    key = "hra_intake_" + secrets.token_urlsafe(32)
    db = SessionLocal()
    try:
        row = db.execute(text("""
            INSERT INTO app_private.intake_clients (name, key_hash, key_prefix)
            VALUES (:name, :h, :prefix) RETURNING client_id
        """), {"name": name.strip(), "h": key_hash(key), "prefix": key[:16]}).first()
        db.commit()
    finally:
        db.close()
    print(f"client_id: {row[0]}")
    print(f"key (shown once, store it on the candidate website's server): {key}")
    return 0


def list_clients() -> int:
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT client_id, name, key_prefix, created_at, last_used_at, revoked_at
            FROM app_private.intake_clients ORDER BY created_at
        """)).mappings().all()
    finally:
        db.close()
    for r in rows:
        state = "revoked " + r["revoked_at"].isoformat() if r["revoked_at"] else "active"
        used = r["last_used_at"].isoformat() if r["last_used_at"] else "never"
        print(f"{r['client_id']}  {r['name']!r}  {r['key_prefix']}...  {state}  last used: {used}")
    if not rows:
        print("(no clients)")
    return 0


def revoke(client_id: str) -> int:
    db = SessionLocal()
    try:
        n = db.execute(text("""
            UPDATE app_private.intake_clients SET revoked_at = NOW()
            WHERE client_id = CAST(:id AS uuid) AND revoked_at IS NULL
        """), {"id": client_id}).rowcount
        db.commit()
    finally:
        db.close()
    print("revoked" if n else "not found or already revoked")
    return 0 if n else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("create").add_argument("name")
    sub.add_parser("list")
    sub.add_parser("revoke").add_argument("client_id")
    args = parser.parse_args()
    if args.cmd == "create":
        return create(args.name)
    if args.cmd == "list":
        return list_clients()
    return revoke(args.client_id)


if __name__ == "__main__":
    raise SystemExit(main())
