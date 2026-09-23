"""Dados do dashboard.

- `carregar_historico`: manda o robô buscar vários trimestres de uma vez, na
  mesma sessão do navegador, para popular os gráficos de evolução.
- `montar_dashboard`: agrega a série no formato que o frontend desenha.
"""
from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.exceptions import EntradaInvalida, ProcessamentoDuplicado
from app.models import MetricaSerie
from app.services import consultas
from app.services.serie import salvar_serie
from app.services.tratamento import (
    INDICADORES,
    INDICADORES_SISTEMA,
    RE_UF,
    SEGMENTOS,
    UFS,
    _variacao,
    referencia,
    trimestre_anterior,
)

log = logging.getLogger(__name__)

# Cotas ativas por segmento (composição do mercado).
COMPOSICAO = [
    ("IMOVEIS", "Imóveis", "11"),
    ("AUTOMOVEIS", "Automóveis", "13"),
    ("MOTOCICLETAS", "Motocicletas", "14"),
    ("PESADOS", "Veículos pesados", "12"),
    ("OUTROS", "Outros bens móveis", "15"),
    ("SERVICOS", "Serviços", "16"),
]

# Contemplações nos últimos 12 meses: (segmento, nome, id sorteio, id lance).
CONTEMPLACOES = [
    ("IMOVEIS", "Imóveis", "32", "33"),
    ("AUTOMOVEIS", "Automóveis", "35", "36"),
    ("MOTOCICLETAS", "Motocicletas", "38", "39"),
    ("OUTROS", "Outros bens e serviços", "41", "42"),
]

MIN_TRIMESTRES, MAX_TRIMESTRES = 4, 40  # o BCB publica o panorama desde dez/2015
PONTOS_MINIGRAFICO = 8

# Só um carregamento de histórico por vez (o robô abre um navegador inteiro).
_trava_historico = threading.Lock()


# --- carregamento ---------------------------------------------------------

def trimestres_recentes(quantidade: int, hoje: datetime | None = None) -> list[str]:
    """Fins de trimestre (mar/jun/set/dez) até hoje, do mais recente para o mais antigo."""
    hoje = hoje or datetime.now(UTC)
    ano, mes = hoje.year, hoje.month - (hoje.month % 3)
    if mes == 0:
        ano, mes = ano - 1, 12
    lista = []
    for _ in range(quantidade):
        lista.append(f"{ano}{mes:02d}")
        mes -= 3
        if mes <= 0:
            ano, mes = ano - 1, mes + 12
    return lista


def carregar_historico(db: Session, s: Settings, coletores: consultas.Coletores, trimestres: int) -> dict:
    if not MIN_TRIMESTRES <= trimestres <= MAX_TRIMESTRES:
        raise EntradaInvalida(f"Informe entre {MIN_TRIMESTRES} e {MAX_TRIMESTRES} trimestres.")
    if not _trava_historico.acquire(blocking=False):
        raise ProcessamentoDuplicado("Já existe um carregamento de histórico em andamento.")
    try:
        # +3: os trimestres mais recentes costumam ainda não estar publicados.
        candidatos = trimestres_recentes(trimestres + 3)
        existentes = set(db.scalars(select(MetricaSerie.data_base).distinct()))
        buscar = [d for d in candidatos if d not in existentes]
        log.info("Carregando histórico: %s trimestre(s) a buscar, %s já na base.", len(buscar), len(existentes & set(candidatos)))

        controle = SimpleNamespace(tentativas=0)
        resultados, fonte = consultas._coletar(controle, s, coletores, buscar) if buscar else ({}, None)

        # Guarda exatamente os `trimestres` publicados mais recentes.
        publicados = [d for d in candidatos if d in existentes or resultados.get(d)]
        alvo = set(publicados[:trimestres])
        carregados = [d for d in buscar if d in alvo and salvar_serie(db, d, resultados[d])]
        sem_dados = [d for d in buscar if not resultados.get(d)]
        log.info("Histórico carregado: %s novos, %s sem publicação.", len(carregados), len(sem_dados))
        return {
            "carregados": sorted(carregados),
            "ja_existentes": sorted(existentes & set(candidatos)),
            "sem_dados": sorted(sem_dados),
            "fonte": fonte,
            "tentativas": controle.tentativas,
        }
    finally:
        _trava_historico.release()


# --- leitura ---------------------------------------------------------------

