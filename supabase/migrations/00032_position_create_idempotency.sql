-- Position creation receipts: no JD text or other form contents are stored here.
-- Retain a tombstone if a position is deleted so retries cannot recreate it.
CREATE TABLE app_private.position_create_requests (
    actor_user_id UUID NOT NULL REFERENCES auth.users(id),
    request_id UUID NOT NULL,
    request_fingerprint TEXT NOT NULL CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    position_id UUID REFERENCES app_private.positions(position_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (actor_user_id, request_id)
);
ALTER TABLE app_private.position_create_requests ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_private.position_create_requests FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON app_private.position_create_requests TO service_role;
