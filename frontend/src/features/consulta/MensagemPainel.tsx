import { useState } from "react";
import type { Execucao, Mensagem } from "../../api";
import { StatusBadge } from "../../components/StatusBadge";
import { dataHora, mensagemDeErro, telefone, whatsappParaHtml } from "../../lib/formato";
import { useEnviarMensagem, useGerarMensagem } from "./hooks";

interface Props {
  execucao: Execucao;
  provedor: string;
}

const linkWhatsApp = (m: Mensagem | null | undefined) =>
  m?.provedor === "link" && m.provedor_message_id?.startsWith("https://wa.me/") ? m.provedor_message_id : null;

export function MensagemPainel({ execucao, provedor }: Props) {
  const [nome, setNome] = useState("");
  const [numero, setNumero] = useState("");
  const [mensagem, setMensagem] = useState<Mensagem | null>(null);
  const gerar = useGerarMensagem();
  const enviar = useEnviarMensagem();

  const ocupado = gerar.isPending || enviar.isPending;
  const erro = gerar.error ?? enviar.error;

  function aoGerar() {
    enviar.reset();
    gerar.mutate(
      { execucao_id: execucao.id, destinatario_nome: nome, destinatario_numero: numero },
      { onSuccess: setMensagem },
    );
  }

  function aoEnviar() {
    if (!mensagem) return;
    // No modo "link", a aba é aberta já no clique (senão o navegador bloqueia
    // como pop-up) e recebe o endereço do WhatsApp quando o backend responde.
    const aba = provedor === "link" ? window.open("", "_blank") : null;
    enviar.mutate(mensagem.id, {
      onSuccess: (m) => {
        setMensagem(m);
        const url = linkWhatsApp(m);
        if (aba && url) aba.location.href = url;
        else aba?.close();
      },
      onError: () => aba?.close(),
    });
  }

  const podeEnviar = mensagem && (mensagem.status === "GERADA" || mensagem.status === "ERRO");
  const url = linkWhatsApp(mensagem);

  return (
    <section className="card">
      <h2>3. Mensagem e envio por WhatsApp</h2>
      <form
        className="grade-form"
        onSubmit={(e) => {
          e.preventDefault();
          aoGerar();
        }}
      >
        <label>
          Nome do destinatário
          <input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Maria Souza" required />
        </label>
        <label>
          WhatsApp (com DDD)
          <input value={numero} onChange={(e) => setNumero(e.target.value)} placeholder="(11) 99999-8888" required />
        </label>
        <div className="alinhar-base">
          <button type="submit" className="secundario" disabled={ocupado}>
            Gerar mensagem
          </button>
        </div>
      </form>

      {erro && <div className="aviso aviso-erro">{mensagemDeErro(erro)}</div>}

      {mensagem && (
        <div className="envio">
          <div className="whatsapp">
            <div className="bolha" dangerouslySetInnerHTML={{ __html: whatsappParaHtml(mensagem.texto) }} />
          </div>
          <div className="envio-lateral">
            <p>
              Para <b>{mensagem.destinatario_nome}</b>
              <br />
              {telefone(mensagem.destinatario_numero)}
            </p>
            <p>
              Status: <StatusBadge status={mensagem.status} />
            </p>
            {mensagem.enviado_em && (
              <p className="meta">
                {url ? "Aberta no WhatsApp em" : "Enviada em"} {dataHora(mensagem.enviado_em)}
              </p>
            )}
            {mensagem.provedor_message_id && !url && <p className="meta">ID: {mensagem.provedor_message_id}</p>}
            {mensagem.erro && <div className="aviso aviso-erro">{mensagem.erro}</div>}

            {url ? (
              <>
                <a className="botao-link" href={url} target="_blank" rel="noreferrer">
                  Abrir no WhatsApp novamente
                </a>
                <p className="meta">Confirme o envio tocando em Enviar no WhatsApp.</p>
              </>
            ) : (
              <button onClick={aoEnviar} disabled={ocupado || !podeEnviar}>
                {mensagem.status === "ERRO" ? "Tentar enviar de novo" : "Enviar WhatsApp"}
              </button>
            )}
            <p className="meta">
              Provedor: <b>{provedor}</b>
              {provedor === "link" && " (abre o seu WhatsApp com a mensagem pronta)"}
              {provedor === "mock" && " (simulado — nada é enviado)"}
            </p>
          </div>
        </div>
      )}
    </section>
  );
}