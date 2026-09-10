"""Extrai campos determinísticos do caminho relativo do arquivo, antes de qualquer chamada a LLM.

Padrão comum em árvores de arquivos organizadas por data e responsável:
`.../ANO/MES/NOME DA PESSOA/arquivo.ext` (ex: `RELATORIOS/2020/03 - MARÇO/02 -
JOAO DA SILVA/arquivo.pdf`). Regras são best-effort: quando não casam,
simplesmente não populam o campo, e metadata_extractor.py cai para extração
via LLM sobre o conteúdo.
"""
import re

_ANO_RE = re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)")
_MES_RE = re.compile(
    r"\b(JAN(?:EIRO)?|FEV(?:EREIRO)?|MAR(?:ÇO|CO)?|ABR(?:IL)?|MAI(?:O)?|JUN(?:HO)?|"
    r"JUL(?:HO)?|AGO(?:STO)?|SET(?:EMBRO)?|OUT(?:UBRO)?|NOV(?:EMBRO)?|DEZ(?:EMBRO)?)\b",
    re.IGNORECASE,
)
# Segmento de pasta tipo "02 - JOAO DA SILVA" ou "JOAO DA SILVA" —
# nome em maiúsculas com pelo menos duas palavras, prefixo numérico opcional.
_NOME_PASTA_RE = re.compile(r"^(?:\d+\s*-\s*)?([A-ZÀ-Ú][A-ZÀ-Ú\s]{4,})(?:\s*\(.*\))?$")


def extract_path_metadata(relative_path: str) -> dict:
    """Retorna campos determinísticos encontrados no caminho: ano, mes, nome_pessoa."""
    segments = [s for s in re.split(r"[\\/]", relative_path) if s]
    fields: dict = {}

    for segment in segments:
        if "ano" not in fields:
            m = _ANO_RE.search(segment)
            if m:
                fields["ano"] = m.group(0)

        if "mes" not in fields:
            m = _MES_RE.search(segment)
            if m:
                fields["mes"] = m.group(0).upper()

        if "nome_pessoa" not in fields:
            m = _NOME_PASTA_RE.match(segment.strip())
            if m:
                candidate = m.group(1).strip()
                # Evita capturar segmentos que são só categoria (ex: "ARQUIVO", "RESOLVIDOS")
                if len(candidate.split()) >= 2 and not _looks_like_category(candidate):
                    fields["nome_pessoa"] = candidate

    return fields


# Palavras genéricas de estrutura de pasta (não nomes de pessoa) — adapte esta
# lista ao vocabulário de categorias da sua própria árvore de arquivos.
_CATEGORY_WORDS = {
    "ARQUIVO", "ARQUIVOS", "DIRETORIO", "RESOLVIDOS", "PENDENTES",
    "CONTRATOS", "RELATORIOS", "DOCUMENTOS", "DOCUMENTOS INTERNOS",
    "GERAL", "DIVERSOS", "OUTROS", "BACKUP", "TEMPLATES",
}


def _looks_like_category(candidate: str) -> bool:
    normalized = re.sub(r"[ÁÀÃÂ]", "A", candidate)
    normalized = re.sub(r"[ÉÊ]", "E", normalized)
    normalized = re.sub(r"[ÍÎ]", "I", normalized)
    normalized = re.sub(r"[ÓÔÕ]", "O", normalized)
    normalized = re.sub(r"[ÚÛ]", "U", normalized)
    normalized = re.sub(r"[Ç]", "C", normalized)
    return normalized in _CATEGORY_WORDS
