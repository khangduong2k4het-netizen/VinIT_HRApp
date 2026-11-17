-- Careers prototype, disabled by default at the API. No existing position is published.
ALTER TABLE app_private.positions ADD COLUMN application_deadline_at timestamptz;
ALTER TABLE app_private.applications ALTER COLUMN created_by DROP NOT NULL;
ALTER TABLE app_private.applications ADD CONSTRAINT application_actor_source_check
    CHECK (created_by IS NOT NULL OR source_code = 'CAREERS_DEMO');
ALTER TABLE app_private.cv_batches ALTER COLUMN uploaded_by DROP NOT NULL;
ALTER TABLE app_private.cv_batches ADD COLUMN intake_source text NOT NULL DEFAULT 'DIRECT_UPLOAD';
ALTER TABLE app_private.cv_batches ADD CONSTRAINT batch_actor_source_check
    CHECK (uploaded_by IS NOT NULL OR intake_source = 'CAREERS_DEMO');
