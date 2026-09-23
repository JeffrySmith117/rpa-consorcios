import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Carregando } from "../../components/Carregando";
import { formatarValor, formatarVariacao, mensagemDeErro, referencia } from "../../lib/formato";
import { useOpcoes } from "../consulta/hooks";
import { CartaoGrafico, CORES_CATEGORIAS, GraficoBarras, GraficoEmpilhado, GraficoLinhas, GraficoRosca, Minigrafico } from "./Graficos";
import { useCarregarHistorico, useDashboard } from "./hooks";

// Mesma regra da tela de resultado: nesses indicadores, cair é bom.
const MENOR_EH_MELHOR = new Set(["inadimplencia"]);
const OPCOES_TRIMESTRES = [8, 12, 20, 40];

// Fatias da rosca em ordem e cor fixas (a cor segue o segmento, não o ranking).
// "Outros bens" e "Serviços" são fatias finas demais sozinhas: viram uma só.
const FATIAS = [
  { chave: "AUTOMOVEIS", segmentos: ["AUTOMOVEIS"], nome: "Automóveis" },
  { chave: "MOTOCICLETAS", segmentos: ["MOTOCICLETAS"], nome: "Motocicletas" },
  { chave: "IMOVEIS", segmentos: ["IMOVEIS"], nome: "Imóveis" },
  { chave: "PESADOS", segmentos: ["PESADOS"], nome: "Veículos pesados" },
  { chave: "OUTROS", segmentos: ["OUTROS", "SERVICOS"], nome: "Outros bens e serviços" },
];

