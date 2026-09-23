// Gráficos reutilizáveis do dashboard (Recharts).
// Regras de legibilidade: um eixo Y por gráfico (nunca dois), linhas de 2px,
// legenda só com 2+ séries, rótulos diretos seletivos e tabela de dados em cada
// cartão para quem não enxerga cores ou prefere números.
import type { ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  type TooltipContentProps,
  XAxis,
  YAxis,
} from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";
import { formatarValor } from "../formato";

export type Unidade = "un" | "R$" | "%" | "meses";

export interface Serie {
  chave: string;
  nome: string;
  cor: string; // variável CSS, ex.: "var(--serie-1)"
}

const TICK = { fill: "var(--suave)", fontSize: 12 };

// Paleta categórica (5 cores validadas para daltonismo, inclusive o par 5↔1 que se encosta na rosca).
export const CORES_CATEGORIAS = ["var(--cat-1)", "var(--cat-2)", "var(--cat-3)", "var(--cat-4)", "var(--cat-5)"];

/** Rótulo curto para eixos: "R$ 150 bi", "12 mi", "2,5%" (sem casa decimal quando não precisa). */
function formatarEixo(valor: number, unidade: Unidade): string {
  if (unidade === "%") return `${valor.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
  const prefixo = unidade === "R$" ? "R$ " : "";
  const escalas: [number, string][] = [[1e9, " bi"], [1e6, " mi"], [1e3, " mil"]];
  for (const [limite, sufixo] of escalas) {
    if (Math.abs(valor) >= limite) {
      const v = valor / limite;
      return `${prefixo}${v.toLocaleString("pt-BR", { maximumFractionDigits: Math.abs(v) >= 10 ? 0 : 1 })}${sufixo}`;
    }
  }
  return `${prefixo}${valor.toLocaleString("pt-BR", { maximumFractionDigits: 0 })}`;
}

// --- cartão com tabela de dados ----------------------------------------------

interface CartaoProps {
  titulo: string;
  subtitulo?: string;
  tabela: { colunas: string[]; linhas: (string | number)[][] };
  largo?: boolean;
  children: ReactNode;
}

export function CartaoGrafico({ titulo, subtitulo, tabela, largo, children }: CartaoProps) {
  return (
    <section className={`card grafico ${largo ? "grafico-largo" : ""}`}>
      <h3 className="grafico-titulo">{titulo}</h3>
      {subtitulo && <p className="meta">{subtitulo}</p>}
      {children}
      <details className="grafico-tabela">
        <summary>Ver dados em tabela</summary>
        <div className="tabela-wrap">
          <table>
            <thead>
              <tr>
                {tabela.colunas.map((c) => (
                  <th key={c}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tabela.linhas.map((l, i) => (
                <tr key={i}>
                  {l.map((v, j) => (
                    <td key={j}>{v}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}

// --- tooltip -----------------------------------------------------------------

function conteudoTooltip(unidade: Unidade) {
  return function ConteudoTooltip({ active, payload, label }: TooltipContentProps<ValueType, NameType>) {
    if (!active || !payload?.length) return null;
    return (
      <div className="tooltip-grafico">
        <strong>{label}</strong>
        {payload.map((p) => (
          <div key={String(p.dataKey)} className="tooltip-linha">
            <span className="tooltip-marca" style={{ background: p.color }} />
            <span>{p.name}</span>
            <b>{typeof p.value === "number" ? formatarValor(p.value, unidade) : "—"}</b>
          </div>
        ))}
      </div>
    );
  };
}

// --- linhas (evolução no tempo) ------------------------------------------------

interface LinhasProps {
  dados: Record<string, string | number | null>[];
  eixoX: string;
  series: Serie[];
  unidade: Unidade;
  altura?: number;
}

export function GraficoLinhas({ dados, eixoX, series, unidade, altura = 260 }: LinhasProps) {
  const ultimo = dados.length - 1;
  return (
    <ResponsiveContainer width="100%" height={altura}>
      <LineChart data={dados} margin={{ top: 12, right: series.length > 1 ? 112 : 16, bottom: 4, left: 4 }}>
        <CartesianGrid vertical={false} stroke="var(--grade)" />
        <XAxis dataKey={eixoX} tick={TICK} tickLine={false} axisLine={{ stroke: "var(--borda)" }} minTickGap={16} />
        <YAxis
          tick={TICK}
          tickLine={false}
          axisLine={false}
          width={80}
          domain={["auto", "auto"]}
          tickFormatter={(v: number) => formatarEixo(v, unidade)}
        />
        <Tooltip content={conteudoTooltip(unidade)} cursor={{ stroke: "var(--suave)", strokeDasharray: "3 3" }} />
        {series.length > 1 && <Legend itemSorter={null} iconType="plainline" wrapperStyle={{ fontSize: 13, color: "var(--texto)" }} />}
        {series.map((s) => (
          <Line
            key={s.chave}
            type="monotone"
            dataKey={s.chave}
            name={s.nome}
            stroke={s.cor}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 5, stroke: "var(--card)", strokeWidth: 2 }}
            connectNulls
            isAnimationActive={false}
          >
            {/* rótulo direto só no último ponto, quando há mais de uma série */}
            {series.length > 1 && (
              <LabelList
                dataKey={s.chave}
                content={({ x, y, index }) =>
                  index === ultimo ? (
                    <text x={Number(x) + 8} y={Number(y)} dy={4} fontSize={12} fill="var(--texto)">
                      {s.nome}
                    </text>
                  ) : null
                }
              />
            )}
          </Line>
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

// --- barras horizontais (ranking) ------------------------------------------

interface BarrasProps {
  dados: { rotulo: string; valor: number; destaque?: boolean }[];
  nomeSerie: string;
  unidade: Unidade;
  alturaBarra?: number;
}

export function GraficoBarras({ dados, nomeSerie, unidade, alturaBarra = 26 }: BarrasProps) {
  const temDestaque = dados.some((d) => d.destaque);
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, dados.length * alturaBarra + 40)}>
      <BarChart data={dados} layout="vertical" margin={{ top: 4, right: 72, bottom: 4, left: 4 }} barCategoryGap={2}>
        <CartesianGrid horizontal={false} stroke="var(--grade)" />
        <XAxis type="number" tick={TICK} tickLine={false} axisLine={false} tickFormatter={(v: number) => formatarEixo(v, unidade)} />
        <YAxis type="category" dataKey="rotulo" tick={TICK} tickLine={false} axisLine={false} width={130} interval={0} />
        <Tooltip content={conteudoTooltip(unidade)} cursor={{ fill: "var(--grade)" }} />
        <Bar dataKey="valor" name={nomeSerie} radius={[0, 4, 4, 0]} isAnimationActive={false}>
          {dados.map((d) => (
            <Cell key={d.rotulo} fill={!temDestaque || d.destaque ? "var(--serie-1)" : "var(--barra-neutra)"} />
          ))}
          {/* rótulo direto só na barra destacada (ou na maior, se nada estiver destacado) */}
          <LabelList
            dataKey="valor"
            content={({ x, y, width, height, value, index }) =>
              (temDestaque ? dados[Number(index)]?.destaque : index === 0) ? (
                <text
                  x={Number(x) + Number(width) + 6}
                  y={Number(y) + Number(height) / 2}
                  dy={4}
                  fontSize={12}
                  fontWeight={600}
                  fill="var(--texto)"
                >
                  {formatarValor(Number(value), unidade)}
                </text>
              ) : null
            }
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// --- barras empilhadas (composição de 2 partes) -------------------------------

interface EmpilhadoProps {
  dados: Record<string, string | number>[];
  eixo: string;
  series: [Serie, Serie];
  unidade: Unidade;
}

export function GraficoEmpilhado({ dados, eixo, series, unidade }: EmpilhadoProps) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(180, dados.length * 44 + 60)}>
      <BarChart data={dados} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 4 }} barCategoryGap={10}>
        <CartesianGrid horizontal={false} stroke="var(--grade)" />
        <XAxis type="number" tick={TICK} tickLine={false} axisLine={false} tickFormatter={(v: number) => formatarEixo(v, unidade)} />
        <YAxis type="category" dataKey={eixo} tick={TICK} tickLine={false} axisLine={false} width={150} interval={0} />
        <Tooltip content={conteudoTooltip(unidade)} cursor={{ fill: "var(--grade)" }} />
        <Legend itemSorter={null} iconType="square" wrapperStyle={{ fontSize: 13, color: "var(--texto)" }} />
        {/* contorno da cor do fundo = 2px de respiro entre os segmentos */}
        <Bar dataKey={series[0].chave} name={series[0].nome} stackId="a" fill={series[0].cor} stroke="var(--card)" strokeWidth={2} isAnimationActive={false} />
        <Bar
          dataKey={series[1].chave}
          name={series[1].nome}
          stackId="a"
          fill={series[1].cor}
          stroke="var(--card)"
          strokeWidth={2}
          radius={[0, 4, 4, 0]}
          isAnimationActive={false}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

// --- minigráfico dos cartões ---------------------------------------------------

export function Minigrafico({ pontos }: { pontos: { data_base: string; valor: number }[] }) {
  if (pontos.length < 2) return <div className="minigrafico-vazio">histórico insuficiente</div>;
  return (
    <ResponsiveContainer width="100%" height={36}>
      <LineChart data={pontos} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
        <YAxis hide domain={["dataMin", "dataMax"]} />
        <Line type="monotone" dataKey="valor" stroke="var(--serie-1)" strokeWidth={2} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// --- rosca (parte de um todo, até 5 fatias) ----------------------------------

interface Fatia {
  rotulo: string;
  valor: number;
  cor: string; // fixa por categoria: a cor segue o segmento, nunca a posição no ranking
  destaque?: boolean;
}

interface RoscaProps {
  dados: Fatia[];
  unidade: Unidade;
  rotuloTotal: string;
}

export function GraficoRosca({ dados, unidade, rotuloTotal }: RoscaProps) {
  const total = dados.reduce((soma, d) => soma + d.valor, 0);
  const temDestaque = dados.some((d) => d.destaque);
  const pct = (v: number) => (total ? ((v / total) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) : "0");

  function TooltipRosca({ active, payload }: TooltipContentProps<ValueType, NameType>) {
    if (!active || !payload?.length) return null;
    const fatia = payload[0].payload as Fatia;
    return (
      <div className="tooltip-grafico">
        <div className="tooltip-linha">
          <span className="tooltip-marca" style={{ background: fatia.cor }} />
          <strong>{fatia.rotulo}</strong>
        </div>
        <div className="tooltip-linha">
          <span>{formatarValor(fatia.valor, unidade)}</span>
          <b>{pct(fatia.valor)}%</b>
        </div>
      </div>
    );
  }

  return (
    <div className="rosca">
      <div className="rosca-grafico">
        <ResponsiveContainer width="100%" height={240}>
          <PieChart>
            <Tooltip content={TooltipRosca} />
            {/* fatias começam às 12h e seguem no sentido horário; contorno da cor do fundo = 2px de respiro */}
            <Pie
              data={dados}
              dataKey="valor"
              nameKey="rotulo"
              innerRadius="58%"
              outerRadius="92%"
              startAngle={90}
              endAngle={-270}
              stroke="var(--card)"
              strokeWidth={2}
              isAnimationActive={false}
            >
              {dados.map((d) => (
                <Cell key={d.rotulo} fill={d.cor} fillOpacity={!temDestaque || d.destaque ? 1 : 0.35} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="rosca-centro">
          <strong>{formatarValor(total, unidade)}</strong>
          <span>{rotuloTotal}</span>
        </div>
      </div>
      <ul className="rosca-legenda">
        {dados.map((d) => (
          <li key={d.rotulo} className={d.destaque ? "destaque" : ""}>
            <span className="tooltip-marca" style={{ background: d.cor }} />
            <span className="rosca-nome">{d.rotulo}</span>
            <b>{pct(d.valor)}%</b>
            <span className="rosca-valor">{formatarValor(d.valor, unidade)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}