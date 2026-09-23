"""Integração com WhatsApp.

Os provedores implementam a mesma interface (`enviar`), e o provedor ativo é
escolhido pela variável WHATSAPP_PROVIDER. Assim, trocar Meta por Twilio (ou
por um mock nos testes) não muda nada no resto do sistema.

- link   → gera o link oficial wa.me: o WhatsApp de quem está usando o sistema
             abre com a conversa e a mensagem prontas; a pessoa confirma o envio.
             Não exige conta nem credenciais (padrão para demonstração).
- meta   → WhatsApp Cloud API oficial (envio 100% automático; número de teste gratuito)
- twilio → Twilio API for WhatsApp (sandbox rápido de configurar)
- mock   → não envia nada; registra no log. Útil para desenvolvimento/testes.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote

import httpx

from app.config import Settings
from app.exceptions import WhatsAppError

log = logging.getLogger(__name__)


@dataclass
class ResultadoEnvio:
    provedor: str
    message_id: str


class ProvedorWhatsApp(Protocol):
    nome: str

    def enviar(self, numero: str, texto: str) -> ResultadoEnvio: ...


class MetaCloudAPI:
    nome = "meta"

    # Erros comuns da Cloud API com explicação acionável.
    DICAS = {
        131047: "Fora da janela de 24h: o destinatário precisa enviar uma mensagem ao número de teste antes.",
        131030: "Número não está na lista de destinatários permitidos do app (Meta > WhatsApp > API Setup).",
        190: "Token de acesso expirado ou inválido (META_ACCESS_TOKEN).",
    }

    def __init__(self, token: str, phone_number_id: str, api_version: str, timeout_s: float = 20):
        self.url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
        self.headers = {"Authorization": f"Bearer {token}"}
        self.timeout_s = timeout_s

    def enviar(self, numero: str, texto: str) -> ResultadoEnvio:
        return self._post({
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "text",
            "text": {"body": texto, "preview_url": False},
        })

    def enviar_template(self, numero: str, template: str = "hello_world", idioma: str = "en_US") -> ResultadoEnvio:
        """Templates aprovados podem ser enviados fora da janela de 24h. O
        'hello_world' já vem aprovado em todo app novo — serve para validar credenciais."""
        return self._post({
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "template",
            "template": {"name": template, "language": {"code": idioma}},
        })

    def _post(self, payload: dict) -> ResultadoEnvio:
        try:
            r = httpx.post(self.url, json=payload, headers=self.headers, timeout=self.timeout_s)
        except httpx.HTTPError as e:
            raise WhatsAppError(f"Falha de comunicação com a API da Meta: {e}") from e

        corpo = _json(r)
        if r.is_error:
            erro = corpo.get("error", {})
            codigo = erro.get("code")
            dica = self.DICAS.get(codigo, "")
            raise WhatsAppError(f"Meta API HTTP {r.status_code} (código {codigo}): {erro.get('message', r.text[:200])} {dica}".strip())
        try:
            return ResultadoEnvio(self.nome, corpo["messages"][0]["id"])
        except (KeyError, IndexError) as e:
            raise WhatsAppError(f"Resposta inesperada da Meta API: {r.text[:200]}") from e


class TwilioWhatsApp:
    nome = "twilio"

    def __init__(self, account_sid: str, auth_token: str, remetente: str, timeout_s: float = 20):
        self.url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        self.auth = (account_sid, auth_token)
        self.remetente = remetente if remetente.startswith("whatsapp:") else f"whatsapp:{remetente}"
        self.timeout_s = timeout_s

    def enviar(self, numero: str, texto: str) -> ResultadoEnvio:
        dados = {"From": self.remetente, "To": f"whatsapp:+{numero}", "Body": texto}
        try:
            r = httpx.post(self.url, data=dados, auth=self.auth, timeout=self.timeout_s)
        except httpx.HTTPError as e:
            raise WhatsAppError(f"Falha de comunicação com a Twilio: {e}") from e
        corpo = _json(r)
        if r.is_error:
            raise WhatsAppError(f"Twilio HTTP {r.status_code} (código {corpo.get('code')}): {corpo.get('message', r.text[:200])}")
        return ResultadoEnvio(self.nome, corpo.get("sid", ""))


class LinkWhatsApp:
    """Click-to-chat oficial (https://wa.me). O `message_id` devolvido é o próprio
    link, que o frontend abre no navegador de quem clicou em Enviar."""

    nome = "link"

    def enviar(self, numero: str, texto: str) -> ResultadoEnvio:
        return ResultadoEnvio(self.nome, f"https://wa.me/{numero}?text={quote(texto)}")


class MockWhatsApp:
    nome = "mock"

    def enviar(self, numero: str, texto: str) -> ResultadoEnvio:
        log.info("[MOCK WhatsApp] para %s:\n%s", numero, texto)
        return ResultadoEnvio(self.nome, f"mock-{uuid.uuid4().hex[:12]}")


def _json(r: httpx.Response) -> dict:
    try:
        corpo = r.json()
        return corpo if isinstance(corpo, dict) else {}
    except ValueError:
        return {}


def criar_provedor(s: Settings) -> ProvedorWhatsApp:
    if s.whatsapp_provider == "link":
        return LinkWhatsApp()
    if s.whatsapp_provider == "meta":
        if not (s.meta_access_token and s.meta_phone_number_id):
            raise WhatsAppError("WHATSAPP_PROVIDER=meta exige META_ACCESS_TOKEN e META_PHONE_NUMBER_ID no .env.")
        return MetaCloudAPI(s.meta_access_token, s.meta_phone_number_id, s.meta_api_version)
    if s.whatsapp_provider == "twilio":
        if not (s.twilio_account_sid and s.twilio_auth_token and s.twilio_whatsapp_from):
            raise WhatsAppError("WHATSAPP_PROVIDER=twilio exige TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN e TWILIO_WHATSAPP_FROM no .env.")
        return TwilioWhatsApp(s.twilio_account_sid, s.twilio_auth_token, s.twilio_whatsapp_from)
    return MockWhatsApp()