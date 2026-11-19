-- P3-1: Talent Pool scans run as background worker jobs instead of inside the request.
-- Adds the TALENT_POOL_SCAN operation capability and job state on talent_pool_scans.

-- The capability CHECK is anonymous in 00001; find it by definition rather than by name.
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

-- Scans that already exist were produced synchronously, so they are COMPLETED.
ALTER TABLE app_private.talent_pool_scans
    ADD COLUMN IF NOT EXISTS operation_id UUID REFERENCES app_private.operations(operation_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'COMPLETED',
    ADD COLUMN IF NOT EXISTS failed_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS error_message TEXT,
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
UPDATE app_private.talent_pool_scans SET completed_at = created_at WHERE completed_at IS NULL AND status = 'COMPLETED';
ALTER TABLE app_private.talent_pool_scans ALTER COLUMN status SET DEFAULT 'PENDING';
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'talent_pool_scans_status_check') THEN
        ALTER TABLE app_private.talent_pool_scans ADD CONSTRAINT talent_pool_scans_status_check
            CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'));
    END IF;
END $$;

-- At most one active scan per position.
CREATE UNIQUE INDEX IF NOT EXISTS uq_talent_pool_scans_active
    ON app_private.talent_pool_scans(position_id) WHERE status IN ('PENDING', 'PROCESSING');
CREATE INDEX IF NOT EXISTS idx_talent_pool_scans_operation ON app_private.talent_pool_scans(operation_id);
