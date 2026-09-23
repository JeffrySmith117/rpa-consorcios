// Cliente HTTP do backend + tipos espelhando os schemas do FastAPI.

export type Variacao = { tipo: "pct" | "pp"; valor: number } | null;

export interface Indicador {
  chave: string;
  nome: string;
  valor: number;
  unidade: "un" | "R$" | "%" | "meses";
  valor_anterior: number | null;
  variacao: Variacao;
}

export interface DadosConsulta {
  data_base: string;
  referencia: string;
  referencia_anterior: string;
  segmento: string;
  segmento_nome: string;
  indicadores: Indicador[];
  sistema: Indicador[];
  uf: {
    uf: string;
    cotas_ativas: number;
    participacao_pct: number | null;
    posicao_ranking: number;
    total_ufs: number;
    variacao: Variacao;
  } | null;
  ranking_ufs: { uf: string; cotas_ativas: number }[];
  total_metricas_fonte: number;
}

export type StatusExecucao = "EM_EXECUCAO" | "SUCESSO" | "SEM_RESULTADO" | "ERRO";
export type StatusMensagem = "GERADA" | "ENVIANDO" | "ENVIADA" | "ERRO";

export interface Execucao {
  id: number;
  data_base: string;
  segmento: string;
  uf: string | null;
  status: StatusExecucao;
  fonte: string | null;
  tentativas: number;
  dados: DadosConsulta | null;
  avisos: string[] | null;
  erro: string | null;
  iniciado_em: string;
  finalizado_em: string | null;
  reaproveitada?: boolean;
}

export interface Mensagem {
  id: number;
  execucao_id: number;
  destinatario_nome: string;
  destinatario_numero: string;
  texto: string;
  status: StatusMensagem;
  provedor: string | null;
  provedor_message_id: string | null;
  erro: string | null;
  criado_em: string;
  enviado_em: string | null;
}

export interface HistoricoItem extends Execucao {
  mensagens: Mensagem[];
}

export interface Opcoes {
  segmentos: Record<string, string>;
  ufs: string[];
  data_bases_sugeridas: string[];
  whatsapp_provider: string;
}

export class ApiError extends Error {
  constructor(public status: number, public codigo: string, mensagem: string) {
    super(mensagem);
  }
}

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await fetch(url, { headers: { "Content-Type": "application/json" }, ...init });
  } catch {
    throw new ApiError(0, "SEM_CONEXAO", "Não foi possível conectar ao backend. Ele está rodando?");
  }
  const corpo = await r.json().catch(() => ({}));
  if (!r.ok) {
    const detalhe = Array.isArray(corpo.detail)
      ? corpo.detail.map((d: { msg: string }) => d.msg).join("; ")
      : corpo.detail ?? `Erro HTTP ${r.status}`;
    throw new ApiError(r.status, corpo.codigo ?? "ERRO", detalhe);
  }
  return corpo as T;
}

const post = <T,>(url: string, body?: unknown) =>
  req<T>(url, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  opcoes: () => req<Opcoes>("/api/opcoes"),
  consultar: (body: { data_base: string; segmento: string; uf: string | null; forcar: boolean }) =>
    post<Execucao>("/api/consultas", body),
  gerarMensagem: (body: { execucao_id: number; destinatario_nome: string; destinatario_numero: string }) =>
    post<Mensagem>("/api/mensagens", body),
  enviar: (id: number) => post<Mensagem>(`/api/mensagens/${id}/enviar`),
  historico: () => req<HistoricoItem[]>("/api/historico"),
};
