import pytest

from app.exceptions import EntradaInvalida, FalhaNavegacao, FonteIndisponivel, ProcessamentoDuplicado
from app.models import Execucao, StatusExecucao
from app.services.consultas import Coletores, executar_consulta, marcar_execucoes_orfas


class ColetorFalso:
    """Simula o robô: devolve respostas/erros em sequência e conta as chamadas."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas = 0

    def __call__(self, data_bases):
        self.chamadas += 1
        r = self.respostas.pop(0) if len(self.respostas) > 1 else self.respostas[0]
        if isinstance(r, Exception):
            raise r
        return r


def test_sucesso_pelo_portal(db, settings, registros):
    portal = ColetorFalso(registros)
    execucao, reaproveitada = executar_consulta(db, settings, Coletores(portal, None), "202606", "imoveis", "sp")

    assert not reaproveitada
    assert execucao.status == StatusExecucao.SUCESSO
    assert execucao.fonte == "portal"
    assert execucao.segmento == "IMOVEIS" and execucao.uf == "SP"
    assert execucao.dados["referencia"] == "jun/2026"
    assert len(execucao.registros_brutos) == 125
    assert execucao.finalizado_em is not None


def test_consulta_sem_resultado(db, settings):
    portal = ColetorFalso({"202605": [], "202602": []})
    execucao, _ = executar_consulta(db, settings, Coletores(portal, None), "202605", "TOTAL")
    assert execucao.status == StatusExecucao.SEM_RESULTADO
    assert "trimestralmente" in execucao.erro


def test_retenta_e_depois_usa_plano_b(db, settings, registros):
    portal = ColetorFalso(FonteIndisponivel("portal fora do ar"))
    api = ColetorFalso(registros)
    execucao, _ = executar_consulta(db, settings, Coletores(portal, api), "202606", "TOTAL")

    assert portal.chamadas == settings.rpa_max_tentativas
    assert execucao.tentativas == settings.rpa_max_tentativas
    assert execucao.status == StatusExecucao.SUCESSO
    assert execucao.fonte == "api_fallback"


def test_falha_transitoria_recupera_na_segunda_tentativa(db, settings, registros):
    portal = ColetorFalso(FalhaNavegacao("grade não carregou"), registros)
    execucao, _ = executar_consulta(db, settings, Coletores(portal, None), "202606", "TOTAL")
    assert execucao.status == StatusExecucao.SUCESSO
    assert execucao.tentativas == 2


def test_falha_definitiva_fica_registrada(db, settings):
    portal = ColetorFalso(FonteIndisponivel("HTTP 503"))
    execucao, _ = executar_consulta(db, settings, Coletores(portal, None), "202606", "TOTAL")
    assert execucao.status == StatusExecucao.ERRO
    assert "HTTP 503" in execucao.erro
    assert execucao.finalizado_em is not None


def test_erro_inesperado_nao_deixa_execucao_presa(db, settings):
    portal = ColetorFalso(ValueError("bug"))
    execucao, _ = executar_consulta(db, settings, Coletores(portal, None), "202606", "TOTAL")
    assert execucao.status == StatusExecucao.ERRO
    assert "ValueError" in execucao.erro


def test_consulta_repetida_e_reaproveitada(db, settings, registros):
    portal = ColetorFalso(registros)
    primeira, _ = executar_consulta(db, settings, Coletores(portal, None), "202606", "TOTAL")
    segunda, reaproveitada = executar_consulta(db, settings, Coletores(portal, None), "202606", "TOTAL")

    assert reaproveitada and segunda.id == primeira.id
    assert portal.chamadas == 1  # o robô não rodou de novo

    terceira, reaproveitada = executar_consulta(db, settings, Coletores(portal, None), "202606", "TOTAL", forcar=True)
    assert not reaproveitada and terceira.id != primeira.id


def test_bloqueia_processamento_concorrente(db, settings, registros):
    db.add(Execucao(chave="202606|TOTAL|-", data_base="202606", segmento="TOTAL", status=StatusExecucao.EM_EXECUCAO))
    db.commit()
    with pytest.raises(ProcessamentoDuplicado):
        executar_consulta(db, settings, Coletores(ColetorFalso(registros), None), "202606", "TOTAL")


def test_execucao_orfa_e_liberada_na_subida(db):
    db.add(Execucao(chave="x", data_base="202606", segmento="TOTAL", status=StatusExecucao.EM_EXECUCAO))
    db.commit()
    assert marcar_execucoes_orfas(db) == 1
    assert db.query(Execucao).one().status == StatusExecucao.ERRO


@pytest.mark.parametrize(
    "data_base,segmento,uf",
    [("2026-06", "TOTAL", None), ("202613", "TOTAL", None), ("209912", "TOTAL", None), ("202606", "BARCOS", None), ("202606", "TOTAL", "XX")],
)
def test_parametros_invalidos(db, settings, data_base, segmento, uf):
    with pytest.raises(EntradaInvalida):
        executar_consulta(db, settings, Coletores(ColetorFalso({}), None), data_base, segmento, uf)
