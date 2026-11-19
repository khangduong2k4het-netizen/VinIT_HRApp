-- Deterministic assessment foundation (Phase 0/1):
-- * assessment fingerprints make identical CV + rubric + profile + runtime
--   + prompt/policy inputs reusable instead of calling the LLM again;
-- * criterion results record whether a deterministic rule or the LLM made
--   the decision, plus the evidence strength used by the scoring engine.

INSERT INTO app_private.assessment_policy_versions (
    policy_version, score_mapping, min_evidence_coverage,
    confidence_thresholds, ranking_rules, status
) VALUES (
    'assessment-v2.0',
    '{"STRONG_MATCH": 100, "MATCH": 80, "NO_MATCH": 0, "UNCLEAR": null}'::jsonb,
    0.70,
    '{"min_evidence_strength": 0.35}'::jsonb,
    'must-have gate, matching score, evidence coverage, application_id',
    'APPROVED'
)
ON CONFLICT (policy_version) DO NOTHING;

ALTER TABLE app_private.assessment_runs
    ADD COLUMN IF NOT EXISTS assessment_fingerprint TEXT,
    ADD COLUMN IF NOT EXISTS matching_policy_version TEXT,
    ADD COLUMN IF NOT EXISTS prompt_version TEXT,
    ADD COLUMN IF NOT EXISTS provider_model_snapshot JSONB;

CREATE UNIQUE INDEX IF NOT EXISTS idx_assessment_runs_fingerprint_completed
    ON app_private.assessment_runs (assessment_fingerprint)
    WHERE status = 'COMPLETED' AND assessment_fingerprint IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_assessment_runs_fingerprint
    ON app_private.assessment_runs (assessment_fingerprint)
    WHERE assessment_fingerprint IS NOT NULL;

ALTER TABLE app_private.criterion_assessment_results
    ADD COLUMN IF NOT EXISTS decision_source TEXT NOT NULL DEFAULT 'LLM',
    ADD COLUMN IF NOT EXISTS evidence_strength NUMERIC(4,3),
    ADD COLUMN IF NOT EXISTS evidence_chunk_id TEXT,
    ADD COLUMN IF NOT EXISTS rule_version TEXT;

ALTER TABLE app_private.criterion_assessment_results
    DROP CONSTRAINT IF EXISTS criterion_assessment_results_decision_source_check;
ALTER TABLE app_private.criterion_assessment_results
    ADD CONSTRAINT criterion_assessment_results_decision_source_check
    CHECK (decision_source IN ('RULE', 'LLM', 'HYBRID'));

COMMENT ON COLUMN app_private.assessment_runs.assessment_fingerprint IS
    'SHA-256 over normalized CV text hash, profile facts, rubric, JD, pinned AI runtime, prompt and matching policy versions.';
COMMENT ON COLUMN app_private.criterion_assessment_results.decision_source IS
    'RULE for deterministic rule-engine decisions, LLM for model adjudication, HYBRID for merged decisions.';
COMMENT ON COLUMN app_private.criterion_assessment_results.evidence_strength IS
    'Deterministic evidence strength 0..1 used instead of a hard LLM confidence cliff.';
