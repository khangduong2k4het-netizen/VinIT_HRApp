-- Admin recovery by email: the mail carries a one-time code that plays the part of the "old password" on the
-- recovery page (code + new password + confirmation). Only the SHA-256 of the code is stored. A code expires
-- (15 minutes), works once, and is cancelled after 5 wrong tries; a new request replaces the open one.
CREATE TABLE IF NOT EXISTS app_private.admin_recovery_codes (
    code_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    code_hash TEXT NOT NULL CHECK (code_hash ~ '^[0-9a-f]{64}$'),
    expires_at TIMESTAMPTZ NOT NULL,
    failed_attempts INTEGER NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
    used_at TIMESTAMPTZ,
    cancelled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- At most one open code per account.
CREATE UNIQUE INDEX IF NOT EXISTS uq_admin_recovery_codes_one_open
    ON app_private.admin_recovery_codes (user_id) WHERE used_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_admin_recovery_codes_user ON app_private.admin_recovery_codes (user_id, created_at DESC);

ALTER TABLE app_private.admin_recovery_codes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_private.admin_recovery_codes FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.admin_recovery_codes TO service_role;
