from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from app.api import get_coletores
from app.database import engine, init_db
from app.exceptions import FonteIndisponivel
from app.main import app
from app.progresso import ouvir, reportar
from app.services.consultas import Coletores, executar_consulta


def textos(execucao) -> list[str]:
    return [e["texto"] for e in execucao.etapas]


def robo_que_reporta(registros):
    def robo(data_bases):
        reportar("Pesquisando “consórcios”")
        reportar("Consultando jun/2026")
        return registros

    return robo


def test_reportar_sem_ouvinte_nao_faz_nada():
    reportar("ninguém está ouvindo")  # não pode levantar erro


def test_ouvinte_recebe_etapas_e_erro_no_ouvinte_nao_propaga():
    recebidas = []
    with ouvir(recebidas.append):
        reportar("a")
    assert recebidas == ["a"]

    def ouvinte_quebrado(_):
        raise RuntimeError("falhou ao gravar")

    with ouvir(ouvinte_quebrado):
        reportar("b")  # o robô segue mesmo se o registro do progresso falhar


def test_etapas_do_robo_ficam_gravadas_na_execucao(db, settings, registros):
    execucao, _ = executar_consulta(db, settings, Coletores(robo_que_reporta(registros), None), "202606", "TOTAL")

    etapas = textos(execucao)
    assert etapas[0] == "Consulta registrada; aguardando o robô"
    assert "Iniciando o robô (tentativa 1 de 2)" in etapas
    assert "Pesquisando “consórcios”" in etapas
    assert etapas[-1] == "Concluído"
    assert all("em" in e for e in execucao.etapas)


def test_retentativa_e_plano_b_aparecem_nas_etapas(db, settings, registros):
    def portal_fora(_):
        raise FonteIndisponivel("HTTP 503")

    execucao, _ = executar_consulta(db, settings, Coletores(portal_fora, lambda _: registros), "202606", "TOTAL")

    etapas = " | ".join(textos(execucao))
    assert "Tentativa 1 falhou (HTTP 503)" in etapas
    assert "plano B" in etapas
    assert execucao.fonte == "api_fallback"


def test_falha_definitiva_registra_etapa_de_erro(db, settings):
    def portal_fora(_):
        raise FonteIndisponivel("HTTP 503")

    execucao, _ = executar_consulta(db, settings, Coletores(portal_fora, None), "202606", "TOTAL")
    assert textos(execucao)[-1] == "Falhou: HTTP 503"


def test_api_em_segundo_plano(db, registros):
    app.dependency_overrides[get_coletores] = lambda: Coletores(robo_que_reporta(registros), None)
    try:
        with TestClient(app) as c:
            r = c.post("/api/consultas", json={"data_base": "202606", "segmento": "TOTAL", "em_segundo_plano": True})
            assert r.status_code == 200
            inicial = r.json()
            # a resposta sai antes do robô rodar
            assert inicial["status"] == "EM_EXECUCAO"
            assert [e["texto"] for e in inicial["etapas"]] == ["Consulta registrada; aguardando o robô"]

            final = c.get(f"/api/consultas/{inicial['id']}").json()
            assert final["status"] == "SUCESSO"
            assert final["etapas"][-1]["texto"] == "Concluído"
            assert final["dados"]["referencia"] == "jun/2026"
    finally:
        app.dependency_overrides.clear()


def test_banco_antigo_ganha_a_coluna_etapas(db):
    with engine.begin() as conexao:
        conexao.execute(text("ALTER TABLE execucoes DROP COLUMN etapas"))
    assert "etapas" not in {c["name"] for c in inspect(engine).get_columns("execucoes")}

    init_db()

    assert "etapas" in {c["name"] for c in inspect(engine).get_columns("execucoes")}