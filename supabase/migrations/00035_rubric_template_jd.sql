-- F2.01: a template version may carry a sample JD ("JD mẫu"). Saving approved criteria as a
-- template copies the position's JD into it, HR can edit it while the version is a draft,
-- and the create-position form pre-fills the JD field from the chosen template.
-- Like the items, it is frozen once the version is published. NULL = no sample JD.
ALTER TABLE app_private.rubric_template_versions
    ADD COLUMN IF NOT EXISTS jd_template TEXT
    CHECK (jd_template IS NULL OR length(jd_template) <= 50000);

COMMENT ON COLUMN app_private.rubric_template_versions.jd_template IS
    'Sample job description used to pre-fill new positions created from this template; NULL when none.';
