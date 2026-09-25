/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The API server (python -m app.server) serves /api and /files; in dev,
// Vite proxies them so the app runs on one origin like in production.
const api = process.env.SECTORAL_API ?? "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Fonts and brand SVGs live in ../app/assets, shared with the PDF renderer.
    fs: { allow: [".."] },
    proxy: { "/api": api, "/files": api },
  },
  test: { environment: "node" },
});
