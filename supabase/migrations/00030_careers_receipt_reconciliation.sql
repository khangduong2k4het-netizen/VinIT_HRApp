-- Do not infer destinations for older staging rows: NULL means manual review.
ALTER TABLE app_private.careers_intake_receipts
    ADD COLUMN storage_backend text,
    ADD COLUMN storage_bucket text,
    ADD COLUMN storage_identity text;
ALTER TABLE app_private.careers_intake_receipts DROP CONSTRAINT careers_intake_receipts_state_check;
ALTER TABLE app_private.careers_intake_receipts ADD CONSTRAINT careers_intake_receipts_state_check
    CHECK (state IN ('STAGING','COMMITTED','ABANDONED'));
