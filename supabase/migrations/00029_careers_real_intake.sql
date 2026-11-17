-- Independent of demo migrations. Durable staging receipt permits reconciliation
-- of an object after a crash between Storage upload and DB commit.
ALTER TABLE app_private.applications ALTER COLUMN created_by DROP NOT NULL;
ALTER TABLE app_private.applications DROP CONSTRAINT IF EXISTS application_actor_source_check;
ALTER TABLE app_private.applications ADD CONSTRAINT application_actor_source_check
    CHECK (created_by IS NOT NULL OR source_code IN ('CAREERS','CAREERS_DEMO','EMAIL_DEMO'));
ALTER TABLE app_private.cv_batches ALTER COLUMN uploaded_by DROP NOT NULL;
ALTER TABLE app_private.cv_batches ADD COLUMN IF NOT EXISTS intake_source text NOT NULL DEFAULT 'DIRECT_UPLOAD';
ALTER TABLE app_private.cv_batches DROP CONSTRAINT IF EXISTS batch_actor_source_check;
ALTER TABLE app_private.cv_batches ADD CONSTRAINT batch_actor_source_check
    CHECK (uploaded_by IS NOT NULL OR intake_source IN ('CAREERS','CAREERS_DEMO','EMAIL_DEMO'));
CREATE TABLE app_private.careers_intake_receipts (
    request_id uuid PRIMARY KEY,
    position_id uuid NOT NULL REFERENCES app_private.positions(position_id),
    fingerprint text NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
    storage_path text NOT NULL UNIQUE,
    state text NOT NULL CHECK (state IN ('STAGING','COMMITTED')),
    application_id uuid REFERENCES app_private.applications(application_id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX careers_intake_pending_idx ON app_private.careers_intake_receipts(created_at) WHERE state='STAGING';
ALTER TABLE app_private.careers_intake_receipts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_private.careers_intake_receipts FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.careers_intake_receipts TO service_role;
