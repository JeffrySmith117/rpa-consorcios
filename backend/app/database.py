import logging
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def _build_engine(url: str):
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")  # leituras concorrentes com escrita
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return engine


engine = _build_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# Colunas adicionadas depois da primeira versão. `create_all` só cria tabelas
# novas; não altera as existentes. Em produção isso seria uma migração do
# Alembic — aqui, um ALTER TABLE simples na subida mantém bancos antigos funcionando.
COLUNAS_NOVAS = {
    "execucoes": {"etapas": "JSON"},
}


def init_db() -> None:
    from app import models  # noqa: F401  (registra os modelos)

    Base.metadata.create_all(engine)
    _adicionar_colunas_novas()


def _adicionar_colunas_novas() -> None:
    inspetor = inspect(engine)
    with engine.begin() as conexao:
        for tabela, colunas in COLUNAS_NOVAS.items():
            existentes = {c["name"] for c in inspetor.get_columns(tabela)}
            for nome, tipo in colunas.items():
                if nome not in existentes:
                    conexao.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}"))
                    log.info("Banco atualizado: coluna %s.%s criada.", tabela, nome)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()