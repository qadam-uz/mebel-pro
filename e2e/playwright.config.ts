import { defineConfig, devices } from '@playwright/test'

// Base URL of the app under test. Override to point at a deployed environment;
// when unset, Playwright boots the local dev stack via `webServer` below.
const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:5173'
const useLocalServers = !process.env.E2E_BASE_URL
const E2E_DATABASE_URL = 'postgresql+asyncpg://mebel:mebel@localhost:5432/mebel_e2e'
const composeCommand = 'docker compose --env-file ../deploy/.env.dev.example -f ../deploy/compose.yaml'
const backendEnv = [
  'ENV=test',
  `DATABASE_URL=${E2E_DATABASE_URL}`,
  'MINIO_ENDPOINT_URL=http://localhost:9000',
  'MINIO_REGION=us-east-1',
  'MINIO_ACCESS_KEY_ID=mebel',
  'MINIO_SECRET_ACCESS_KEY=mebel-secret',
  'MINIO_BUCKET=mebel',
  'MINIO_USE_SSL=false',
  `OTP_DEV_CODES='["000000"]'`,
  'OTP_RATE_LIMITS_ENABLED=false',
].join(' ')

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

  // Boot the dev stack for local runs: data services first, then migrated
  // backend, then Vite. The Docker data services are required because the
  // backend readiness and file-storage contract depend on real Postgres/MinIO.
  webServer: useLocalServers
    ? [
        {
          command:
            `${composeCommand} up -d --wait postgres minio && ${composeCommand} run --rm createbuckets && ${composeCommand} exec -T postgres psql -U mebel -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS mebel_e2e WITH (FORCE);" -c "CREATE DATABASE mebel_e2e;" && ${backendEnv} uv --directory ../backend run alembic upgrade head && ${backendEnv} uv --directory ../backend run fastapi dev app/main.py --port 8000`,
          url: 'http://localhost:8000/api/v1/healthz',
          reuseExistingServer: !process.env.CI,
          timeout: 90_000,
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
