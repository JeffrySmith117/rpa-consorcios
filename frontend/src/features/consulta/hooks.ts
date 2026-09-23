import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Execucao } from "../../api";
import { chaves } from "../../api/chaves";

/** Enquanto o robô roda, a execução é consultada de novo nesse intervalo. */
export const INTERVALO_ACOMPANHAMENTO_MS = 800;

export interface ParametrosConsulta {
  data_base: string;
  segmento: string;
  uf: string | null;
  forcar: boolean;
}

export function useOpcoes() {
  // Segmentos, UFs e data-bases não mudam durante o uso: busca uma vez só.
  return useQuery({ queryKey: chaves.opcoes, queryFn: api.opcoes, staleTime: Infinity });
}

export function useExecucao(id: number | null) {
  return useQuery({
    queryKey: chaves.execucao(id ?? 0),
    queryFn: () => api.obterConsulta(id!),
    enabled: id !== null,
    // Polling só enquanto o robô está rodando; quando a execução termina, para sozinho.
    refetchInterval: (consulta) =>
      consulta.state.data?.status === "EM_EXECUCAO" ? INTERVALO_ACOMPANHAMENTO_MS : false,
  });
}

export function useIniciarConsulta() {
  const cache = useQueryClient();
  return useMutation({
    // Em segundo plano: o backend responde na hora e o progresso vem pelo useExecucao.
    mutationFn: (p: ParametrosConsulta) => api.consultar({ ...p, em_segundo_plano: true }),
    onSuccess: (execucao: Execucao) => {
      cache.setQueryData(chaves.execucao(execucao.id), execucao);
      cache.invalidateQueries({ queryKey: chaves.historico });
    },
  });
}

export function useGerarMensagem() {
  return useMutation({
    mutationFn: (body: { execucao_id: number; destinatario_nome: string; destinatario_numero: string }) =>
      api.gerarMensagem(body),
  });
}

export function useEnviarMensagem() {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.enviar(id),
    onSettled: () => cache.invalidateQueries({ queryKey: chaves.historico }),
  });
}