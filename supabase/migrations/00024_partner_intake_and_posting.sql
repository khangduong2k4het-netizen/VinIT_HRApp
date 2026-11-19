-- P3-3 / F3.03: a separate candidate website (partner site) sends CVs to HRA
-- server-to-server, and shows the job posting HR writes in HRA.

-- Candidate-facing posting text (intro, benefits, deadline, how to apply).
-- Shown on the candidate website next to the JD; never used for screening.
ALTER TABLE app_private.positions ADD COLUMN IF NOT EXISTS posting_content TEXT
    CHECK (posting_content IS NULL OR length(posting_content) <= 20000);

-- API keys of candidate websites allowed to call /v1/intake. Only a SHA-256 of
-- the key is stored; the key is shown once when created.
CREATE TABLE IF NOT EXISTS app_private.intake_clients (
    client_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 100),
    key_hash TEXT NOT NULL UNIQUE CHECK (key_hash ~ '^[0-9a-f]{64}$'),
    key_prefix TEXT NOT NULL,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);

-- Consent captured on a partner site is recorded with its own channel.
DO $$
DECLARE constraint_name TEXT;
BEGIN
    FOR constraint_name IN
        SELECT con.conname FROM pg_constraint con
        WHERE con.conrelid = 'app_private.application_data_consents'::regclass AND con.contype = 'c'
          AND pg_get_constraintdef(con.oid) LIKE '%channel%'
    LOOP
        EXECUTE format('ALTER TABLE app_private.application_data_consents DROP CONSTRAINT %I', constraint_name);
    END LOOP;
END $$;
ALTER TABLE app_private.application_data_consents ADD CONSTRAINT application_data_consents_channel_check
    CHECK (channel IN ('PORTAL', 'EMAIL_LINK', 'MANUAL', 'PARTNER_SITE'));

ALTER TABLE app_private.intake_clients ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_private.intake_clients FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.intake_clients TO service_role;
