import os
import sqlite3
import time

import httpx

import queue_db
from config import UploaderConfig
from file_mover import move_to_up_ok
from scanner import to_long_path
from structured_logger import StructuredLogger


class Uploader:
    def __init__(self, config: UploaderConfig, root_path: str, logger: StructuredLogger):
        self.config = config
        self.root_path = os.path.abspath(root_path)
        self.logger = logger
        self._client = httpx.Client(timeout=config.timeout_seconds)

    def close(self):
        self._client.close()

    def process_item(self, conn: sqlite3.Connection, item: queue_db.QueueItem):
        if item.status in ("pendente", "erro"):
            self._upload(conn, item)
            # Recarrega o item para pegar o document_id gravado, se o upload deu certo
            row = conn.execute(
                "SELECT * FROM upload_queue WHERE caminho_absoluto = ?", (item.caminho_absoluto,)
            ).fetchone()
            if row is None or row["status"] != "enviado_aguardando_confirmacao":
                return
            item = queue_db.QueueItem(
                caminho_absoluto=row["caminho_absoluto"],
                hash_sha256=row["hash_sha256"],
                document_id=row["document_id"],
                status=row["status"],
                tentativas=row["tentativas"],
                mensagem_erro=row["mensagem_erro"],
            )

        if item.status == "enviado_aguardando_confirmacao" and item.document_id:
            self._poll_and_confirm(conn, item)

    def _upload(self, conn: sqlite3.Connection, item: queue_db.QueueItem):
        relative_path = os.path.relpath(item.caminho_absoluto, self.root_path)
        self.logger.log("upload_start", path=item.caminho_absoluto, relative_path=relative_path)

        try:
            with open(to_long_path(item.caminho_absoluto), "rb") as f:
                response = self._client.post(
                    f"{self.config.api_url}/ingest",
                    params={"source_path": relative_path},
                    files={"file": (os.path.basename(item.caminho_absoluto), f)},
                    headers={"Authorization": f"Bearer {self.config.api_token}"},
                )
        except httpx.RequestError as exc:
            queue_db.mark_erro(conn, item.caminho_absoluto, str(exc))
            self.logger.log("upload_network_error", path=item.caminho_absoluto, error=str(exc))
            return

        if response.status_code >= 500:
            queue_db.mark_erro(conn, item.caminho_absoluto, f"HTTP {response.status_code}: {response.text}")
            self.logger.log("upload_server_error", path=item.caminho_absoluto, status_code=response.status_code)
            return

        if response.status_code >= 400:
            queue_db.mark_falha_permanente(
                conn, item.caminho_absoluto, f"HTTP {response.status_code}: {response.text}"
            )
            self.logger.log("upload_rejected", path=item.caminho_absoluto, status_code=response.status_code)
            return

        document_id = response.json()["document_id"]
        queue_db.mark_enviado_aguardando(conn, item.caminho_absoluto, document_id)
        self.logger.log("upload_accepted", path=item.caminho_absoluto, document_id=document_id)

    def _poll_and_confirm(self, conn: sqlite3.Connection, item: queue_db.QueueItem):
        start = time.monotonic()
        while time.monotonic() - start < self.config.poll_timeout_seconds:
            try:
                response = self._client.get(
                    f"{self.config.api_url}/ingest/status/{item.document_id}",
                    headers={"Authorization": f"Bearer {self.config.api_token}"},
                )
                response.raise_for_status()
                status = response.json()["status"]
            except httpx.HTTPError as exc:
                self.logger.log("poll_error", document_id=item.document_id, error=str(exc))
                time.sleep(self.config.poll_interval_seconds)
                continue

            self.logger.log("poll_status", document_id=item.document_id, status=status)

            if status == "concluido":
                self._confirm_and_move(conn, item)
                return
            if status == "erro_processamento":
                queue_db.mark_falha_permanente(
                    conn, item.caminho_absoluto, "erro_processamento reportado pelo servidor"
                )
                self.logger.log("processing_failed", document_id=item.document_id)
                return

            time.sleep(self.config.poll_interval_seconds)

        queue_db.mark_erro(conn, item.caminho_absoluto, "Timeout de polling aguardando confirmação")
        self.logger.log("poll_timeout", document_id=item.document_id)

    def _confirm_and_move(self, conn: sqlite3.Connection, item: queue_db.QueueItem):
        relative_path = os.path.relpath(item.caminho_absoluto, self.root_path)
        try:
            new_path = move_to_up_ok(self.root_path, item.caminho_absoluto, relative_path)
        except OSError as exc:
            queue_db.mark_erro(conn, item.caminho_absoluto, f"Falha ao mover para up-ok/: {exc}")
            self.logger.log("move_error", path=item.caminho_absoluto, error=str(exc))
            return

        queue_db.mark_confirmado_movido(conn, item.caminho_absoluto)
        self.logger.log("confirmed_and_moved", path=item.caminho_absoluto, new_path=new_path,
                         document_id=item.document_id)
