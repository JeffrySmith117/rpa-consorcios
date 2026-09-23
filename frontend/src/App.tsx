import { lazy, Suspense } from "react";
import { Link, Navigate, NavLink, Outlet, Route, Routes } from "react-router-dom";
import { Carregando } from "./components/Carregando";
import { PaginaConsulta } from "./features/consulta/PaginaConsulta";
import { PaginaHistorico } from "./features/historico/PaginaHistorico";

// O dashboard (e a biblioteca de gráficos) só é baixado quando a rota é aberta.
const PaginaDashboard = lazy(() =>
  import("./features/dashboard/PaginaDashboard").then((m) => ({ default: m.PaginaDashboard })),
);

/**
 * Rotas:
 *   /consulta          nova consulta
 *   /consulta/:id      execução específica (progresso ao vivo ou resultado) — link compartilhável
 *   /dashboard         gráficos; filtros na própria URL (?segmento=&uf=&data_base=)
 *   /historico         execuções e mensagens
 */
export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/consulta" replace />} />
        <Route path="consulta" element={<PaginaConsulta />} />
        <Route path="consulta/:id" element={<PaginaConsulta />} />
        <Route
          path="dashboard"
          element={
            <Suspense fallback={<Carregando texto="Carregando dashboard…" />}>
              <PaginaDashboard />
            </Suspense>
          }
        />
        <Route path="historico" element={<PaginaHistorico />} />
        <Route path="*" element={<PaginaNaoEncontrada />} />
      </Route>
    </Routes>
  );
}

function Layout() {
  const classe = ({ isActive }: { isActive: boolean }) => (isActive ? "ativa" : "");
  return (
    <>
      <header>
        <div className="container topo">
          <div>
            <h1>RPA Consórcios → WhatsApp</h1>
            <span>Dados Abertos do Banco Central · Panorama do Sistema de Consórcios</span>
          </div>
          <nav>
            <NavLink to="/consulta" className={classe}>
              Nova consulta
            </NavLink>
            <NavLink to="/dashboard" className={classe}>
              Dashboard
            </NavLink>
            <NavLink to="/historico" className={classe}>
              Histórico
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="container">
        <Outlet />
      </main>
    </>
  );
}

function PaginaNaoEncontrada() {
  return (
    <section className="card">
      <h2>Página não encontrada</h2>
      <p>
        <Link to="/consulta">Voltar para a nova consulta</Link>
      </p>
    </section>
  );
}