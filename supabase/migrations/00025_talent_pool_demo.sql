-- Synthetic-only consent prototype, not a production consent policy.
CREATE TABLE app_private.talent_pool_demo_consents (
    application_id uuid PRIMARY KEY REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    notice_version text NOT NULL CHECK (notice_version = 'synthetic-demo-v1'),
    token_hash text NOT NULL UNIQUE CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    accepted_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    withdrawn_at timestamptz,
    CHECK (expires_at > accepted_at)
);
ALTER TABLE app_private.talent_pool_demo_consents ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_private.talent_pool_demo_consents FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.talent_pool_demo_consents TO service_role;
