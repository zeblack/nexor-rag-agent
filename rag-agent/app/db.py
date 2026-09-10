import json
from contextlib import contextmanager

from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.types import UserDefinedType

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class AgType(UserDefinedType):
    """Declara o bind parameter como tipo agtype nativo do Apache AGE — a
    função cypher() exige que o 3º argumento seja um parâmetro puro desse
    tipo (não aceita cast inline como :param::agtype no ponto de uso)."""

    cache_ok = True

    def get_col_spec(self, **kw):
        return "agtype"


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def run_cypher(session, query: str, params: dict | None = None):
    """Executa uma consulta Cypher no grafo rag_graph via Apache AGE.

    A função cypher() do AGE tem assinatura cypher(graph_name, query, params agtype)
    — os parâmetros Cypher ($nome dentro da query) não são bind params do SQLAlchemy,
    precisam ser serializados como JSON e passados como terceiro argumento da própria
    função SQL cypher(), referenciado aqui via um bind param separado (:cypher_params)
    que NÃO aparece dentro da string Cypher.
    """
    session.execute(text("LOAD 'age';"))
    session.execute(text("SET search_path = ag_catalog, \"$user\", public;"))
    full_query = text(
        f"SELECT * FROM cypher('rag_graph', $$ {query} $$, :cypher_params) AS (result agtype);"
    ).bindparams(bindparam("cypher_params", type_=AgType()))
    return session.execute(full_query, {"cypher_params": json.dumps(params or {})})
