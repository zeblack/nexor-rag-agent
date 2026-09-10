from typing import Literal

from pydantic import BaseModel


class IngestResponse(BaseModel):
    document_id: str
    status: Literal["enfileirado"]


class IngestStatusResponse(BaseModel):
    document_id: str
    status: Literal["enfileirado", "processando", "concluido", "erro_processamento"]
    detalhe: str | None = None


class ModelInfo(BaseModel):
    id: str
    label: str


class ModelsResponse(BaseModel):
    models: list[ModelInfo]
    default_model: str


class QueryRequest(BaseModel):
    question: str
    model: str
    top_k: int = 8


class Citation(BaseModel):
    document_id: str
    source_path: str
    chunk_index: int
    snippet: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    graph_documents: list[str] = []


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    postgres: Literal["ok", "error"]
    vpn_status: Literal["ok", "degraded", "unknown"]
