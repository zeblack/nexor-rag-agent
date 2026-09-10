import hashlib
import os

LONG_PATH_PREFIX = "\\\\?\\"

# Mesma lista de exclusão do router de ingestão do agente RAG — evita gastar
# ciclo de rede com arquivo que a API vai rejeitar de qualquer forma.
EXCLUDED_EXTENSIONS = {".bpm", ".exe", ".dll", ".bin", ".ini", ".lnk", ".log"}
EXCLUDED_FILENAMES = {"thumbs.db", ".ds_store"}
UP_OK_DIRNAME = "up-ok"


def to_long_path(path: str) -> str:
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


def sha256_of_file(file_path: str, block_size: int = 1024 * 1024 * 8) -> str:
    h = hashlib.sha256()
    with open(to_long_path(file_path), "rb") as f:
        while True:
            chunk = f.read(block_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def scan_root(root_path: str):
    """Gera (caminho_absoluto, caminho_relativo, hash) para cada arquivo elegível
    da árvore, pulando exclusões e o que já está dentro da pasta up-ok/."""
    root_path = os.path.abspath(root_path)
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Nunca descer dentro de up-ok/ — arquivos lá já foram confirmados.
        dirnames[:] = [d for d in dirnames if d != UP_OK_DIRNAME]

        for filename in filenames:
            abs_path = os.path.join(dirpath, filename)
            if is_excluded(abs_path):
                continue
            relative_path = os.path.relpath(abs_path, root_path)
            file_hash = sha256_of_file(abs_path)
            yield abs_path, relative_path, file_hash
