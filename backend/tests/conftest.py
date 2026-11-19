"""Tests may use only a disposable, migrated local PostgreSQL *_test database.

Integration fixtures TRUNCATE positions and auth.users CASCADE, deleting most
application data. Never point TEST_DATABASE_URL at a real Supabase project or
an existing development database; do not share it with another test process.
See backend/tests/README.md for setup and safety requirements.
"""
import os
from psycopg2.extensions import parse_dsn

url = os.environ.get("TEST_DATABASE_URL")
if url:
    try:
        parsed = parse_dsn(url)  # libpq's effective values, including URL query overrides
    except Exception as exc:
        raise RuntimeError("TEST_DATABASE_URL is not a valid PostgreSQL URL") from exc
    host = parsed.get("host")  # require explicit host; otherwise PGHOST could be remote
    hostaddr = parsed.get("hostaddr") or os.environ.get("PGHOSTADDR")
    local_host = host in ("localhost", "127.0.0.1", "::1") or (host and host.startswith("/") and "," not in host)
    local_addr = not hostaddr or hostaddr in ("127.0.0.1", "::1")
    dbname = parsed.get("dbname", "")
    has_indirection = any(parsed.get(key) for key in ("service", "servicefile", "options")) or any(
        os.environ.get(key) for key in ("PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")
    )
    if not local_host or not local_addr or not dbname.endswith("_test") or has_indirection:
        raise RuntimeError("TEST_DATABASE_URL must point to an explicit local disposable database named *_test")
    os.environ["DATABASE_URL"] = url
os.environ["APP_ENV"] = "testing"
# Tests must not inherit a developer's backend/.env (environment variables take
# precedence over it). Individual tests monkeypatch settings when they need the
# local auth backend or the mock AI.
os.environ["AUTH_BACKEND"] = "supabase"
os.environ["LLM_PROVIDER"] = "local"
os.environ["STORAGE_BACKEND"] = "local"
# Popping a variable would let .env supply it again, so secrets are set to empty.
os.environ["SUPABASE_JWT_SECRET"] = ""
os.environ["ADMIN_BOOTSTRAP_TOKEN"] = ""
os.environ["DEBUG"] = "false"
