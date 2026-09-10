import fitz  # PyMuPDF

from app.ingestion.parsers import ParsedDocument


def has_extractable_text(file_path: str, min_chars: int = 50) -> bool:
    """Checagem barata: o PDF tem camada de texto extraível, ou é puramente imagem (scan)?"""
    doc = fitz.open(file_path)
    try:
        total_chars = 0
        # amostra as primeiras páginas — suficiente pra decidir sem abrir o documento inteiro
        for page in doc[: min(5, doc.page_count)]:
            total_chars += len(page.get_text().strip())
            if total_chars >= min_chars:
                return True
        return total_chars >= min_chars
    finally:
        doc.close()


def parse(file_path: str) -> ParsedDocument:
    doc = fitz.open(file_path)
    try:
        text = "\n\n".join(page.get_text() for page in doc)
    finally:
        doc.close()
    return ParsedDocument(text=text, parser_used="pymupdf")
