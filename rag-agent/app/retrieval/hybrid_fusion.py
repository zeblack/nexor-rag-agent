from app.retrieval import RetrievedChunk

_RRF_K = 60  # constante padrão do Reciprocal Rank Fusion


def reciprocal_rank_fusion(
    vector_results: list[RetrievedChunk],
    fulltext_results: list[RetrievedChunk],
    top_k: int = 10,
) -> list[RetrievedChunk]:
    scores: dict[int, float] = {}
    chunks_by_id: dict[int, RetrievedChunk] = {}

    for rank, chunk in enumerate(vector_results, start=1):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (_RRF_K + rank)
        chunks_by_id[chunk.chunk_id] = chunk

    for rank, chunk in enumerate(fulltext_results, start=1):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (_RRF_K + rank)
        chunks_by_id.setdefault(chunk.chunk_id, chunk)

    ranked_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)[:top_k]

    fused = []
    for chunk_id in ranked_ids:
        chunk = chunks_by_id[chunk_id]
        chunk.score = scores[chunk_id]
        fused.append(chunk)
    return fused
