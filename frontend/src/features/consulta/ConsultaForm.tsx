import { useState } from "react";
import type { Etapa, Opcoes } from "../../api";
import { referencia } from "../../lib/formato";
import type { ParametrosConsulta } from "./hooks";
import { ProgressoRobo } from "./ProgressoRobo";

interface Props {
  opcoes: Opcoes;
  executando: boolean;
  etapas: Etapa[] | null; // progresso ao vivo do robô enquanto executa
  onExecutar: (p: ParametrosConsulta) => void;
}

export function ConsultaForm({ opcoes, executando, etapas, onExecutar }: Props) {
  const [dataBase, setDataBase] = useState(opcoes.data_bases_sugeridas[1] ?? "");
  const [segmento, setSegmento] = useState("TOTAL");
  const [uf, setUf] = useState("");
  const [forcar, setForcar] = useState(false);

  return (
    <form
      className="card"
      onSubmit={(e) => {
        e.preventDefault();
        onExecutar({ data_base: dataBase, segmento, uf: uf || null, forcar });
      }}
    >
      <h2>1. Nova consulta</h2>
      <p className="ajuda">
        O robô abre o portal de Dados Abertos do Banco Central, consulta o <em>Panorama do Sistema de Consórcios</em>{" "}
        da data-base escolhida (e do trimestre anterior, para comparação) e extrai os indicadores.
      </p>
      <div className="grade-form">
        <label>
          Data-base
          <select value={dataBase} onChange={(e) => setDataBase(e.target.value)} disabled={executando}>
            {opcoes.data_bases_sugeridas.map((db) => (
              <option key={db} value={db}>
                {referencia(db)} ({db})
              </option>
            ))}
          </select>
        </label>
        <label>
          Segmento
          <select value={segmento} onChange={(e) => setSegmento(e.target.value)} disabled={executando}>
            {Object.entries(opcoes.segmentos).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label>
          UF (opcional)
          <select value={uf} onChange={(e) => setUf(e.target.value)} disabled={executando}>
            <option value="">—</option>
            {opcoes.ufs.map((u) => (
              <option key={u}>{u}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="linha-acoes">
        <label className="check">
          <input type="checkbox" checked={forcar} onChange={(e) => setForcar(e.target.checked)} disabled={executando} />
          Reprocessar mesmo se esta consulta já foi feita
        </label>
        <button type="submit" disabled={executando || !dataBase}>
          {executando ? "Robô em execução…" : "Executar RPA"}
        </button>
      </div>
      {executando && etapas && <ProgressoRobo etapas={etapas} emAndamento />}
    </form>
  );
}