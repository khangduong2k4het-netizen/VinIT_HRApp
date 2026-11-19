-- Retention workflow support and audit tamper evidence.
--
-- Safety model:
-- * A retention case survives the candidate purge as an anonymised record:
--   the application FK becomes SET NULL and only a domain-separated SHA-256
--   opaque id remains.  Candidate rows/files are deleted by the backend
--   service after an authorised HR confirmation; nothing here auto-deletes.
-- * audit_events become append-only for UPDATE/DELETE and gain a SHA-256
--   hash chain.  This is tamper evidence against application-level mistakes;
--   a database superuser who can disable triggers/drop tables is outside the
--   application threat model and must be controlled operationally.

-- ======================================
-- Retention cases / deletion jobs
-- ======================================

ALTER TABLE app_private.application_retention_cases
    ADD COLUMN IF NOT EXISTS position_id UUID REFERENCES app_private.positions(position_id),
    ADD COLUMN IF NOT EXISTS application_opaque_id TEXT;

UPDATE app_private.application_retention_cases c
SET position_id = a.position_id
FROM app_private.applications a
WHERE c.application_id = a.application_id
  AND c.position_id IS NULL;

-- Keep the case as anonymised evidence after the application row is purged.
DO $$
BEGIN
    ALTER TABLE app_private.application_retention_cases
        ALTER COLUMN application_id DROP NOT NULL;
EXCEPTION WHEN others THEN
    -- Re-running a partially applied local migration must not fail solely
    -- because the column is already nullable.
    NULL;
END $$;

DO $$
DECLARE constraint_name TEXT;
BEGIN
    SELECT conname INTO constraint_name
    FROM pg_constraint
    WHERE conrelid = 'app_private.application_retention_cases'::regclass
      AND contype = 'f'
      AND conkey = ARRAY[(
          SELECT attnum FROM pg_attribute
          WHERE attrelid = 'app_private.application_retention_cases'::regclass
            AND attname = 'application_id'
      )];
    IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE app_private.application_retention_cases DROP CONSTRAINT %I', constraint_name);
    END IF;
END $$;

ALTER TABLE app_private.application_retention_cases
    ADD CONSTRAINT application_retention_cases_application_id_fkey
    FOREIGN KEY (application_id) REFERENCES app_private.applications(application_id) ON DELETE SET NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_retention_cases_open_application
    ON app_private.application_retention_cases (application_id)
    WHERE application_id IS NOT NULL AND status IN ('PENDING', 'SCHEDULED_FOR_DELETION');

CREATE INDEX IF NOT EXISTS idx_retention_cases_position_status_due
    ON app_private.application_retention_cases (position_id, status, due_date);

CREATE INDEX IF NOT EXISTS idx_retention_cases_opaque
    ON app_private.application_retention_cases (application_opaque_id)
    WHERE application_opaque_id IS NOT NULL;

ALTER TABLE app_private.deletion_jobs
    ADD COLUMN IF NOT EXISTS application_opaque_id TEXT;

DO $$
BEGIN
    ALTER TABLE app_private.deletion_jobs
        ALTER COLUMN retention_case_id DROP NOT NULL;
EXCEPTION WHEN others THEN
    NULL;
END $$;

DO $$
DECLARE constraint_name TEXT;
BEGIN
    SELECT conname INTO constraint_name
    FROM pg_constraint
    WHERE conrelid = 'app_private.deletion_jobs'::regclass
      AND contype = 'f'
      AND conkey = ARRAY[(
          SELECT attnum FROM pg_attribute
          WHERE attrelid = 'app_private.deletion_jobs'::regclass
            AND attname = 'retention_case_id'
      )];
    IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE app_private.deletion_jobs DROP CONSTRAINT %I', constraint_name);
    END IF;
END $$;

