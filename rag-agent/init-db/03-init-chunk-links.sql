-- Links de similaridade cruzada entre chunks de documentos diferentes
CREATE TABLE IF NOT EXISTS chunk_links (
    chunk_id_a        BIGINT NOT NULL REFERENCES chunks (chunk_id) ON DELETE CASCADE,
    chunk_id_b        BIGINT NOT NULL REFERENCES chunks (chunk_id) ON DELETE CASCADE,
    similarity_score   REAL NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (chunk_id_a, chunk_id_b),
    CHECK (chunk_id_a < chunk_id_b)  -- evita par duplicado em ordem invertida
);

CREATE INDEX IF NOT EXISTS idx_chunk_links_a ON chunk_links (chunk_id_a);
CREATE INDEX IF NOT EXISTS idx_chunk_links_b ON chunk_links (chunk_id_b);
