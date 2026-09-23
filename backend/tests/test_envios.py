import httpx
import pytest
import respx

from app.exceptions import EntradaInvalida, EnvioDuplicado, WhatsAppError
from app.models import StatusMensagem
from app.services.consultas import Coletores, executar_consulta
from app.services.envios import criar_mensagem, enviar_mensagem, normalizar_numero
from app.whatsapp.providers import MetaCloudAPI, MockWhatsApp, ResultadoEnvio


class ProvedorFalso:
    nome = "falso"

    def __init__(self, falhar=False):
        self.falhar = falhar
        self.enviados = []

    def enviar(self, numero, texto):
        if self.falhar:
            raise WhatsAppError("fora da janela de 24h")
        self.enviados.append((numero, texto))
        return ResultadoEnvio(self.nome, f"id-{len(self.enviados)}")


@pytest.fixture
def execucao(db, settings, registros):
    e, _ = executar_consulta(db, settings, Coletores(lambda _: registros, None), "202606", "TOTAL", "RJ")
    return e


@pytest.mark.parametrize(
    "entrada,esperado",
    [("(11) 99999-8888", "5511999998888"), ("+55 21 3333-4444", "552133334444"), ("5511999998888", "5511999998888")],
)
def test_normaliza_numero(entrada, esperado):
    assert normalizar_numero(entrada) == esperado


@pytest.mark.parametrize("entrada", ["", "123", "abc", "9" * 20])
def test_rejeita_numero_invalido(entrada):
    with pytest.raises(EntradaInvalida):
        normalizar_numero(entrada)


def test_fluxo_gerar_e_enviar(db, execucao):
    msg = criar_mensagem(db, execucao.id, "Carlos", "(11) 99999-8888")
    assert msg.status == StatusMensagem.GERADA
    assert "Olá, Carlos!" in msg.texto and "RJ" in msg.texto

    provedor = ProvedorFalso()
    msg = enviar_mensagem(db, msg.id, provedor)
    assert msg.status == StatusMensagem.ENVIADA
    assert msg.provedor_message_id == "id-1"
    assert provedor.enviados == [("5511999998888", msg.texto)]


def test_gerar_duas_vezes_nao_duplica(db, execucao):
    a = criar_mensagem(db, execucao.id, "Carlos", "11999998888")
    b = criar_mensagem(db, execucao.id, "Carlos", "(11) 99999-8888")
    assert a.id == b.id


def test_nao_reenvia_mensagem_ja_enviada(db, execucao):
    msg = criar_mensagem(db, execucao.id, "Carlos", "11999998888")
    provedor = ProvedorFalso()
    enviar_mensagem(db, msg.id, provedor)

    with pytest.raises(EnvioDuplicado):
        enviar_mensagem(db, msg.id, provedor)
    assert len(provedor.enviados) == 1


def test_falha_no_envio_fica_registrada_e_permite_nova_tentativa(db, execucao):
    msg = criar_mensagem(db, execucao.id, "Carlos", "11999998888")

    msg = enviar_mensagem(db, msg.id, ProvedorFalso(falhar=True))
    assert msg.status == StatusMensagem.ERRO
    assert "24h" in msg.erro

    msg = enviar_mensagem(db, msg.id, ProvedorFalso())
    assert msg.status == StatusMensagem.ENVIADA and msg.erro is None


def test_nao_gera_mensagem_de_execucao_sem_sucesso(db, settings):
    e, _ = executar_consulta(db, settings, Coletores(lambda _: {"202605": []}, None), "202605", "TOTAL")
    with pytest.raises(EntradaInvalida):
        criar_mensagem(db, e.id, "Carlos", "11999998888")


def test_mock_nao_chama_rede():
    assert MockWhatsApp().enviar("5511999998888", "oi").message_id.startswith("mock-")


@respx.mock
def test_meta_cloud_api_sucesso_e_erro():
    rota = respx.post("https://graph.facebook.com/v21.0/123/messages")
    meta = MetaCloudAPI("token", "123", "v21.0")

    rota.mock(return_value=httpx.Response(200, json={"messages": [{"id": "wamid.ABC"}]}))
    assert meta.enviar("5511999998888", "oi").message_id == "wamid.ABC"
    enviado = rota.calls.last.request
    assert enviado.headers["Authorization"] == "Bearer token"
    assert b'"to":"5511999998888"' in enviado.content.replace(b" ", b"")

    rota.mock(return_value=httpx.Response(400, json={"error": {"code": 131047, "message": "Re-engagement message"}}))
    with pytest.raises(WhatsAppError, match="janela de 24h"):
        meta.enviar("5511999998888", "oi")
