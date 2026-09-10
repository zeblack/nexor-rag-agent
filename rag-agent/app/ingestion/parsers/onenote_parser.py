"""Parser para .one/.onetoc2 (Microsoft OneNote).

Formato binário proprietário (MS-ONESTORE) sem biblioteca Python de extração de
texto madura e mantida. Sem uma ferramenta externa (ex: OneNote instalado via COM,
Windows-only, ou conversão manual), não é possível extrair texto de forma confiável.
Levanta erro explícito para que o router registre isso como falha conhecida do
parser (não um "arquivo corrompido"), permitindo decidir depois se vale investir
em uma dependência externa para este formato de baixo volume na base real.
"""
from app.ingestion.parsers import ParsedDocument


def parse(file_path: str) -> ParsedDocument:
    raise NotImplementedError(
        "Extração de texto de .one/.onetoc2 (OneNote) não suportada nesta versão — "
        "formato binário proprietário sem biblioteca de extração madura disponível."
    )
