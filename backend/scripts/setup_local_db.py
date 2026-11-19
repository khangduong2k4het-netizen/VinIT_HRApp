"""Create and migrate a local PostgreSQL database for running HRA without Supabase.

Usage (from the backend folder):
    python scripts/setup_local_db.py                      # create/migrate "hra_local"
    python scripts/setup_local_db.py --write-env          # also create backend/.env if missing
    python scripts/setup_local_db.py --admin-url postgresql://postgres:PASS@127.0.0.1:5432/postgres

What it does:
  1. Creates the roles the migrations grant to (anon, authenticated, service_role) if missing.
  2. Creates the database if missing.
  3. Creates a minimal `auth` schema (auth.users, auth.uid()) standing in for Supabase Auth.
  4. Applies supabase/migrations/*.sql in order, once each (tracked in public.hra_local_migrations).
  5. With --write-env: writes backend/.env for AUTH_BACKEND=local + LLM_PROVIDER=mock with fresh
     random secrets. An existing .env is never overwritten.

Only local hosts are accepted unless --allow-remote is given. Never point this at
Supabase or a shared database.
"""
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import make_dsn, parse_dsn

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "supabase" / "migrations"
ENV_FILE = ROOT / "backend" / ".env"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

AUTH_STUB = """
CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE IF NOT EXISTS auth.users (id UUID PRIMARY KEY, email TEXT UNIQUE);
CREATE OR REPLACE FUNCTION auth.uid() RETURNS UUID LANGUAGE sql STABLE AS $$ SELECT NULL::UUID $$;
"""


def _local(dsn: str) -> bool:
    host = parse_dsn(dsn).get("host") or "localhost"
    return host in LOCAL_HOSTS or host.startswith("/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--admin-url", default="postgresql://postgres@127.0.0.1:5432/postgres",
                        help="Superuser connection to an existing database (used to create roles/database).")
    parser.add_argument("--database", default="hra_local", help="Database to create and migrate.")
    parser.add_argument("--write-env", action="store_true", help="Create backend/.env for local auth + mock AI if missing.")
    parser.add_argument("--allow-remote", action="store_true", help="Allow a non-local host (not recommended).")
    args = parser.parse_args()

    if not _local(args.admin_url) and not args.allow_remote:
        print("Refusing a non-local host. Use --allow-remote only for a disposable, private database.", file=sys.stderr)
        return 2

    admin = psycopg2.connect(args.admin_url)
    admin.autocommit = True
    with admin.cursor() as cur:
        for role, extra in (("anon", ""), ("authenticated", ""), ("service_role", " BYPASSRLS")):
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
            if not cur.fetchone():
                cur.execute(sql.SQL("CREATE ROLE {} NOLOGIN" + extra).format(sql.Identifier(role)))
                print(f"created role {role}")
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (args.database,))
        if not cur.fetchone():
            cur.execute(sql.SQL("CREATE DATABASE {} ENCODING 'UTF8'").format(sql.Identifier(args.database)))
            print(f"created database {args.database}")
    admin.close()

    target = make_dsn(args.admin_url, dbname=args.database)
    conn = psycopg2.connect(target)
    with conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.hra_local_migrations') IS NOT NULL, to_regnamespace('app_private') IS NOT NULL")
        tracked, has_schema = cur.fetchone()
        if not tracked and has_schema:
            print("This database already has app tables but no migration log; it was not created by this script. "
                  "Use a fresh --database name.", file=sys.stderr)
            return 1
        cur.execute(AUTH_STUB)
        cur.execute("CREATE TABLE IF NOT EXISTS public.hra_local_migrations (filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
        cur.execute("SELECT filename FROM public.hra_local_migrations")
        applied = {row[0] for row in cur.fetchall()}

    for path in sorted(MIGRATIONS.glob("*.sql")):
        if path.name in applied:
            continue
        with conn, conn.cursor() as cur:  # one transaction per migration
            cur.execute(path.read_text(encoding="utf-8"))
            cur.execute("INSERT INTO public.hra_local_migrations (filename) VALUES (%s)", (path.name,))
        print(f"applied {path.name}")
    conn.close()
    print(f"database {args.database} is up to date")

    if args.write_env:
        if ENV_FILE.exists():
            print(f"{ENV_FILE} already exists; not overwritten.")
        else:
            app_url = make_dsn(args.admin_url, dbname=args.database)
            params = parse_dsn(app_url)
            user = params.get("user", "postgres")
            password = params.get("password")
            host = params.get("host", "127.0.0.1")
            port = params.get("port", "5432")
            credentials = f"{user}:{password}" if password else user
            ENV_FILE.write_text("\n".join([
                "# Local development without Supabase or AI Core. Generated by scripts/setup_local_db.py.",
                "APP_ENV=development",
                "DEBUG=true",
                f"DATABASE_URL=postgresql://{credentials}@{host}:{port}/{args.database}",
                "AUTH_BACKEND=local",
                f"SUPABASE_JWT_SECRET={secrets.token_urlsafe(48)}",
                "# Needed once to create the first Admin at http://localhost:3000/bootstrap; remove afterwards.",
                f"ADMIN_BOOTSTRAP_TOKEN={secrets.token_urlsafe(32)}",
                "STORAGE_BACKEND=local",
                "LOCAL_STORAGE_PATH=./storage",
                "LLM_PROVIDER=mock",
                "",
            ]), encoding="utf-8")
            print(f"wrote {ENV_FILE} (contains secrets; it is git-ignored)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
