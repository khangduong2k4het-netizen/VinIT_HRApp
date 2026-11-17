-- P3-3 (public application portal) and P3-1 phase 1 (Talent Pool eligibility).
-- All new objects are backend-only: RLS on, no access for browser roles.

-- Applications can now come from the public portal, with no signed-in creator.
ALTER TABLE app_private.applications ALTER COLUMN created_by DROP NOT NULL;
ALTER TABLE app_private.cv_batches ALTER COLUMN uploaded_by DROP NOT NULL;

-- Opt-in: a position is visible on the public portal only when HR turns this on.
ALTER TABLE app_private.positions ADD COLUMN IF NOT EXISTS public_apply_enabled BOOLEAN NOT NULL DEFAULT FALSE;

-- SHA-256 of the stored CV, used to reject a resubmission to the same position.
ALTER TABLE app_private.application_documents ADD COLUMN IF NOT EXISTS content_sha256 TEXT;
CREATE INDEX IF NOT EXISTS idx_application_documents_sha ON app_private.application_documents(content_sha256)
    WHERE content_sha256 IS NOT NULL;

-- Consent captured when the CV is received. Append-only except for withdrawn_at.
CREATE TABLE IF NOT EXISTS app_private.application_data_consents (
    consent_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    purpose TEXT NOT NULL CHECK (purpose IN ('THIS_POSITION', 'TALENT_POOL')),
    notice_version TEXT NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('PORTAL', 'EMAIL_LINK', 'MANUAL')),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    withdrawn_at TIMESTAMPTZ,
    withdrawn_by UUID REFERENCES auth.users(id),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_consent_application_purpose
    ON app_private.application_data_consents(application_id, purpose);

-- HR marks a received application as a Talent Pool candidate (requires consent).
CREATE TABLE IF NOT EXISTS app_private.talent_pool_marks (
    mark_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    marked_by UUID NOT NULL REFERENCES auth.users(id),
    marked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reason_code TEXT NOT NULL CHECK (reason_code IN ('STRONG_FIT', 'NEAR_MISS', 'OTHER_ROLE_FIT')),
    removed_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_talent_pool_active_mark
    ON app_private.talent_pool_marks(application_id) WHERE removed_at IS NULL;

-- Public-endpoint throttling. Only a salted hash of the address is stored.
CREATE TABLE IF NOT EXISTS app_private.public_intake_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ip_hash TEXT NOT NULL,
    position_id UUID REFERENCES app_private.positions(position_id) ON DELETE CASCADE,
    outcome TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_public_intake_events_ip ON app_private.public_intake_events(ip_hash, created_at);

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['application_data_consents', 'talent_pool_marks', 'public_intake_events'] LOOP
        EXECUTE format('ALTER TABLE app_private.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('REVOKE ALL ON app_private.%I FROM PUBLIC, anon, authenticated', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.%I TO service_role', t);
    END LOOP;
END $$;
