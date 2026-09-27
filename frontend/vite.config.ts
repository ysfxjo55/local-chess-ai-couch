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
      // Development only: production uses VITE_API_BASE_URL to call the
      // separately deployed API origin documented in the repository README.
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
