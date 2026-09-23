import { useEffect, useState } from "react";
import { api, ApiError, type Execucao, type Opcoes } from "./api";
import { ConsultaForm, type ParametrosConsulta } from "./components/ConsultaForm";
import { Historico } from "./components/Historico";
import { MensagemPainel } from "./components/MensagemPainel";
import { Resultado } from "./components/Resultado";

type Aba = "consulta" | "historico";

export default function App() {
  const [aba, setAba] = useState<Aba>("consulta");
  const [opcoes, setOpcoes] = useState<Opcoes | null>(null);
  const [execucao, setExecucao] = useState<Execucao | null>(null);
  const [executando, setExecutando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api.opcoes().then(setOpcoes).catch((e) => setErro(e.message));
  }, []);

  async function executar(p: ParametrosConsulta) {
    setExecutando(true);
    setErro(null);
    setExecucao(null);
    try {
      setExecucao(await api.consultar(p));
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : String(e));
    } finally {
      setExecutando(false);
    }
  }

  return (
    <>
      <header>
        <div className="container topo">
          <div>
            <h1>RPA Consórcios → WhatsApp</h1>
            <span>Dados Abertos do Banco Central · Panorama do Sistema de Consórcios</span>
          </div>
          <nav>
            <button className={aba === "consulta" ? "ativa" : ""} onClick={() => setAba("consulta")}>
              Nova consulta
            </button>
            <button className={aba === "historico" ? "ativa" : ""} onClick={() => setAba("historico")}>
              Histórico
            </button>
          </nav>
        </div>
      </header>

      <main className="container">
        {erro && <div className="aviso aviso-erro">{erro}</div>}

        {aba === "consulta" && opcoes && (
          <>
            <ConsultaForm opcoes={opcoes} executando={executando} onExecutar={executar} />
            {execucao && <Resultado execucao={execucao} />}
            {execucao?.status === "SUCESSO" && (
              <MensagemPainel key={execucao.id} execucao={execucao} provedor={opcoes.whatsapp_provider} />
            )}
          </>
        )}
        {aba === "historico" && <Historico />}
      </main>
    </>
  );
}
