const ROTULOS: Record<string, [string, string]> = {
  EM_EXECUCAO: ["Em execução", "info"],
  SUCESSO: ["Sucesso", "ok"],
  SEM_RESULTADO: ["Sem resultado", "alerta"],
  ERRO: ["Erro", "erro"],
  GERADA: ["Gerada", "info"],
  ENVIANDO: ["Enviando", "info"],
  ENVIADA: ["Enviada", "ok"],
};

export function StatusBadge({ status }: { status: string }) {
  const [rotulo, tom] = ROTULOS[status] ?? [status, "info"];
  return <span className={`badge badge-${tom}`}>{rotulo}</span>;
}
