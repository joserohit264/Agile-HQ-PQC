import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Production build is emitted straight into the Flask static folder and served at /static/app/,
// so `python run.py` serves it without Node. In dev (`npm run dev`) API and Socket.IO calls are
// proxied to a running `python run.py` on :5000.
export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === "build" ? "/static/app/" : "/",
  build: { outDir: "../agile_hq_pqc/web/static/app", emptyOutDir: true, chunkSizeWarningLimit: 900 },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:5000",
      "/socket.io": { target: "http://127.0.0.1:5000", ws: true },
    },
  },
}));
