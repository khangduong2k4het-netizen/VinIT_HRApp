-- Gmail test-only; no mailbox content, addresses or tokens are stored here.
ALTER TABLE app_private.applications DROP CONSTRAINT application_actor_source_check;
ALTER TABLE app_private.applications ADD CONSTRAINT application_actor_source_check
    CHECK (created_by IS NOT NULL OR source_code IN ('CAREERS','EMAIL_TEST','CAREERS_DEMO','EMAIL_DEMO'));
ALTER TABLE app_private.cv_batches DROP CONSTRAINT batch_actor_source_check;
ALTER TABLE app_private.cv_batches ADD CONSTRAINT batch_actor_source_check
    CHECK (uploaded_by IS NOT NULL OR intake_source IN ('CAREERS','EMAIL_TEST','CAREERS_DEMO','EMAIL_DEMO'));
CREATE TABLE app_private.gmail_test_messages (
    receipt_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    mailbox_hash text NOT NULL CHECK (mailbox_hash ~ '^[0-9a-f]{64}$'),
    message_id text NOT NULL CHECK (length(message_id) BETWEEN 1 AND 200),
    status text NOT NULL CHECK (status IN ('PENDING','REVIEW','SPAM','MALWARE','ACCEPTED')),
    reason text,
    application_id uuid REFERENCES app_private.applications(application_id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (mailbox_hash,message_id)
);
CREATE INDEX gmail_test_review_idx ON app_private.gmail_test_messages(updated_at DESC) WHERE status='REVIEW';
ALTER TABLE app_private.gmail_test_messages ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_private.gmail_test_messages FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.gmail_test_messages TO service_role;
