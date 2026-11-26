-- Forgot-password: one-time reset tokens. Only the SHA-256 of the token is stored,
-- the token itself is only in the link sent to the account's email (or echoed in
-- development). A token expires, is used once, and is invalidated by a newer request.
CREATE TABLE IF NOT EXISTS app_private.password_reset_tokens (
    token_hash TEXT PRIMARY KEY CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user
    ON app_private.password_reset_tokens (user_id, created_at DESC);

ALTER TABLE app_private.password_reset_tokens ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_private.password_reset_tokens FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.password_reset_tokens TO service_role;
