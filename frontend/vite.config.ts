/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em desenvolvimento, /api é redirecionado para o backend FastAPI.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/testes/setup.ts",
    // Um arquivo de teste por vez: em máquinas com pouca memória livre, vários
    // processos do jsdom subindo juntos podem falhar ao reservar memória.
    fileParallelism: false,
  },
});