ALTER TABLE app_private.deletion_jobs
    ADD CONSTRAINT deletion_jobs_retention_case_id_fkey
    FOREIGN KEY (retention_case_id) REFERENCES app_private.application_retention_cases(retention_case_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_deletion_jobs_case_status
    ON app_private.deletion_jobs (retention_case_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_deletion_jobs_opaque
    ON app_private.deletion_jobs (application_opaque_id)
    WHERE application_opaque_id IS NOT NULL;

ALTER TABLE app_private.application_retention_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_private.deletion_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_private.deletion_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_private.application_retention_cases, app_private.deletion_jobs, app_private.deletion_events
    FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON app_private.application_retention_cases, app_private.deletion_jobs, app_private.deletion_events
    TO service_role;

-- Refresh service-role views so new columns are visible consistently.
DROP VIEW IF EXISTS public.application_retention_cases;
CREATE VIEW public.application_retention_cases WITH (security_invoker=true) AS
    SELECT * FROM app_private.application_retention_cases;
DROP VIEW IF EXISTS public.deletion_jobs;
CREATE VIEW public.deletion_jobs WITH (security_invoker=true) AS
    SELECT * FROM app_private.deletion_jobs;
DROP VIEW IF EXISTS public.deletion_events;
CREATE VIEW public.deletion_events WITH (security_invoker=true) AS
    SELECT * FROM app_private.deletion_events;
REVOKE ALL ON public.application_retention_cases, public.deletion_jobs, public.deletion_events
    FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON public.application_retention_cases, public.deletion_jobs, public.deletion_events
    TO service_role;

-- ======================================
-- Audit hash chain + append-only guard
-- ======================================

CREATE SEQUENCE IF NOT EXISTS app_private.audit_event_chain_seq AS BIGINT;

ALTER TABLE app_private.audit_events
    ADD COLUMN IF NOT EXISTS chain_sequence BIGINT,
    ADD COLUMN IF NOT EXISTS previous_event_hash TEXT,
    ADD COLUMN IF NOT EXISTS event_hash TEXT;

WITH ordered AS (
    SELECT event_id, ROW_NUMBER() OVER (ORDER BY created_at, event_id) AS seq
    FROM app_private.audit_events
    WHERE chain_sequence IS NULL
)
UPDATE app_private.audit_events e
SET chain_sequence = ordered.seq + COALESCE((SELECT MAX(chain_sequence) FROM app_private.audit_events), 0)
FROM ordered
WHERE e.event_id = ordered.event_id;

SELECT setval('app_private.audit_event_chain_seq',
              COALESCE((SELECT MAX(chain_sequence) FROM app_private.audit_events), 0) + 1,
              false);

ALTER TABLE app_private.audit_events
    ALTER COLUMN chain_sequence SET NOT NULL,
    ALTER COLUMN chain_sequence SET DEFAULT nextval('app_private.audit_event_chain_seq');

ALTER SEQUENCE app_private.audit_event_chain_seq
    OWNED BY app_private.audit_events.chain_sequence;

CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_events_chain_sequence
    ON app_private.audit_events (chain_sequence);

CREATE OR REPLACE FUNCTION app_private.compute_audit_event_hash(
    previous_hash TEXT,
    audit_row app_private.audit_events
) RETURNS TEXT AS $$
    SELECT encode(digest(concat_ws('|',
        'vinuni-hra-audit-v1',
        COALESCE(previous_hash, ''),
        COALESCE((audit_row).chain_sequence::TEXT, ''),
        COALESCE((audit_row).event_id::TEXT, ''),
        COALESCE((audit_row).actor_user_id::TEXT, ''),
        COALESCE((audit_row).action_type, ''),
        COALESCE((audit_row).object_type, ''),
        COALESCE((audit_row).object_id::TEXT, ''),
        COALESCE((audit_row).position_id::TEXT, ''),
        COALESCE((audit_row).outcome, ''),
        COALESCE((audit_row).correlation_id::TEXT, ''),
        COALESCE((audit_row).metadata::TEXT, ''),
        COALESCE(to_char((audit_row).created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'), '')
    ), 'sha256'), 'hex');
$$ LANGUAGE sql IMMUTABLE;

DO $$
DECLARE audit_row app_private.audit_events%ROWTYPE;
DECLARE previous_hash TEXT := NULL;
DECLARE computed_hash TEXT;
BEGIN
    FOR audit_row IN
        SELECT * FROM app_private.audit_events ORDER BY chain_sequence
    LOOP
        computed_hash := app_private.compute_audit_event_hash(previous_hash, audit_row);
        UPDATE app_private.audit_events
        SET previous_event_hash = previous_hash,
            event_hash = computed_hash
        WHERE event_id = audit_row.event_id;
        previous_hash := computed_hash;
    END LOOP;
END $$;

CREATE OR REPLACE FUNCTION app_private.set_audit_event_hash() RETURNS trigger AS $$
DECLARE previous_hash TEXT;
BEGIN
    -- Serialise chain appends inside the inserting transaction.  The lock is
    -- released at commit/rollback; sequence gaps after rollback are harmless.
    PERFORM pg_advisory_xact_lock(418630022);
    IF NEW.created_at IS NULL THEN
        NEW.created_at := NOW();
    END IF;
    NEW.chain_sequence := nextval('app_private.audit_event_chain_seq');
    SELECT event_hash INTO previous_hash
    FROM app_private.audit_events
    ORDER BY chain_sequence DESC
    LIMIT 1;
    NEW.previous_event_hash := previous_hash;
    NEW.event_hash := app_private.compute_audit_event_hash(previous_hash, NEW);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_events_set_hash ON app_private.audit_events;
CREATE TRIGGER audit_events_set_hash
    BEFORE INSERT ON app_private.audit_events
    FOR EACH ROW EXECUTE FUNCTION app_private.set_audit_event_hash();

CREATE OR REPLACE FUNCTION app_private.prevent_audit_event_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_events are append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_events_append_only ON app_private.audit_events;
CREATE TRIGGER audit_events_append_only
    BEFORE UPDATE OR DELETE ON app_private.audit_events
    FOR EACH ROW EXECUTE FUNCTION app_private.prevent_audit_event_mutation();

REVOKE UPDATE, DELETE ON app_private.audit_events FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT, INSERT ON app_private.audit_events TO service_role;
REVOKE EXECUTE ON FUNCTION app_private.compute_audit_event_hash(TEXT, app_private.audit_events) FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION app_private.set_audit_event_hash() FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION app_private.prevent_audit_event_mutation() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION app_private.compute_audit_event_hash(TEXT, app_private.audit_events) TO service_role;

-- Refresh the service-role view after adding hash-chain columns.
DROP VIEW IF EXISTS public.audit_events;
CREATE VIEW public.audit_events WITH (security_invoker=true) AS
    SELECT * FROM app_private.audit_events;
REVOKE ALL ON public.audit_events FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON public.audit_events TO service_role;
