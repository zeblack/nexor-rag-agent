"""Teste manual: consulta híbrida via API. Espera uma pergunta que só faz
sentido cruzando dois documentos de teste (ex: entidade compartilhada)."""
import sys

import httpx

API_URL = "http://localhost:8000"
TOKEN = "CHANGE_ME"  # mesmo valor de API_AUTH_TOKEN no .env


def query(question: str, model: str) -> dict:
    response = httpx.post(
        f"{API_URL}/query",
        json={"question": question, "model": model, "top_k": 8},
        headers={"Authorization": f"Bearer {TOKEN}"},
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else "O que os dois documentos têm em comum?"

    models_response = httpx.get(f"{API_URL}/models").json()
    model = models_response["default_model"]
    print(f"Usando modelo: {model}\n")

    result = query(question, model)
    print("Resposta:", result["answer"])
    print("\nCitações:")
    for c in result["citations"]:
        print(f"  - {c['source_path']} (chunk {c['chunk_index']}): {c['snippet'][:100]}...")
    print("\nDocumentos cruzados via grafo:", result["graph_documents"])
