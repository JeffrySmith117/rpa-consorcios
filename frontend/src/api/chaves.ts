// Chaves do cache do TanStack Query, num lugar só: quem grava e quem invalida
// usam a mesma chave, sem string solta espalhada pelos componentes.
export interface FiltrosDashboard {
  segmento: string;
  uf: string | null;
  data_base: string | null;
}

export const chaves = {
  opcoes: ["opcoes"] as const,
  execucao: (id: number) => ["execucao", id] as const,
  historico: ["historico"] as const,
  dashboard: (filtros: FiltrosDashboard) => ["dashboard", filtros] as const,
  dashboardTodos: ["dashboard"] as const,
};