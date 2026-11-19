-- Semantic retrieval (pgvector + BGE) and Learning-to-Rank foundations.
--
-- Embeddings are stored per CV document chunk with the chunk text hash and
-- the embedding model/index version, so a model change never silently mixes
-- vectors from different spaces.  Raw chunk text is NOT duplicated here;
-- the worker retains the extracted text offsets needed to recover quotes.
--
-- The vector dimension is fixed at 1024 to match the default BGE config
-- (bge-m3 / bge-large).  Switching to a model with another dimension
-- requires a deliberate follow-up migration, not a silent config change.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS app_private.cv_chunk_embeddings (
    embedding_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES app_private.application_documents(document_id) ON DELETE CASCADE,
    chunk_id TEXT NOT NULL,
    chunk_text_sha256 TEXT NOT NULL,
    section TEXT,
    page_number INTEGER,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    embedding vector(1024) NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_dimension INTEGER NOT NULL DEFAULT 1024,
    index_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (document_id, chunk_id, chunk_text_sha256, embedding_model, index_version)
);

CREATE INDEX IF NOT EXISTS idx_cv_chunk_embeddings_document
    ON app_private.cv_chunk_embeddings (document_id, embedding_model, index_version);

CREATE INDEX IF NOT EXISTS idx_cv_chunk_embeddings_vector_hnsw
    ON app_private.cv_chunk_embeddings
    USING hnsw (embedding vector_cosine_ops);

COMMENT ON TABLE app_private.cv_chunk_embeddings IS
    'BGE embeddings for CV chunks, keyed by document/chunk/text hash and embedding index version. No raw CV text is stored in this table.';

-- LTR registry: artifacts are trained offline; only APPROVED rows whose
-- metrics pass the configured gates may influence a ranking.
CREATE TABLE IF NOT EXISTS app_private.ltr_model_versions (
    model_version TEXT PRIMARY KEY,
    artifact JSONB NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    feature_names JSONB NOT NULL DEFAULT '[]'::jsonb,
    training_examples INTEGER NOT NULL DEFAULT 0,
    training_groups INTEGER NOT NULL DEFAULT 0,
    data_sha256 TEXT,
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'APPROVED', 'REJECTED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at TIMESTAMPTZ
);

COMMENT ON TABLE app_private.ltr_model_versions IS
    'Offline Learning-to-Rank model artifacts and holdout metrics. Approval is an explicit HR/ops decision; training alone never activates a model.';

ALTER TABLE app_private.ranking_runs
    ADD COLUMN IF NOT EXISTS ltr_model_version TEXT,
    ADD COLUMN IF NOT EXISTS ltr_mode TEXT;

ALTER TABLE app_private.ranking_items
    ADD COLUMN IF NOT EXISTS ltr_score NUMERIC(6,5);

COMMENT ON COLUMN app_private.ranking_items.ltr_score IS
    'LTR score recorded for shadow evaluation or gated active ranking; null when LTR is off.';

ALTER TABLE app_private.cv_chunk_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_private.ltr_model_versions ENABLE ROW LEVEL SECURITY;
