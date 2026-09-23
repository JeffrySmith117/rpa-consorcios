"""Transforma os registros brutos do BCB (uma linha por métrica) em
informação estruturada para um segmento de consórcio.

Etapas:
1. validação  — descarta linhas sem id/valor numérico, registra aviso
2. correção   — confere total × soma das partes e corrige unidades trocadas
3. normalização — converte "mil", "R$ bilhões"... para valores absolutos
4. seleção    — monta os indicadores do segmento pedido (+ UF, se houver)
5. comparação — variação contra o trimestre anterior, quando disponível
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

SEGMENTOS = {
    "TOTAL": "Todos os segmentos",
    "IMOVEIS": "Imóveis",
    "AUTOMOVEIS": "Automóveis",
    "MOTOCICLETAS": "Motocicletas",
    "PESADOS": "Veículos pesados",
}

UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}

# Indicador → {segmento: IdMetrica}. Nem todo indicador existe para todo
# segmento na fonte (ex.: carteira de pesados); nesse caso ele é omitido.
INDICADORES: dict[str, tuple[str, dict[str, str]]] = {
    "cotas_ativas": ("Cotas ativas", {"TOTAL": "10", "IMOVEIS": "11", "PESADOS": "12", "AUTOMOVEIS": "13", "MOTOCICLETAS": "14"}),
    "cotas_comercializadas": ("Cotas vendidas (12 meses)", {"TOTAL": "54", "IMOVEIS": "55", "PESADOS": "56", "AUTOMOVEIS": "57", "MOTOCICLETAS": "58"}),
    "contempladas": ("Cotas contempladas (12 meses)", {"TOTAL": "28", "IMOVEIS": "31", "AUTOMOVEIS": "34", "MOTOCICLETAS": "37"}),
    "carteira": ("Carteira", {"TOTAL": "22", "IMOVEIS": "23", "AUTOMOVEIS": "24", "MOTOCICLETAS": "25"}),
    "recursos_a_coletar": ("Recursos a coletar", {"TOTAL": "68", "IMOVEIS": "69", "AUTOMOVEIS": "70", "MOTOCICLETAS": "71"}),
    "indice_exclusao": ("Índice de exclusão", {"TOTAL": "49", "IMOVEIS": "50", "AUTOMOVEIS": "51", "MOTOCICLETAS": "52"}),
    "taxa_adm_media": ("Taxa média de administração", {"TOTAL": "78", "IMOVEIS": "79", "PESADOS": "80", "AUTOMOVEIS": "81", "MOTOCICLETAS": "82"}),
    "valor_medio_credito": ("Valor médio do crédito", {"TOTAL": "85", "IMOVEIS": "86", "PESADOS": "87", "AUTOMOVEIS": "88", "MOTOCICLETAS": "89"}),
    "prazo_medio": ("Prazo médio dos grupos", {"TOTAL": "92", "IMOVEIS": "93", "PESADOS": "94", "AUTOMOVEIS": "95", "MOTOCICLETAS": "96"}),
    "administradoras": ("Administradoras atuando", {"TOTAL": "2", "IMOVEIS": "5", "PESADOS": "6", "AUTOMOVEIS": "7", "MOTOCICLETAS": "8"}),
}

# Só existem para o sistema como um todo.
INDICADORES_SISTEMA: dict[str, tuple[str, str]] = {
    "inadimplencia": ("Inadimplência (sistema)", "61"),
    "pre_inadimplencia": ("Pré-inadimplência (sistema)", "62"),
}

# Totais que devem ser iguais à soma das partes — usados para detectar
# unidades informadas errado na fonte.
CHECAGENS_TOTAL: list[tuple[str, list[str]]] = [
    ("28", ["31", "34", "37", "40"]),  # contempladas
    ("68", ["69", "70", "71", "72"]),  # recursos a coletar
    ("63", ["64", "65", "66", "67"]),  # recursos coletados
]

FATORES = {
    "unidade": (1, "un"),
    "mil": (1e3, "un"),
    "r$ mil": (1e3, "R$"),
    "r$ milhões": (1e6, "R$"),
    "r$ bilhões": (1e9, "R$"),
    "%": (1, "%"),
    "meses": (1, "meses"),
}

RE_UF = re.compile(r"Cotas Ativas por Estado - ([A-Z]{2})\s*$", re.IGNORECASE)


@dataclass
class Metrica:
    id: str
    nome: str
    valor_bruto: float
    unidade_bruta: str
    unidade: str  # unidade após eventual correção


def referencia(data_base: str) -> str:
    """'202606' → 'jun/2026'."""
    return f"{MESES[int(data_base[4:]) - 1]}/{data_base[:4]}"


def trimestre_anterior(data_base: str) -> str:
    ano, mes = int(data_base[:4]), int(data_base[4:])
    mes -= 3
    if mes <= 0:
        mes += 12
        ano -= 1
    return f"{ano}{mes:02d}"


def _numero(v) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    if isinstance(v, str):
        try:
            return float(v.replace(".", "").replace(",", ".")) if "," in v else float(v)
        except ValueError:
            return None
    return None


def validar_registros(registros: list[dict], avisos: list[str]) -> dict[str, Metrica]:
    metricas: dict[str, Metrica] = {}
    for r in registros:
        mid = str(r.get("IdMetrica") or "").strip()
        nome = (r.get("Metrica") or "").strip()
        valor = _numero(r.get("Valor"))
        unidade = (r.get("Unidade") or "").strip()
        if not mid:
            avisos.append("Registro sem IdMetrica descartado.")
            continue
        if valor is None:
            avisos.append(f"Métrica {mid} ({nome or 'sem nome'}) sem valor numérico — ignorada.")
            continue
        if mid in metricas:
            avisos.append(f"Métrica {mid} repetida na fonte — mantida a primeira ocorrência.")
            continue
        metricas[mid] = Metrica(mid, nome, valor, unidade, unidade)
    return metricas


def corrigir_unidades(metricas: dict[str, Metrica], avisos: list[str]) -> None:
    """Se total ≈ soma das partes (valores brutos) mas as unidades divergem,
    a fonte rotulou alguma unidade errado: alinha todas à unidade majoritária."""
    for total_id, partes_ids in CHECAGENS_TOTAL:
        grupo = [metricas.get(i) for i in [total_id, *partes_ids]]
        if any(m is None for m in grupo):
            continue
        total, partes = grupo[0], grupo[1:]
        soma = sum(p.valor_bruto for p in partes)
        if total.valor_bruto == 0 or abs(total.valor_bruto - soma) / abs(total.valor_bruto) > 0.01:
            continue
        unidades = Counter(m.unidade_bruta for m in grupo)
        if len(unidades) == 1:
            continue
        majoritaria = unidades.most_common(1)[0][0]
        for m in grupo:
            if m.unidade_bruta != majoritaria:
                m.unidade = majoritaria
                avisos.append(
                    f"Unidade corrigida na métrica {m.id} ({m.nome}): fonte informa "
                    f"'{m.unidade_bruta}', mas total = soma das partes indica '{majoritaria}'."
                )


def normalizar(m: Metrica, avisos: list[str]) -> tuple[float, str] | None:
    fator = FATORES.get(m.unidade.lower())
    if fator is None:
        avisos.append(f"Unidade desconhecida '{m.unidade}' na métrica {m.id} — ignorada.")
        return None
    mult, unidade = fator
    valor = m.valor_bruto * mult
    if valor < 0 or (unidade == "%" and valor > 100):
        avisos.append(f"Valor fora do intervalo esperado na métrica {m.id}: {m.valor_bruto} {m.unidade}.")
    return valor, unidade


def _processar(registros: list[dict], avisos: list[str]) -> dict[str, tuple[float, str]]:
    metricas = validar_registros(registros, avisos)
    corrigir_unidades(metricas, avisos)
    normalizadas: dict[str, tuple[float, str]] = {}
    for mid, m in metricas.items():
        n = normalizar(m, avisos)
        if n:
            normalizadas[mid] = n
    return normalizadas


def _cotas_por_uf(registros: list[dict], normalizadas: dict[str, tuple[float, str]]) -> dict[str, float]:
    ufs = {}
    for r in registros:
        match = RE_UF.search(r.get("Metrica") or "")
        mid = str(r.get("IdMetrica"))
        if match and mid in normalizadas:
            ufs[match.group(1).upper()] = normalizadas[mid][0]
    return ufs


def _variacao(atual: float, anterior: float | None, unidade: str) -> dict | None:
    if anterior is None:
        return None
    if unidade == "%":
        return {"tipo": "pp", "valor": round(atual - anterior, 2)}
    if anterior == 0:
        return None
    return {"tipo": "pct", "valor": round((atual - anterior) / anterior * 100, 2)}


def estruturar(
    data_base: str,
    segmento: str,
    uf: str | None,
    registros: list[dict],
    registros_anterior: list[dict] | None,
) -> tuple[dict, list[str]]:
    """Retorna (dados_estruturados, avisos)."""
    avisos: list[str] = []
    atual = _processar(registros, avisos)
    # Avisos do trimestre anterior não interessam ao usuário; só usamos os valores.
    anterior = _processar(registros_anterior, []) if registros_anterior else {}
    data_base_ant = trimestre_anterior(data_base)
    if not registros_anterior:
        avisos.append(f"Sem dados de {referencia(data_base_ant)} — variações não calculadas.")

    def montar(chave: str, nome: str, mid: str) -> dict | None:
        if mid not in atual:
            avisos.append(f"Indicador '{nome}' ausente na fonte para {referencia(data_base)}.")
            return None
        valor, unidade = atual[mid]
        valor_ant = anterior.get(mid, (None, None))[0]
        return {
            "chave": chave,
            "nome": nome,
            "valor": valor,
            "unidade": unidade,
            "valor_anterior": valor_ant,
            "variacao": _variacao(valor, valor_ant, unidade),
        }

    indicadores = []
    for chave, (nome, por_segmento) in INDICADORES.items():
        mid = por_segmento.get(segmento)
        if mid and (item := montar(chave, nome, mid)):
            indicadores.append(item)

    sistema = [item for chave, (nome, mid) in INDICADORES_SISTEMA.items() if (item := montar(chave, nome, mid))]

    cotas_uf = _cotas_por_uf(registros, atual)
    ranking = sorted(cotas_uf.items(), key=lambda kv: kv[1], reverse=True)
    total_uf = sum(cotas_uf.values())
    dados_uf = None
    if uf:
        if uf in cotas_uf:
            posicao = next(i for i, (sigla, _) in enumerate(ranking, 1) if sigla == uf)
            cotas_uf_ant = _cotas_por_uf(registros_anterior or [], anterior)
            dados_uf = {
                "uf": uf,
                "cotas_ativas": cotas_uf[uf],
                "participacao_pct": round(cotas_uf[uf] / total_uf * 100, 2) if total_uf else None,
                "posicao_ranking": posicao,
                "total_ufs": len(ranking),
                "variacao": _variacao(cotas_uf[uf], cotas_uf_ant.get(uf), "un"),
            }
        else:
            avisos.append(f"Cotas ativas da UF {uf} não encontradas na fonte.")

    dados = {
        "data_base": data_base,
        "referencia": referencia(data_base),
        "data_base_anterior": data_base_ant,
        "referencia_anterior": referencia(data_base_ant),
        "segmento": segmento,
        "segmento_nome": SEGMENTOS[segmento],
        "indicadores": indicadores,
        "sistema": sistema,
        "uf": dados_uf,
        "ranking_ufs": [{"uf": s, "cotas_ativas": v} for s, v in ranking[:5]],
        "total_metricas_fonte": len(registros),
    }
    return dados, avisos
