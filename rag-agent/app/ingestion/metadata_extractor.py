"""Combina path_metadata.py (prioridade, determinístico, custo zero) com LLM
(fallback, só para campos que o caminho não resolveu)."""
import json

from app.config import settings
from app.ingestion.path_metadata import extract_path_metadata
from app.models_registry import registry
from app.openrouter_client import client

# Campos de exemplo — adapte esta lista e o prompt à taxonomia de metadata
# relevante para o seu próprio domínio de documentos (ex: número de pedido,
# código de referência, título, autor, categoria).
_LLM_FIELDS_PROMPT = """Extraia os seguintes campos do texto abaixo, se presentes: identificador
ou número de referência, nome da organização/entidade citada, título ou assunto principal.
Responda APENAS um JSON com as chaves "identificador", "organizacao", "titulo"
(use null para o que não encontrar). Não invente valores.

Texto:
{content}
"""


def extract_structured_fields(relative_path: str, content_sample: str) -> dict:
    fields = extract_path_metadata(relative_path)

    missing_llm_fields = {"identificador", "organizacao", "titulo"} - fields.keys()
    if missing_llm_fields and content_sample.strip():
        llm_fields = _extract_via_llm(content_sample)
        for key in missing_llm_fields:
            value = llm_fields.get(key)
            if value:
                fields[key] = value

    return fields


def _extract_via_llm(content_sample: str) -> dict:
    prompt = _LLM_FIELDS_PROMPT.format(content=content_sample[:4000])
    try:
        raw = client.chat_completion(
            model=registry.default_model,
            messages=[{"role": "user", "content": prompt}],
            json_mode=True,
        )
        return json.loads(raw)
    except Exception:  # noqa: BLE001 - extração de metadata é best-effort, não deve derrubar a ingestão
        return {}
