import path from "node:path";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

import { cloudflare } from "@cloudflare/vite-plugin";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), cloudflare()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // Dev-time only: forwards /api/* to the FastAPI backend so the browser
      // never has to deal with cross-origin requests during `npm run dev`.
      // In production the built bundle is served same-origin by FastAPI itself.
      "/api": {
        // Use 127.0.0.1, not "localhost" — on this machine "localhost"
        // can resolve to ::1 first, where an unrelated process is bound to
        // port 8000, causing an ECONNRESET instead of reaching the backend.
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});