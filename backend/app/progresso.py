"""Canal de progresso do robô.

O robô e o orquestrador chamam `reportar("Pesquisando 'consórcios'")` sem saber
quem está ouvindo. Quem quiser acompanhar (a execução em segundo plano, que
grava as etapas no banco para o frontend exibir) registra um ouvinte com
`ouvir(...)`. Sem ouvinte, `reportar` não faz nada — por isso os testes e o
carregamento de histórico funcionam sem mudança.

Usa ContextVar: cada thread/execução tem o seu ouvinte, então duas consultas
rodando em paralelo não misturam as etapas.
"""
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

log = logging.getLogger(__name__)

_ouvinte: ContextVar[Callable[[str], None] | None] = ContextVar("ouvinte_progresso", default=None)


def reportar(etapa: str) -> None:
    ouvinte = _ouvinte.get()
    if ouvinte is None:
        return
    try:
        ouvinte(etapa)
    except Exception:  # noqa: BLE001 — falha ao registrar progresso nunca derruba o robô
        log.exception("Não foi possível registrar a etapa de progresso: %s", etapa)


@contextmanager
def ouvir(ouvinte: Callable[[str], None]) -> Iterator[None]:
    token = _ouvinte.set(ouvinte)
    try:
        yield
    finally:
        _ouvinte.reset(token)