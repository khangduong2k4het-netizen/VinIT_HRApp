-- Password-reset requests from an address that matches no ACTIVE account are kept for the Admin (labelled
-- UNMATCHED) so a person who mistyped or forgot their email can still be recognised by name and unit. The public
-- answer stays identical for every email. Additive only.

ALTER TABLE app_private.password_reset_requests ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE app_private.password_reset_requests ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'MATCHED'
    CHECK (kind IN ('MATCHED', 'UNMATCHED'));
ALTER TABLE app_private.password_reset_requests ADD COLUMN IF NOT EXISTS full_name TEXT
    CHECK (full_name IS NULL OR char_length(full_name) <= 100);
ALTER TABLE app_private.password_reset_requests ADD COLUMN IF NOT EXISTS unit TEXT
    CHECK (unit IS NULL OR char_length(unit) <= 100);

ALTER TABLE app_private.password_reset_requests DROP CONSTRAINT IF EXISTS password_reset_requests_status_check;
ALTER TABLE app_private.password_reset_requests ADD CONSTRAINT password_reset_requests_status_check
    CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED', 'HANDLED', 'DISMISSED'));
ALTER TABLE app_private.password_reset_requests DROP CONSTRAINT IF EXISTS password_reset_requests_kind_user;
ALTER TABLE app_private.password_reset_requests ADD CONSTRAINT password_reset_requests_kind_user
    CHECK (kind = 'UNMATCHED' OR user_id IS NOT NULL);

CREATE INDEX IF NOT EXISTS idx_password_reset_requests_unmatched
    ON app_private.password_reset_requests (kind, status, requested_at DESC);
