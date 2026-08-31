# E2E — `mebel-pro/e2e`

End-to-end browser tests with **Playwright** (TypeScript). Standalone pnpm
package — it tests the running `web` app (which talks to the running `backend`).

`@playwright/test`, Chromium only (`projects` in `playwright.config.ts`); Playwright
transpiles TS itself — `tsc` runs only for `pnpm typecheck`.

## Commands

```bash
pnpm install:browsers        # one-time: download Chromium (+ OS deps)
pnpm test                    # run the suite (boots the whole stack itself, see below); single spec: pnpm test tests/x.spec.ts
pnpm test:ui                 # interactive UI mode
pnpm test:headed             # headed browser
pnpm typecheck               # tsc --noEmit
```

Host prerequisites for `pnpm test`: Docker running, `uv sync` done in `../backend`,
`pnpm install` done in `../web` — the webServer commands shell into both sibling projects,
and a missing toolchain there fails the boot as an unrelated-looking timeout.

## How it runs

`playwright.config.ts` + `env.ts` (`env.ts` is the single place the stack's coordinates are
declared — both the config and the specs read them from there):

- `baseURL` = `E2E_BASE_URL`, else `http://localhost:5173`.
- The seeding DSN = `E2E_DATABASE_URL`, else
  `postgresql+asyncpg://mebel:mebel@localhost:5432/mebel_e2e`. Several specs shell out to the
  backend CLI (`app.cli seed-platform-user`) to create a platform user; that runs on the host,
  outside the app under test, so it needs the database's own address.
- When `E2E_BASE_URL` is **unset**, Playwright's `webServer` boots the local stack:
  1. Docker Compose (pinned to `--env-file ../deploy/.env.dev.example` — your real
     `deploy/.env` is deliberately **not** read) starts Postgres + MinIO, creates the MinIO
     bucket, recreates the database named in the DSN (`mebel_e2e` by default), migrates it,
     then runs `uv --directory ../backend run fastapi dev app/main.py --port 8000` with
     `TELEGRAM_LOGIN_DEV_MODE=true` + `TELEGRAM_LOGIN_RATE_LIMITS_ENABLED=false` set.
  2. `pnpm --dir ../web dev` runs Vite on :5173, which proxies `/api` → :8000.
- ⚠️ **Stop the docker dev stack's `backend` and `web` containers before `pnpm test`.**
  `reuseExistingServer` health-checks :8000/:5173 and adopts *anything* answering there —
  skipping the `mebel_e2e` recreate/migration and the Telegram-login env entirely. An adopted
  docker backend reads the demo DB `mebel` with rate limits on, so seeding lands in a database
  the API never opens and every spec fails on its first login (401s) — it reads like a sweeping
  regression but is stack adoption. The docker `postgres`/`minio` may stay up: the run
  shares them (same compose project `mebel-pro`) and only owns its own database.
- A host Postgres already listening on :5432 also breaks the run silently: the DB recreate
  runs *inside* the container (`compose exec postgres psql`) while the backend and the
  seeding CLI connect to `localhost:5432` — a host server shadows the container and the two
  halves talk to different Postgreses.
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
   `TELEGRAM_LOGIN_DEV_MODE=true` and `TELEGRAM_LOGIN_RATE_LIMITS_ENABLED=false`. There is no
   real bot and no public webhook here, so client sign-in runs through the dev-confirm route
   that the first setting opens (it 404s when off, and every client login fails); with the
   production per-IP token budget in force the suite's parallel sign-ins from one localhost IP
   exhaust the allowance partway through and fail on rate limiting. Playwright applies both to
   the server it boots itself; it has no way to apply them to a server it did not start.

A second local stack on offset ports is the usual way to exercise this — a
`COMPOSE_PROJECT_NAME` plus a ports override on `deploy/compose.yaml`, with
`TELEGRAM_LOGIN_DEV_MODE=true` and `TELEGRAM_LOGIN_RATE_LIMITS_ENABLED=false` in its
environment. Nothing in the repo is needed to make it work.

## Layout

```
e2e/
  playwright.config.ts   # base URL, projects (browsers), webServer, reporters
  env.ts                 # E2E_BASE_URL / E2E_DATABASE_URL — declared once, imported everywhere
  tsconfig.json          # for `pnpm typecheck` only
  tests/                 # *.spec.ts — one file per flow/feature (`ls tests/` for the inventory);
                         # helpers.ts is the shared seeding/login module
```

`tests/helpers.ts` carries the shared credentials, the client sign-in helpers
(`clientTokenViaApi` / `loginClient` / `devConfirmLogin` — the bot handshake driven through
the dev-confirm route), and **bilingual UI-copy locator regexes** (e.g. `/^(Password|Parol)$/`).
Web copy changes must keep these in sync — and since the web pre-push gate does not run
Playwright, that drift ships silently unless you grep `e2e/tests/` and run the touched spec.

## Conventions

- One spec file per user-facing flow; name by feature, not by page.
- Prefer **role/label/text locators** (`getByRole`, `getByLabel`, `getByText`) over CSS/XPath — they survive refactors and assert accessibility.
- Use web-first assertions (`await expect(locator).toBeVisible()`) — they auto-retry; never `waitForTimeout`.
- Keep tests independent and parallel-safe (`fullyParallel`): no shared mutable state, each test sets up what it needs. If a flow needs seeded data, do it via the API (`request` fixture) in a setup step, not the UI.
- This package is for *integration through the browser*. Don't duplicate lower-layer tests here — see the **testing-practices** skill for where a given test belongs.
