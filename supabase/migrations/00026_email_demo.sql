-- Distinct origin for the offline synthetic mailbox intake.
ALTER TABLE app_private.applications DROP CONSTRAINT application_actor_source_check;
ALTER TABLE app_private.applications ADD CONSTRAINT application_actor_source_check
    CHECK (created_by IS NOT NULL OR source_code IN ('CAREERS_DEMO','EMAIL_DEMO'));
ALTER TABLE app_private.cv_batches DROP CONSTRAINT batch_actor_source_check;
ALTER TABLE app_private.cv_batches ADD CONSTRAINT batch_actor_source_check
    CHECK (uploaded_by IS NOT NULL OR intake_source IN ('CAREERS_DEMO','EMAIL_DEMO'));
