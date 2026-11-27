-- =============================================================================
-- Migration 00039: Closed-Loop Evidence Sign-Off (HR verification on criteria)
-- =============================================================================
-- Append-only HR verdicts on AI criterion assessment results. Latest verdict
-- per result_id feeds directly into P3-2 AI Quality Dashboard calibration
-- aggregates (never broken down by individual recruiter).

CREATE TABLE IF NOT EXISTS app_private.evidence_signoffs (
    signoff_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    result_id UUID NOT NULL REFERENCES app_private.criterion_assessment_results(result_id) ON DELETE CASCADE,
    application_id UUID NOT NULL REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id) ON DELETE CASCADE,
    criterion_id UUID NOT NULL REFERENCES app_private.criteria_items(criterion_id) ON DELETE CASCADE,
    verdict TEXT NOT NULL CHECK (verdict IN ('CONFIRMED', 'DISPUTED')),
    reason_code TEXT CHECK (
        reason_code IS NULL OR reason_code IN (
            'WRONG_QUOTE',
            'WRONG_LEVEL',
            'MISSING_CONTEXT',
            'OCR_NOISE',
            'RUBRIC_AMBIGUOUS',
            'OTHER'
        )
    ),
    note TEXT CHECK (note IS NULL OR length(note) <= 500),
    reviewed_by UUID NOT NULL REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT evidence_signoffs_disputed_requires_reason
        CHECK (verdict = 'CONFIRMED' OR reason_code IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_evidence_signoffs_result_latest
    ON app_private.evidence_signoffs (result_id, created_at DESC, signoff_id DESC);

CREATE INDEX IF NOT EXISTS idx_evidence_signoffs_app_latest
    ON app_private.evidence_signoffs (application_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_evidence_signoffs_pos_created
    ON app_private.evidence_signoffs (position_id, created_at DESC);

ALTER TABLE app_private.evidence_signoffs ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON app_private.evidence_signoffs FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.evidence_signoffs TO service_role;