export function PaginaDashboard() {
  // Filtros ficam na URL (/dashboard?segmento=IMOVEIS&uf=SP): dá para compartilhar o link
  // e o "voltar" do navegador desfaz a última troca de filtro.
  const [url, setUrl] = useSearchParams();
  const segmento = url.get("segmento") ?? "TOTAL";
  const uf = url.get("uf") ?? "";
  const dataBase = url.get("data_base") ?? "";
  const filtrar = (campo: string, valor: string) =>
    setUrl((atual) => {
      const proximo = new URLSearchParams(atual);
      if (valor && !(campo === "segmento" && valor === "TOTAL")) proximo.set(campo, valor);
      else proximo.delete(campo);
      return proximo;
    });

  const opcoes = useOpcoes();
  const dashboard = useDashboard({ segmento, uf: uf || null, data_base: dataBase || null });
  const carregar = useCarregarHistorico();
  const [trimestres, setTrimestres] = useState(12);

  const dados = dashboard.data;
  const erro = dashboard.error ?? carregar.error;
  const r = carregar.data;
  const avisoHistorico = r
    ? `${r.carregados.length} trimestre(s) novo(s) carregado(s)` +
      (r.ja_existentes.length ? `, ${r.ja_existentes.length} já estavam na base` : "") +
      (r.sem_dados.length ? `, ${r.sem_dados.length} ainda sem publicação no BCB` : "") +
      (r.fonte ? ` · fonte: ${r.fonte === "api_fallback" ? "API OData (plano B)" : r.fonte}` : "") +
      "."
    : null;

  if (opcoes.isPending) return <Carregando texto="Carregando opções…" />;
  if (opcoes.isError) return <div className="aviso aviso-erro">{mensagemDeErro(opcoes.error)}</div>;

  const vazio = dados && dados.trimestres_disponiveis.length === 0;
  const serie = dados?.serie ?? [];
  const temCarteira = serie.some((p) => p.carteira !== null);

  return (
    <>
      <section className="card">
        <div className="titulo-linha">
          <h2>Dashboard</h2>
          {dados?.referencia && (
            <span className="meta">
              referência <b>{dados.referencia}</b> · {dados.trimestres_disponiveis.length} trimestre(s) na base
            </span>
          )}
        </div>
        <div className="filtros">
          <label>
            Segmento
            <select value={segmento} onChange={(e) => filtrar("segmento", e.target.value)}>
              {Object.entries(opcoes.data.segmentos).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label>
            UF em destaque
            <select value={uf} onChange={(e) => filtrar("uf", e.target.value)}>
              <option value="">—</option>
              {opcoes.data.ufs.map((u) => (
                <option key={u}>{u}</option>
              ))}
            </select>
          </label>
          <label>
            Trimestre de referência
            <select value={dataBase} onChange={(e) => filtrar("data_base", e.target.value)} disabled={!dados?.trimestres_disponiveis.length}>
              <option value="">Mais recente</option>
              {[...(dados?.trimestres_disponiveis ?? [])].reverse().map((d) => (
                <option key={d} value={d}>
                  {referencia(d)}
                </option>
              ))}
            </select>
          </label>
          <div className="filtros-historico">
            <label>
              Histórico
              <select value={trimestres} onChange={(e) => setTrimestres(Number(e.target.value))} disabled={carregar.isPending}>
                {OPCOES_TRIMESTRES.map((n) => (
                  <option key={n} value={n}>
                    últimos {n} trimestres
                  </option>
                ))}
              </select>
            </label>
            <button onClick={() => carregar.mutate(trimestres)} disabled={carregar.isPending}>
              {carregar.isPending ? "Robô buscando…" : "Carregar histórico"}
            </button>
          </div>
        </div>
        {carregar.isPending && (
          <div className="progresso">
            <span className="spinner" /> O robô está consultando o portal do BCB trimestre a trimestre (≈ 30 s a 2 min).
          </div>
        )}
        {avisoHistorico && <div className="aviso aviso-ok">{avisoHistorico}</div>}
        {erro && <div className="aviso aviso-erro">{mensagemDeErro(erro)}</div>}
        {dashboard.isPending && <Carregando texto="Carregando dashboard…" />}
      </section>

      {vazio && (
        <section className="card vazio">
          <h3>Ainda não há dados para os gráficos</h3>
          <p className="meta">
            Clique em <b>Carregar histórico</b> para o robô buscar os trimestres no portal do BCB. Cada consulta feita em
            "Nova consulta" também alimenta o dashboard.
          </p>
        </section>
      )}

      {dados && !vazio && (
        <>
          <div className="kpis">
            {dados.kpis.map((k) => {
              const v = formatarVariacao(k.variacao, MENOR_EH_MELHOR.has(k.chave));
              return (
                <div key={k.chave} className="card kpi">
                  <span className="indicador-nome">{k.nome}</span>
                  <strong className="kpi-valor">{formatarValor(k.valor, k.unidade)}</strong>
                  <span className={`variacao ${v?.classe ?? "neutro"}`}>
                    {v ? `${v.texto} vs trimestre anterior` : "sem trimestre anterior"}
                  </span>
                  <Minigrafico pontos={k.minigrafico} />
                </div>
              );
            })}
          </div>

          <div className="graficos">
            <CartaoGrafico
              titulo={`Cotas ativas — ${dados.segmento_nome}`}
              subtitulo="Evolução trimestral"
              tabela={{
                colunas: ["Trimestre", "Cotas ativas"],
                linhas: serie.map((p) => [p.referencia, p.cotas_ativas === null ? "—" : formatarValor(p.cotas_ativas, "un")]),
              }}
            >
              <GraficoLinhas
                dados={serie as never}
                eixoX="referencia"
                unidade="un"
                series={[{ chave: "cotas_ativas", nome: "Cotas ativas", cor: "var(--serie-1)" }]}
              />
            </CartaoGrafico>

            {temCarteira ? (
              <CartaoGrafico
                titulo={`Carteira — ${dados.segmento_nome}`}
                subtitulo="Evolução trimestral, em reais"
                tabela={{
                  colunas: ["Trimestre", "Carteira"],
                  linhas: serie.map((p) => [p.referencia, p.carteira === null ? "—" : formatarValor(p.carteira, "R$")]),
                }}
              >
                <GraficoLinhas
                  dados={serie as never}
                  eixoX="referencia"
                  unidade="R$"
                  series={[{ chave: "carteira", nome: "Carteira", cor: "var(--serie-1)" }]}
                />
              </CartaoGrafico>
            ) : (
              <section className="card grafico vazio">
                <h3 className="grafico-titulo">Carteira — {dados.segmento_nome}</h3>
                <p className="meta">O BCB não publica a carteira separada para este segmento.</p>
              </section>
            )}

            <CartaoGrafico
              titulo="Inadimplência × pré-inadimplência"
              subtitulo="Sistema de consórcios como um todo, em %"
              tabela={{
                colunas: ["Trimestre", "Inadimplência", "Pré-inadimplência"],
                linhas: serie.map((p) => [
                  p.referencia,
                  p.inadimplencia === null ? "—" : formatarValor(p.inadimplencia, "%"),
                  p.pre_inadimplencia === null ? "—" : formatarValor(p.pre_inadimplencia, "%"),
                ]),
              }}
            >
              <GraficoLinhas
                dados={serie as never}
                eixoX="referencia"
                unidade="%"
                series={[
                  { chave: "inadimplencia", nome: "Inadimplência", cor: "var(--serie-1)" },
                  { chave: "pre_inadimplencia", nome: "Pré-inadimplência", cor: "var(--serie-2)" },
                ]}
              />
            </CartaoGrafico>

            <CartaoGrafico
              titulo="Composição do mercado"
              subtitulo={`Participação de cada segmento nas cotas ativas, ${dados.referencia}`}
              tabela={{
                colunas: ["Segmento", "Cotas ativas"],
                linhas: dados.composicao.map((c) => [c.nome, formatarValor(c.valor, "un")]),
              }}
            >
              <GraficoRosca
                unidade="un"
                rotuloTotal="cotas ativas"
                dados={FATIAS.map((f, i) => ({
                  rotulo: f.nome,
                  cor: CORES_CATEGORIAS[i],
                  valor: dados.composicao.filter((c) => f.segmentos.includes(c.segmento)).reduce((soma, c) => soma + c.valor, 0),
                  destaque: f.chave === dados.segmento,
                })).filter((f) => f.valor > 0)}
              />
            </CartaoGrafico>

            <CartaoGrafico
              largo
              titulo="Contemplações: sorteio × lance"
              subtitulo={`Cotas contempladas nos 12 meses até ${dados.referencia}`}
              tabela={{
                colunas: ["Segmento", "Sorteio", "Lance"],
                linhas: dados.contemplacoes.map((c) => [c.nome, formatarValor(c.sorteio, "un"), formatarValor(c.lance, "un")]),
              }}
            >
              <GraficoEmpilhado
                dados={dados.contemplacoes as never}
                eixo="nome"
                unidade="un"
                series={[
                  { chave: "sorteio", nome: "Sorteio", cor: "var(--serie-1)" },
                  { chave: "lance", nome: "Lance", cor: "var(--serie-2)" },
                ]}
              />
            </CartaoGrafico>

            <CartaoGrafico
              largo
              titulo="Cotas ativas por UF"
              subtitulo={`Todos os segmentos, ${dados.referencia}${dados.uf ? ` · ${dados.uf} em destaque` : ""}`}
              tabela={{
                colunas: ["UF", "Cotas ativas", "% do país"],
                linhas: dados.ufs.map((u) => [
                  u.uf,
                  formatarValor(u.valor, "un"),
                  u.participacao_pct === null ? "—" : `${u.participacao_pct.toLocaleString("pt-BR")}%`,
                ]),
              }}
            >
              <GraficoBarras
                nomeSerie="Cotas ativas"
                unidade="un"
                alturaBarra={22}
                dados={dados.ufs.map((u) => ({ rotulo: u.uf, valor: u.valor, destaque: u.selecionada }))}
              />
            </CartaoGrafico>
          </div>
        </>
      )}
    </>
  );
}