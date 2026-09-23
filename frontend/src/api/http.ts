// Transporte HTTP: fetch + tradução dos erros do backend ({codigo, detail}) em ApiError.

export class ApiError extends Error {
  constructor(public status: number, public codigo: string, mensagem: string) {
    super(mensagem);
  }
}

export async function req<T>(url: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await fetch(url, { headers: { "Content-Type": "application/json" }, ...init });
  } catch {
    throw new ApiError(0, "SEM_CONEXAO", "Não foi possível conectar ao backend. Ele está rodando?");
  }
  const corpo = await r.json().catch(() => ({}));
  if (!r.ok) {
    const detalhe = Array.isArray(corpo.detail)
      ? corpo.detail.map((d: { msg: string }) => d.msg).join("; ")
      : corpo.detail ?? `Erro HTTP ${r.status}`;
    throw new ApiError(r.status, corpo.codigo ?? "ERRO", detalhe);
  }
  return corpo as T;
}

export const post = <T,>(url: string, body?: unknown) =>
  req<T>(url, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });