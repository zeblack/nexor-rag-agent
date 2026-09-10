import logging
import os

from sqlalchemy import text

from app.db import get_session
from app.ingestion import router
from app.ingestion.chunker import chunk_text
from app.ingestion.embedder import embed_batch
from app.ingestion.entity_extraction_task import extract_entities_for_document
from app.ingestion.metadata_extractor import extract_structured_fields
from app.queue import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="ingest_document")
def ingest_document_task(document_id: str, file_path: str, source_path: str):
    _mark_status(document_id, "processando")
    try:
        parsed = router.parse(file_path)
        structured_fields = extract_structured_fields(source_path, parsed.text)
        chunks = chunk_text(parsed.text)
        embeddings = embed_batch(chunks)

        with get_session() as session:
            session.execute(
                text("UPDATE documents SET structured_fields = :fields WHERE document_id = :doc_id"),
                {"fields": _to_jsonb(structured_fields), "doc_id": document_id},
            )
            for idx, (chunk_content, embedding) in enumerate(zip(chunks, embeddings)):
                session.execute(
                    text(
                        """
                        INSERT INTO chunks (document_id, chunk_index, content, embedding)
                        VALUES (:doc_id, :idx, :content, :embedding)
                        ON CONFLICT (document_id, chunk_index) DO UPDATE
                        SET content = EXCLUDED.content, embedding = EXCLUDED.embedding
                        """
                    ),
                    {"doc_id": document_id, "idx": idx, "content": chunk_content, "embedding": str(embedding)},
                )

        _mark_status(document_id, "concluido")
        extract_entities_for_document.delay(document_id)

    except router.ExcludedFileError as exc:
        logger.info("Arquivo excluído por política: %s", exc)
        _mark_status(document_id, "erro_processamento", str(exc))
    except Exception as exc:  # noqa: BLE001 - worker precisa capturar qualquer falha de pipeline
        logger.exception("Falha ao processar documento %s", document_id)
        _mark_status(document_id, "erro_processamento", str(exc))
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


def _mark_status(document_id: str, status: str, error_message: str | None = None):
    with get_session() as session:
        session.execute(
            text(
                "UPDATE documents SET status = :status, error_message = :error, updated_at = now() "
                "WHERE document_id = :doc_id"
            ),
            {"status": status, "error": error_message, "doc_id": document_id},
        )


def _to_jsonb(fields: dict) -> str:
    import json

    return json.dumps(fields, ensure_ascii=False)
