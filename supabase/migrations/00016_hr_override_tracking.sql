-- F2.03 — HR override tracking for the operational analytics dashboard.
--
-- Decision (2026-11-12): an override is recorded at APPLICATION level when HR
--   * moves an application into SHORTLIST although the AI did not conclude
--     MEETS_MANDATORY (direction ADVANCED_DESPITE_AI), or
--   * rejects at screening (REJECTED_SCREENING) an application the AI marked
--     MEETS_MANDATORY (direction REJECTED_DESPITE_AI).
-- Applications without a valid AI conclusion are never counted as overrides.
-- Every status change snapshots the AI conclusion shown at decision time, so
-- overrides are never inferred later from current state.
-- Reason codes are mandatory for overrides; OTHER additionally requires a note.

ALTER TABLE app_private.application_status_events
    ADD COLUMN ai_assessment_id UUID REFERENCES app_private.assessment_runs(assessment_id) ON DELETE SET NULL,
    ADD COLUMN ai_matching_status TEXT CHECK (ai_matching_status IS NULL OR ai_matching_status IN (
        'NOT_ASSESSED', 'NEEDS_HR_VERIFICATION', 'POSSIBLE_MISMATCH', 'MEETS_MANDATORY')),
    ADD COLUMN ai_matching_score NUMERIC(5,1),
    ADD COLUMN ai_evidence_coverage NUMERIC(5,4),
    ADD COLUMN override_direction TEXT CHECK (override_direction IS NULL OR override_direction IN (
        'ADVANCED_DESPITE_AI', 'REJECTED_DESPITE_AI')),
    ADD COLUMN override_reason_code TEXT CHECK (override_reason_code IS NULL OR override_reason_code IN (
        'SYNONYM_TERMS', 'EQUIVALENT_CREDENTIAL', 'IMPLICIT_EVIDENCE', 'INTERVIEW_VERIFICATION',
        'EXTRACTION_ERROR', 'CRITERIA_MISFIT', 'OTHER')),
    ADD CONSTRAINT status_event_override_has_reason CHECK (
        override_direction IS NULL OR override_reason_code IS NOT NULL),
    ADD CONSTRAINT status_event_other_reason_has_note CHECK (
        override_reason_code IS DISTINCT FROM 'OTHER' OR (note IS NOT NULL AND length(btrim(note)) > 0));

CREATE INDEX IF NOT EXISTS idx_status_events_changed_at ON app_private.application_status_events (changed_at);
CREATE INDEX IF NOT EXISTS idx_status_events_application ON app_private.application_status_events (application_id, changed_at);
CREATE INDEX IF NOT EXISTS idx_status_events_override ON app_private.application_status_events (override_direction)
    WHERE override_direction IS NOT NULL;
