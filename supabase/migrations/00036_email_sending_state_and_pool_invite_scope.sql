-- Wave 5 fixes.
-- 1) Candidate emails get a SENDING state: a message is claimed (DRAFT/FAILED -> SENDING) by one conditional
--    UPDATE before SMTP is called, so two workers can never send the same letter twice.
-- 2) A Talent Pool invitation is tied to the scan that justified it (the target position), so access and
--    consent are checked again from that scan every time it is saved or sent.
-- 3) Mailbox messages keep a retry counter so a failed message cannot be retried forever.

ALTER TABLE app_private.candidate_emails DROP CONSTRAINT IF EXISTS candidate_emails_status_check;
ALTER TABLE app_private.candidate_emails ADD CONSTRAINT candidate_emails_status_check
    CHECK (status IN ('DRAFT', 'SENDING', 'RECORDED', 'SENT', 'FAILED', 'CANCELLED'));

ALTER TABLE app_private.candidate_emails ADD COLUMN IF NOT EXISTS sending_started_at TIMESTAMPTZ;
ALTER TABLE app_private.candidate_emails ADD COLUMN IF NOT EXISTS pool_scan_id UUID
    REFERENCES app_private.talent_pool_scans(scan_id) ON DELETE SET NULL;

DROP INDEX IF EXISTS app_private.idx_candidate_emails_sent_recent;
CREATE INDEX IF NOT EXISTS idx_candidate_emails_sent_recent ON app_private.candidate_emails(sent_by, sending_started_at)
    WHERE status IN ('SENDING', 'RECORDED', 'SENT', 'FAILED');

ALTER TABLE app_private.mailbox_messages ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE app_private.mailbox_messages ADD COLUMN IF NOT EXISTS retry_started_at TIMESTAMPTZ;
