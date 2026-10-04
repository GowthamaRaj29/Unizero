import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
 
// ai-services (app.py) has no CORS middleware and we're keeping it that
// way, so the browser can never call http://localhost:8001 directly —
// it'll be blocked by the browser's own cross-origin policy before the
// request leaves the tab. This proxy makes Vite's Node process (not the
// browser) forward /ai-api/* to ai-services, so from the browser's point
// of view every request stays same-origin (localhost:5173). See
// services/aiApi.js — its default base URL is "/ai-api" to match this.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: "localhost",
    proxy: {
      "/ai-api": {
        target: "http://localhost:8001",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ai-api/, ""),
      },
    },
  },
});
 