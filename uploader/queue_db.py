import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass

_SCHEMA = """
CREATE TABLE IF NOT EXISTS upload_queue (
    caminho_absoluto      TEXT PRIMARY KEY,
    hash_sha256            TEXT NOT NULL,
    document_id            TEXT,
    status                 TEXT NOT NULL DEFAULT 'pendente'
                               CHECK (status IN (
                                   'pendente', 'enviado_aguardando_confirmacao',
                                   'confirmado_movido', 'erro', 'falha_permanente'
                               )),
    tentativas              INTEGER NOT NULL DEFAULT 0,
    timestamp_ultima_tentativa TEXT,
    mensagem_erro           TEXT
);
CREATE INDEX IF NOT EXISTS idx_upload_queue_status ON upload_queue (status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_upload_queue_hash ON upload_queue (hash_sha256);
"""


@dataclass
class QueueItem:
    caminho_absoluto: str
    hash_sha256: str
    document_id: str | None
    status: str
    tentativas: int
    mensagem_erro: str | None


@contextmanager
def get_connection(db_path: str = "uploader_state.db"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_if_new(conn: sqlite3.Connection, caminho_absoluto: str, hash_sha256: str) -> bool:
    """Insere só se o hash ainda não existe na fila. Retorna True se inseriu."""
    try:
        conn.execute(
            "INSERT INTO upload_queue (caminho_absoluto, hash_sha256) VALUES (?, ?)",
            (caminho_absoluto, hash_sha256),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def get_eligible_items(conn: sqlite3.Connection, max_retries: int) -> list[QueueItem]:
    rows = conn.execute(
        """
        SELECT * FROM upload_queue
        WHERE status IN ('pendente', 'enviado_aguardando_confirmacao')
           OR (status = 'erro' AND tentativas < ?)
        ORDER BY rowid
        """,
        (max_retries,),
    ).fetchall()
    return [
        QueueItem(
            caminho_absoluto=r["caminho_absoluto"],
            hash_sha256=r["hash_sha256"],
            document_id=r["document_id"],
            status=r["status"],
            tentativas=r["tentativas"],
            mensagem_erro=r["mensagem_erro"],
        )
        for r in rows
    ]


def mark_enviado_aguardando(conn: sqlite3.Connection, caminho_absoluto: str, document_id: str):
    conn.execute(
        """
        UPDATE upload_queue
        SET status = 'enviado_aguardando_confirmacao', document_id = ?,
            timestamp_ultima_tentativa = datetime('now')
        WHERE caminho_absoluto = ?
        """,
        (document_id, caminho_absoluto),
    )


def mark_erro(conn: sqlite3.Connection, caminho_absoluto: str, mensagem: str):
    conn.execute(
        """
        UPDATE upload_queue
        SET status = 'erro', tentativas = tentativas + 1,
            timestamp_ultima_tentativa = datetime('now'), mensagem_erro = ?
        WHERE caminho_absoluto = ?
        """,
        (mensagem, caminho_absoluto),
    )


def mark_falha_permanente(conn: sqlite3.Connection, caminho_absoluto: str, mensagem: str):
    conn.execute(
        """
        UPDATE upload_queue
        SET status = 'falha_permanente', timestamp_ultima_tentativa = datetime('now'),
            mensagem_erro = ?
        WHERE caminho_absoluto = ?
        """,
        (mensagem, caminho_absoluto),
    )


def mark_confirmado_movido(conn: sqlite3.Connection, caminho_absoluto: str):
    conn.execute(
        """
        UPDATE upload_queue
        SET status = 'confirmado_movido', timestamp_ultima_tentativa = datetime('now')
        WHERE caminho_absoluto = ?
        """,
        (caminho_absoluto,),
    )


def status_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT status, COUNT(*) as n FROM upload_queue GROUP BY status").fetchall()
    return {r["status"]: r["n"] for r in rows}


def falhas_permanentes(conn: sqlite3.Connection) -> list[QueueItem]:
    rows = conn.execute("SELECT * FROM upload_queue WHERE status = 'falha_permanente'").fetchall()
    return [
        QueueItem(
            caminho_absoluto=r["caminho_absoluto"],
            hash_sha256=r["hash_sha256"],
            document_id=r["document_id"],
            status=r["status"],
            tentativas=r["tentativas"],
            mensagem_erro=r["mensagem_erro"],
        )
        for r in rows
    ]
