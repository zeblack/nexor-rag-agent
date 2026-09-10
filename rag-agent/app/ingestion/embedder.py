from FlagEmbedding import BGEM3FlagModel

from app.config import settings

_model: BGEM3FlagModel | None = None


def _get_model() -> BGEM3FlagModel:
    global _model
    if _model is None:
        _model = BGEM3FlagModel(
            settings.embedding_model_name,
            use_fp16=settings.embedding_device != "cpu",
            device=settings.embedding_device,
        )
    return _model


def embed_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _get_model()
    output = model.encode(texts, batch_size=12, max_length=8192)
    return [vec.tolist() for vec in output["dense_vecs"]]
