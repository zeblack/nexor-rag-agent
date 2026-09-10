import logging
import os

from app.ingestion.parsers import ParsedDocument
from app.ingestion.parsers import (
    docling_parser,
    docx_parser,
    iwork_parser,
    msg_parser,
    odt_ods_parser,
    onenote_parser,
    pptx_parser,
    pymupdf_parser,
    xlsx_parser,
)

logger = logging.getLogger(__name__)

LONG_PATH_PREFIX = "\\\\?\\"

# Formatos não-documentais: skip esperado, não erro de parser desconhecido.
EXCLUDED_EXTENSIONS = {
    ".bpm", ".exe", ".dll", ".bin", ".ini", ".lnk", ".log",
}
EXCLUDED_FILENAMES = {"thumbs.db", ".ds_store"}


class UnsupportedFileError(Exception):
    pass


class ExcludedFileError(Exception):
    """Levantado para arquivos que são skip esperado, não falha de parsing."""
    pass


def to_long_path(path: str) -> str:
    """Aplica o prefixo de caminho estendido do Windows quando necessário."""
    if os.name != "nt":
        return path
    abs_path = os.path.abspath(path)
    if abs_path.startswith(LONG_PATH_PREFIX):
        return abs_path
    return LONG_PATH_PREFIX + abs_path


def is_excluded(file_path: str) -> bool:
    filename = os.path.basename(file_path).lower()
    # Cópias duplicadas geram nomes tipo " (1).DS_Store" ou "Thumbs (1).db" —
    # checar se o nome de exclusão aparece como sufixo, não só igualdade exata.
    if any(filename.endswith(excluded) for excluded in EXCLUDED_FILENAMES):
        return True
    ext = os.path.splitext(file_path)[1].lower()
    return ext in EXCLUDED_EXTENSIONS


def parse(file_path: str) -> ParsedDocument:
    """Decide o parser por extensão, com fallback em cascata. Levanta
    ExcludedFileError para formatos não-documentais e UnsupportedFileError
    se todos os parsers da cascata falharem."""
    if is_excluded(file_path):
        raise ExcludedFileError(f"Arquivo excluído por política do router: {file_path}")

    long_path = to_long_path(file_path)
    ext = os.path.splitext(file_path)[1].lower()

    cascade = _cascade_for_extension(ext, long_path)
    if cascade is None:
        raise UnsupportedFileError(f"Nenhum parser configurado para a extensão '{ext}'")

    last_error: Exception | None = None
    for parser_fn, parser_name in cascade:
        try:
            return parser_fn(long_path)
        except Exception as exc:  # noqa: BLE001 - cascata precisa capturar qualquer falha de parser
            logger.warning("Parser %s falhou para %s: %s", parser_name, file_path, exc)
            last_error = exc
            continue

    raise UnsupportedFileError(
        f"Todos os parsers da cascata falharam para '{file_path}': {last_error}"
    )


def _cascade_for_extension(ext: str, long_path: str):
    if ext == ".pdf":
        if pymupdf_parser.has_extractable_text(long_path):
            return [(pymupdf_parser.parse, "pymupdf"), (docling_parser.parse, "docling_ocr")]
        return [(docling_parser.parse, "docling_ocr"), (pymupdf_parser.parse, "pymupdf")]
    if ext == ".docx":
        return [(docx_parser.parse, "python-docx")]
    if ext in (".xlsx", ".xlsb"):
        return [(xlsx_parser.parse, "openpyxl_or_pyxlsb")]
    if ext in (".odt", ".ods"):
        return [(odt_ods_parser.parse, "odfpy")]
    if ext == ".pptx":
        return [(pptx_parser.parse, "python-pptx")]
    if ext == ".msg":
        return [(msg_parser.parse, "extract-msg")]
    if ext in (".pages", ".numbers"):
        return [(iwork_parser.parse, "iwork_quicklook")]
    if ext in (".one", ".onetoc2"):
        return [(onenote_parser.parse, "onenote_unsupported")]
    return None
