/// <reference types="vitest/config" />
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // Site help Markdown lives in the repo at docs/site/ (editable on GitHub).
      "@site-docs": path.resolve(rootDir, "../docs/site"),
    },
  },
  server: {
    port: 5173,
    // Allow Vite to read markdown outside frontend/ during local `npm run dev`.
    fs: {
      allow: [rootDir, path.resolve(rootDir, "../docs/site")],
    },
    proxy: {
      "/api": "http://localhost:8000",
      "/docs": "http://localhost:8000",
      "/openapi.json": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
