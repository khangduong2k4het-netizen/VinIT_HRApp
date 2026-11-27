-- A person who forgot their password asks an Admin (with a reason). The Admin checks and approves; only then
-- does the system email a one-time reset link to the account's own address. No request row is stored for an
-- unknown or inactive email, so nothing reveals whether an account exists and Admins are not spammed.
CREATE TABLE IF NOT EXISTS app_private.password_reset_requests (
    request_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (char_length(btrim(reason)) BETWEEN 5 AND 500),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    requested_ip_hash TEXT,
    decided_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    decided_at TIMESTAMPTZ,
    decision_note TEXT CHECK (decision_note IS NULL OR char_length(decision_note) <= 500)
);

-- At most one open request per account.
CREATE UNIQUE INDEX IF NOT EXISTS uq_password_reset_requests_one_pending
    ON app_private.password_reset_requests (user_id) WHERE status = 'PENDING';
CREATE INDEX IF NOT EXISTS idx_password_reset_requests_status
    ON app_private.password_reset_requests (status, requested_at DESC);

ALTER TABLE app_private.password_reset_requests ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_private.password_reset_requests FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.password_reset_requests TO service_role;
