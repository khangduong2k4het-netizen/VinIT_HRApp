-- Structured requirement specs for deterministic matching (audit M1):
-- each criterion may carry an HR-reviewable atomic requirement (kind,
-- threshold and accepted evidence terms).  A NULL spec means the engine's
-- inferred draft has not been materialized/reviewed yet; approved rubrics
-- store the spec that was in force when HR approved them.

ALTER TABLE app_private.criteria_items
    ADD COLUMN IF NOT EXISTS requirement_spec JSONB;

COMMENT ON COLUMN app_private.criteria_items.requirement_spec IS
    'Structured requirement spec reviewed with the rubric: kind, terms, thresholds and language/degree requirements used by deterministic matching.';
