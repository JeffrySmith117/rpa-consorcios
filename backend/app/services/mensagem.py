"""Geração da mensagem de WhatsApp a partir dos dados estruturados.
Usa a formatação do WhatsApp (*negrito*, _itálico_)."""
from __future__ import annotations

# Ordem e seleção do que entra na mensagem (o resto fica só na tela).
DESTAQUES = [
    "cotas_ativas",
    "cotas_comercializadas",
    "contempladas",
    "carteira",
    "taxa_adm_media",
    "valor_medio_credito",
    "prazo_medio",
]


def _br(valor: float, casas: int = 1) -> str:
    s = f"{valor:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_valor(valor: float, unidade: str) -> str:
    if unidade == "%":
        return f"{_br(valor, 2)}%"
    if unidade == "meses":
        return f"{valor:.0f} meses"
    if unidade == "R$":
        for limite, sufixo in ((1e9, "bi"), (1e6, "mi"), (1e3, "mil")):
            if abs(valor) >= limite:
                return f"R$ {_br(valor / limite)} {sufixo}"
        return f"R$ {_br(valor, 2)}"
    if abs(valor) >= 1e6:
        return f"{_br(valor / 1e6)} {'milhão' if abs(valor) < 2e6 else 'milhões'}"
    if abs(valor) >= 1e3:
        return f"{_br(valor / 1e3)} mil"
    return _br(valor, 0)


def formatar_variacao(variacao: dict | None) -> str:
    if not variacao:
        return ""
    casas, unidade = (2, " p.p.") if variacao["tipo"] == "pp" else (1, "%")
    v = round(variacao["valor"], casas)
    if v == 0:
        return " (estável)"
    seta, sinal = ("▲", "+") if v > 0 else ("▼", "")
    return f" ({seta} {sinal}{_br(v, casas)}{unidade})"


def gerar_mensagem(nome: str, dados: dict) -> str:
    primeiro_nome = nome.strip().split()[0].title() if nome.strip() else "cliente"
    por_chave = {i["chave"]: i for i in dados["indicadores"]}

    linhas = [
        f"Olá, {primeiro_nome}! 👋",
        "",
        f"Aqui está o *Panorama de Consórcios* do Banco Central — referência *{dados['referencia']}*, "
        f"segmento *{dados['segmento_nome']}*:",
        "",
    ]
    for chave in DESTAQUES:
        if item := por_chave.get(chave):
            linhas.append(f"• {item['nome']}: *{formatar_valor(item['valor'], item['unidade'])}*{formatar_variacao(item['variacao'])}")

    for item in dados["sistema"]:
        if item["chave"] == "inadimplencia":
            linhas.append(f"• {item['nome']}: *{formatar_valor(item['valor'], item['unidade'])}*{formatar_variacao(item['variacao'])}")

    if uf := dados.get("uf"):
        qtd = formatar_valor(uf["cotas_ativas"], "un")
        de = " de" if "milh" in qtd else ""
        escopo = " (todos os segmentos)" if dados["segmento"] != "TOTAL" else ""
        participacao = f"{_br(uf['participacao_pct'], 1)}% do país, " if uf.get("participacao_pct") is not None else ""
        linhas += [
            "",
            f"📍 *{uf['uf']}*: {qtd}{de} cotas ativas{escopo}{formatar_variacao(uf['variacao'])} — "
            f"{participacao}{uf['posicao_ranking']}º lugar entre as UFs.",
        ]

    if any(i.get("variacao") for i in dados["indicadores"]):
        linhas += ["", f"_Variações em relação a {dados['referencia_anterior']}._"]
    linhas += ["", "Fonte: BCB — Dados Abertos (Panorama do Sistema de Consórcios)."]
    return "\n".join(linhas)
