"""Rotas HTTP. Só traduzem HTTP ↔ serviços; a regra de negócio fica em app/services.

Rotas síncronas (def) de propósito: o FastAPI as executa em thread pool,
então o navegador do Playwright (API síncrona) não bloqueia o event loop."""
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.database import get_db
from app.models import Execucao, Mensagem
from app.schemas import ConsultaIn, ExecucaoResultado, HistoricoItem, HistoricoMetricasIn, MensagemIn, MensagemOut, Opcoes
from app.services import consultas, dashboard, envios
from app.services.tratamento import SEGMENTOS, UFS
from app.whatsapp.providers import criar_provedor

router = APIRouter(prefix="/api")


def get_coletores(s: Settings = Depends(get_settings)) -> consultas.Coletores:
    return consultas.coletores_padrao(s)


@router.get("/opcoes", response_model=Opcoes)
def opcoes(s: Settings = Depends(get_settings)):
    hoje = datetime.now(UTC)
    trimestres = []
    ano, mes = hoje.year, hoje.month - (hoje.month % 3)
    for _ in range(12):
        if mes == 0:
            ano, mes = ano - 1, 12
        trimestres.append(f"{ano}{mes:02d}")
        mes -= 3
    return Opcoes(segmentos=SEGMENTOS, ufs=sorted(UFS), data_bases_sugeridas=trimestres, whatsapp_provider=s.whatsapp_provider)


@router.post("/consultas", response_model=ExecucaoResultado)
def executar_consulta(
    body: ConsultaIn,
    tarefas: BackgroundTasks,
    db: Session = Depends(get_db),
    s: Settings = Depends(get_settings),
    coletores: consultas.Coletores = Depends(get_coletores),
):
    if body.em_segundo_plano:
        # Responde já com a execução EM_EXECUCAO; o robô roda depois da resposta
        # e grava cada etapa, que o frontend acompanha por GET /api/consultas/{id}.
        execucao, reaproveitada = consultas.iniciar_consulta(db, body.data_base, body.segmento, body.uf, body.forcar)
        if not reaproveitada:
            tarefas.add_task(consultas.processar_em_segundo_plano, execucao.id, s, coletores)
    else:
        execucao, reaproveitada = consultas.executar_consulta(db, s, coletores, body.data_base, body.segmento, body.uf, body.forcar)
    return ExecucaoResultado.model_validate(execucao).model_copy(update={"reaproveitada": reaproveitada})


@router.get("/consultas/{execucao_id}", response_model=ExecucaoResultado)
def obter_consulta(execucao_id: int, db: Session = Depends(get_db)):
    return consultas.obter_execucao(db, execucao_id)


@router.get("/consultas/{execucao_id}/bruto")
def registros_brutos(execucao_id: int, db: Session = Depends(get_db)):
    """Registros exatamente como vieram do BCB — rastreabilidade/auditoria."""
    return consultas.obter_execucao(db, execucao_id).registros_brutos or []


@router.post("/mensagens", response_model=MensagemOut)
def gerar_mensagem(body: MensagemIn, db: Session = Depends(get_db)):
    return envios.criar_mensagem(db, body.execucao_id, body.destinatario_nome, body.destinatario_numero)


@router.post("/mensagens/{mensagem_id}/enviar", response_model=MensagemOut)
def enviar_mensagem(mensagem_id: int, db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    return envios.enviar_mensagem(db, mensagem_id, criar_provedor(s))


@router.get("/historico", response_model=list[HistoricoItem])
def historico(
    status: str | None = Query(default=None),
    limite: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    q = select(Execucao).options(selectinload(Execucao.mensagens)).order_by(Execucao.id.desc()).limit(limite)
    if status:
        q = q.where(Execucao.status == status.upper())
    return db.scalars(q).all()


@router.get("/mensagens", response_model=list[MensagemOut])
def listar_mensagens(limite: int = Query(default=50, le=200), db: Session = Depends(get_db)):
    return db.scalars(select(Mensagem).order_by(Mensagem.id.desc()).limit(limite)).all()


@router.get("/dashboard")
def obter_dashboard(
    segmento: str = Query(default="TOTAL"),
    uf: str | None = Query(default=None),
    data_base: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return dashboard.montar_dashboard(db, segmento, uf, data_base)


@router.post("/dashboard/historico")
def carregar_historico(
    body: HistoricoMetricasIn,
    db: Session = Depends(get_db),
    s: Settings = Depends(get_settings),
    coletores: consultas.Coletores = Depends(get_coletores),
):
    """Executa o robô para vários trimestres de uma vez e grava a série histórica."""
    return dashboard.carregar_historico(db, s, coletores, body.trimestres)