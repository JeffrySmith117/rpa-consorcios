"""Robô que opera o Portal de Dados Abertos do Banco Central como um usuário faria:

    Portal de Dados Abertos → pesquisar "consórcios" → abrir o conjunto
    "Dados Agregados do Segmento de Consórcios" → abrir o recurso "Métricas"
    → "Ir para recurso" (portal Olinda) → preencher "Data Base" e "Máximo"
    → clicar "Executar" → aguardar a grade de resultados → capturar os registros.

Se a navegação pelo catálogo falhar (ex.: o catálogo mudou de layout), o robô
registra o problema no log e segue pelo link direto do formulário, para não
parar a operação por causa de uma etapa que não afeta os dados.

Estratégia de extração
----------------------
A grade de resultados do portal (Angular ui-grid) é *virtualizada*: só as
~15 linhas visíveis existem no DOM. Raspar o HTML exigiria rolar a grade e
remontar as linhas — frágil e lento. Em vez disso, o robô escuta a resposta
de rede que o próprio portal recebe ao clicar em "Executar" (a mesma que
alimenta a grade) e lê o JSON dali. O DOM é usado para *validar* a
navegação: cabeçalhos esperados presentes e a grade renderizada.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from app.exceptions import FalhaNavegacao, FonteIndisponivel, RespostaInvalida
from app.progresso import reportar
from app.services.tratamento import referencia

log = logging.getLogger(__name__)

# Seletores centralizados: se o portal mudar, só este bloco precisa de ajuste.
# Catálogo (dadosabertos.bcb.gov.br)
TERMO_BUSCA = "consórcios"
SEL_BUSCA = "input[name=q]"
SEL_CONJUNTO = "a[title='Dados Agregados do Segmento de Consórcios']"
SEL_RECURSO_METRICAS = "a.heading[title='Métricas']"
SEL_IR_PARA_RECURSO = "a.btn.resource-url-analytics"
# Formulário de consulta (olinda.bcb.gov.br)
SEL_DATA_BASE = "input#param0"
SEL_MAXIMO = "input[ng-model='formulario.$top']"
SEL_FORMATO = "select[ng-model='formulario.$format']"
SEL_EXECUTAR = "button[type=submit]:has-text('Executar')"
SEL_URL_PUBLICA = "#urlPublica"
SEL_GRADE = ".ui-grid"
SEL_CABECALHOS = ".ui-grid-header-cell .ui-grid-cell-contents"
SEL_LINHAS = ".ui-grid-row"

CABECALHOS_ESPERADOS = {"Data Base", "Métrica", "Valor", "Unidade"}
CAMPOS_OBRIGATORIOS = {"DataBase", "IdMetrica", "Metrica", "Valor", "Unidade"}
MAXIMO_REGISTROS = 1000  # o conjunto tem ~125 métricas por data-base


class PortalBCB:
    def __init__(
        self,
        url: str,
        headless: bool = True,
        timeout_ms: int = 30_000,
        screenshot_dir: Path | None = None,
        url_catalogo: str | None = None,
    ):
        self.url = url  # link direto do formulário (atalho se o catálogo falhar)
        self.url_catalogo = url_catalogo  # None = pula a navegação pelo catálogo
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.screenshot_dir = screenshot_dir

    def consultar(self, data_bases: list[str]) -> dict[str, list[dict]]:
        """Executa uma consulta por data-base na mesma sessão do navegador.
        Retorna {data_base: [registros]} — lista vazia = consulta sem resultado."""
        resultados: dict[str, list[dict]] = {}
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=self.headless)
            page: Page | None = None
            try:
                page = browser.new_page(locale="pt-BR")
                page.set_default_timeout(self.timeout_ms)
                self._abrir_portal(page)
                for db in data_bases:
                    resultados[db] = self._executar_consulta(page, db)
            except (FalhaNavegacao, FonteIndisponivel, RespostaInvalida):
                self._screenshot(page, "falha")
                raise
            except PlaywrightTimeout as e:
                self._screenshot(page, "timeout")
                raise FonteIndisponivel(f"Tempo esgotado aguardando o portal do BCB: {e.message.splitlines()[0]}") from e
            except PlaywrightError as e:
                self._screenshot(page, "erro")
                raise FonteIndisponivel(f"Erro do navegador ao acessar o portal: {e.message.splitlines()[0]}") from e
            finally:
                browser.close()
        return resultados

    # --- passos da automação -------------------------------------------------

    def _abrir_portal(self, page: Page) -> None:
        if self.url_catalogo:
            try:
                self._navegar_pelo_catalogo(page)
            except (PlaywrightTimeout, FalhaNavegacao) as e:
                msg = e.message if isinstance(e, PlaywrightTimeout) else str(e)
                log.warning("Navegação pelo catálogo falhou (%s). Seguindo pelo link direto do formulário.", msg.splitlines()[0])
                reportar("Catálogo não respondeu como esperado — seguindo pelo link direto do formulário")
                self._screenshot(page, "catalogo")
                self._abrir_link_direto(page)
        else:
            self._abrir_link_direto(page)
        try:
            # O formulário é montado pelo Angular depois do carregamento inicial.
            page.wait_for_selector(SEL_DATA_BASE, state="visible")
            reportar("Formulário de consulta carregado")
        except PlaywrightTimeout as e:
            raise FalhaNavegacao("Formulário de consulta não apareceu (campo 'Data Base' ausente).") from e

    def _navegar_pelo_catalogo(self, page: Page) -> None:
        log.info("Abrindo Portal de Dados Abertos: %s", self.url_catalogo)
        reportar("Abrindo o Portal de Dados Abertos do Banco Central")
        self._goto(page, self.url_catalogo)

        log.info("Pesquisando '%s'", TERMO_BUSCA)
        reportar(f"Pesquisando “{TERMO_BUSCA}”")
        page.fill(SEL_BUSCA, TERMO_BUSCA)
        with page.expect_navigation(wait_until="domcontentloaded"):
            page.press(SEL_BUSCA, "Enter")

        log.info("Abrindo conjunto de dados 'Dados Agregados do Segmento de Consórcios'")
        reportar("Abrindo o conjunto “Dados Agregados do Segmento de Consórcios”")
        if page.locator(SEL_CONJUNTO).count() == 0:
            raise FalhaNavegacao("Conjunto de dados de consórcios não encontrado no resultado da busca.")
        with page.expect_navigation(wait_until="domcontentloaded"):
            page.locator(SEL_CONJUNTO).first.click()

        log.info("Abrindo recurso 'Métricas'")
        reportar("Abrindo o recurso “Métricas”")
        with page.expect_navigation(wait_until="domcontentloaded"):
            page.locator(SEL_RECURSO_METRICAS).first.click()

        destino = page.locator(SEL_IR_PARA_RECURSO).first.get_attribute("href") or ""
        if "recursos/Metricas" not in destino:
            raise FalhaNavegacao(f"Link 'Ir para recurso' aponta para um destino inesperado: {destino!r}")
        log.info("Clicando em 'Ir para recurso' -> %s", destino)
        reportar("Clicando em “Ir para recurso” (portal Olinda)")
        with page.expect_navigation(wait_until="domcontentloaded"):
            page.locator(SEL_IR_PARA_RECURSO).first.click()

    def _abrir_link_direto(self, page: Page) -> None:
        log.info("Abrindo formulário de consulta: %s", self.url)
        reportar("Abrindo o formulário de consulta pelo link direto")
        self._goto(page, self.url)

    @staticmethod
    def _goto(page: Page, url: str) -> None:
        resp = page.goto(url, wait_until="domcontentloaded")
        if resp is None or resp.status >= 500:
            raise FonteIndisponivel(f"{url} respondeu HTTP {resp.status if resp else '??'}")

    def _executar_consulta(self, page: Page, data_base: str) -> list[dict]:
        log.info("Consultando data-base %s", data_base)
        reportar(f"Consultando {referencia(data_base)}: preenchendo o formulário e clicando em “Executar”")
        page.fill(SEL_DATA_BASE, data_base)
        page.fill(SEL_MAXIMO, str(MAXIMO_REGISTROS))
        page.select_option(SEL_FORMATO, "json")

        # Confere que o portal montou a URL de pesquisa com os parâmetros digitados.
        url_publica = page.inner_text(SEL_URL_PUBLICA)
        if f"@DataBase={data_base}" not in url_publica:
            raise FalhaNavegacao(f"Portal não aplicou o parâmetro Data Base (URL gerada: {url_publica!r}).")

        def eh_resposta_da_consulta(r) -> bool:
            return "/odata/Metricas(" in r.url and f"@DataBase={data_base}" in r.url

        inicio = time.monotonic()
        with page.expect_response(eh_resposta_da_consulta) as info:
            page.click(SEL_EXECUTAR)
        resposta = info.value
        log.info("Resposta do portal: HTTP %s em %.1fs", resposta.status, time.monotonic() - inicio)

        if resposta.status >= 500:
            raise FonteIndisponivel(f"Serviço de dados do BCB respondeu HTTP {resposta.status}.")
        if resposta.status >= 400:
            raise RespostaInvalida(f"Consulta rejeitada pelo portal (HTTP {resposta.status}).")

        registros = self._ler_registros(resposta.text())
        self._validar_grade(page, esperado=len(registros))
        reportar(
            f"{referencia(data_base)}: {len(registros)} métricas recebidas e grade validada"
            if registros
            else f"{referencia(data_base)}: nenhum dado publicado"
        )
        return registros

    def _ler_registros(self, corpo: str) -> list[dict]:
        # O Olinda devolve erros como JSON envolto em comentário: /*{"codigo":500,...}*/
        texto = corpo.strip()
        if texto.startswith("/*"):
            raise FonteIndisponivel(f"Serviço de dados do BCB retornou erro: {texto[:200]}")
        try:
            payload = json.loads(texto)
        except json.JSONDecodeError as e:
            raise RespostaInvalida("Resposta do portal não é um JSON válido.") from e

        registros = payload.get("value") if isinstance(payload, dict) else None
        if not isinstance(registros, list):
            raise RespostaInvalida("Resposta do portal sem a lista 'value'.")
        if registros:
            faltando = CAMPOS_OBRIGATORIOS - set(registros[0])
            if faltando:
                raise RespostaInvalida(f"Registros sem os campos esperados: {sorted(faltando)}")
        return registros

    def _validar_grade(self, page: Page, esperado: int) -> None:
        """Confirma pelo DOM que o portal exibiu o resultado."""
        page.wait_for_selector(SEL_GRADE, state="attached")
        if esperado == 0:
            return  # consulta sem resultado: a grade fica vazia, não há o que validar
        try:
            page.wait_for_selector(SEL_LINHAS, state="attached")
        except PlaywrightTimeout as e:
            raise FalhaNavegacao("O portal recebeu dados, mas a grade de resultados não foi exibida.") from e
        cabecalhos = {t.strip() for t in page.locator(SEL_CABECALHOS).all_inner_texts()}
        if not CABECALHOS_ESPERADOS <= cabecalhos:
            raise FalhaNavegacao(f"Colunas da grade diferentes do esperado: {sorted(cabecalhos)}")

    def _screenshot(self, page: Page | None, motivo: str) -> None:
        if not (page and self.screenshot_dir):
            return
        try:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)
            caminho = self.screenshot_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{motivo}.png"
            page.screenshot(path=str(caminho), full_page=True)
            log.warning("Screenshot da falha salvo em %s", caminho)
        except Exception:  # noqa: BLE001 — screenshot é best-effort
            log.exception("Não foi possível salvar screenshot")