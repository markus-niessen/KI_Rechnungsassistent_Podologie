import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const backendPaths = [
  "/health",
  "/patients",
  "/services",
  "/business-profiles",
  "/invoices",
  "/payments",
  "/reminders",
  "/reminder-settings",
  "/ai",
];

export default defineConfig(({ mode }) => {
  const backendTarget = loadEnv(mode, ".", "VITE_").VITE_BACKEND_URL ?? "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    server: {
      proxy: Object.fromEntries(
        backendPaths.map((path) => [
          path,
          {
            target: backendTarget,
            changeOrigin: true,
          },
        ]),
      ),
    },
    test: {
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts",
      globals: true,
    },
  };
});
