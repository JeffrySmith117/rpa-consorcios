"""Erros de domínio. Cada um carrega o status HTTP correspondente para que a
camada de API os traduza sem lógica espalhada pelas rotas."""


class AppError(Exception):
    status_code = 500
    codigo = "ERRO_INTERNO"

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


class EntradaInvalida(AppError):
    status_code = 422
    codigo = "ENTRADA_INVALIDA"


class NaoEncontrado(AppError):
    status_code = 404
    codigo = "NAO_ENCONTRADO"


class ProcessamentoDuplicado(AppError):
    status_code = 409
    codigo = "PROCESSAMENTO_DUPLICADO"


class EnvioDuplicado(AppError):
    status_code = 409
    codigo = "ENVIO_DUPLICADO"


# --- Erros do RPA ---------------------------------------------------------

class RPAError(AppError):
    """Base para falhas da automação."""

    status_code = 502
    codigo = "FALHA_RPA"


class FonteIndisponivel(RPAError):
    """Portal fora do ar, timeout, HTTP 5xx. Erro transitório: vale tentar de novo."""

    codigo = "FONTE_INDISPONIVEL"


class FalhaNavegacao(RPAError):
    """Elemento esperado não apareceu (layout mudou, página não carregou)."""

    codigo = "FALHA_NAVEGACAO"


class RespostaInvalida(RPAError):
    """A fonte respondeu, mas o conteúdo não tem o formato esperado."""

    codigo = "RESPOSTA_INVALIDA"


class WhatsAppError(AppError):
    status_code = 502
    codigo = "FALHA_WHATSAPP"
