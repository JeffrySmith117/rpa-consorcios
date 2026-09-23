import { useQuery } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { chaves } from "../../api/chaves";
import { Carregando } from "../../components/Carregando";
import { StatusBadge } from "../../components/StatusBadge";
import { dataHora, duracao, formatarValor, mensagemDeErro, referencia, telefone } from "../../lib/formato";

export function PaginaHistorico() {
  const historico = useQuery({ queryKey: chaves.historico, queryFn: api.historico });
  const [aberto, setAberto] = useState<number | null>(null);
  const itens = historico.data;

  return (
    <section className="card">
      <div className="titulo-linha">
        <h2>Histórico de execuções</h2>
        <button className="secundario" onClick={() => historico.refetch()} disabled={historico.isFetching}>
          {historico.isFetching ? "Atualizando…" : "Atualizar"}
        </button>
      </div>
      {historico.isPending && <Carregando />}
      {historico.isError && <div className="aviso aviso-erro">{mensagemDeErro(historico.error)}</div>}
      {itens?.length === 0 && <p>Nenhuma execução ainda.</p>}
      {!!itens?.length && (
        <div className="tabela-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Data e hora</th>
                <th>Consulta</th>
                <th>Status</th>
                <th>Fonte</th>
                <th>Mensagens</th>
              </tr>
            </thead>
            <tbody>
              {itens.map((e) => (
                <Fragment key={e.id}>
                  <tr className="clicavel" onClick={() => setAberto(aberto === e.id ? null : e.id)}>
                    <td>{e.id}</td>
                    <td>{dataHora(e.iniciado_em)}</td>
                    <td>
                      {referencia(e.data_base)} · {e.segmento}
                      {e.uf && ` · ${e.uf}`}
                    </td>
                    <td>
                      <StatusBadge status={e.status} />
                    </td>
                    <td>
                      {e.fonte ?? "—"} ({e.tentativas}x)
                    </td>
                    <td>
                      {e.mensagens.length === 0
                        ? "—"
                        : e.mensagens.map((m) => (
                            <span key={m.id} className="mini">
                              <StatusBadge status={m.status} />
                            </span>
                          ))}
                    </td>
                  </tr>
                  {aberto === e.id && (
                    <tr className="detalhe">
                      <td colSpan={6}>
                        <p className="meta">
                          Duração: {duracao(e.iniciado_em, e.finalizado_em)} · finalizada em {dataHora(e.finalizado_em)} ·{" "}
                          <Link to={`/consulta/${e.id}`}>abrir execução</Link>
                        </p>
                        {e.erro && <div className="aviso aviso-erro">{e.erro}</div>}
                        {e.dados && (
                          <p>
                            <b>Informações encontradas:</b>{" "}
                            {e.dados.indicadores
                              .slice(0, 4)
                              .map((i) => `${i.nome}: ${formatarValor(i.valor, i.unidade)}`)
                              .join(" · ")}
                            {" "}
                            <a href={`/api/consultas/${e.id}/bruto`} target="_blank" rel="noreferrer">
                              (dados brutos)
                            </a>
                          </p>
                        )}
                        {!!e.avisos?.length && (
                          <ul className="meta">
                            {e.avisos.map((a, i) => (
                              <li key={i}>{a}</li>
                            ))}
                          </ul>
                        )}
                        {e.mensagens.map((m) => (
                          <div key={m.id} className="hist-msg">
                            <p>
                              <StatusBadge status={m.status} /> Mensagem #{m.id} para <b>{m.destinatario_nome}</b> (
                              {telefone(m.destinatario_numero)}) · gerada {dataHora(m.criado_em)}
                              {m.enviado_em && ` · enviada ${dataHora(m.enviado_em)}`}
                              {m.provedor && ` · via ${m.provedor}`}
                            </p>
                            {m.erro && <div className="aviso aviso-erro">{m.erro}</div>}
                            <pre>{m.texto}</pre>
                          </div>
                        ))}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}