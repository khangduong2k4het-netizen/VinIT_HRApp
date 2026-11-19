-- Org-wide HR settings that used to be hard-coded in the backend.
--
-- Only the thresholds that change a *business* decision live here. Anything that
-- is a technical constant (coverage 0.7, page sizes) stays in code: a settings row
-- that nothing may sensibly change is just another way to break the app.
--
-- The value is stored as an integer range rather than typed columns on purpose:
-- adding the next threshold should not need a migration that rewrites a schema.
CREATE TABLE app_private.app_settings (
    setting_key TEXT PRIMARY KEY CHECK (setting_key ~ '^[a-z][a-z0-9_]{2,63}$'),
    value_int INTEGER,
    -- Bounds are enforced by the API, not the table: the API knows what each
    -- setting means and can return a message HR understands.
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by UUID REFERENCES auth.users(id)
);

-- Defaults match the values the code shipped with, so deploying this migration
-- changes nothing until someone edits a setting.
INSERT INTO app_private.app_settings (setting_key, value_int) VALUES
    ('deadline_soon_days', 7),
    ('waiting_attention_days', 7);

ALTER TABLE app_private.app_settings ENABLE ROW LEVEL SECURITY;
-- Same posture as the other managed controls: reads and writes go through the
-- backend with the service role; no browser role can see or change these.
REVOKE ALL ON app_private.app_settings FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON app_private.app_settings TO service_role;
GRANT UPDATE (value_int, updated_at, updated_by) ON app_private.app_settings TO service_role;
