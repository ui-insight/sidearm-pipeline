import { defineConfig } from "@playwright/test";

const port = Number(process.env.PLAYWRIGHT_PORT ?? "4173");
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${port}`;
const serverMode = process.env.PLAYWRIGHT_SERVER_MODE ?? "dev";
const frontendCommand =
  serverMode === "preview"
    ? `npm --prefix ../frontend run preview -- --host 127.0.0.1 --strictPort --port ${port}`
    : `npm --prefix ../frontend run dev -- --host 127.0.0.1 --strictPort --port ${port}`;

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  retries: process.env.CI ? 2 : 1,
  workers: process.env.CI ? 1 : undefined,
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  webServer: {
    command: frontendCommand,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
