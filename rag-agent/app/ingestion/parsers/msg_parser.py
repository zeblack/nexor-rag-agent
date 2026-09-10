import extract_msg

from app.ingestion.parsers import ParsedDocument


def parse(file_path: str) -> ParsedDocument:
    msg = extract_msg.Message(file_path)
    try:
        parts = [
            f"De: {msg.sender or ''}",
            f"Para: {msg.to or ''}",
            f"Assunto: {msg.subject or ''}",
            f"Data: {msg.date or ''}",
            "",
            msg.body or "",
        ]
    finally:
        msg.close()
    return ParsedDocument(text="\n".join(parts), parser_used="extract-msg")
