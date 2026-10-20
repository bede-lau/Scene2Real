import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, devices } from '@playwright/test';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const PORT = process.env.PORT ?? '8097';

export default defineConfig({
  testDir: '.',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
  },
  webServer: {
    command: 'bash tests/e2e/serve_fixtures.sh',
    url: `http://127.0.0.1:${PORT}`,
    cwd: root,
    reuseExistingServer: false,
    timeout: 120_000,
    env: { ...process.env, PORT: String(PORT), SCENE2REAL_SPATIAL_REVIEW: '0' },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  reporter: process.env.CI ? 'github' : 'list',
  outputDir: 'test-results',
});
