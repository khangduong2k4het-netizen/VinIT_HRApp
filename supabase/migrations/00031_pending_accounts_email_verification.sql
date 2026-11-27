-- Self-registered accounts wait for Admin approval in their own status, and must first
-- verify their email address (one-time link, same token table as password reset).
ALTER TABLE app_private.user_profiles DROP CONSTRAINT IF EXISTS user_profiles_account_status_check;
ALTER TABLE app_private.user_profiles
    ADD CONSTRAINT user_profiles_account_status_check
    CHECK (account_status IN ('ACTIVE', 'INACTIVE', 'SUSPENDED', 'PENDING'));

-- NULL for accounts an Admin created or that registered before this migration (nothing to verify).
-- A PENDING account with NULL here has not verified its email yet and cannot be approved.
ALTER TABLE app_private.user_profiles ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ;

ALTER TABLE app_private.password_reset_tokens
    ADD COLUMN IF NOT EXISTS purpose TEXT NOT NULL DEFAULT 'RESET'
    CHECK (purpose IN ('RESET', 'VERIFY_EMAIL'));
