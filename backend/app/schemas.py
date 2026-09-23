from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConsultaIn(BaseModel):
    data_base: str = Field(examples=["202606"], description="AAAAMM — o BCB publica em mar, jun, set e dez")
    segmento: str = Field(default="TOTAL", examples=["IMOVEIS"])
    uf: str | None = Field(default=None, examples=["SP"])
    forcar: bool = Field(default=False, description="Reprocessa mesmo se a consulta já foi feita")


class MensagemIn(BaseModel):
    execucao_id: int
    destinatario_nome: str = Field(min_length=1, max_length=120)
    destinatario_numero: str = Field(examples=["(11) 99999-8888"])


class MensagemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    execucao_id: int
    destinatario_nome: str
    destinatario_numero: str
    texto: str
    status: str
    provedor: str | None
    provedor_message_id: str | None
    erro: str | None
    criado_em: datetime
    enviado_em: datetime | None


class ExecucaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    data_base: str
    segmento: str
    uf: str | None
    status: str
    fonte: str | None
    tentativas: int
    dados: dict | None
    avisos: list[str] | None
    erro: str | None
    iniciado_em: datetime
    finalizado_em: datetime | None


class ExecucaoResultado(ExecucaoOut):
    reaproveitada: bool = False


class HistoricoItem(ExecucaoOut):
    mensagens: list[MensagemOut]


class Opcoes(BaseModel):
    segmentos: dict[str, str]
    ufs: list[str]
    data_bases_sugeridas: list[str]
    whatsapp_provider: str
