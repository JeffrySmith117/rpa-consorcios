import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Carregando } from "../../components/Carregando";
import { mensagemDeErro } from "../../lib/formato";
import { ConsultaForm } from "./ConsultaForm";
import { useExecucao, useIniciarConsulta, useOpcoes, type ParametrosConsulta } from "./hooks";
import { MensagemPainel } from "./MensagemPainel";
import { Resultado } from "./Resultado";

/** Rotas /consulta e /consulta/:id. Com id na URL, a execução é acompanhada
 * (e continua sendo, mesmo recarregando a página no meio do robô). */
export function PaginaConsulta() {
  const { id } = useParams();
  const execucaoId = id ? Number(id) : null;
  const [parametros] = useSearchParams();
  const navegar = useNavigate();

  const opcoes = useOpcoes();
  const iniciar = useIniciarConsulta();
  const execucao = useExecucao(execucaoId);

  if (opcoes.isPending) return <Carregando texto="Carregando opções…" />;
  if (opcoes.isError) return <div className="aviso aviso-erro">{mensagemDeErro(opcoes.error)}</div>;

  const dados = execucao.data;
  const rodando = dados?.status === "EM_EXECUCAO";
  const erro = iniciar.error ?? execucao.error;

  function executar(p: ParametrosConsulta) {
    iniciar.mutate(p, {
      onSuccess: (e) => navegar(`/consulta/${e.id}${e.reaproveitada ? "?reaproveitada=1" : ""}`),
    });
  }

  return (
    <>
      <ConsultaForm
        opcoes={opcoes.data}
        executando={iniciar.isPending || rodando}
        etapas={rodando ? (dados.etapas ?? []) : null}
        onExecutar={executar}
      />
      {erro && <div className="aviso aviso-erro">{mensagemDeErro(erro)}</div>}
      {execucaoId !== null && execucao.isPending && <Carregando texto={`Carregando execução #${execucaoId}…`} />}
      {dados && !rodando && <Resultado execucao={{ ...dados, reaproveitada: parametros.get("reaproveitada") === "1" }} />}
      {dados?.status === "SUCESSO" && (
        <MensagemPainel key={dados.id} execucao={dados} provedor={opcoes.data.whatsapp_provider} />
      )}
    </>
  );
}