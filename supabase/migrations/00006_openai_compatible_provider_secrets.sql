-- Admin-managed OpenAI-compatible providers.
--
-- provider_name is the Admin-entered display name (for example OpenAI,
-- OpenRouter or DeepSeek) while provider remains the transport label
-- 'compatible'. api_key_ciphertext is application-level Fernet ciphertext;
-- plaintext API keys are never stored. The public view deliberately exposes
-- only whether a key exists and a four-character display hint, never the
-- ciphertext itself.

ALTER TABLE app_private.ai_configuration_versions
    ADD COLUMN IF NOT EXISTS provider_name TEXT,
    ADD COLUMN IF NOT EXISTS api_key_ciphertext TEXT,
    ADD COLUMN IF NOT EXISTS api_key_hint TEXT;

ALTER TABLE app_private.ai_configuration_versions
    DROP CONSTRAINT IF EXISTS ai_configuration_versions_provider_name_check,
    DROP CONSTRAINT IF EXISTS ai_configuration_versions_api_key_ciphertext_check,
    DROP CONSTRAINT IF EXISTS ai_configuration_versions_api_key_hint_check;

ALTER TABLE app_private.ai_configuration_versions
    ADD CONSTRAINT ai_configuration_versions_provider_name_check
        CHECK (provider_name IS NULL OR char_length(btrim(provider_name)) BETWEEN 1 AND 120),
    ADD CONSTRAINT ai_configuration_versions_api_key_ciphertext_check
        CHECK (api_key_ciphertext IS NULL OR char_length(api_key_ciphertext) BETWEEN 1 AND 4096),
    ADD CONSTRAINT ai_configuration_versions_api_key_hint_check
        CHECK (api_key_hint IS NULL OR char_length(api_key_hint) BETWEEN 1 AND 16);

COMMENT ON COLUMN app_private.ai_configuration_versions.provider_name IS
    'Admin-entered display name for a provider configuration; internal provider remains the transport label.';
COMMENT ON COLUMN app_private.ai_configuration_versions.api_key_ciphertext IS
    'Fernet ciphertext of an Admin-entered OpenAI-compatible provider API key. Never expose through APIs, views, logs, audit metadata or operation snapshots.';
COMMENT ON COLUMN app_private.ai_configuration_versions.api_key_hint IS
    'Non-secret display hint containing only the final four characters of a stored provider API key.';

-- Recreate the view with an explicit column list so api_key_ciphertext cannot
-- leak through SELECT *. DROP/CREATE is used because CREATE OR REPLACE cannot
-- insert new columns ahead of the existing view columns on every deployment.
-- The view remains unavailable to anon/authenticated.
DROP VIEW IF EXISTS public.ai_configuration_versions;
CREATE VIEW public.ai_configuration_versions
WITH (security_invoker = true) AS
SELECT
    config_id,
    provider,
    provider_name,
    model_name,
    model_version,
    deployment_mode,
    ai_policy_version,
    status,
    enabled_at,
    disabled_at,
    created_at,
    api_base,
    temperature_default,
    created_by,
    (api_key_ciphertext IS NOT NULL) AS api_key_configured,
    api_key_hint
FROM app_private.ai_configuration_versions;

REVOKE ALL ON public.ai_configuration_versions FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.ai_configuration_versions TO service_role;
