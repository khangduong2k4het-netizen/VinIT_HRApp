-- F2.04/F2.05: backend-only records. No browser access through PostgREST.
ALTER TABLE app_private.assessment_runs ADD COLUMN source_extracted_text_path TEXT;
ALTER TABLE app_private.document_processing_runs ADD COLUMN ocr_mean_confidence NUMERIC(5,2)
    CHECK (ocr_mean_confidence BETWEEN 0 AND 100);
CREATE TABLE app_private.quality_inspections (
    inspection_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID NOT NULL UNIQUE REFERENCES app_private.assessment_runs(assessment_id) ON DELETE CASCADE,
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id) ON DELETE CASCADE,
    reasons JSONB NOT NULL,
    policy_version TEXT NOT NULL DEFAULT 'qa-v1',
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','IN_REVIEW','COMPLETED')),
    assigned_to UUID REFERENCES auth.users(id),
    revision INTEGER NOT NULL DEFAULT 0,
    verdict TEXT CHECK (verdict IN ('CORRECT','ISSUES_FOUND')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX quality_inspection_queue ON app_private.quality_inspections(position_id, status, created_at);
CREATE TABLE app_private.quality_inspection_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    inspection_id UUID NOT NULL REFERENCES app_private.quality_inspections(inspection_id) ON DELETE CASCADE,
    actor_id UUID NOT NULL REFERENCES auth.users(id),
    action TEXT NOT NULL CHECK (action IN ('CLAIM','SUBMIT')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE app_private.quality_flags (
    flag_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    inspection_id UUID NOT NULL REFERENCES app_private.quality_inspections(inspection_id) ON DELETE CASCADE,
    category TEXT NOT NULL CHECK (category IN ('INCORRECT_EVIDENCE','MISSING_CONTENT','INCORRECT_FACT','OCR_ERROR','INCORRECT_MATCH')),
    criterion_result_id UUID REFERENCES app_private.criterion_assessment_results(result_id) ON DELETE CASCADE,
    note TEXT NOT NULL CHECK (length(btrim(note)) BETWEEN 1 AND 2000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE app_private.cross_position_duplicates (
    signal_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id_1 UUID NOT NULL REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    application_id_2 UUID NOT NULL REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    fingerprint_1 TEXT NOT NULL,
    fingerprint_2 TEXT NOT NULL,
    signal_type TEXT NOT NULL CHECK (signal_type IN ('EMAIL_MATCH','PHONE_MATCH','NAME_CONTENT_MATCH')),
    confidence NUMERIC(3,2) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    detector_version TEXT NOT NULL DEFAULT 'cross-v1',
    review_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (review_status IN ('PENDING','CONFIRMED','DISMISSED','SUPERSEDED')),
    reviewed_by UUID REFERENCES auth.users(id),
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (application_id_1 < application_id_2),
    UNIQUE(application_id_1, application_id_2, fingerprint_1, fingerprint_2)
);
CREATE INDEX cross_duplicate_first ON app_private.cross_position_duplicates(application_id_1, review_status);
CREATE INDEX cross_duplicate_second ON app_private.cross_position_duplicates(application_id_2, review_status);
CREATE INDEX identity_normalized_email ON app_private.application_identities(lower(btrim(email))) WHERE email IS NOT NULL;
DO $$ DECLARE t TEXT; BEGIN
    FOREACH t IN ARRAY ARRAY['quality_inspections','quality_inspection_events','quality_flags','cross_position_duplicates'] LOOP
        EXECUTE format('ALTER TABLE app_private.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('REVOKE ALL ON app_private.%I FROM PUBLIC, anon, authenticated', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.%I TO service_role', t);
    END LOOP;
END $$;
