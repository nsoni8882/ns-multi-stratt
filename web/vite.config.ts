import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  // Pages serves the site under /<repo>/. Override with VITE_BASE for a custom domain or org site.
  base: process.env.VITE_BASE ?? "/ns-multi-stratt/",
  plugins: [react()],
  test: { environment: "jsdom", globals: true, setupFiles: "./src/test-setup.ts" },
});
