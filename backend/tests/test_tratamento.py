import copy

from app.services.tratamento import estruturar, referencia, trimestre_anterior


def _indicador(dados, chave):
    return next((i for i in dados["indicadores"] if i["chave"] == chave), None)


def test_utilitarios_de_data():
    assert referencia("202606") == "jun/2026"
    assert trimestre_anterior("202606") == "202603"
    assert trimestre_anterior("202603") == "202512"


def test_estrutura_segmento_com_uf_e_variacao(registros):
    dados, _ = estruturar("202606", "IMOVEIS", "SP", registros["202606"], registros["202603"])

    cotas = _indicador(dados, "cotas_ativas")
    assert cotas["unidade"] == "un"
    assert cotas["valor"] > 1_000_000  # "3202.55 mil" normalizado para valor absoluto
    assert cotas["variacao"]["tipo"] == "pct"

    taxa = _indicador(dados, "taxa_adm_media")
    assert taxa["unidade"] == "%"
    assert taxa["variacao"]["tipo"] == "pp"  # percentuais variam em pontos percentuais

    assert dados["uf"]["uf"] == "SP"
    assert dados["uf"]["posicao_ranking"] == 1
    assert 0 < dados["uf"]["participacao_pct"] < 100
    assert len(dados["ranking_ufs"]) == 5


def test_corrige_unidades_erradas_da_fonte(registros):
    """Na fonte, a métrica 37 vem como 'mi' e a 68 como 'R$ milhões', mas o
    total bate com a soma das partes só se forem 'mil' e 'R$ bilhões'."""
    dados, avisos = estruturar("202606", "TOTAL", None, registros["202606"], registros["202603"])

    assert any("métrica 37" in a and "'mil'" in a for a in avisos)
    assert any("métrica 68" in a and "'R$ bilhões'" in a for a in avisos)
    recursos = _indicador(dados, "recursos_a_coletar")
    assert recursos["valor"] > 100e9  # bilhões, não milhões


def test_segmento_sem_indicador_na_fonte_e_omitido(registros):
    dados, _ = estruturar("202606", "PESADOS", None, registros["202606"], None)
    assert _indicador(dados, "carteira") is None  # BCB não publica carteira só de pesados
    assert _indicador(dados, "cotas_ativas") is not None


def test_dados_incompletos_geram_avisos(registros):
    atual = copy.deepcopy(registros["202606"])
    for r in atual:
        if r["IdMetrica"] == "11":
            r["Valor"] = None
    atual = [r for r in atual if r["IdMetrica"] != "23"]

    dados, avisos = estruturar("202606", "IMOVEIS", None, atual, None)

    assert _indicador(dados, "cotas_ativas") is None
    assert _indicador(dados, "carteira") is None
    assert any("sem valor numérico" in a for a in avisos)
    assert any("'Carteira' ausente" in a for a in avisos)
    assert any("variações não calculadas" in a for a in avisos)


def test_uf_inexistente_na_fonte_gera_aviso(registros):
    atual = [r for r in registros["202606"] if not r["Metrica"].endswith("- AC")]
    dados, avisos = estruturar("202606", "TOTAL", "AC", atual, None)
    assert dados["uf"] is None
    assert any("UF AC" in a for a in avisos)
