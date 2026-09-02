import { defineConfig, devices } from '@playwright/test'

import { baseUrl, databaseName, databaseUrl, databaseUser, usesLocalServers } from './env'

const composeCommand = 'docker compose --env-file ../deploy/.env.dev.example -f ../deploy/compose.yaml'
// The contract the backend under test must satisfy. Playwright can only apply
// it to the server it boots itself — an external stack (`E2E_BASE_URL`) owns its
// own process, so the same settings have to be set there. There is no bot and no
// public webhook here, so `TELEGRAM_LOGIN_DEV_MODE=true` opens the dev-confirm
// route the suite uses in the bot's place; and with the production per-IP budget
// in force the suite's parallel client sign-ins from one localhost IP exhaust the
// token allowance, so `TELEGRAM_LOGIN_RATE_LIMITS_ENABLED=false`. The bot
// *username* is not a credential — it builds the `t.me` links the login card
// renders and asserts on, so it is pinned here rather than left to a local
// `.env`. See `e2e/AGENTS.md`.
const backendEnv = [
  'ENV=test',
  `DATABASE_URL=${databaseUrl}`,
  'MINIO_ENDPOINT_URL=http://localhost:9000',
  'MINIO_REGION=us-east-1',
  'MINIO_ACCESS_KEY_ID=mebel',
  'MINIO_SECRET_ACCESS_KEY=mebel-secret',
  'MINIO_BUCKET=mebel',
  'MINIO_USE_SSL=false',
  'TELEGRAM_BOT_USERNAME=mebel_pro_uz_bot',
  'TELEGRAM_LOGIN_DEV_MODE=true',
  'TELEGRAM_LOGIN_RATE_LIMITS_ENABLED=false',
].join(' ')

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',

  use: {
    baseURL: baseUrl,
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
  webServer: usesLocalServers
    ? [
        {
          command:
            `${composeCommand} up -d --wait postgres minio && ${composeCommand} run --rm createbuckets && ${composeCommand} exec -T postgres psql -U ${databaseUser} -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS ${databaseName} WITH (FORCE);" -c "CREATE DATABASE ${databaseName};" && ${backendEnv} uv --directory ../backend run alembic upgrade head && ${backendEnv} uv --directory ../backend run fastapi dev app/main.py --port 8000`,
          url: 'http://localhost:8000/api/v1/healthz',
          reuseExistingServer: !process.env.CI,
          timeout: 90_000,
        },
        {
          command: 'pnpm --dir ../web dev',
          url: baseUrl,
          reuseExistingServer: !process.env.CI,
          timeout: 60_000,
        },
      ]
    : undefined,
})
