from odf import table, teletype, text
from odf.opendocument import load

from app.ingestion.parsers import ParsedDocument


def parse(file_path: str) -> ParsedDocument:
    doc = load(file_path)
    parts = []
    for paragraph in doc.getElementsByType(text.P):
        content = teletype.extractText(paragraph)
        if content.strip():
            parts.append(content)
    for row in doc.getElementsByType(table.TableRow):
        cells = doc_row_cells(row)
        if cells:
            parts.append(" | ".join(cells))
    return ParsedDocument(text="\n".join(parts), parser_used="odfpy")


def doc_row_cells(row) -> list[str]:
    from odf import table as odf_table

    cells = []
    for cell in row.getElementsByType(odf_table.TableCell):
        cells.append(teletype.extractText(cell))
    return cells
