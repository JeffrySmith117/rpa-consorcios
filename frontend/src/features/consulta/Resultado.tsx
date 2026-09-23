import type { Execucao, Indicador } from "../../api";
import { StatusBadge } from "../../components/StatusBadge";
import { duracao, formatarValor, formatarVariacao } from "../../lib/formato";
import { ProgressoRobo } from "./ProgressoRobo";

// Indicadores em que queda é boa notícia (cor da variação invertida).
const MENOR_EH_MELHOR = new Set(["indice_exclusao", "taxa_adm_media", "inadimplencia", "pre_inadimplencia"]);

function CartaoIndicador({ ind }: { ind: Indicador }) {
  const v = formatarVariacao(ind.variacao, MENOR_EH_MELHOR.has(ind.chave));
  return (
    <div className="indicador">
      <span className="indicador-nome">{ind.nome}</span>
      <strong className="indicador-valor">{formatarValor(ind.valor, ind.unidade)}</strong>
      {v && <span className={`variacao ${v.classe}`}>{v.texto}</span>}
    </div>
  );
}

export function Resultado({ execucao }: { execucao: Execucao }) {
  const d = execucao.dados;
  return (
    <section className="card">
      <div className="titulo-linha">
        <h2>2. Dados encontrados</h2>
        <StatusBadge status={execucao.status} />
      </div>
      <p className="meta">
        Execução #{execucao.id} · fonte: <b>{execucao.fonte === "api_fallback" ? "API OData (plano B)" : execucao.fonte ?? "—"}</b> ·
        tentativas: {execucao.tentativas} · duração: {duracao(execucao.iniciado_em, execucao.finalizado_em)}
        {execucao.reaproveitada && <span className="tag">resultado reaproveitado — consulta já processada</span>}
      </p>

      {execucao.erro && <div className={`aviso ${execucao.status === "ERRO" ? "aviso-erro" : ""}`}>{execucao.erro}</div>}

      {d && (
        <>
          <p>
            <b>{d.segmento_nome}</b> · referência <b>{d.referencia}</b> · variações contra {d.referencia_anterior} ·{" "}
            {d.total_metricas_fonte} métricas lidas da fonte
          </p>
          <div className="indicadores">
            {d.indicadores.map((i) => (
              <CartaoIndicador key={i.chave} ind={i} />
            ))}
            {d.sistema.map((i) => (
              <CartaoIndicador key={i.chave} ind={i} />
            ))}
          </div>

          <div className="dupla">
            {d.uf && (
              <div>
                <h3>UF selecionada: {d.uf.uf}</h3>
                <p>
                  {formatarValor(d.uf.cotas_ativas, "un")} cotas ativas (todos os segmentos) ·{" "}
                  {d.uf.participacao_pct?.toLocaleString("pt-BR")}% do país · {d.uf.posicao_ranking}º de {d.uf.total_ufs}
                </p>
              </div>
            )}
            <div>
              <h3>Top 5 UFs em cotas ativas</h3>
              <ol className="ranking">
                {d.ranking_ufs.map((r) => (
                  <li key={r.uf}>
                    <b>{r.uf}</b> {formatarValor(r.cotas_ativas, "un")}
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </>
      )}

      {!!execucao.etapas?.length && (
        <details className="avisos">
          <summary>Etapas executadas pelo robô ({execucao.etapas.length})</summary>
          <ProgressoRobo etapas={execucao.etapas} emAndamento={false} />
        </details>
      )}

      {!!execucao.avisos?.length && (
        <details className="avisos" open>
          <summary>Tratamento e validação ({execucao.avisos.length} aviso(s))</summary>
          <ul>
            {execucao.avisos.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}