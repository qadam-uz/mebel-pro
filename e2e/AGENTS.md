# E2E — `mebel-pro/e2e`

End-to-end browser tests with **Playwright** (TypeScript). Standalone pnpm
package — it tests the running `web` app (which talks to the running `backend`).

## Toolchain

| Concern   | Tool                                  |
| --------- | ------------------------------------- |
| Runner    | `@playwright/test` (Playwright 1.5x)  |
| Language  | TypeScript (Playwright transpiles; `tsc` only for `pnpm typecheck`) |
| Browsers  | Chromium by default (`projects` in `playwright.config.ts`) |
| PM        | pnpm                                  |

## Commands

```bash
pnpm install                 # deps
pnpm install:browsers        # one-time: download Chromium (+ OS deps)
pnpm test                    # run the suite (boots web+backend dev servers, see below)
pnpm test:ui                 # interactive UI mode
pnpm test:headed             # headed browser
pnpm report                  # open last HTML report
pnpm codegen                 # record a test against localhost:5173
pnpm typecheck               # tsc --noEmit
```

## How it runs

`playwright.config.ts` + `env.ts` (`env.ts` is the single place the stack's coordinates are
declared — both the config and the specs read them from there):

- `baseURL` = `E2E_BASE_URL`, else `http://localhost:5173`.
- The seeding DSN = `E2E_DATABASE_URL`, else
  `postgresql+asyncpg://mebel:mebel@localhost:5432/mebel_e2e`. Several specs shell out to the
  backend CLI (`app.cli seed-platform-user`) to create a platform user; that runs on the host,
  outside the app under test, so it needs the database's own address.
- When `E2E_BASE_URL` is **unset**, Playwright's `webServer` boots the local stack:
  1. Docker Compose starts Postgres + MinIO, creates the MinIO bucket, recreates the database
     named in the DSN (`mebel_e2e` by default), migrates it, then runs
     `uv --directory ../backend run fastapi dev app/main.py --port 8000`.
  2. `pnpm --dir ../web dev` runs Vite on :5173, which proxies `/api` → :8000.
  `reuseExistingServer` is on locally, so if you already have them running it won't double-start.
- `CI` env: retries=2, single worker, `github` + `html` reporters, `forbidOnly`.

### Running against an external stack

`E2E_BASE_URL` skips the `webServer` block entirely — Playwright then boots and configures
nothing, so **three things become yours to supply**, and any one of them missing fails most of
the suite:

```bash
E2E_BASE_URL=http://localhost:25173 \
E2E_DATABASE_URL=postgresql+asyncpg://mebel:mebel@localhost:25432/mebel \
pnpm test
```

1. **`E2E_BASE_URL`** — the app's origin.
2. **`E2E_DATABASE_URL`** — the database *that stack's backend reads*, reachable from this
   host. Point it anywhere else and the seeded platform user lands in a database the API under
   test never opens: seeding "succeeds", every login 401s, and most specs fail instantly.
3. **The backend's own settings**, which only that stack can set —
   `OTP_DEV_CODES=["000000"]` (the suite verifies with the fixed dev code) and
   `OTP_RATE_LIMITS_ENABLED=false`. With the production OTP budget in force the suite's client
   logins exhaust the per-IP send allowance partway through and fail on rate limiting.
   Playwright applies both to the server it boots itself; it has no way to apply them to a
   server it did not start.

A second local stack on offset ports is the usual way to exercise this — a
`COMPOSE_PROJECT_NAME` plus a ports override on `deploy/compose.yaml`, with
`OTP_RATE_LIMITS_ENABLED=false` in its environment. Nothing in the repo is needed to make it
work.

## Layout

```
e2e/
  playwright.config.ts   # base URL, projects (browsers), webServer, reporters
  env.ts                 # E2E_BASE_URL / E2E_DATABASE_URL — declared once, imported everywhere
  tsconfig.json          # for `pnpm typecheck` only
  tests/                 # *.spec.ts — one file per flow/feature
    smoke.spec.ts
    access-and-provisioning.spec.ts
    catalog-and-inventory.spec.ts
    cutting-drafts.spec.ts
    order-production.spec.ts
```

## Conventions

- One spec file per user-facing flow; name by feature, not by page.
- Prefer **role/label/text locators** (`getByRole`, `getByLabel`, `getByText`) over CSS/XPath — they survive refactors and assert accessibility.
- Use web-first assertions (`await expect(locator).toBeVisible()`) — they auto-retry; never `waitForTimeout`.
- Keep tests independent and parallel-safe (`fullyParallel`): no shared mutable state, each test sets up what it needs. If a flow needs seeded data, do it via the API (`request` fixture) in a setup step, not the UI.
- This package is for *integration through the browser*. Component-level and pure-logic tests belong in `web/` (Vitest), API tests in `backend/` (pytest). Don't duplicate those here — see the **testing-practices** skill for where a given test belongs.
- `pnpm typecheck && pnpm test` must pass; keep the suite green before pushing.
