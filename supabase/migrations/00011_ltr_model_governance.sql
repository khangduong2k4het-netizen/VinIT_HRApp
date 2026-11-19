-- LTR model governance: bind approvals to an immutable artifact hash and
-- retain an append-only review history with actor and reason.
--
-- Registration alone never approves a model.  An explicit review transition
-- DRAFT -> APPROVED/REJECTED is required before production ACTIVE ranking
-- may use a registry artifact.

ALTER TABLE app_private.ltr_model_versions
    ADD COLUMN IF NOT EXISTS artifact_sha256 TEXT,
    ADD COLUMN IF NOT EXISTS registered_by UUID REFERENCES auth.users(id),
    ADD COLUMN IF NOT EXISTS reviewed_by UUID REFERENCES auth.users(id),
    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS review_reason TEXT;

CREATE TABLE IF NOT EXISTS app_private.ltr_model_review_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_version TEXT NOT NULL
        REFERENCES app_private.ltr_model_versions(model_version) ON DELETE CASCADE,
    artifact_sha256 TEXT NOT NULL,
    actor_user_id UUID REFERENCES auth.users(id),
    action TEXT NOT NULL CHECK (action IN ('REGISTERED', 'APPROVED', 'REJECTED')),
    from_status TEXT CHECK (from_status IN ('DRAFT', 'APPROVED', 'REJECTED')),
    to_status TEXT NOT NULL CHECK (to_status IN ('DRAFT', 'APPROVED', 'REJECTED')),
    reason TEXT,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    data_sha256 TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ltr_model_review_events_model_time
    ON app_private.ltr_model_review_events (model_version, created_at DESC);

COMMENT ON COLUMN app_private.ltr_model_versions.artifact_sha256 IS
    'SHA-256 of the canonical LTR artifact JSON. Approval is bound to this exact artifact content.';

COMMENT ON TABLE app_private.ltr_model_review_events IS
    'Append-only LTR registration/review history with actor, action, artifact hash, metrics snapshot and reason.';

ALTER TABLE app_private.ltr_model_review_events ENABLE ROW LEVEL SECURITY;
