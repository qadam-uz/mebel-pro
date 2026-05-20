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

`playwright.config.ts`:
- `baseURL` = `E2E_BASE_URL` env var, else `http://localhost:5173`.
- When `E2E_BASE_URL` is **unset**, Playwright's `webServer` boots the local stack:
  1. `uv --directory ../backend run fastapi dev app/main.py --port 8000` (needs uv + a reachable Postgres — `docker compose -f ../deploy/compose.yaml up -d postgres`),
  2. `pnpm --dir ../web dev` (Vite on :5173, which proxies `/api` → :8000).
  `reuseExistingServer` is on locally, so if you already have them running it won't double-start.
- Set `E2E_BASE_URL=https://staging.example.com pnpm test` to run against a deployed environment (no servers booted).
- `CI` env: retries=2, single worker, `github` + `html` reporters, `forbidOnly`.

## Layout

```
e2e/
  playwright.config.ts   # base URL, projects (browsers), webServer, reporters
  tsconfig.json          # for `pnpm typecheck` only
  tests/                 # *.spec.ts — one file per flow/feature
    smoke.spec.ts        # home loads, routing, 404
```

## Conventions

- One spec file per user-facing flow; name by feature, not by page.
- Prefer **role/label/text locators** (`getByRole`, `getByLabel`, `getByText`) over CSS/XPath — they survive refactors and assert accessibility.
- Use web-first assertions (`await expect(locator).toBeVisible()`) — they auto-retry; never `waitForTimeout`.
- Keep tests independent and parallel-safe (`fullyParallel`): no shared mutable state, each test sets up what it needs. If a flow needs seeded data, do it via the API (`request` fixture) in a setup step, not the UI.
- This package is for *integration through the browser*. Component-level and pure-logic tests belong in `web/` (Vitest), API tests in `backend/` (pytest). Don't duplicate those here — see the **testing-practices** skill for where a given test belongs.
- `pnpm typecheck` must pass; keep the suite green before pushing.