def montar_dashboard(db: Session, segmento: str = "TOTAL", uf: str | None = None, data_base: str | None = None) -> dict:
    segmento = (segmento or "TOTAL").upper()
    if segmento not in SEGMENTOS:
        raise EntradaInvalida(f"Segmento inválido. Opções: {', '.join(SEGMENTOS)}.")
    uf = (uf or "").upper() or None
    if uf and uf not in UFS:
        raise EntradaInvalida(f"UF inválida: {uf}.")

    valores: dict[str, dict[str, float]] = {}
    unidades: dict[str, str] = {}
    nomes: dict[str, str] = {}
    for linha in db.scalars(select(MetricaSerie)):
        valores.setdefault(linha.data_base, {})[linha.id_metrica] = linha.valor
        unidades[linha.id_metrica] = linha.unidade
        nomes[linha.id_metrica] = linha.nome

    disponiveis = sorted(valores)
    base = {
        "segmento": segmento,
        "segmento_nome": SEGMENTOS[segmento],
        "uf": uf,
        "trimestres_disponiveis": disponiveis,
    }
    if not disponiveis:
        return {**base, "data_base": None, "referencia": None, "kpis": [], "serie": [], "composicao": [], "ufs": [], "contemplacoes": []}

    ref = data_base if data_base in valores else disponiveis[-1]
    atual = valores[ref]
    anterior = valores.get(trimestre_anterior(ref), {})
    ate_ref = [d for d in disponiveis if d <= ref]

    def id_do(indicador: str) -> str | None:
        return INDICADORES[indicador][1].get(segmento)

    ids_uf = {m.group(1).upper(): mid for mid, nome in nomes.items() if (m := RE_UF.search(nome))}

    def kpi(chave: str, nome: str, mid: str | None) -> dict | None:
        if not mid or mid not in atual:
            return None
        unidade = unidades[mid]
        return {
            "chave": chave,
            "nome": nome,
            "valor": atual[mid],
            "unidade": unidade,
            "variacao": _variacao(atual[mid], anterior.get(mid), unidade),
            "minigrafico": [
                {"data_base": d, "valor": valores[d][mid]} for d in ate_ref[-PONTOS_MINIGRAFICO:] if mid in valores[d]
            ],
        }

    kpis = [
        kpi("cotas_ativas", "Cotas ativas", id_do("cotas_ativas")),
        kpi("carteira", "Carteira", id_do("carteira")),
        kpi("cotas_comercializadas", "Cotas vendidas (12 meses)", id_do("cotas_comercializadas")),
        kpi("inadimplencia", "Inadimplência (sistema)", INDICADORES_SISTEMA["inadimplencia"][1]),
    ]
    if uf:
        kpis.append(kpi("uf", f"Cotas ativas em {uf}", ids_uf.get(uf)))

    serie = []
    for d in disponiveis:
        v = valores[d]
        serie.append({
            "data_base": d,
            "referencia": referencia(d),
            "cotas_ativas": v.get(id_do("cotas_ativas") or ""),
            "carteira": v.get(id_do("carteira") or ""),
            "inadimplencia": v.get(INDICADORES_SISTEMA["inadimplencia"][1]),
            "pre_inadimplencia": v.get(INDICADORES_SISTEMA["pre_inadimplencia"][1]),
        })

    composicao = sorted(
        ({"segmento": k, "nome": n, "valor": atual[mid], "selecionado": k == segmento} for k, n, mid in COMPOSICAO if mid in atual),
        key=lambda c: c["valor"],
        reverse=True,
    )
    total_ufs = sum(atual[mid] for mid in ids_uf.values() if mid in atual) or None
    ufs = sorted(
        (
            {
                "uf": sigla,
                "valor": atual[mid],
                "participacao_pct": round(atual[mid] / total_ufs * 100, 2) if total_ufs else None,
                "selecionada": sigla == uf,
            }
            for sigla, mid in ids_uf.items()
            if mid in atual
        ),
        key=lambda u: u["valor"],
        reverse=True,
    )
    contemplacoes = [
        {"segmento": k, "nome": n, "sorteio": atual[s_id], "lance": atual[l_id], "selecionado": k == segmento}
        for k, n, s_id, l_id in CONTEMPLACOES
        if s_id in atual and l_id in atual
    ]

    return {
        **base,
        "data_base": ref,
        "referencia": referencia(ref),
        "kpis": [k for k in kpis if k],
        "serie": serie,
        "composicao": composicao,
        "ufs": ufs,
        "contemplacoes": contemplacoes,
    }