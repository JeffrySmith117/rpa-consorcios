import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import { chaves, type FiltrosDashboard } from "../../api/chaves";

export function useDashboard(filtros: FiltrosDashboard) {
  return useQuery({
    queryKey: chaves.dashboard(filtros),
    queryFn: () => api.dashboard(filtros),
    // Ao trocar um filtro, mantém os gráficos anteriores na tela até os novos chegarem (sem "piscar").
    placeholderData: keepPreviousData,
  });
}

export function useCarregarHistorico() {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: (trimestres: number) => api.carregarHistorico(trimestres),
    // Novos trimestres na base: todas as combinações de filtro do dashboard ficam desatualizadas.
    onSuccess: () => cache.invalidateQueries({ queryKey: chaves.dashboardTodos }),
  });
}