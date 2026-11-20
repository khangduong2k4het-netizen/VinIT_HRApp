-- P3-1 phase 2, merged from PR #3 (Hoang248): rules-only Talent Pool scans run as
-- worker jobs, with HR decisions (CONTACT / SKIP / LATER) per result.
--
-- 00023 created a first version of these tables (LLM scoring, rank_number, criteria).
-- Scan results are derived data and can be re-run at any time, so the old tables are
-- replaced instead of migrated. Nothing outside these two tables references them.
-- Replaces PR #3's 00024_talent_pool_scans + 00025_talent_pool_scan_jobs, which
-- collided with 00023/00024 already on khangduong.

-- An old-style scan job still queued would find no scan row; close it first.
UPDATE app_private.operations
SET status = 'FAILED', error_code = 'PROCESSING_ERROR',
    error_message = 'Lượt quét Talent Pool cũ đã bị thay thế; vui lòng quét lại.', completed_at = NOW()
WHERE capability = 'TALENT_POOL_SCAN' AND status IN ('PENDING', 'PROCESSING');

DROP TABLE IF EXISTS app_private.talent_pool_scan_results;
DROP TABLE IF EXISTS app_private.talent_pool_scans;

-- Capability already added by 00023; re-assert it in case 00023 changed later.
DO $$
DECLARE c RECORD;
BEGIN
    FOR c IN
        SELECT conname FROM pg_constraint
        WHERE conrelid = 'app_private.operations'::regclass AND contype = 'c'
          AND pg_get_constraintdef(oid) ILIKE '%capability%'
    LOOP
        EXECUTE format('ALTER TABLE app_private.operations DROP CONSTRAINT %I', c.conname);
    END LOOP;
END $$;
ALTER TABLE app_private.operations
    ADD CONSTRAINT operations_capability_check
    CHECK (capability IN ('CV_PROCESSING', 'CRITERIA_GENERATION', 'ASSESSMENT', 'RANKING', 'DELETION', 'TALENT_POOL_SCAN'));

-- Same queue index as 00004, now covering scan jobs.
DROP INDEX IF EXISTS app_private.idx_operations_worker_queue;
CREATE INDEX idx_operations_worker_queue
    ON app_private.operations(status, created_at)
    WHERE status IN ('PENDING', 'PROCESSING')
      AND capability IN ('CV_PROCESSING', 'ASSESSMENT', 'RANKING', 'TALENT_POOL_SCAN');

CREATE TABLE app_private.talent_pool_scans (
    scan_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id) ON DELETE CASCADE,
    criteria_version_id UUID NOT NULL REFERENCES app_private.criteria_versions(criteria_version_id),
    requested_by UUID NOT NULL REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    eligible_count INTEGER NOT NULL DEFAULT 0,
    scored_count INTEGER NOT NULL DEFAULT 0,
    skipped_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
    method TEXT NOT NULL DEFAULT 'RULES_ONLY' CHECK (method IN ('RULES_ONLY')),
    operation_id UUID REFERENCES app_private.operations(operation_id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'PENDING'
        CONSTRAINT talent_pool_scans_status_check CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
    failed_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    completed_at TIMESTAMPTZ
);
CREATE INDEX idx_talent_pool_scans_position ON app_private.talent_pool_scans(position_id, created_at DESC);
CREATE INDEX idx_talent_pool_scans_operation ON app_private.talent_pool_scans(operation_id);
-- At most one active scan per position.
CREATE UNIQUE INDEX uq_talent_pool_scans_active
    ON app_private.talent_pool_scans(position_id) WHERE status IN ('PENDING', 'PROCESSING');

-- Scores and redacted evidence quotes only; deleting the application deletes its results.
CREATE TABLE app_private.talent_pool_scan_results (
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
CREATE INDEX idx_talent_pool_scan_results_app ON app_private.talent_pool_scan_results(application_id);

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['talent_pool_scans', 'talent_pool_scan_results'] LOOP
        EXECUTE format('ALTER TABLE app_private.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('REVOKE ALL ON app_private.%I FROM PUBLIC, anon, authenticated', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.%I TO service_role', t);
    END LOOP;
END $$;
