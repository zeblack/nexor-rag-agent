import asyncio
import hashlib
import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text

from app.config import settings
from app.db import get_session
from app.ingestion.embedder import embed_batch
from app.models_registry import registry
from app.openrouter_client import client as openrouter_client
from app.retrieval import graph_expansion, hybrid_fusion, reranker
from app.retrieval import fulltext_search, vector_search
from app.schemas import (
    Citation,
    HealthResponse,
    IngestResponse,
    IngestStatusResponse,
    ModelInfo,
    ModelsResponse,
    QueryRequest,
    QueryResponse,
)
from app.vpn_healthcheck import get_status as get_vpn_status, run_healthcheck_loop
from app.worker import ingest_document_task

logger = logging.getLogger(__name__)
security = HTTPBearer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_healthcheck_loop())
    yield
    task.cancel()


app = FastAPI(title="RAG Agent", lifespan=lifespan)


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != settings.api_auth_token:
        raise HTTPException(status_code=401, detail="Token inválido")


@app.post("/ingest", response_model=IngestResponse, dependencies=[Depends(require_auth)])
async def ingest(file: UploadFile, source_path: str):
    content = await file.read()
    content_hash = hashlib.sha256(content).hexdigest()
    document_id = f"{content_hash}:{source_path}"

    # /tmp/rag_ingest é um volume compartilhado entre rag_agent e rag_worker —
    # containers separados não compartilham o /tmp padrão do sistema.
    shared_tmp_dir = "/tmp/rag_ingest"
    os.makedirs(shared_tmp_dir, exist_ok=True)
    temp_path = os.path.join(shared_tmp_dir, f"ingest_{content_hash}{os.path.splitext(file.filename or '')[1]}")
    with open(temp_path, "wb") as f:
        f.write(content)

    with get_session() as session:
        session.execute(
            text(
                """
                INSERT INTO documents (document_id, source_path, content_hash, status)
                VALUES (:doc_id, :source_path, :content_hash, 'enfileirado')
                ON CONFLICT (document_id) DO NOTHING
                """
            ),
            {"doc_id": document_id, "source_path": source_path, "content_hash": content_hash},
        )

    ingest_document_task.delay(document_id, temp_path, source_path)
    return IngestResponse(document_id=document_id, status="enfileirado")


@app.get("/ingest/status/{document_id:path}", response_model=IngestStatusResponse, dependencies=[Depends(require_auth)])
def ingest_status(document_id: str):
    with get_session() as session:
        row = session.execute(
            text("SELECT status, error_message FROM documents WHERE document_id = :doc_id"),
            {"doc_id": document_id},
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="document_id não encontrado")

    return IngestStatusResponse(document_id=document_id, status=row.status, detalhe=row.error_message)


@app.get("/models", response_model=ModelsResponse)
def list_models():
    return ModelsResponse(
        models=[ModelInfo(**m) for m in registry.list_models()],
        default_model=registry.default_model,
    )


@app.post("/query", response_model=QueryResponse, dependencies=[Depends(require_auth)])
def query(request: QueryRequest):
    if not registry.is_allowed(request.model):
        raise HTTPException(status_code=400, detail=f"Modelo '{request.model}' não permitido")

    with get_session() as session:
        query_embedding = embed_batch([request.question])[0]
        vec_results = vector_search.search(session, query_embedding, top_k=20)
        text_results = fulltext_search.search(session, request.question, top_k=20)

        fused = hybrid_fusion.reciprocal_rank_fusion(vec_results, text_results, top_k=request.top_k)
        graph_documents = graph_expansion.expand_via_graph(session, fused)
        top_chunks = reranker.rerank(request.question, fused, top_k=5)

    context = "\n\n---\n\n".join(c.content for c in top_chunks)
    prompt = (
        f"Responda a pergunta com base no contexto abaixo. Cite os documentos usados.\n\n"
        f"Contexto:\n{context}\n\nPergunta: {request.question}"
    )
    try:
        answer = openrouter_client.chat_completion(
            model=request.model,
            messages=[{"role": "user", "content": prompt}],
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Falha na chamada ao OpenRouter: {exc.response.status_code} {exc.response.text}",
        ) from exc

    citations = [
        Citation(
            document_id=c.document_id,
            source_path=c.source_path,
            chunk_index=c.chunk_index,
            snippet=c.content[:280],
        )
        for c in top_chunks
    ]

    return QueryResponse(answer=answer, citations=citations, graph_documents=graph_documents)


@app.get("/health", response_model=HealthResponse)
def health():
    postgres_status = "ok"
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - health check deve reportar erro, não propagar exceção
        postgres_status = "error"

    vpn_status = get_vpn_status()
    overall = "ok" if postgres_status == "ok" and vpn_status == "ok" else "degraded"

    return HealthResponse(status=overall, postgres=postgres_status, vpn_status=vpn_status)
