"""Extração de entidades/relações via LLM, disparada pelo worker após o
documento ser marcado 'concluido'. Roda como tarefa própria da fila — não
bloqueia a confirmação de conclusão do documento (parsing+chunking+embedding)."""
import json
import logging

from sqlalchemy import text

from app.db import get_session, run_cypher
from app.models_registry import registry
from app.openrouter_client import client
from app.queue import celery_app

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """Extraia entidades e relações do texto abaixo. Responda APENAS um JSON:
{{"entities": [{{"name": "...", "type": "PESSOA|EMPRESA|VALOR|DATA|OUTRO"}}],
  "relations": [{{"source": "...", "target": "...", "type": "MENTIONS|RELATED_TO|PARTY_OF"}}]}}
Não invente entidades que não aparecem explicitamente no texto.

Texto:
{content}
"""


@celery_app.task(name="extract_entities")
def extract_entities_for_document(document_id: str):
    with get_session() as session:
        chunks = session.execute(
            text("SELECT chunk_id, content FROM chunks WHERE document_id = :doc_id ORDER BY chunk_index"),
            {"doc_id": document_id},
        ).fetchall()

        for chunk_id, content in chunks:
            try:
                extracted = _extract_via_llm(content)
            except Exception as exc:  # noqa: BLE001 - extração de entidade é enriquecimento, não crítico
                logger.warning("Falha na extração de entidades do chunk %s: %s", chunk_id, exc)
                continue

            for entity in extracted.get("entities", []):
                run_cypher(
                    session,
                    """
                    MERGE (e:Entity {name: $name, type: $type})
                    SET e.source_document_id = $doc_id, e.source_chunk_id = $chunk_id
                    """,
                    {
                        "name": entity.get("name", ""),
                        "type": entity.get("type", "OUTRO"),
                        "doc_id": document_id,
                        "chunk_id": str(chunk_id),
                    },
                )

            for relation in extracted.get("relations", []):
                run_cypher(
                    session,
                    """
                    MATCH (a:Entity {name: $source}), (b:Entity {name: $target})
                    MERGE (a)-[r:RELATED {type: $rel_type}]->(b)
                    """,
                    {
                        "source": relation.get("source", ""),
                        "target": relation.get("target", ""),
                        "rel_type": relation.get("type", "RELATED_TO"),
                    },
                )


def _extract_via_llm(content: str) -> dict:
    prompt = _EXTRACTION_PROMPT.format(content=content[:4000])
    raw = client.chat_completion(
        model=registry.default_model,
        messages=[{"role": "user", "content": prompt}],
        json_mode=True,
    )
    return json.loads(raw)
