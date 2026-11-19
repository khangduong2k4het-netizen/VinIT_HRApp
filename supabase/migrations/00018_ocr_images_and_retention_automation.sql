-- F2.06: numeric diagnostics of image OCR (no text).
-- F2.07: retention reminders, legal holds, reopen guard and purge OTP.
--
-- Safety model:
-- * Nothing here deletes candidate data. The periodic cycle only creates
--   cases, cancels cases of reopened positions and records reminders.
--   Physical purge stays an explicit, per-case action by an authorised user
--   who also enters a one-time code.
-- * Holds store a reason code and a Legal approval reference only. No free
--   text that could contain candidate identifiers.
-- * All tables are backend-only (RLS on, no grants to anon/authenticated).

ALTER TABLE app_private.document_processing_runs
    ADD COLUMN IF NOT EXISTS image_quality JSONB;

-- ======================================
-- Retention cases: hold status and cancel reason
-- ======================================

DO $$
DECLARE constraint_name TEXT;
BEGIN
    FOR constraint_name IN
        SELECT conname FROM pg_constraint
        WHERE conrelid = 'app_private.application_retention_cases'::regclass
          AND contype = 'c'
          AND pg_get_constraintdef(oid) LIKE '%status%'
    LOOP
        EXECUTE format('ALTER TABLE app_private.application_retention_cases DROP CONSTRAINT %I', constraint_name);
    END LOOP;
END $$;

ALTER TABLE app_private.application_retention_cases
    ADD CONSTRAINT application_retention_cases_status_check
    CHECK (status IN ('PENDING', 'SCHEDULED_FOR_DELETION', 'ON_HOLD', 'DELETED', 'CANCELLED'));

ALTER TABLE app_private.application_retention_cases
    ADD COLUMN IF NOT EXISTS cancel_reason TEXT
        CHECK (cancel_reason IS NULL OR cancel_reason IN ('MANUAL', 'POSITION_REOPENED')),
    ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;

-- One open case per application now also covers ON_HOLD.
DROP INDEX IF EXISTS app_private.idx_retention_cases_open_application;
CREATE UNIQUE INDEX idx_retention_cases_open_application
    ON app_private.application_retention_cases (application_id)
    WHERE status IN ('PENDING', 'SCHEDULED_FOR_DELETION', 'ON_HOLD') AND application_id IS NOT NULL;

-- ======================================
-- Retention exception holds
-- ======================================

CREATE TABLE IF NOT EXISTS app_private.retention_holds (
    hold_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    retention_case_id UUID NOT NULL REFERENCES app_private.application_retention_cases(retention_case_id),
    reason_code TEXT NOT NULL CHECK (reason_code IN ('COMPLAINT', 'INSPECTION', 'LEGAL_REQUEST', 'OTHER_LEGAL_BASIS')),
    -- Number/code of the Legal & Privacy approval document, not free text.
    legal_approval_reference TEXT NOT NULL
        CHECK (legal_approval_reference ~ '^[A-Za-z0-9][A-Za-z0-9 ./_:-]{1,79}$'),
    hold_until DATE,
    created_by UUID NOT NULL REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    released_by UUID REFERENCES auth.users(id),
    released_at TIMESTAMPTZ,
    release_reason TEXT CHECK (release_reason IS NULL OR release_reason IN ('MANUAL', 'POSITION_REOPENED'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_retention_holds_active
    ON app_private.retention_holds (retention_case_id) WHERE released_at IS NULL;

-- ======================================
-- Reminder notifications (30/15/7 days before due)
-- ======================================

CREATE TABLE IF NOT EXISTS app_private.retention_notifications (
    notification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id) ON DELETE CASCADE,
    -- Identifies one closure: a reopened and re-closed position gets new reminders.
    position_closed_at TIMESTAMPTZ NOT NULL,
    due_date TIMESTAMPTZ NOT NULL,
    milestone_days INTEGER NOT NULL CHECK (milestone_days > 0),
    recipient_user_id UUID NOT NULL REFERENCES auth.users(id),
    channel TEXT NOT NULL CHECK (channel IN ('IN_APP', 'EMAIL')),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'SENT', 'FAILED', 'SKIPPED')),
    open_case_count INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ,
    UNIQUE (position_id, position_closed_at, milestone_days, recipient_user_id, channel)
);
CREATE INDEX IF NOT EXISTS idx_retention_notifications_recipient
    ON app_private.retention_notifications (recipient_user_id, channel, read_at, created_at DESC);

-- ======================================
-- One-time codes for physical purge
-- ======================================

CREATE TABLE IF NOT EXISTS app_private.retention_purge_challenges (
    challenge_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    retention_case_id UUID NOT NULL REFERENCES app_private.application_retention_cases(retention_case_id),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    code_hash TEXT NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('EMAIL', 'DEV_ECHO')),
    attempts INTEGER NOT NULL DEFAULT 0,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_retention_purge_challenges_case
    ON app_private.retention_purge_challenges (retention_case_id, user_id, created_at DESC);

DO $$ DECLARE t TEXT; BEGIN
    FOREACH t IN ARRAY ARRAY['retention_holds', 'retention_notifications', 'retention_purge_challenges'] LOOP
        EXECUTE format('ALTER TABLE app_private.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('REVOKE ALL ON app_private.%I FROM PUBLIC, anon, authenticated', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.%I TO service_role', t);
    END LOOP;
END $$;
