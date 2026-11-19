-- Phase 2 batch 1 — Workflow core (doc/PHASE2_IMPLEMENTATION_PLAN.md)
--   F2.01 Rubric Library by job family
--   F2.02 Structured HR–HM scorecards on shortlist shares
-- Decisions applied: plan defaults D-01…D-10; overall recommendation uses a
-- four-level scale. Only the job-family taxonomy is seeded; no rubric content.

-- ========================================
-- F2.01 — RUBRIC LIBRARY
-- ========================================

CREATE TABLE app_private.job_families (
    job_family_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code TEXT NOT NULL UNIQUE CHECK (code ~ '^[A-Z][A-Z0-9_]{1,49}$'),
    name TEXT NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 200),
    description TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
    display_order INTEGER NOT NULL DEFAULT 0,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- D-01: the five job families named in the roadmap. Taxonomy only.
INSERT INTO app_private.job_families (code, name, display_order) VALUES
    ('ACADEMIC_FACULTY', 'Academic/Faculty', 1),
    ('RESEARCH', 'Research', 2),
    ('IT_DIGITAL', 'IT & Digital', 3),
    ('ADMIN_OPERATIONS', 'Admin & Operations', 4),
    ('STUDENT_SERVICES', 'Student Services', 5);

CREATE TABLE app_private.rubric_templates (
    template_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_family_id UUID NOT NULL REFERENCES app_private.job_families(job_family_id),
    title TEXT NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 200),
    level_band TEXT CHECK (level_band IS NULL OR length(btrim(level_band)) BETWEEN 1 AND 100),
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'ARCHIVED')),
    created_by UUID NOT NULL REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE app_private.rubric_template_versions (
    template_version_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_id UUID NOT NULL REFERENCES app_private.rubric_templates(template_id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL CHECK (version_number >= 1),
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')),
    mandatory_weight_total NUMERIC(5,2) NOT NULL DEFAULT 70.0,
    nice_to_have_weight_total NUMERIC(5,2) NOT NULL DEFAULT 30.0,
    change_note TEXT,
    created_by UUID NOT NULL REFERENCES auth.users(id),
    published_by UUID REFERENCES auth.users(id),
    published_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    UNIQUE (template_id, version_number),
    CONSTRAINT rubric_template_weights_total_100 CHECK (
        mandatory_weight_total > 0 AND nice_to_have_weight_total >= 0
        AND mandatory_weight_total + nice_to_have_weight_total = 100)
);
-- D-03: at most one current published version and one open draft per template.
CREATE UNIQUE INDEX rubric_template_one_published
    ON app_private.rubric_template_versions (template_id) WHERE status = 'PUBLISHED';
CREATE UNIQUE INDEX rubric_template_one_draft
    ON app_private.rubric_template_versions (template_id) WHERE status = 'DRAFT';

CREATE TABLE app_private.rubric_template_items (
    template_item_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_version_id UUID NOT NULL REFERENCES app_private.rubric_template_versions(template_version_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('MUST_HAVE', 'NICE_TO_HAVE')),
    weight_in_group NUMERIC(5,2) NOT NULL CHECK (weight_in_group >= 0 AND weight_in_group <= 100),
    expected_evidence_keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_guidance TEXT,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX idx_rubric_template_items_version ON app_private.rubric_template_items (template_version_id, display_order);

CREATE TABLE app_private.rubric_template_review_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_version_id UUID NOT NULL REFERENCES app_private.rubric_template_versions(template_version_id) ON DELETE CASCADE,
    reviewed_by UUID NOT NULL REFERENCES auth.users(id),
    decision TEXT NOT NULL CHECK (decision IN ('PUBLISH', 'ARCHIVE', 'REQUEST_CHANGES')),
    comment TEXT,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Positions link to a family; the legacy text column stays for compatibility.
ALTER TABLE app_private.positions
    ADD COLUMN job_family_id UUID REFERENCES app_private.job_families(job_family_id);
-- Exact-match backfill only (no fuzzy matching).
UPDATE app_private.positions p SET job_family_id = f.job_family_id
FROM app_private.job_families f
WHERE p.job_family_id IS NULL AND p.job_family IS NOT NULL
  AND (btrim(p.job_family) = f.name OR upper(btrim(p.job_family)) = f.code);

-- D-04: a template only ever produces a criteria DRAFT; provenance is kept.
ALTER TABLE app_private.criteria_versions DROP CONSTRAINT criteria_versions_origin_check;
ALTER TABLE app_private.criteria_versions ADD CONSTRAINT criteria_versions_origin_check
    CHECK (origin IN ('AI_DRAFT', 'HR_CREATED', 'TEMPLATE_CLONE'));
ALTER TABLE app_private.criteria_versions
    ADD COLUMN source_template_version_id UUID REFERENCES app_private.rubric_template_versions(template_version_id);
ALTER TABLE app_private.criteria_items
    ADD COLUMN source_template_item_id UUID REFERENCES app_private.rubric_template_items(template_item_id) ON DELETE SET NULL;

-- ========================================
-- F2.02 — STRUCTURED SCORECARDS
-- ========================================

CREATE TABLE app_private.shortlist_scorecards (
    scorecard_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    share_id UUID NOT NULL REFERENCES app_private.shortlist_shares(share_id) ON DELETE CASCADE,
    share_item_id UUID NOT NULL UNIQUE REFERENCES app_private.shortlist_share_items(share_item_id) ON DELETE CASCADE,
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id),
    application_id UUID NOT NULL REFERENCES app_private.applications(application_id),
    -- Locked to the assessment snapshot taken when the share was created.
    assessment_id UUID REFERENCES app_private.assessment_runs(assessment_id),
    criteria_version_id UUID REFERENCES app_private.criteria_versions(criteria_version_id),
    reviewer_user_id UUID NOT NULL REFERENCES auth.users(id),
    status TEXT NOT NULL DEFAULT 'NOT_STARTED' CHECK (status IN ('NOT_STARTED', 'IN_PROGRESS', 'SUBMITTED')),
    -- D-06: four-level overall recommendation.
    overall_recommendation TEXT CHECK (overall_recommendation IN ('STRONG_YES', 'YES', 'NO', 'STRONG_NO')),
    strengths TEXT CHECK (strengths IS NULL OR length(strengths) <= 4000),
    concerns TEXT CHECK (concerns IS NULL OR length(concerns) <= 4000),
    due_at TIMESTAMPTZ NOT NULL,
    submitted_at TIMESTAMPTZ,
    reopened_by UUID REFERENCES auth.users(id),
    reopened_at TIMESTAMPTZ,
    reopen_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT scorecard_submitted_complete CHECK (
        status <> 'SUBMITTED' OR (submitted_at IS NOT NULL AND overall_recommendation IS NOT NULL))
);
CREATE INDEX idx_scorecards_reviewer ON app_private.shortlist_scorecards (reviewer_user_id, status, due_at);
CREATE INDEX idx_scorecards_share ON app_private.shortlist_scorecards (share_id);

CREATE TABLE app_private.shortlist_scorecard_criteria (
    scorecard_criterion_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scorecard_id UUID NOT NULL REFERENCES app_private.shortlist_scorecards(scorecard_id) ON DELETE CASCADE,
    criterion_id UUID NOT NULL REFERENCES app_private.criteria_items(criterion_id),
    rating SMALLINT CHECK (rating BETWEEN 1 AND 5),
    evidence_assessment TEXT CHECK (evidence_assessment IN ('INSUFFICIENT_EVIDENCE')),
    comment TEXT CHECK (comment IS NULL OR length(comment) <= 2000),
    updated_at TIMESTAMPTZ,
    UNIQUE (scorecard_id, criterion_id),
    -- A criterion is either rated 1–5 or marked as lacking evidence, never both.
    CONSTRAINT scorecard_criterion_single_answer CHECK (rating IS NULL OR evidence_assessment IS NULL)
);

-- ========================================
-- ACCESS: backend-only via service_role (same model as Phase 1)
-- ========================================
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['job_families', 'rubric_templates', 'rubric_template_versions', 'rubric_template_items',
                             'rubric_template_review_events', 'shortlist_scorecards', 'shortlist_scorecard_criteria'] LOOP
        EXECUTE format('ALTER TABLE app_private.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('REVOKE ALL ON app_private.%I FROM PUBLIC, anon, authenticated', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.%I TO service_role', t);
    END LOOP;
END $$;
