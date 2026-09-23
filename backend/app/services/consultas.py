"""Orquestra uma execução do RPA: validação → trava de duplicidade →
coleta (com retentativas e plano B) → tratamento → persistência."""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import Settings
from app.exceptions import AppError, EntradaInvalida, FalhaNavegacao, FonteIndisponivel, NaoEncontrado, ProcessamentoDuplicado
from app.models import Execucao, StatusExecucao
from app.rpa.bcb_portal import PortalBCB
from app.rpa.olinda_api import OlindaAPI
from app.services.tratamento import SEGMENTOS, UFS, estruturar, referencia, trimestre_anterior

log = logging.getLogger(__name__)

Coletor = Callable[[list[str]], dict[str, list[dict]]]


@dataclass
class Coletores:
    portal: Coletor
    api: Coletor | None  # plano B; None = desabilitado


def coletores_padrao(s: Settings) -> Coletores:
    portal = PortalBCB(
        s.bcb_portal_url, s.rpa_headless, s.rpa_timeout_ms, s.screenshot_dir, url_catalogo=s.bcb_dados_abertos_url or None
    )
    api = OlindaAPI(s.bcb_odata_url) if s.rpa_fallback_api else None
    return Coletores(portal.consultar, api.consultar if api else None)


def validar_parametros(data_base: str, segmento: str, uf: str | None) -> tuple[str, str, str | None]:
    data_base = (data_base or "").strip()
    if not re.fullmatch(r"\d{6}", data_base) or not 1 <= int(data_base[4:]) <= 12:
        raise EntradaInvalida("Data-base deve estar no formato AAAAMM (ex.: 202606).")
    if data_base > datetime.now(UTC).strftime("%Y%m"):
        raise EntradaInvalida("Data-base no futuro.")
    segmento = (segmento or "").strip().upper()
    if segmento not in SEGMENTOS:
        raise EntradaInvalida(f"Segmento inválido. Opções: {', '.join(SEGMENTOS)}.")
    uf = (uf or "").strip().upper() or None
    if uf and uf not in UFS:
        raise EntradaInvalida(f"UF inválida: {uf}.")
    return data_base, segmento, uf


def executar_consulta(
    db: Session,
    s: Settings,
    coletores: Coletores,
    data_base: str,
    segmento: str,
    uf: str | None = None,
    forcar: bool = False,
) -> tuple[Execucao, bool]:
    """Retorna (execução, reaproveitada). Dados do BCB de uma data-base passada
    não mudam, então uma consulta idêntica já concluída é reaproveitada em vez
    de processada de novo — a menos que `forcar=True`."""
    data_base, segmento, uf = validar_parametros(data_base, segmento, uf)
    chave = f"{data_base}|{segmento}|{uf or '-'}"

    if not forcar:
        anterior = db.scalars(
            select(Execucao)
            .where(Execucao.chave == chave, Execucao.status == StatusExecucao.SUCESSO)
            .order_by(Execucao.id.desc())
        ).first()
        if anterior:
            log.info("Consulta %s já processada (execução #%s) — reaproveitando.", chave, anterior.id)
            return anterior, True

    execucao = Execucao(chave=chave, data_base=data_base, segmento=segmento, uf=uf, status=StatusExecucao.EM_EXECUCAO)
    db.add(execucao)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ProcessamentoDuplicado(f"Já existe uma execução em andamento para esta consulta ({chave}).")

    log.info("Execução #%s iniciada: %s", execucao.id, chave)
    try:
        data_bases = [data_base, trimestre_anterior(data_base)]
        resultados, fonte = _coletar(execucao, s, coletores, data_bases)
        execucao.fonte = fonte
        registros = resultados.get(data_base) or []
        execucao.registros_brutos = registros

        if not registros:
            execucao.status = StatusExecucao.SEM_RESULTADO
            execucao.erro = (
                f"Nenhum dado publicado para {referencia(data_base)}. "
                "O BCB publica o panorama trimestralmente (mar, jun, set, dez), com defasagem de alguns meses."
            )
        else:
            dados, avisos = estruturar(data_base, segmento, uf, registros, resultados.get(data_bases[1]))
            execucao.dados, execucao.avisos = dados, avisos
            execucao.status = StatusExecucao.SUCESSO
    except AppError as e:
        execucao.status, execucao.erro = StatusExecucao.ERRO, e.mensagem
        log.error("Execução #%s falhou: %s", execucao.id, e.mensagem)
    except Exception as e:  # noqa: BLE001 — nenhuma execução pode ficar presa em EM_EXECUCAO
        execucao.status, execucao.erro = StatusExecucao.ERRO, f"Erro inesperado: {type(e).__name__}: {e}"
        log.exception("Execução #%s falhou com erro inesperado", execucao.id)
    finally:
        execucao.finalizado_em = datetime.now(UTC)
        db.commit()

    log.info("Execução #%s finalizada: %s (fonte=%s, tentativas=%s)", execucao.id, execucao.status, execucao.fonte, execucao.tentativas)
    return execucao, False


def _coletar(execucao: Execucao, s: Settings, coletores: Coletores, data_bases: list[str]) -> tuple[dict, str]:
    retentar = Retrying(
        stop=stop_after_attempt(s.rpa_max_tentativas),
        wait=wait_exponential(multiplier=2, min=2, max=15),
        retry=retry_if_exception_type((FonteIndisponivel, FalhaNavegacao)),
        reraise=True,
        before_sleep=lambda rs: log.warning(
            "Tentativa %s falhou (%s) — tentando novamente.", rs.attempt_number, rs.outcome.exception()
        ),
    )
    try:
        for tentativa in retentar:
            with tentativa:
                execucao.tentativas = tentativa.retry_state.attempt_number
                return coletores.portal(data_bases), "portal"
    except (FonteIndisponivel, FalhaNavegacao) as erro_portal:
        if not coletores.api:
            raise
        log.warning("Portal falhou após %s tentativas (%s). Usando API OData como plano B.", execucao.tentativas, erro_portal)
        return coletores.api(data_bases), "api_fallback"
    raise AssertionError("inalcançável")


def obter_execucao(db: Session, execucao_id: int) -> Execucao:
    execucao = db.get(Execucao, execucao_id)
    if not execucao:
        raise NaoEncontrado(f"Execução #{execucao_id} não encontrada.")
    return execucao


def marcar_execucoes_orfas(db: Session) -> int:
    """Na subida da aplicação: execuções que ficaram EM_EXECUCAO (processo
    derrubado no meio) são marcadas como erro para liberar a trava."""
    orfas = db.scalars(select(Execucao).where(Execucao.status == StatusExecucao.EM_EXECUCAO)).all()
    for e in orfas:
        e.status, e.erro, e.finalizado_em = StatusExecucao.ERRO, "Interrompida (aplicação reiniciada durante a execução).", datetime.now(UTC)
    db.commit()
    return len(orfas)