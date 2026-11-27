-- F2.01 extension: HR saves a position's APPROVED criteria as a rubric template draft,
-- so the library grows from criteria people already reviewed.
--
-- requirement_spec keeps the structured rule (kind, terms, min years, degree level,
-- language...) that HR may have edited on the position; a template applied later gets
-- it back instead of re-inferring it from the text. NULL = infer when applied (as before).
ALTER TABLE app_private.rubric_template_items
    ADD COLUMN IF NOT EXISTS requirement_spec JSONB;

-- Where a template version came from (NULL for versions written in the library itself).
ALTER TABLE app_private.rubric_template_versions
    ADD COLUMN IF NOT EXISTS source_criteria_version_id UUID
    REFERENCES app_private.criteria_versions(criteria_version_id) ON DELETE SET NULL;

COMMENT ON COLUMN app_private.rubric_template_items.requirement_spec IS
    'Structured requirement copied from approved position criteria; NULL means infer from name/description/keywords when applied.';
COMMENT ON COLUMN app_private.rubric_template_versions.source_criteria_version_id IS
    'Approved criteria version this template version was saved from, if any.';
