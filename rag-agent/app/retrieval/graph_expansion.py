from app.db import run_cypher
from app.retrieval import RetrievedChunk


def expand_via_graph(session, chunks: list[RetrievedChunk]) -> list[str]:
    """Para os top-K chunks pós-RRF, consulta o grafo AGE por entidades
    compartilhadas com OUTROS documentos. Retorna a lista de document_id
    externos que contribuíram, para transparência na resposta final."""
    related_documents: set[str] = set()

    for chunk in chunks:
        result = run_cypher(
            session,
            """
            MATCH (e:Entity {source_chunk_id: $chunk_id})-[]-(other:Entity)
            WHERE other.source_document_id <> $doc_id
            RETURN DISTINCT other.source_document_id
            """,
            {"chunk_id": str(chunk.chunk_id), "doc_id": chunk.document_id},
        )
        for row in result:
            doc_id = _parse_agtype_string(row[0])
            if doc_id:
                related_documents.add(doc_id)

    return sorted(related_documents)


def _parse_agtype_string(raw) -> str | None:
    """agtype vem como string serializada (ex: '"abc123"') — desembrulha."""
    if raw is None:
        return None
    value = str(raw).strip('"')
    return value or None
