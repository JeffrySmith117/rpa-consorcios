// Endpoints do backend. Os componentes não chamam fetch direto: usam os hooks
// de cada feature (TanStack Query), que por sua vez usam estas funções.
import { post, req } from "./http";
import type { Dashboard, Execucao, HistoricoItem, Mensagem, Opcoes, ResultadoHistorico } from "./tipos";

export { ApiError } from "./http";
export type * from "./tipos";

export const api = {
  opcoes: () => req<Opcoes>("/api/opcoes"),
  consultar: (body: { data_base: string; segmento: string; uf: string | null; forcar: boolean; em_segundo_plano?: boolean }) =>
    post<Execucao>("/api/consultas", body),
  obterConsulta: (id: number) => req<Execucao>(`/api/consultas/${id}`),
  gerarMensagem: (body: { execucao_id: number; destinatario_nome: string; destinatario_numero: string }) =>
    post<Mensagem>("/api/mensagens", body),
  enviar: (id: number) => post<Mensagem>(`/api/mensagens/${id}/enviar`),
  historico: () => req<HistoricoItem[]>("/api/historico"),
  dashboard: (params: { segmento: string; uf: string | null; data_base: string | null }) => {
    const q = new URLSearchParams({ segmento: params.segmento });
    if (params.uf) q.set("uf", params.uf);
    if (params.data_base) q.set("data_base", params.data_base);
    return req<Dashboard>(`/api/dashboard?${q}`);
  },
  carregarHistorico: (trimestres: number) => post<ResultadoHistorico>("/api/dashboard/historico", { trimestres }),
};