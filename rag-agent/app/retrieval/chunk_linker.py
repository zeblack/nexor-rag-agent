from sqlalchemy import text

_SIMILARITY_THRESHOLD = 0.82


def link_new_chunk(session, chunk_id: int, document_id: str, embedding: list[float]):
    """Compara o embedding do chunk recém-inserido contra chunks de OUTROS
    documentos e grava pares acima do threshold em chunk_links."""
    candidates = session.execute(
        text(
            """
            SELECT chunk_id, 1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM chunks
            WHERE document_id != :doc_id AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT 20
            """
        ),
        {"embedding": str(embedding), "doc_id": document_id},
    ).fetchall()

    for candidate_id, similarity in candidates:
        if similarity < _SIMILARITY_THRESHOLD:
            continue
        chunk_a, chunk_b = sorted((chunk_id, candidate_id))
        session.execute(
            text(
                """
                INSERT INTO chunk_links (chunk_id_a, chunk_id_b, similarity_score)
                VALUES (:a, :b, :score)
                ON CONFLICT (chunk_id_a, chunk_id_b) DO NOTHING
                """
            ),
            {"a": chunk_a, "b": chunk_b, "score": similarity},
        )
