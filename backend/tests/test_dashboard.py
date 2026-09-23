from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.api import get_coletores
from app.exceptions import EntradaInvalida
from app.main import app
from app.models import MetricaSerie
from app.services.consultas import Coletores, executar_consulta
from app.services.dashboard import carregar_historico, montar_dashboard, trimestres_recentes
from app.services.serie import salvar_serie


def test_trimestres_recentes():
    assert trimestres_recentes(3, datetime(2026, 9, 23)) == ["202609", "202606", "202603"]
    assert trimestres_recentes(3, datetime(2026, 2, 10)) == ["202512", "202509", "202506"]


def test_serie_grava_valores_tratados(db, registros):
    assert salvar_serie(db, "202606", registros["202606"]) == 125
    # métrica 68 vem como "R$ milhões" na fonte; na série fica em reais já corrigida para bilhões
    recursos = db.query(MetricaSerie).filter_by(data_base="202606", id_metrica="68").one()
    assert recursos.unidade == "R$" and recursos.valor > 100e9
    # gravar de novo o mesmo trimestre substitui, não duplica
    salvar_serie(db, "202606", registros["202606"])
    assert db.query(MetricaSerie).filter_by(data_base="202606").count() == 125


def test_consulta_alimenta_a_serie(db, settings, registros):
    executar_consulta(db, settings, Coletores(lambda _: registros, None), "202606", "TOTAL")
    assert {d for (d,) in db.query(MetricaSerie.data_base).distinct()} == {"202606", "202603"}


def test_dashboard_vazio(db):
    d = montar_dashboard(db)
    assert d["trimestres_disponiveis"] == [] and d["kpis"] == [] and d["data_base"] is None


def test_dashboard_monta_graficos(db, registros):
    salvar_serie(db, "202603", registros["202603"])
    salvar_serie(db, "202606", registros["202606"])

    d = montar_dashboard(db, "imoveis", "sp")

    assert d["data_base"] == "202606" and d["referencia"] == "jun/2026"
    assert [p["data_base"] for p in d["serie"]] == ["202603", "202606"]
    assert all(p["cotas_ativas"] > 1e6 for p in d["serie"])

    kpis = {k["chave"]: k for k in d["kpis"]}
    assert set(kpis) == {"cotas_ativas", "carteira", "cotas_comercializadas", "inadimplencia", "uf"}
    assert kpis["cotas_ativas"]["variacao"]["tipo"] == "pct"
    assert kpis["inadimplencia"]["variacao"]["tipo"] == "pp"
    assert len(kpis["cotas_ativas"]["minigrafico"]) == 2

    assert d["composicao"][0]["valor"] >= d["composicao"][-1]["valor"]
    assert next(c for c in d["composicao"] if c["segmento"] == "IMOVEIS")["selecionado"]
    assert len(d["ufs"]) == 27 and d["ufs"][0]["uf"] == "SP" and d["ufs"][0]["selecionada"]
    assert round(sum(u["participacao_pct"] for u in d["ufs"])) == 100
    assert {c["segmento"] for c in d["contemplacoes"]} == {"IMOVEIS", "AUTOMOVEIS", "MOTOCICLETAS", "OUTROS"}


def test_dashboard_segmento_sem_carteira(db, registros):
    salvar_serie(db, "202606", registros["202606"])
    d = montar_dashboard(db, "PESADOS")
    assert "carteira" not in {k["chave"] for k in d["kpis"]}
    assert d["serie"][0]["carteira"] is None


def test_carregar_historico_busca_so_o_que_falta(db, settings, registros):
    salvar_serie(db, "202603", registros["202603"])
    pedidos = []

    def robo(data_bases):
        pedidos.append(list(data_bases))
        return {db_: registros["202606"] if db_ == "202606" else [] for db_ in data_bases}

    r = carregar_historico(db, settings, Coletores(robo, None), trimestres=4)

    assert len(pedidos) == 1 and "202603" not in pedidos[0]  # não rebusca o que já tem
    assert r["carregados"] == ["202606"]
    assert "202603" in r["ja_existentes"]
    assert r["fonte"] == "portal" and r["tentativas"] == 1


def test_carregar_historico_valida_quantidade(db, settings):
    with pytest.raises(EntradaInvalida):
        carregar_historico(db, settings, Coletores(lambda _: {}, None), trimestres=100)


def test_api_dashboard(db, registros):
    app.dependency_overrides[get_coletores] = lambda: Coletores(lambda dbs: {d: registros.get(d, []) for d in dbs}, None)
    try:
        with TestClient(app) as c:
            assert c.get("/api/dashboard").json()["trimestres_disponiveis"] == []
            r = c.post("/api/dashboard/historico", json={"trimestres": 4})
            assert r.status_code == 200 and "202606" in r.json()["carregados"]
            d = c.get("/api/dashboard", params={"segmento": "AUTOMOVEIS", "uf": "MG"}).json()
            assert d["segmento_nome"] == "Automóveis" and any(u["selecionada"] for u in d["ufs"])
            assert c.get("/api/dashboard", params={"segmento": "BARCOS"}).status_code == 422
            assert c.post("/api/dashboard/historico", json={"trimestres": 2}).status_code == 422
    finally:
        app.dependency_overrides.clear()