from docling.document_converter import DocumentConverter

from app.ingestion.parsers import ParsedDocument

_converter = DocumentConverter()


def parse(file_path: str) -> ParsedDocument:
    """PDF via OCR completo (scans sem camada de texto)."""
    result = _converter.convert(file_path)
    text = result.document.export_to_markdown()
    return ParsedDocument(text=text, parser_used="docling_ocr")
