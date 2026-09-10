-- Schema base: documentos, chunks, busca vetorial (pgvector) e full-text (tsvector nativo)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    document_id         TEXT PRIMARY KEY,          -- sha256(conteúdo bruto) || ':' || caminho_relativo
    source_path          TEXT NOT NULL,             -- caminho relativo original, preservado sempre
    content_hash          TEXT NOT NULL,             -- sha256 do conteúdo bruto, isolado para consulta rápida
    status                TEXT NOT NULL DEFAULT 'enfileirado'
                              CHECK (status IN ('enfileirado', 'processando', 'concluido', 'erro_processamento')),
    error_message         TEXT,
    structured_fields     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_structured_fields ON documents USING GIN (structured_fields);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents (status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_content_hash ON documents (content_hash);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id       BIGSERIAL PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES documents (document_id) ON DELETE CASCADE,
    chunk_index      INT NOT NULL,
    content          TEXT NOT NULL,
    embedding        VECTOR(1024),                  -- BGE-M3 = 1024 dimensões
    content_tsv      TSVECTOR GENERATED ALWAYS AS (to_tsvector('portuguese', content)) STORED,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_content_tsv ON chunks USING GIN (content_tsv);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks (document_id);
