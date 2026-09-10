import os
import shutil

from scanner import UP_OK_DIRNAME, to_long_path


def move_to_up_ok(root_path: str, absolute_path: str, relative_path: str) -> str:
    """Move o arquivo confirmado para <root>/up-ok/<caminho relativo>, criando
    a subpasta espelho se necessário. Retorna o novo caminho absoluto."""
    dest_path = os.path.join(root_path, UP_OK_DIRNAME, relative_path)
    dest_dir = os.path.dirname(dest_path)
    os.makedirs(to_long_path(dest_dir), exist_ok=True)
    shutil.move(to_long_path(absolute_path), to_long_path(dest_path))
    return dest_path
