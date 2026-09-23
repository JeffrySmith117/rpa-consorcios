"""Modelos persistidos. O histórico exigido pelo desafio é a junção de
`Execucao` (consulta + dados encontrados) com `Mensagem` (destinatário,
texto, status do envio)."""
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def agora() -> datetime:
    return datetime.now(UTC)


class StatusExecucao(StrEnum):
    EM_EXECUCAO = "EM_EXECUCAO"
    SUCESSO = "SUCESSO"
    SEM_RESULTADO = "SEM_RESULTADO"
    ERRO = "ERRO"


class StatusMensagem(StrEnum):
    GERADA = "GERADA"
    ENVIANDO = "ENVIANDO"
    ENVIADA = "ENVIADA"
    ERRO = "ERRO"


class Execucao(Base):
    __tablename__ = "execucoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Identifica a consulta de forma única: "AAAAMM|SEGMENTO|UF".
    chave: Mapped[str] = mapped_column(String(64), index=True)
    data_base: Mapped[str] = mapped_column(String(6))
    segmento: Mapped[str] = mapped_column(String(32))
    uf: Mapped[str | None] = mapped_column(String(2))

    status: Mapped[str] = mapped_column(String(20), default=StatusExecucao.EM_EXECUCAO)
    fonte: Mapped[str | None] = mapped_column(String(20))  # "portal" | "api_fallback"
    tentativas: Mapped[int] = mapped_column(Integer, default=0)

    dados: Mapped[dict | None] = mapped_column(JSON)  # informações tratadas
    registros_brutos: Mapped[list | None] = mapped_column(JSON)  # como vieram da fonte
    avisos: Mapped[list | None] = mapped_column(JSON)  # dados incompletos, etc.
    erro: Mapped[str | None] = mapped_column(Text)

    iniciado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    finalizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    mensagens: Mapped[list["Mensagem"]] = relationship(back_populates="execucao", order_by="Mensagem.id")

    __table_args__ = (
        # Trava de concorrência: só pode existir UMA execução em andamento por chave.
        # Duas requisições simultâneas → a segunda recebe IntegrityError → HTTP 409.
        Index(
            "uq_execucao_em_andamento",
            "chave",
            unique=True,
            sqlite_where=text("status = 'EM_EXECUCAO'"),
            postgresql_where=text("status = 'EM_EXECUCAO'"),
        ),
    )


class Mensagem(Base):
    __tablename__ = "mensagens"

    id: Mapped[int] = mapped_column(primary_key=True)
    execucao_id: Mapped[int] = mapped_column(ForeignKey("execucoes.id"), index=True)

    destinatario_nome: Mapped[str] = mapped_column(String(120))
    destinatario_numero: Mapped[str] = mapped_column(String(20))  # E.164 sem "+", ex.: 5511999998888
    texto: Mapped[str] = mapped_column(Text)
    # sha256(numero + texto): mesma mensagem para o mesmo número = duplicata.
    chave_idempotencia: Mapped[str] = mapped_column(String(64), index=True)

    status: Mapped[str] = mapped_column(String(20), default=StatusMensagem.GERADA)
    provedor: Mapped[str | None] = mapped_column(String(20))
    provedor_message_id: Mapped[str | None] = mapped_column(String(128))
    erro: Mapped[str | None] = mapped_column(Text)

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    execucao: Mapped[Execucao] = relationship(back_populates="mensagens")

    __table_args__ = (
        # Garante no banco que a mesma mensagem não é enviada (nem está sendo
        # enviada) duas vezes para o mesmo número. Envios com ERRO podem ser refeitos.
        Index(
            "uq_mensagem_enviada",
            "chave_idempotencia",
            unique=True,
            sqlite_where=text("status IN ('ENVIANDO', 'ENVIADA')"),
            postgresql_where=text("status IN ('ENVIANDO', 'ENVIADA')"),
        ),
    )
