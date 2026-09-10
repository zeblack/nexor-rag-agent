from sqlalchemy import text

from app.retrieval import RetrievedChunk


def search(session, query_embedding: list[float], top_k: int = 20) -> list[RetrievedChunk]:
    rows = session.execute(
        text(
            """
            SELECT c.chunk_id, c.document_id, d.source_path, c.chunk_index, c.content,
                   1 - (c.embedding <=> CAST(:embedding AS vector)) AS score
            FROM chunks c
            JOIN documents d ON d.document_id = c.document_id
            WHERE c.embedding IS NOT NULL
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
            """
        ),
        {"embedding": str(query_embedding), "top_k": top_k},
    ).fetchall()

    return [
        RetrievedChunk(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            source_path=row.source_path,
            chunk_index=row.chunk_index,
            content=row.content,
            score=row.score,
        )
        for row in rows
    ]
