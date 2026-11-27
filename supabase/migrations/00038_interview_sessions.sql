-- Interview Coordination & Calendar Loop (00038):
-- Connects structured interview rounds, multi-panelist conflict checking,
-- RFC 5545 .ics calendar export, AI evidence prep briefs, and F3.05 email invites.

CREATE TABLE IF NOT EXISTS app_private.interview_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id) ON DELETE CASCADE,
    round_no SMALLINT NOT NULL DEFAULT 1 CHECK (round_no BETWEEN 1 AND 10),
    title TEXT NOT NULL DEFAULT 'Phỏng vấn chuyên môn' CHECK (length(btrim(title)) BETWEEN 1 AND 160),
    session_status TEXT NOT NULL DEFAULT 'SCHEDULED'
        CHECK (session_status IN ('SCHEDULED', 'COMPLETED', 'CANCELLED', 'NO_SHOW')),
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    format TEXT NOT NULL CHECK (format IN ('ONLINE', 'ONSITE', 'PHONE')),
    location_or_link TEXT,
    prep_notes TEXT CHECK (prep_notes IS NULL OR length(prep_notes) <= 2000),
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (ends_at > starts_at),
    CHECK (format = 'ONSITE' OR (location_or_link IS NOT NULL AND length(btrim(location_or_link)) > 0))
);

-- Prevent duplicate active rounds for the same application at the DB layer.
CREATE UNIQUE INDEX IF NOT EXISTS uq_interview_sessions_active_round
    ON app_private.interview_sessions (application_id, round_no)
    WHERE session_status IN ('SCHEDULED', 'COMPLETED');

CREATE INDEX IF NOT EXISTS idx_interview_sessions_application
    ON app_private.interview_sessions (application_id, round_no);
CREATE INDEX IF NOT EXISTS idx_interview_sessions_time
    ON app_private.interview_sessions (starts_at, ends_at)
    WHERE session_status = 'SCHEDULED';

CREATE TABLE IF NOT EXISTS app_private.interview_panelists (
    session_id UUID NOT NULL REFERENCES app_private.interview_sessions(session_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    panel_role TEXT NOT NULL DEFAULT 'INTERVIEWER'
        CHECK (panel_role IN ('LEAD_INTERVIEWER', 'INTERVIEWER', 'OBSERVER')),
    added_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (session_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_interview_panelists_user
    ON app_private.interview_panelists (user_id);

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['interview_sessions', 'interview_panelists'] LOOP
        EXECUTE format('ALTER TABLE app_private.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('REVOKE ALL ON app_private.%I FROM PUBLIC, anon, authenticated', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.%I TO service_role', t);
    END LOOP;
END $$;
