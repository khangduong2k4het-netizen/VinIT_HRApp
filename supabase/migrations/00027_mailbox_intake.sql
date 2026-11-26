-- F3.03 (email channel): CVs sent to a connected Gmail recruiting mailbox become
-- applications. Gmail tells HRA about new mail through Google Cloud Pub/Sub; HRA
-- reads the message, picks the position from the address (+REQ-IT-043) or a
-- position code in the subject / body / file name, and creates the application.
-- Mail it cannot place waits in a triage list for HR.

-- One connected mailbox (Admin connects it with Google sign-in).
CREATE TABLE IF NOT EXISTS app_private.mailbox_accounts (
    account_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider TEXT NOT NULL DEFAULT 'GMAIL' CHECK (provider IN ('GMAIL')),
    email_address TEXT NOT NULL,
    refresh_token_ciphertext TEXT NOT NULL,     -- Fernet-encrypted, never returned by the API
    history_id TEXT,                            -- Gmail history position already processed
    watch_expires_at TIMESTAMPTZ,               -- Gmail push watch must be renewed before this
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'ERROR', 'DISCONNECTED')),
    last_error TEXT,                            -- error code only, no mail content
    last_sync_at TIMESTAMPTZ,
    connected_by UUID REFERENCES auth.users(id),
    connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- At most one active mailbox per address.
CREATE UNIQUE INDEX IF NOT EXISTS uq_mailbox_accounts_active
    ON app_private.mailbox_accounts (provider, lower(email_address)) WHERE status <> 'DISCONNECTED';

-- One row per received message HRA looked at.
CREATE TABLE IF NOT EXISTS app_private.mailbox_messages (
    message_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES app_private.mailbox_accounts(account_id) ON DELETE CASCADE,
    provider_message_id TEXT NOT NULL,          -- Gmail message id
    internet_message_id TEXT,                   -- RFC Message-ID, for duplicates across resends
    thread_id TEXT,
    from_address TEXT,
    from_name TEXT,
    to_addresses TEXT,
    subject TEXT,
    received_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'NEW'
        CHECK (status IN ('NEW', 'MATCHED', 'NEEDS_TRIAGE', 'IGNORED', 'FAILED')),
    match_method TEXT CHECK (match_method IN ('PLUS_ADDRESS', 'SUBJECT_CODE', 'BODY_CODE', 'FILENAME_CODE', 'HR')),
    reason TEXT,                                -- why it needs triage / was ignored (code, not content)
    suggestions JSONB NOT NULL DEFAULT '[]'::jsonb,
    position_id UUID REFERENCES app_private.positions(position_id) ON DELETE SET NULL,
    decided_by UUID REFERENCES auth.users(id),
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (account_id, provider_message_id)
);
CREATE INDEX IF NOT EXISTS idx_mailbox_messages_status ON app_private.mailbox_messages(status, created_at DESC);

-- Attachments kept from a message. A file waiting for triage is stored so HR can
-- open it; once it becomes an application the application's own copy is used.
CREATE TABLE IF NOT EXISTS app_private.mailbox_attachments (
    attachment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID NOT NULL REFERENCES app_private.mailbox_messages(message_id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    mime_type TEXT,
    size_bytes BIGINT,
    content_sha256 TEXT,
    storage_path TEXT,
    status TEXT NOT NULL DEFAULT 'STORED' CHECK (status IN ('STORED', 'REJECTED', 'USED', 'DISCARDED')),
    reject_reason TEXT,
    application_id UUID REFERENCES app_private.applications(application_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_mailbox_attachments_message ON app_private.mailbox_attachments(message_id);

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['mailbox_accounts', 'mailbox_messages', 'mailbox_attachments'] LOOP
        EXECUTE format('ALTER TABLE app_private.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('REVOKE ALL ON app_private.%I FROM PUBLIC, anon, authenticated', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.%I TO service_role', t);
    END LOOP;
END $$;

-- A CV sent by email is recorded as consent for that position only (channel EMAIL);
-- it is kept for the general retention period and is not added to the Talent Pool.
DO $$
DECLARE constraint_name TEXT;
BEGIN
    FOR constraint_name IN
        SELECT con.conname FROM pg_constraint con
        WHERE con.conrelid = 'app_private.application_data_consents'::regclass AND con.contype = 'c'
          AND pg_get_constraintdef(con.oid) LIKE '%channel%'
    LOOP
        EXECUTE format('ALTER TABLE app_private.application_data_consents DROP CONSTRAINT %I', constraint_name);
    END LOOP;
END $$;
ALTER TABLE app_private.application_data_consents ADD CONSTRAINT application_data_consents_channel_check
    CHECK (channel IN ('PORTAL', 'EMAIL_LINK', 'MANUAL', 'PARTNER_SITE', 'EMAIL'));
