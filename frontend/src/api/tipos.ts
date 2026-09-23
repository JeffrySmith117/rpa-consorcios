// Tipos espelhando os schemas do FastAPI (backend/app/schemas.py e services).

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

export interface Etapa {
  texto: string;
  em: string; // ISO 8601
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
  etapas: Etapa[] | null;
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

// --- Dashboard ---------------------------------------------------------------

export interface KpiDashboard {
  chave: string;
  nome: string;
  valor: number;
  unidade: Indicador["unidade"];
  variacao: Variacao;
  minigrafico: { data_base: string; valor: number }[];
}

export interface PontoSerie {
  data_base: string;
  referencia: string;
  cotas_ativas: number | null;
  carteira: number | null;
  inadimplencia: number | null;
  pre_inadimplencia: number | null;
}

export interface Dashboard {
  segmento: string;
  segmento_nome: string;
  uf: string | null;
  trimestres_disponiveis: string[];
  data_base: string | null;
  referencia: string | null;
  kpis: KpiDashboard[];
  serie: PontoSerie[];
  composicao: { segmento: string; nome: string; valor: number; selecionado: boolean }[];
  ufs: { uf: string; valor: number; participacao_pct: number | null; selecionada: boolean }[];
  contemplacoes: { segmento: string; nome: string; sorteio: number; lance: number; selecionado: boolean }[];
}

export interface ResultadoHistorico {
  carregados: string[];
  ja_existentes: string[];
  sem_dados: string[];
  fonte: string | null;
  tentativas: number;
}