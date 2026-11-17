-- Candidate self-service withdrawal: the portal shows a one-time bearer token after the
-- Talent Pool box was ticked; only its SHA-256 is stored.
ALTER TABLE app_private.application_data_consents
    ADD COLUMN IF NOT EXISTS withdrawal_token_hash TEXT
    CHECK (withdrawal_token_hash IS NULL OR withdrawal_token_hash ~ '^[0-9a-f]{64}$');
CREATE UNIQUE INDEX IF NOT EXISTS uq_consent_withdrawal_token
    ON app_private.application_data_consents(withdrawal_token_hash) WHERE withdrawal_token_hash IS NOT NULL;
