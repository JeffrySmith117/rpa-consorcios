import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PaginaConsulta } from "./PaginaConsulta";

const OPCOES = {
  segmentos: { TOTAL: "Todos os segmentos" },
  ufs: ["SP"],
  data_bases_sugeridas: ["202609", "202606"],
  whatsapp_provider: "link",
};

const execucao = (status: string, etapas: string[], dados: object | null = null) => ({
  id: 7,
  data_base: "202606",
  segmento: "TOTAL",
  uf: null,
  status,
  fonte: status === "EM_EXECUCAO" ? null : "portal",
  tentativas: 1,
  dados,
  avisos: [],
  erro: null,
  etapas: etapas.map((texto, i) => ({ texto, em: new Date(Date.UTC(2026, 8, 23, 12, 0, i)).toISOString() })),
  iniciado_em: "2026-09-23T12:00:00Z",
  finalizado_em: status === "EM_EXECUCAO" ? null : "2026-09-23T12:00:05Z",
});

const DADOS = {
  data_base: "202606",
  referencia: "jun/2026",
  referencia_anterior: "mar/2026",
  segmento: "TOTAL",
  segmento_nome: "Todos os segmentos",
  indicadores: [],
  sistema: [],
  uf: null,
  ranking_ufs: [],
  total_metricas_fonte: 125,
};

/** Backend falso: o robô "roda" por duas consultas de acompanhamento e depois conclui. */
function backendFalso() {
  let acompanhamentos = 0;
  return vi.fn(async (url: string, init?: RequestInit) => {
    const responder = (corpo: unknown) =>
      new Response(JSON.stringify(corpo), { status: 200, headers: { "Content-Type": "application/json" } });
    if (url === "/api/opcoes") return responder(OPCOES);
    if (url === "/api/consultas" && init?.method === "POST") {
      expect(JSON.parse(String(init.body))).toMatchObject({ data_base: "202606", em_segundo_plano: true });
      return responder(execucao("EM_EXECUCAO", ["Consulta registrada; aguardando o robô"]));
    }
    if (url === "/api/consultas/7") {
      acompanhamentos += 1;
      return acompanhamentos < 2
        ? responder(execucao("EM_EXECUCAO", ["Consulta registrada; aguardando o robô", "Pesquisando “consórcios”"]))
        : responder(execucao("SUCESSO", ["Consulta registrada; aguardando o robô", "Concluído"], DADOS));
    }
    throw new Error(`rota inesperada: ${url}`);
  });
}

function MostraEndereco() {
  return <div data-testid="endereco">{useLocation().pathname}</div>;
}

function renderizar() {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={cache}>
      <MemoryRouter initialEntries={["/consulta"]}>
        <Routes>
          <Route path="/consulta" element={<PaginaConsulta />} />
          <Route path="/consulta/:id" element={<PaginaConsulta />} />
        </Routes>
        <MostraEndereco />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("PaginaConsulta", () => {
  it("dispara em segundo plano, mostra o progresso ao vivo e depois o resultado", async () => {
    vi.stubGlobal("fetch", backendFalso());
    renderizar();

    fireEvent.click(await screen.findByRole("button", { name: "Executar RPA" }));

    // a URL passa a apontar para a execução (link compartilhável)
    expect(await screen.findByText("/consulta/7")).toBeInTheDocument();
    // progresso ao vivo, vindo do polling
    expect(await screen.findByText("Pesquisando “consórcios”")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Robô em execução…" })).toBeDisabled();

    // quando o robô termina, o polling para e o resultado aparece
    expect(await screen.findByText("2. Dados encontrados", {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.getByText("3. Mensagem e envio por WhatsApp")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Executar RPA" })).toBeEnabled();
  });
});