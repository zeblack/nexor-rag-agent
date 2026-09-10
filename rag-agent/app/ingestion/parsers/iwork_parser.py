"""Parser para .pages/.numbers (Apple iWork).

Formato é um pacote ZIP contendo `Index.zip` (para .pages/.numbers modernos) com
snapshots de conteúdo em protobuf binário proprietário — não há biblioteca Python
madura para decodificar o protobuf da Apple. Extraímos o que é possível sem essa
dependência: o preview/QuickLook em texto, quando presente no pacote, que cobre
boa parte dos arquivos exportados/sincronizados via iCloud.
"""
import zipfile

from app.ingestion.parsers import ParsedDocument


def parse(file_path: str) -> ParsedDocument:
    parts = []
    with zipfile.ZipFile(file_path) as zf:
        preview_candidates = [
            n for n in zf.namelist()
            if n.startswith("QuickLook/") and n.lower().endswith((".txt", ".pdf", ".html"))
        ]
        for name in preview_candidates:
            if name.lower().endswith(".txt") or name.lower().endswith(".html"):
                parts.append(zf.read(name).decode("utf-8", errors="replace"))

    if not parts:
        raise ValueError(
            "Arquivo iWork sem preview de texto legível (QuickLook ausente) — "
            "conteúdo binário protobuf não suportado nesta versão do parser."
        )
    return ParsedDocument(text="\n".join(parts), parser_used="iwork_quicklook")
