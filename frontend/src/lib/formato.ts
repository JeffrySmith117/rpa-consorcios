import type { Variacao } from "../api";

const nf = (casas: number) =>
  new Intl.NumberFormat("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

export function formatarValor(valor: number, unidade: string): string {
  if (unidade === "%") return `${nf(2).format(valor)}%`;
  if (unidade === "meses") return `${Math.round(valor)} meses`;
  const prefixo = unidade === "R$" ? "R$ " : "";
  const escalas: [number, string][] =
    unidade === "R$" ? [[1e9, " bi"], [1e6, " mi"], [1e3, " mil"]] : [[1e6, " mi"], [1e3, " mil"]];
  for (const [limite, sufixo] of escalas) {
    if (Math.abs(valor) >= limite) return `${prefixo}${nf(1).format(valor / limite)}${sufixo}`;
  }
  return `${prefixo}${nf(0).format(valor)}`;
}

export function formatarVariacao(v: Variacao, menorEhMelhor = false): { texto: string; classe: string } | null {
  if (!v) return null;
  const casas = v.tipo === "pp" ? 2 : 1;
  const arred = Number(v.valor.toFixed(casas));
  if (arred === 0) return { texto: "estável", classe: "neutro" };
  const sufixo = v.tipo === "pp" ? " p.p." : "%";
  return {
    texto: `${arred > 0 ? "▲ +" : "▼ "}${nf(casas).format(arred)}${sufixo}`,
    // Para índices como inadimplência, subir é ruim: a cor inverte.
    classe: (arred > 0) !== menorEhMelhor ? "sobe" : "desce",
  };
}

export const referencia = (db: string) => {
  const meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  return `${meses[Number(db.slice(4)) - 1]}/${db.slice(0, 4)}`;
};

export const dataHora = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "medium" }) : "—";

export const duracao = (inicio: string, fim: string | null) =>
  fim ? `${((new Date(fim).getTime() - new Date(inicio).getTime()) / 1000).toFixed(1)}s` : "—";

export const telefone = (n: string) =>
  n.length === 13 ? `+${n.slice(0, 2)} (${n.slice(2, 4)}) ${n.slice(4, 9)}-${n.slice(9)}` : `+${n}`;

/** Converte a marcação do WhatsApp (*negrito*, _itálico_) em HTML seguro. */
export function whatsappParaHtml(texto: string): string {
  const esc = texto.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return esc
    .replace(/\*([^*\n]+)\*/g, "<strong>$1</strong>")
    .replace(/(^|\s)_([^_\n]+)_/g, "$1<em>$2</em>")
    .replace(/\n/g, "<br>");
}

/** Texto amigável para qualquer erro vindo da API ou da rede. */
export const mensagemDeErro = (erro: unknown) => (erro instanceof Error ? erro.message : String(erro));