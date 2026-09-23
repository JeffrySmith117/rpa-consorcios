import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles.css";

const cache = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1, // uma nova tentativa em falha de rede; erros da API (4xx) aparecem na hora
      refetchOnWindowFocus: false, // dados do BCB não mudam ao trocar de aba
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={cache}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);