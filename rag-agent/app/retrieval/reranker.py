from FlagEmbedding import FlagReranker

from app.config import settings
from app.retrieval import RetrievedChunk

_model: FlagReranker | None = None


def _get_model() -> FlagReranker:
    global _model
    if _model is None:
        _model = FlagReranker(
            settings.reranker_model_name,
            use_fp16=settings.embedding_device != "cpu",
        )
    return _model


def rerank(query: str, chunks: list[RetrievedChunk], top_k: int = 5) -> list[RetrievedChunk]:
    if not chunks:
        return []
    model = _get_model()
    pairs = [[query, chunk.content] for chunk in chunks]
    scores = model.compute_score(pairs, normalize=True)
    if isinstance(scores, float):
        scores = [scores]

    for chunk, score in zip(chunks, scores):
        chunk.score = score

    return sorted(chunks, key=lambda c: c.score, reverse=True)[:top_k]
