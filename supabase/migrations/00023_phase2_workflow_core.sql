-- Phase 2 workflow foundation. Apply only to an approved, verified environment.
SET LOCAL lock_timeout = '5s';

CREATE TABLE app_private.job_families (
    job_family_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    code text NOT NULL UNIQUE, name text NOT NULL, is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO app_private.job_families (code,name) VALUES
    ('IT_DIGITAL','IT & Digital'), ('ADMIN_OPERATIONS','Vận hành & Hành chính');
ALTER TABLE app_private.positions ADD COLUMN job_family_id uuid REFERENCES app_private.job_families(job_family_id);
-- Exact matches only; keep legacy text when no unambiguous approved family matches.
UPDATE app_private.positions p SET job_family_id=f.job_family_id
FROM app_private.job_families f WHERE p.job_family=f.code OR p.job_family=f.name;

CREATE TABLE app_private.rubric_templates (
    template_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_family_id uuid NOT NULL REFERENCES app_private.job_families(job_family_id),
    title text NOT NULL, level_band text, created_by uuid NOT NULL REFERENCES auth.users(id),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE app_private.rubric_template_versions (
    template_version_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_id uuid NOT NULL REFERENCES app_private.rubric_templates(template_id) ON DELETE CASCADE,
    version_number integer NOT NULL, status text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','PUBLISHED','ARCHIVED')),
    mandatory_weight_total numeric(5,2) NOT NULL DEFAULT 70 CHECK (mandatory_weight_total BETWEEN 0 AND 100),
    nice_to_have_weight_total numeric(5,2) NOT NULL DEFAULT 30 CHECK (nice_to_have_weight_total BETWEEN 0 AND 100),
    created_by uuid NOT NULL REFERENCES auth.users(id), published_by uuid REFERENCES auth.users(id),
    created_at timestamptz NOT NULL DEFAULT now(), published_at timestamptz,
    UNIQUE(template_id,version_number), CHECK (mandatory_weight_total + nice_to_have_weight_total = 100)
);
CREATE UNIQUE INDEX rubric_one_published ON app_private.rubric_template_versions(template_id) WHERE status='PUBLISHED';
CREATE TABLE app_private.rubric_template_items (
    template_item_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_version_id uuid NOT NULL REFERENCES app_private.rubric_template_versions(template_version_id) ON DELETE CASCADE,
    name text NOT NULL, description text NOT NULL,
    category text NOT NULL CHECK (category IN ('MUST_HAVE','NICE_TO_HAVE')),
    weight_in_group numeric(5,2) NOT NULL CHECK (weight_in_group BETWEEN 0 AND 100),
    expected_evidence_keywords jsonb NOT NULL DEFAULT '[]', requirement_spec jsonb,
    evidence_guidance text, display_order integer NOT NULL DEFAULT 0
);
ALTER TABLE app_private.criteria_versions DROP CONSTRAINT criteria_versions_origin_check;
ALTER TABLE app_private.criteria_versions ADD CONSTRAINT criteria_versions_origin_check CHECK (origin IN ('AI_DRAFT','HR_CREATED','TEMPLATE_CLONE'));
ALTER TABLE app_private.criteria_versions ADD COLUMN source_template_version_id uuid REFERENCES app_private.rubric_template_versions(template_version_id);
ALTER TABLE app_private.criteria_items ADD COLUMN source_template_item_id uuid REFERENCES app_private.rubric_template_items(template_item_id);

CREATE TABLE app_private.shortlist_scorecards (
    scorecard_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    share_item_id uuid NOT NULL UNIQUE REFERENCES app_private.shortlist_share_items(share_item_id) ON DELETE CASCADE,
    reviewer_user_id uuid NOT NULL REFERENCES auth.users(id),
    criteria_version_id uuid REFERENCES app_private.criteria_versions(criteria_version_id),
    status text NOT NULL DEFAULT 'NOT_STARTED' CHECK (status IN ('NOT_STARTED','IN_PROGRESS','SUBMITTED')),
    due_at timestamptz NOT NULL,
    overall_recommendation text CHECK (overall_recommendation IN ('STRONGLY_RECOMMEND','RECOMMEND','CONSIDER','NOT_RECOMMEND')), strengths text, concerns text,
    submitted_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE app_private.shortlist_scorecard_criteria (
    scorecard_id uuid NOT NULL REFERENCES app_private.shortlist_scorecards(scorecard_id) ON DELETE CASCADE,
    criterion_id uuid NOT NULL REFERENCES app_private.criteria_items(criterion_id),
    rating smallint CHECK (rating BETWEEN 1 AND 5), insufficient_evidence boolean NOT NULL DEFAULT false,
    comment text, PRIMARY KEY(scorecard_id,criterion_id),
    CHECK (NOT insufficient_evidence OR rating IS NULL)
);

-- Direct clients cannot bypass API checks. Backend connects as service_role.
DO $$ DECLARE t text; BEGIN
    FOREACH t IN ARRAY ARRAY['job_families','rubric_templates','rubric_template_versions','rubric_template_items','shortlist_scorecards','shortlist_scorecard_criteria'] LOOP
        EXECUTE format('ALTER TABLE app_private.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('REVOKE ALL ON TABLE app_private.%I FROM PUBLIC, anon, authenticated', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE app_private.%I TO service_role', t);
    END LOOP;
END $$;

ALTER TABLE app_private.rubric_template_versions ADD COLUMN revision integer NOT NULL DEFAULT 1;
CREATE UNIQUE INDEX rubric_one_draft ON app_private.rubric_template_versions(template_id) WHERE status='DRAFT';
CREATE FUNCTION app_private.guard_rubric_item_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_id uuid; version_status text;
BEGIN
    IF TG_OP = 'DELETE' THEN version_id := OLD.template_version_id; ELSE version_id := NEW.template_version_id; END IF;
    SELECT status INTO version_status FROM app_private.rubric_template_versions WHERE template_version_id=version_id FOR SHARE;
    IF version_status IS DISTINCT FROM 'DRAFT' THEN RAISE EXCEPTION 'Rubric template version is immutable'; END IF;
    IF TG_OP = 'UPDATE' AND OLD.template_version_id <> NEW.template_version_id THEN RAISE EXCEPTION 'Cannot move rubric items'; END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;
CREATE TRIGGER rubric_item_immutable BEFORE INSERT OR UPDATE OR DELETE ON app_private.rubric_template_items
FOR EACH ROW EXECUTE FUNCTION app_private.guard_rubric_item_immutable();
CREATE FUNCTION app_private.guard_rubric_version_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status <> 'DRAFT' AND (NEW.template_id,NEW.version_number,NEW.mandatory_weight_total,NEW.nice_to_have_weight_total,NEW.created_by,NEW.created_at,NEW.published_by,NEW.published_at,NEW.revision)
        IS DISTINCT FROM (OLD.template_id,OLD.version_number,OLD.mandatory_weight_total,OLD.nice_to_have_weight_total,OLD.created_by,OLD.created_at,OLD.published_by,OLD.published_at,OLD.revision) THEN
        RAISE EXCEPTION 'Published rubric version is immutable';
    END IF;
    IF OLD.status='ARCHIVED' AND NEW.status<>'ARCHIVED' OR OLD.status='PUBLISHED' AND NEW.status NOT IN ('PUBLISHED','ARCHIVED') THEN
        RAISE EXCEPTION 'Invalid rubric version transition';
    END IF;
    RETURN NEW;
END $$;
CREATE FUNCTION app_private.guard_rubric_version_delete() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status <> 'DRAFT' THEN RAISE EXCEPTION 'Published rubric version cannot be deleted'; END IF;
    RETURN OLD;
END $$;
CREATE TRIGGER rubric_version_no_delete BEFORE DELETE ON app_private.rubric_template_versions
FOR EACH ROW EXECUTE FUNCTION app_private.guard_rubric_version_delete();
CREATE TRIGGER rubric_version_immutable BEFORE UPDATE ON app_private.rubric_template_versions
FOR EACH ROW EXECUTE FUNCTION app_private.guard_rubric_version_immutable();
ALTER TABLE app_private.shortlist_scorecards ADD COLUMN revision integer NOT NULL DEFAULT 1;
CREATE TABLE app_private.scorecard_reopen_events (
    event_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    scorecard_id uuid NOT NULL REFERENCES app_private.shortlist_scorecards(scorecard_id) ON DELETE CASCADE,
    actor_user_id uuid NOT NULL REFERENCES auth.users(id), reason text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE app_private.scorecard_reopen_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_private.scorecard_reopen_events FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON app_private.scorecard_reopen_events TO service_role;
REVOKE ALL ON FUNCTION app_private.guard_rubric_item_immutable() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION app_private.guard_rubric_version_immutable() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION app_private.guard_rubric_version_delete() FROM PUBLIC, anon, authenticated;
-- Published version identity includes its template's family, title and level.
CREATE FUNCTION app_private.guard_published_rubric_template() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.job_family_id, NEW.title, NEW.level_band, NEW.created_by, NEW.created_at)
        IS DISTINCT FROM (OLD.job_family_id, OLD.title, OLD.level_band, OLD.created_by, OLD.created_at)
        AND EXISTS (SELECT 1 FROM app_private.rubric_template_versions v
                    WHERE v.template_id=OLD.template_id AND v.status IN ('PUBLISHED','ARCHIVED')) THEN
        RAISE EXCEPTION 'Published rubric identity is immutable';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER rubric_template_immutable BEFORE UPDATE ON app_private.rubric_templates
FOR EACH ROW EXECUTE FUNCTION app_private.guard_published_rubric_template();
REVOKE ALL ON FUNCTION app_private.guard_published_rubric_template() FROM PUBLIC, anon, authenticated;
