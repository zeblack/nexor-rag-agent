"""Teste manual: consulta Cypher direta ao grafo de entidades via Apache AGE,
para confirmar que uma entidade compartilhada aparece ligada a dois documentos."""
import sys

from app.db import get_session, run_cypher


def find_entity_documents(entity_name: str) -> list[str]:
    with get_session() as session:
        result = run_cypher(
            session,
            "MATCH (e:Entity {name: $name}) RETURN DISTINCT e.source_document_id",
            {"name": entity_name},
        )
        return [str(row[0]).strip('"') for row in result]


if __name__ == "__main__":
    entity_name = sys.argv[1] if len(sys.argv) > 1 else "Entidade de Teste"
    documents = find_entity_documents(entity_name)
    print(f"Entidade '{entity_name}' encontrada em {len(documents)} documento(s):")
    for doc_id in documents:
        print(f"  - {doc_id}")
