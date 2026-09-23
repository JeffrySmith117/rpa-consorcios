import { useEffect, useState } from "react";
import type { Etapa } from "../api";

interface Props {
  etapas: Etapa[];
  emAndamento: boolean;
}

const segundos = (ms: number) => `${(ms / 1000).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} s`;

/** Linha do tempo das etapas do robô: ao vivo durante a execução e,
 * depois, como registro do que foi feito (rastreabilidade). */
export function ProgressoRobo({ etapas, emAndamento }: Props) {
  const inicio = etapas.length ? new Date(etapas[0].em).getTime() : Date.now();
  const [agora, setAgora] = useState(Date.now());

  useEffect(() => {
    if (!emAndamento) return;
    const id = setInterval(() => setAgora(Date.now()), 200);
    return () => clearInterval(id);
  }, [emAndamento]);

  const ultima = etapas.length - 1;
  return (
    <div className="progresso-robo" aria-live="polite">
      {emAndamento && (
        <div className="progresso-cabecalho">
          <span className="spinner" />
          <b>Robô em execução</b>
          <span className="meta">{segundos(agora - inicio)}</span>
        </div>
      )}
      <ol className="etapas">
        {etapas.map((e, i) => {
          const rodando = emAndamento && i === ultima;
          const falhou = e.texto.startsWith("Falhou") || e.texto.startsWith("Tentativa");
          return (
            <li key={i} className={rodando ? "rodando" : falhou ? "falhou" : "feita"}>
              <span className="etapa-icone">{rodando ? <span className="spinner" /> : falhou ? "!" : "✓"}</span>
              <span className="etapa-texto">{e.texto}</span>
              <span className="etapa-tempo">+{segundos(new Date(e.em).getTime() - inicio)}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}