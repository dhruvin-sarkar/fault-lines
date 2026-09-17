import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const REPORT = fileURLToPath(new URL("../paper/report.pdf", import.meta.url));

/** Publishes the technical report at the site root as report.pdf, so links open the PDF itself rather than a repository viewer. */
function reportPdf() {
  let base = "/";
  return {
    name: "report-pdf",
    configResolved(config) {
      base = config.base;
    },
    configureServer(server) {
      server.middlewares.use(`${base}report.pdf`, (_req, res) => {
        res.setHeader("Content-Type", "application/pdf");
        res.end(readFileSync(REPORT));
      });
    },
    generateBundle() {
      this.emitFile({ type: "asset", fileName: "report.pdf", source: readFileSync(REPORT) });
    },
  };
}

// Served from https://dhruvin-sarkar.github.io/fault-lines/
export default defineConfig({
  base: "/fault-lines/",
  plugins: [react(), reportPdf()],
});
