-- Independent of the synthetic-only 00024-00026. No existing position becomes
-- visible until the backend's PUBLIC_CAREERS_ENABLED flag is explicitly set.
-- The nullable column may already exist in disposable demo databases.
ALTER TABLE app_private.positions
    ADD COLUMN IF NOT EXISTS application_deadline_at timestamptz;
CREATE INDEX IF NOT EXISTS positions_public_careers_idx
    ON app_private.positions (position_id)
    WHERE status = 'OPEN' AND application_deadline_at IS NOT NULL;
