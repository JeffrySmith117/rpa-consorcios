import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProgressoRobo } from "./ProgressoRobo";

const etapas = [
  { texto: "Consulta registrada; aguardando o robô", em: "2026-09-23T12:00:00.000Z" },
  { texto: "Tentativa 1 falhou (HTTP 503); tentando de novo em instantes", em: "2026-09-23T12:00:02.000Z" },
  { texto: "Pesquisando “consórcios”", em: "2026-09-23T12:00:08.500Z" },
];

describe("ProgressoRobo", () => {
  it("ao vivo: cabeçalho de execução e a última etapa marcada como em andamento", () => {
    render(<ProgressoRobo etapas={etapas} emAndamento />);

    expect(screen.getByText("Robô em execução")).toBeInTheDocument();
    const itens = screen.getAllByRole("listitem");
    expect(itens).toHaveLength(3);
    expect(itens[0]).toHaveClass("feita");
    expect(itens[1]).toHaveClass("falhou"); // retentativas aparecem destacadas
    expect(itens[2]).toHaveClass("rodando");
    expect(itens[2]).toHaveTextContent("+8,5 s");
  });

  it("concluído: vira registro, sem cabeçalho e sem etapa em andamento", () => {
    render(<ProgressoRobo etapas={etapas} emAndamento={false} />);

    expect(screen.queryByText("Robô em execução")).not.toBeInTheDocument();
    expect(screen.getAllByRole("listitem")[2]).toHaveClass("feita");
  });
});