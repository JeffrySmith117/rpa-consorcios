"""Geração e envio de mensagens, com controle de envio duplicado."""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import AppError, EntradaInvalida, EnvioDuplicado, NaoEncontrado
from app.models import Execucao, Mensagem, StatusExecucao, StatusMensagem
from app.services.mensagem import gerar_mensagem
from app.whatsapp.providers import ProvedorWhatsApp

log = logging.getLogger(__name__)


def normalizar_numero(numero: str) -> str:
    """Aceita '(11) 99999-8888', '+55 11 99999-8888'... e devolve '5511999998888'."""
    digitos = re.sub(r"\D", "", numero or "")
    if len(digitos) in (10, 11):  # DDD + número, sem DDI → assume Brasil
        digitos = "55" + digitos
    if not 12 <= len(digitos) <= 15:
        raise EntradaInvalida("Número de WhatsApp inválido. Use DDD + número, ex.: (11) 99999-8888.")
    return digitos


def mascarar(numero: str) -> str:
    """Para logs: 5511999998888 → 55119****8888 (evita dado pessoal completo no log)."""
    return numero[:5] + "*" * (len(numero) - 9) + numero[-4:] if len(numero) > 9 else "****"


def chave_idempotencia(numero: str, texto: str) -> str:
    return hashlib.sha256(f"{numero}\n{texto}".encode()).hexdigest()


def criar_mensagem(db: Session, execucao_id: int, nome: str, numero: str) -> Mensagem:
    execucao = db.get(Execucao, execucao_id)
    if not execucao:
        raise NaoEncontrado(f"Execução #{execucao_id} não encontrada.")
    if execucao.status != StatusExecucao.SUCESSO or not execucao.dados:
        raise EntradaInvalida("Só é possível gerar mensagem a partir de uma execução concluída com sucesso.")
    nome = (nome or "").strip()
    if not nome:
        raise EntradaInvalida("Informe o nome do destinatário.")
    numero = normalizar_numero(numero)

    texto = gerar_mensagem(nome, execucao.dados)
    chave = chave_idempotencia(numero, texto)

    # Gerar de novo a mesma mensagem (duplo clique, recarregar a página) devolve
    # a existente em vez de criar outra linha no histórico.
    existente = db.scalars(
        select(Mensagem)
        .where(Mensagem.chave_idempotencia == chave, Mensagem.status != StatusMensagem.ERRO)
        .order_by(Mensagem.id.desc())
    ).first()
    if existente:
        return existente

    msg = Mensagem(
        execucao_id=execucao.id,
        destinatario_nome=nome,
        destinatario_numero=numero,
        texto=texto,
        chave_idempotencia=chave,
        status=StatusMensagem.GERADA,
    )
    db.add(msg)
    db.commit()
    log.info("Mensagem #%s gerada para %s (execução #%s)", msg.id, mascarar(numero), execucao.id)
    return msg


def enviar_mensagem(db: Session, mensagem_id: int, provedor: ProvedorWhatsApp) -> Mensagem:
    msg = db.get(Mensagem, mensagem_id)
    if not msg:
        raise NaoEncontrado(f"Mensagem #{mensagem_id} não encontrada.")
    if msg.status == StatusMensagem.ENVIADA:
        raise EnvioDuplicado(f"Mensagem #{msg.id} já foi enviada em {msg.enviado_em:%d/%m/%Y %H:%M} UTC.")
    if msg.status == StatusMensagem.ENVIANDO:
        raise EnvioDuplicado(f"Mensagem #{msg.id} já está sendo enviada.")

    # Reserva o envio ANTES de chamar o provedor. O índice único parcial
    # (chave_idempotencia com status ENVIANDO/ENVIADA) impede que duas
    # requisições — ou duas mensagens idênticas — passem daqui ao mesmo tempo.
    msg.status, msg.erro = StatusMensagem.ENVIANDO, None
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise EnvioDuplicado("Esta mesma mensagem já foi enviada (ou está sendo enviada) para este número.")

    try:
        resultado = provedor.enviar(msg.destinatario_numero, msg.texto)
        msg.status = StatusMensagem.ENVIADA
        msg.provedor, msg.provedor_message_id = resultado.provedor, resultado.message_id
        msg.enviado_em = datetime.now(UTC)
        log.info("Mensagem #%s enviada via %s (id=%s)", msg.id, resultado.provedor, resultado.message_id)
    except AppError as e:
        msg.status, msg.erro, msg.provedor = StatusMensagem.ERRO, e.mensagem, provedor.nome
        log.error("Falha ao enviar mensagem #%s: %s", msg.id, e.mensagem)
    except Exception as e:  # noqa: BLE001 — não deixar a mensagem presa em ENVIANDO
        msg.status, msg.erro, msg.provedor = StatusMensagem.ERRO, f"Erro inesperado: {type(e).__name__}: {e}", provedor.nome
        log.exception("Falha inesperada ao enviar mensagem #%s", msg.id)
    finally:
        db.commit()
    return msg
