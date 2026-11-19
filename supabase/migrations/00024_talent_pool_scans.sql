-- P3-1 phase 2: scan the Talent Pool against a new position's approved rubric.
-- A scan scores pool applications in place (no copy, no new application in the
-- target position). Results hold scores and redacted evidence quotes only.
CREATE TABLE IF NOT EXISTS app_private.talent_pool_scans (
    scan_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id) ON DELETE CASCADE,
    criteria_version_id UUID NOT NULL REFERENCES app_private.criteria_versions(criteria_version_id),
    requested_by UUID NOT NULL REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    eligible_count INTEGER NOT NULL DEFAULT 0,
    scored_count INTEGER NOT NULL DEFAULT 0,
    skipped_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
    method TEXT NOT NULL DEFAULT 'RULES_ONLY' CHECK (method IN ('RULES_ONLY'))
);
CREATE INDEX IF NOT EXISTS idx_talent_pool_scans_position ON app_private.talent_pool_scans(position_id, created_at DESC);

CREATE TABLE IF NOT EXISTS app_private.talent_pool_scan_results (
    scan_id UUID NOT NULL REFERENCES app_private.talent_pool_scans(scan_id) ON DELETE CASCADE,
    application_id UUID NOT NULL REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    matching_score NUMERIC(5,2),
    evidence_coverage NUMERIC(5,4) NOT NULL DEFAULT 0,
    matching_status TEXT NOT NULL,
    unresolved_count INTEGER NOT NULL DEFAULT 0,
    criterion_results JSONB NOT NULL DEFAULT '[]'::jsonb,
    hr_decision TEXT CHECK (hr_decision IN ('CONTACT', 'SKIP', 'LATER')),
    decided_by UUID REFERENCES auth.users(id),
    decided_at TIMESTAMPTZ,
    PRIMARY KEY (scan_id, application_id)
);

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['talent_pool_scans', 'talent_pool_scan_results'] LOOP
        EXECUTE format('ALTER TABLE app_private.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('REVOKE ALL ON app_private.%I FROM PUBLIC, anon, authenticated', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.%I TO service_role', t);
    END LOOP;
END $$;
