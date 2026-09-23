"""Orquestra uma execução do RPA: validação → trava de duplicidade →
coleta (com retentativas e plano B) → tratamento → persistência.

A execução tem duas fases:
- `iniciar_consulta`: valida, aplica as regras de duplicidade e cria o registro
  EM_EXECUCAO (rápido — a API responde na hora);
- `processar_execucao`: roda o robô e trata os dados, gravando cada etapa em
  `execucao.etapas` para o frontend acompanhar o progresso.

`executar_consulta` faz as duas em sequência (modo síncrono) e
`processar_em_segundo_plano` roda a segunda numa sessão própria, fora da requisição.
"""
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
from app.database import SessionLocal
from app.exceptions import AppError, EntradaInvalida, FalhaNavegacao, FonteIndisponivel, NaoEncontrado, ProcessamentoDuplicado
from app.models import Execucao, StatusExecucao
from app.progresso import ouvir, reportar
from app.rpa.bcb_portal import PortalBCB
from app.rpa.olinda_api import OlindaAPI
from app.services.serie import salvar_serie
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


def iniciar_consulta(
    db: Session, data_base: str, segmento: str, uf: str | None = None, forcar: bool = False
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
    execucao.etapas = [_etapa("Consulta registrada; aguardando o robô")]
    db.add(execucao)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ProcessamentoDuplicado(f"Já existe uma execução em andamento para esta consulta ({chave}).")
    log.info("Execução #%s iniciada: %s", execucao.id, chave)
    return execucao, False


def processar_execucao(db: Session, s: Settings, coletores: Coletores, execucao: Execucao) -> Execucao:
    def registrar(texto: str) -> None:
        # Nova lista (e não .append) para o SQLAlchemy perceber a mudança no JSON.
        execucao.etapas = [*(execucao.etapas or []), _etapa(texto)]
        db.commit()

    try:
        with ouvir(registrar):
            data_bases = [execucao.data_base, trimestre_anterior(execucao.data_base)]
            resultados, fonte = _coletar(execucao, s, coletores, data_bases)
            execucao.fonte = fonte
            registros = resultados.get(execucao.data_base) or []
            execucao.registros_brutos = registros

            if not registros:
                execucao.status = StatusExecucao.SEM_RESULTADO
                execucao.erro = (
                    f"Nenhum dado publicado para {referencia(execucao.data_base)}. "
                    "O BCB publica o panorama trimestralmente (mar, jun, set, dez), com defasagem de alguns meses."
                )
                reportar("Consulta concluída sem resultado")
            else:
                reportar("Validando, corrigindo unidades e estruturando os dados")
                dados, avisos = estruturar(execucao.data_base, execucao.segmento, execucao.uf, registros, resultados.get(data_bases[1]))
                execucao.dados, execucao.avisos = dados, avisos
                execucao.status = StatusExecucao.SUCESSO
                _alimentar_serie(db, resultados)
                reportar("Concluído")
    except AppError as e:
        execucao.status, execucao.erro = StatusExecucao.ERRO, e.mensagem
        execucao.etapas = [*(execucao.etapas or []), _etapa(f"Falhou: {e.mensagem}")]
        log.error("Execução #%s falhou: %s", execucao.id, e.mensagem)
    except Exception as e:  # noqa: BLE001 — nenhuma execução pode ficar presa em EM_EXECUCAO
        db.rollback()
        execucao.status, execucao.erro = StatusExecucao.ERRO, f"Erro inesperado: {type(e).__name__}: {e}"
        execucao.etapas = [*(execucao.etapas or []), _etapa("Falhou: erro inesperado (detalhes no log)")]
        log.exception("Execução #%s falhou com erro inesperado", execucao.id)
    finally:
        execucao.finalizado_em = datetime.now(UTC)
        db.commit()

    log.info("Execução #%s finalizada: %s (fonte=%s, tentativas=%s)", execucao.id, execucao.status, execucao.fonte, execucao.tentativas)
    return execucao


def executar_consulta(
    db: Session,
    s: Settings,
    coletores: Coletores,
    data_base: str,
    segmento: str,
    uf: str | None = None,
    forcar: bool = False,
) -> tuple[Execucao, bool]:
    """Modo síncrono: inicia e processa na mesma chamada."""
    execucao, reaproveitada = iniciar_consulta(db, data_base, segmento, uf, forcar)
    if reaproveitada:
        return execucao, True
    return processar_execucao(db, s, coletores, execucao), False


def processar_em_segundo_plano(execucao_id: int, s: Settings, coletores: Coletores) -> None:
    """Roda fora da requisição HTTP, com sessão de banco própria."""
    with SessionLocal() as db:
        execucao = db.get(Execucao, execucao_id)
        if execucao is None or execucao.status != StatusExecucao.EM_EXECUCAO:
            return
        processar_execucao(db, s, coletores, execucao)


def _etapa(texto: str) -> dict:
    return {"texto": texto, "em": datetime.now(UTC).isoformat()}


def _alimentar_serie(db: Session, resultados: dict[str, list[dict]]) -> None:
    """Aproveita os trimestres já coletados para o histórico do dashboard.
    Falhar aqui não pode derrubar a consulta, que já foi concluída."""
    try:
        for data_base, registros in resultados.items():
            if registros:
                salvar_serie(db, data_base, registros)
    except Exception:  # noqa: BLE001
        db.rollback()
        log.exception("Não foi possível atualizar a série histórica")


def _coletar(execucao: Execucao, s: Settings, coletores: Coletores, data_bases: list[str]) -> tuple[dict, str]:
    def antes_de_esperar(rs) -> None:
        log.warning("Tentativa %s falhou (%s) — tentando novamente.", rs.attempt_number, rs.outcome.exception())
        reportar(f"Tentativa {rs.attempt_number} falhou ({rs.outcome.exception()}); tentando de novo em instantes")

    retentar = Retrying(
        stop=stop_after_attempt(s.rpa_max_tentativas),
        wait=wait_exponential(multiplier=2, min=2, max=15),
        retry=retry_if_exception_type((FonteIndisponivel, FalhaNavegacao)),
        reraise=True,
        before_sleep=antes_de_esperar,
    )
    try:
        for tentativa in retentar:
            with tentativa:
                execucao.tentativas = tentativa.retry_state.attempt_number
                reportar(f"Iniciando o robô (tentativa {execucao.tentativas} de {s.rpa_max_tentativas})")
                return coletores.portal(data_bases), "portal"
    except (FonteIndisponivel, FalhaNavegacao) as erro_portal:
        if not coletores.api:
            raise
        log.warning("Portal falhou após %s tentativas (%s). Usando API OData como plano B.", execucao.tentativas, erro_portal)
        reportar("Portal indisponível após as tentativas — consultando a API OData do BCB (plano B)")
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