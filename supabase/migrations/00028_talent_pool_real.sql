-- Independent of synthetic-only migrations 00024-00026; no legacy application
-- becomes opted in. Rows are inserted only from a future verified intake flow.
CREATE TABLE app_private.talent_pool_consents (
    application_id uuid PRIMARY KEY REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    notice_version text NOT NULL CHECK (length(notice_version) BETWEEN 1 AND 100),
    token_hash text NOT NULL UNIQUE CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    consent_expires_at timestamptz NOT NULL,
    retention_expires_at timestamptz NOT NULL,
    withdrawn_at timestamptz,
    CHECK (consent_expires_at > accepted_at),
    CHECK (retention_expires_at > accepted_at)
);
CREATE INDEX talent_pool_consent_active_idx ON app_private.talent_pool_consents(application_id)
    WHERE withdrawn_at IS NULL;
ALTER TABLE app_private.talent_pool_consents ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_private.talent_pool_consents FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.talent_pool_consents TO service_role;
