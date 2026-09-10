"""Teste manual: envia 2-3 documentos sintéticos que compartilham uma entidade
proposital, e acompanha o status via polling até 'concluido'."""
import sys
import time

import httpx

API_URL = "http://localhost:8000"
TOKEN = "CHANGE_ME"  # mesmo valor de API_AUTH_TOKEN no .env


def ingest_file(path: str, source_path: str) -> str:
    with open(path, "rb") as f:
        response = httpx.post(
            f"{API_URL}/ingest",
            params={"source_path": source_path},
            files={"file": (source_path, f)},
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=60.0,
        )
    response.raise_for_status()
    return response.json()["document_id"]


def wait_for_completion(document_id: str, timeout_seconds: int = 300):
    start = time.time()
    while time.time() - start < timeout_seconds:
        response = httpx.get(
            f"{API_URL}/ingest/status/{document_id}",
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        if response.status_code == 404:
            # Pequena janela entre o commit do /ingest e a visibilidade da linha —
            # tolera algumas tentativas antes de considerar erro de verdade.
            print(f"  {document_id[:16]}... -> ainda não visível, tentando de novo")
            time.sleep(1)
            continue
        response.raise_for_status()
        status = response.json()["status"]
        print(f"  {document_id[:16]}... -> {status}")
        if status in ("concluido", "erro_processamento"):
            return status
        time.sleep(3)
    raise TimeoutError(f"Timeout aguardando conclusão de {document_id}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python test_ingest.py <arquivo1> [arquivo2] ...")
        sys.exit(1)

    for file_path in sys.argv[1:]:
        print(f"Enviando {file_path}...")
        doc_id = ingest_file(file_path, file_path)
        status = wait_for_completion(doc_id)
        print(f"Resultado: {status}\n")
