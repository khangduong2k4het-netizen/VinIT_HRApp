-- Local authentication (AUTH_BACKEND=local) for running without Supabase Auth.
-- Identities still live in auth.users so every existing foreign key keeps
-- working; only the password verifier is stored here. Unused (empty) when
-- AUTH_BACKEND=supabase.
CREATE TABLE app_private.local_credentials (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    -- Self-describing scrypt hash: scrypt$N$r$p$salt$digest (base64). Never a plain password.
    password_hash TEXT NOT NULL CHECK (password_hash LIKE 'scrypt$%'),
    password_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    failed_attempts INTEGER NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
    locked_until TIMESTAMPTZ
);

ALTER TABLE app_private.local_credentials ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_private.local_credentials FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.local_credentials TO service_role;
