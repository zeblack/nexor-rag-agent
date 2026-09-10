from sqlalchemy import text

from app.retrieval import RetrievedChunk


def search(session, query: str, top_k: int = 20) -> list[RetrievedChunk]:
    rows = session.execute(
        text(
            """
            SELECT c.chunk_id, c.document_id, d.source_path, c.chunk_index, c.content,
                   ts_rank(c.content_tsv, plainto_tsquery('portuguese', :query)) AS score
            FROM chunks c
            JOIN documents d ON d.document_id = c.document_id
            WHERE c.content_tsv @@ plainto_tsquery('portuguese', :query)
            ORDER BY score DESC
            LIMIT :top_k
            """
        ),
        {"query": query, "top_k": top_k},
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
