import { lazy, Suspense, useEffect, useState } from "react";
import { api, ApiError, type Etapa, type Execucao, type Opcoes } from "./api";
import { ConsultaForm, type ParametrosConsulta } from "./components/ConsultaForm";
import { Historico } from "./components/Historico";
import { MensagemPainel } from "./components/MensagemPainel";
import { Resultado } from "./components/Resultado";

// O dashboard (e a biblioteca de gráficos) só é baixado quando a aba é aberta.
const Dashboard = lazy(() => import("./components/Dashboard").then((m) => ({ default: m.Dashboard })));

type Aba = "consulta" | "dashboard" | "historico";

const INTERVALO_ACOMPANHAMENTO_MS = 800;
const esperar = (ms: number) => new Promise((resolver) => setTimeout(resolver, ms));

export default function App() {
  const [aba, setAba] = useState<Aba>("consulta");
  const [opcoes, setOpcoes] = useState<Opcoes | null>(null);
  const [execucao, setExecucao] = useState<Execucao | null>(null);
  const [executando, setExecutando] = useState(false);
  const [etapas, setEtapas] = useState<Etapa[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api.opcoes().then(setOpcoes).catch((e) => setErro(e.message));
  }, []);

  // O backend responde na hora e roda o robô em segundo plano; aqui acompanhamos
  // a execução (polling) mostrando cada etapa até ela terminar.
  async function executar(p: ParametrosConsulta) {
    setExecutando(true);
    setErro(null);
    setExecucao(null);
    try {
      let atual = await api.consultar({ ...p, em_segundo_plano: true });
      while (atual.status === "EM_EXECUCAO") {
        setEtapas(atual.etapas ?? []);
        await esperar(INTERVALO_ACOMPANHAMENTO_MS);
        atual = { ...(await api.obterConsulta(atual.id)), reaproveitada: atual.reaproveitada };
      }
      setExecucao(atual);
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : String(e));
    } finally {
      setExecutando(false);
      setEtapas(null);
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
            <button className={aba === "dashboard" ? "ativa" : ""} onClick={() => setAba("dashboard")}>
              Dashboard
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
            <ConsultaForm opcoes={opcoes} executando={executando} etapas={etapas} onExecutar={executar} />
            {execucao && <Resultado execucao={execucao} />}
            {execucao?.status === "SUCESSO" && (
              <MensagemPainel key={execucao.id} execucao={execucao} provedor={opcoes.whatsapp_provider} />
            )}
          </>
        )}
        {aba === "dashboard" && opcoes && (
          <Suspense fallback={<div className="progresso"><span className="spinner" /> Carregando dashboard…</div>}>
            <Dashboard opcoes={opcoes} />
          </Suspense>
        )}
        {aba === "historico" && <Historico />}
      </main>
    </>
  );
}