-- P3-2: Admin-written change markers shown on the AI quality trend charts.
-- Backend-only table (no browser access through PostgREST). Markers record
-- changes that the data cannot reveal by itself, such as a dictionary or
-- rubric update. They never alter assessments or decisions.
CREATE TABLE IF NOT EXISTS app_private.quality_markers (
    marker_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    occurred_on DATE NOT NULL,
    title TEXT NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 200),
    note TEXT CHECK (note IS NULL OR length(note) <= 1000),
    created_by UUID NOT NULL REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_quality_markers_date ON app_private.quality_markers(occurred_on);

ALTER TABLE app_private.quality_markers ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_private.quality_markers FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.quality_markers TO service_role;
