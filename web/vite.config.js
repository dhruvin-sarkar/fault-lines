import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Served from https://dhruvin-sarkar.github.io/fault-lines/
export default defineConfig({
  base: "/fault-lines/",
  plugins: [react()],
});
