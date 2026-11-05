import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development the UI calls /api/*; Vite forwards it to the FastAPI server, so the
// API needs no CORS settings. Override the target with DOCUMIND_API_URL.
const apiTarget = process.env.DOCUMIND_API_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: apiTarget, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") },
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
