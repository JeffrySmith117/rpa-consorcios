import { describe, expect, it } from "vitest";
import { formatarValor, formatarVariacao, referencia, telefone, whatsappParaHtml } from "./formato";

describe("formatarValor", () => {
  it("usa escala e formato brasileiro", () => {
    expect(formatarValor(13_400_000, "un")).toBe("13,4 mi");
    expect(formatarValor(169_500, "un")).toBe("169,5 mil");
    expect(formatarValor(164.1e9, "R$")).toBe("R$ 164,1 bi");
    expect(formatarValor(2.123, "%")).toBe("2,12%");
    expect(formatarValor(217.4, "meses")).toBe("217 meses");
  });
});

describe("formatarVariacao", () => {
  it("sobe verde e desce vermelho nos indicadores comuns", () => {
    expect(formatarVariacao({ tipo: "pct", valor: 2.94 })).toEqual({ texto: "▲ +2,9%", classe: "sobe" });
    expect(formatarVariacao({ tipo: "pct", valor: -5.5 })).toEqual({ texto: "▼ -5,5%", classe: "desce" });
  });

  it("inverte a cor quando cair é bom (ex.: inadimplência)", () => {
    expect(formatarVariacao({ tipo: "pp", valor: -0.13 }, true)).toEqual({ texto: "▼ -0,13 p.p.", classe: "sobe" });
    expect(formatarVariacao({ tipo: "pp", valor: 0.07 }, true)?.classe).toBe("desce");
  });

  it("variação que arredonda para zero é 'estável'; sem variação não mostra nada", () => {
    expect(formatarVariacao({ tipo: "pct", valor: 0.01 })).toEqual({ texto: "estável", classe: "neutro" });
    expect(formatarVariacao(null)).toBeNull();
  });
});

describe("utilitários", () => {
  it("referência e telefone", () => {
    expect(referencia("202606")).toBe("jun/2026");
    expect(telefone("5586999010203")).toBe("+55 (86) 99901-0203");
  });

  it("converte a marcação do WhatsApp e escapa HTML (sem injeção de script)", () => {
    expect(whatsappParaHtml("*Cotas*: _alta_\nfim")).toBe("<strong>Cotas</strong>: <em>alta</em><br>fim");
    expect(whatsappParaHtml("<script>alert(1)</script>")).toBe("&lt;script&gt;alert(1)&lt;/script&gt;");
  });
});