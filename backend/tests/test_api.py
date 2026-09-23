"""Fluxo completo pela API HTTP, com o robô substituído por dados gravados."""
import pytest
from fastapi.testclient import TestClient

from app.api import get_coletores
from app.main import app
from app.services.consultas import Coletores


@pytest.fixture
def client(db, registros):
    app.dependency_overrides[get_coletores] = lambda: Coletores(lambda _: registros, None)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_fluxo_completo(client):
    assert client.get("/api/saude").json() == {"status": "ok"}
    assert "IMOVEIS" in client.get("/api/opcoes").json()["segmentos"]

    r = client.post("/api/consultas", json={"data_base": "202606", "segmento": "IMOVEIS", "uf": "SP"})
    assert r.status_code == 200
    execucao = r.json()
    assert execucao["status"] == "SUCESSO" and not execucao["reaproveitada"]

    r = client.post("/api/consultas", json={"data_base": "202606", "segmento": "IMOVEIS", "uf": "SP"})
    assert r.json()["reaproveitada"] and r.json()["id"] == execucao["id"]

    r = client.post("/api/mensagens", json={"execucao_id": execucao["id"], "destinatario_nome": "Ana", "destinatario_numero": "11 98888-7777"})
    assert r.status_code == 200
    msg = r.json()

    r = client.post(f"/api/mensagens/{msg['id']}/enviar")
    assert r.status_code == 200 and r.json()["status"] == "ENVIADA" and r.json()["provedor"] == "mock"

    r = client.post(f"/api/mensagens/{msg['id']}/enviar")
    assert r.status_code == 409 and r.json()["codigo"] == "ENVIO_DUPLICADO"

    historico = client.get("/api/historico").json()
    assert historico[0]["id"] == execucao["id"]
    assert historico[0]["mensagens"][0]["status"] == "ENVIADA"
    assert len(client.get(f"/api/consultas/{execucao['id']}/bruto").json()) == 125


def test_erros_de_entrada_viram_http_adequado(client):
    r = client.post("/api/consultas", json={"data_base": "junho", "segmento": "TOTAL"})
    assert r.status_code == 422 and r.json()["codigo"] == "ENTRADA_INVALIDA"
    assert client.get("/api/consultas/999").status_code == 404
    assert client.post("/api/mensagens/999/enviar").status_code == 404
