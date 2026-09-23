"""Plano B: consulta direta à API OData que o portal usa por baixo.
Usada apenas quando a navegação no portal falha após todas as tentativas
(ex.: mudança de layout), para não deixar a operação parada."""
import logging

import httpx

from app.exceptions import FonteIndisponivel, RespostaInvalida

log = logging.getLogger(__name__)


class OlindaAPI:
    def __init__(self, base_url: str, timeout_s: float = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def consultar(self, data_bases: list[str]) -> dict[str, list[dict]]:
        with httpx.Client(timeout=self.timeout_s) as client:
            return {db: self._consultar_uma(client, db) for db in data_bases}

    def _consultar_uma(self, client: httpx.Client, data_base: str) -> list[dict]:
        url = f"{self.base_url}/Metricas(DataBase=@DataBase)"
        params = {"@DataBase": data_base, "$top": "1000", "$format": "json"}
        log.info("API OData: consultando data-base %s", data_base)
        try:
            r = client.get(url, params=params)
        except httpx.HTTPError as e:
            raise FonteIndisponivel(f"API do BCB inacessível: {e}") from e
        if r.status_code >= 500 or r.text.lstrip().startswith("/*"):
            raise FonteIndisponivel(f"API do BCB retornou erro (HTTP {r.status_code}).")
        if r.status_code >= 400:
            raise RespostaInvalida(f"API do BCB rejeitou a consulta (HTTP {r.status_code}).")
        try:
            registros = r.json()["value"]
        except (ValueError, KeyError) as e:
            raise RespostaInvalida("Resposta da API do BCB fora do formato esperado.") from e
        return registros
