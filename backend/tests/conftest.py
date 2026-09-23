import json
import os
import tempfile
from pathlib import Path

# Configura o ambiente ANTES de importar a aplicação (engine e settings são criados no import).
_tmp = Path(tempfile.mkdtemp(prefix="rpa-testes-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'teste.db').as_posix()}"
os.environ["LOG_DIR"] = str(_tmp / "logs")
os.environ["WHATSAPP_PROVIDER"] = "mock"
os.environ["RPA_MAX_TENTATIVAS"] = "2"

import pytest  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import Base, SessionLocal, engine, init_db  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def carregar(data_base: str) -> list[dict]:
    return json.loads((FIXTURES / f"metricas_{data_base}.json").read_text(encoding="utf-8"))


@pytest.fixture
def registros() -> dict[str, list[dict]]:
    return {"202606": carregar("202606"), "202603": carregar("202603")}


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def db():
    Base.metadata.drop_all(engine)
    init_db()
    with SessionLocal() as sessao:
        yield sessao


@pytest.fixture(autouse=True)
def sem_espera_entre_tentativas(monkeypatch):
    """Retentativas sem o backoff real, para os testes rodarem rápido."""
    import tenacity

    monkeypatch.setattr(tenacity.nap, "sleep", lambda _: None)
