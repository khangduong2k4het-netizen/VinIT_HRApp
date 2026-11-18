-- P3-1 phase 2: scan the Talent Pool for a new position.
-- HR starts a scan for a position with approved criteria; the worker scores every
-- eligible pooled application (consent present and not withdrawn, inside the pool
-- window, not queued for deletion, marked by HR) against that position's rubric.
-- Results are kept apart from the position's own applicants and ranking.

-- New worker job type. It never blocks CV uploads on the target position: the
-- one-job-per-position guards only look at CV_PROCESSING / ASSESSMENT / RANKING.
DO $$
DECLARE constraint_name TEXT;
BEGIN
    FOR constraint_name IN
        SELECT con.conname FROM pg_constraint con
        WHERE con.conrelid = 'app_private.operations'::regclass AND con.contype = 'c'
          AND pg_get_constraintdef(con.oid) LIKE '%capability%'
    LOOP
        EXECUTE format('ALTER TABLE app_private.operations DROP CONSTRAINT %I', constraint_name);
    END LOOP;
END $$;
ALTER TABLE app_private.operations ADD CONSTRAINT operations_capability_check
    CHECK (capability IN ('CV_PROCESSING', 'CRITERIA_GENERATION', 'ASSESSMENT', 'RANKING', 'DELETION', 'TALENT_POOL_SCAN'));

CREATE TABLE IF NOT EXISTS app_private.talent_pool_scans (
    scan_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id) ON DELETE CASCADE,
    criteria_version_id UUID NOT NULL REFERENCES app_private.criteria_versions(criteria_version_id),
    operation_id UUID REFERENCES app_private.operations(operation_id),
    requested_by UUID REFERENCES auth.users(id),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
    candidate_count INTEGER NOT NULL DEFAULT 0,
    scored_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_talent_pool_scans_position ON app_private.talent_pool_scans(position_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_talent_pool_scans_operation ON app_private.talent_pool_scans(operation_id)
    WHERE operation_id IS NOT NULL;

-- One row per pooled application in a scan. Deleting the application (retention
-- purge) deletes its results, including the verified CV quotes kept in criteria.
CREATE TABLE IF NOT EXISTS app_private.talent_pool_scan_results (
    result_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_id UUID NOT NULL REFERENCES app_private.talent_pool_scans(scan_id) ON DELETE CASCADE,
    application_id UUID NOT NULL REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('SCORED', 'FAILED')),
    matching_status TEXT,
    matching_score NUMERIC,
    evidence_coverage NUMERIC,
    rank_number INTEGER,
    criteria JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (scan_id, application_id)
);
CREATE INDEX IF NOT EXISTS idx_talent_pool_scan_results_app ON app_private.talent_pool_scan_results(application_id);

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['talent_pool_scans', 'talent_pool_scan_results'] LOOP
        EXECUTE format('ALTER TABLE app_private.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('REVOKE ALL ON app_private.%I FROM PUBLIC, anon, authenticated', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.%I TO service_role', t);
    END LOOP;
END $$;
