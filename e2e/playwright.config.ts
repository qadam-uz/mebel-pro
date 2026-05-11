import { defineConfig, devices } from '@playwright/test'

// Base URL of the app under test. Override to point at a deployed environment;
// when unset, Playwright boots the local dev stack via `webServer` below.
const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:5173'
const useLocalServers = !process.env.E2E_BASE_URL

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',

  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    // Enable more browsers as the suite matures:
    // { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    // { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],

  // Boot the dev stack for local runs. The backend needs uv + a reachable
  // Postgres (see deploy/compose.yaml); start it yourself if these aren't set up.
  webServer: useLocalServers
    ? [
        {
          command: 'uv --directory ../backend run fastapi dev app/main.py --port 8000',
          url: 'http://localhost:8000/api/v1/healthz',
          reuseExistingServer: !process.env.CI,
          timeout: 60_000,
        },
        {
          command: 'pnpm --dir ../web dev',
          url: BASE_URL,
          reuseExistingServer: !process.env.CI,
          timeout: 60_000,
        },
      ]
    : undefined,
})
