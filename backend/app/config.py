"""Configuração centralizada. Todos os valores sensíveis vêm do ambiente (.env),
nunca do código-fonte."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    # --- Aplicação ---
    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'rpa.db').as_posix()}"
    log_dir: Path = BASE_DIR / "logs"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"

    # --- RPA ---
    # Ponto de partida da navegação (catálogo). Vazio = ir direto ao formulário.
    bcb_dados_abertos_url: str = "https://dadosabertos.bcb.gov.br/"
    bcb_portal_url: str = (
        "https://olinda.bcb.gov.br/olinda/servico/PANORAMA_DE_CONSORCIOS/versao/v1/aplicacao#!/recursos/Metricas"
    )
    bcb_odata_url: str = "https://olinda.bcb.gov.br/olinda/servico/PANORAMA_DE_CONSORCIOS/versao/v1/odata"
    rpa_headless: bool = True
    rpa_timeout_ms: int = 30_000
    rpa_max_tentativas: int = 3
    # Se o portal falhar após todas as tentativas, consulta a API OData diretamente.
    rpa_fallback_api: bool = True

    # --- WhatsApp ---
    whatsapp_provider: Literal["link", "meta", "twilio", "mock"] = "link"

    meta_access_token: str | None = None
    meta_phone_number_id: str | None = None
    meta_api_version: str = "v21.0"

    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_whatsapp_from: str | None = None  # ex.: whatsapp:+14155238886 (sandbox)

    @property
    def screenshot_dir(self) -> Path:
        return self.log_dir / "screenshots"


@lru_cache
def get_settings() -> Settings:
    return Settings()