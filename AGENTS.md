# Mebel Pro

Furniture-panel cutting platform. `docs/` is the single source of truth — English, served
live at `/docs`. Start with [`docs/index.md`](docs/index.md) (what it is) and
[`docs/architecture.md`](docs/architecture.md) (operating envelope, topology, stack,
invariants); read feature/entity specs under `docs/ref/` on demand. Keep the docs up to date
as you work. If a request conflicts with the docs, surface the conflict and consolidate —
don't silently code around it.

## Repo map

| Path          | What                                                                          | Stack                                                                                 | Details                                   |
| ------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ----------------------------------------- |
| `backend/`    | REST API (JSON, `/api/v1`)                                                    | Python 3.12 · FastAPI · async SQLAlchemy 2.0 · Alembic · Postgres · MinIO/S3 · **uv** | [`backend/AGENTS.md`](backend/AGENTS.md)  |
| `web/`        | Web client — 3 SPAs (client / workshop / admin) + static landing              | Vue 3 · Vite 7 · TypeScript · Pinia · Vue Router · Tailwind v4 · Vitest · **pnpm**    | [`web/AGENTS.md`](web/AGENTS.md)          |
| `e2e/`        | End-to-end browser tests                                                      | Playwright · TypeScript · **pnpm**                                                    | [`e2e/AGENTS.md`](e2e/AGENTS.md)          |
| `deploy/`     | Container orchestration                                                       | Docker Compose · Caddy (edge, auto-HTTPS) · nginx · Postgres · MinIO                  | [`deploy/AGENTS.md`](deploy/AGENTS.md)    |
| `docs/`       | Project documentation — **English, source of truth** (served live at `/docs`) | Markdown                                                                              | managed via the **docs-management** skill |
| `impl_specs/` | Historical implementation handoffs (specs, prototypes) — **not canon**; on conflict `docs/` wins | Markdown · HTML                                                    | —                                         |

**Read the relevant `AGENTS.md` before working in a directory.** There is no
workspace-level package manager; `backend/` uses `uv`, `web/` and `e2e/` each
have their own `pnpm` project.

## Run it locally

**A. All in Docker (hot reload):**

```bash
cd deploy && cp .env.dev.example .env && docker compose up --build
# web → :5173 · API → :8000 · docs → :8000/docs · Postgres → :5432 · MinIO → :9000 (console :9001)
```

**B. On the host (data services in Docker):**

```bash
docker compose -f deploy/compose.yaml up -d postgres minio createbuckets
cd backend && cp .env.dev.example .env && uv sync && uv run alembic upgrade head && uv run fastapi dev app/main.py   # :8000
cd web && pnpm install && pnpm dev                                                        # :5173, proxies /api → :8000
```

Full recipe — seeding, API tokens, browser login, PDF checks — is the **verify** skill. Traps:

- A host Postgres already listening on :5432 **shadows the docker one** for every
  `localhost:5432` DSN (alembic, e2e seeding, host-run backend all hit the wrong server).
  Free the port, or reach the container via the machine's LAN IP.
- `bash deploy/seed-demo.sh` (demo data; credentials in the script header; `--reset` wipes
  volumes and re-seeds) requires the **docker** backend container — it execs `app.cli`
  inside it. It cannot seed a host-run backend.
- E2E boots and owns its own stack — **stop the docker `backend` and `web` containers
  before `pnpm test`** (see `e2e/AGENTS.md` for why reuse silently breaks the suite).

## Check gates

While iterating, run only the touched project's checks — single test file first
(`uv run pytest tests/test_x.py` · `pnpm test src/path` · `cd e2e && pnpm test tests/x.spec.ts`).
The full chains below are the **pre-push** bar; CI mirrors them exactly. (Locally,
`pnpm build` re-runs `vue-tsc`, so build subsumes typecheck.)

- `backend/`: `uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest`
- `web/`: `pnpm lint:check && pnpm format:check && pnpm typecheck && pnpm i18n:check && pnpm test && pnpm build`
- `e2e/`: `pnpm typecheck && pnpm test`

> ⚠️ CI (`.github/workflows/ci.yml`) mirrors these gates and **auto-deploys to production on a
> green push to `main`** — merging to `main` is an unattended prod deploy. Do risky work on a
> feature branch / PR and merge deliberately. CI/CD flow, prod topology, infra contract:
> [`deploy/AGENTS.md`](deploy/AGENTS.md).

The web gate does **not** run the Playwright suite. When changing UI flows, labels, or
dialogs, grep `e2e/tests/` for affected locators and run the touched spec — locator drift
ships silently otherwise.

## How to work

- Plan first for anything that spans modules or adds surface (API / schema / entity /
  feature). For feature work, encode the target state into `docs/` before or alongside the
  implementation — writing the spec is itself a design check.
- Design to the operating envelope in [`docs/architecture.md`](docs/architecture.md) — no
  higher, no lower. Default to the boring, smaller thing; before adding a service, queue,
  cache, or layer, name the present problem it solves, with a number behind it. **Boring
  caps complexity, not quality**: within the simple shape the bar stays at craftsmanship —
  handled edge cases, real error paths, tight naming, polished screens. Simplicity is a
  design constraint, never permission for sloppy work.
- Load the matching skill **before** working in its area — each carries project rules the
  code can't show:
  - anything under `docs/` (create, edit, move, review, "where does this go?") → **docs-management**
  - test strategy (what to test, where a test belongs, unit vs. E2E) → **testing-practices**
  - launching / driving the running app (seed, tokens, browser login, PDFs) → **verify**
- **Verify like a user, not just a compiler.** The check gates are necessary, not
  sufficient. For any change with a runtime surface, run the app locally, seed realistic
  data with `bash deploy/seed-demo.sh` when an empty stack won't exercise the flow, and
  drive the affected flow in a real browser — states, layout, copy. UI work must also clear
  the design system and UX bar in [`web/DESIGN.md`](web/DESIGN.md).

## Conventions

- Work happens on feature branches off `main`; commit only when asked.
- API surface is owned by the backend (`/api/v1`); the web client talks to it through `web/src/shared/api/client.ts`. In every environment the API is same-origin under `/api` (Vite proxy in dev, Caddy edge in prod) — don't hardcode `localhost:8000` in app code.
- Pin versions (Docker image tags, `packageManager`, `requires-python`, lockfiles are committed). Don't introduce `latest`.
- Add new dependencies via the project's tool (`uv add`, `pnpm add`) so the lockfile updates.

### Convention over Configuration

Prefer sensible behavior baked in over knobs the user must set. **Every config has a default**, and the default's _direction_ is deliberate:

- **Non-security config → leans to dev.** `ENV=dev` out of the box; the dev conveniences
  (`DEBUG=true`, `TELEGRAM_LOGIN_DEV_MODE=true`) live in the `.env.dev.example` templates — copy
  the template and everything works, no edits.
- **Security config → leans to prod (fail safe).** The baked-in _code_ default is the
  locked-down one (`TELEGRAM_LOGIN_DEV_MODE=false`, `DEBUG=false`, auth required, no secret bypass).
  A misconfiguration must err toward refusing access, never toward opening it. Secrets have
  **no real default** — they're `{{change-me}}` placeholders that must be set.

**Env files come in two committed templates per subproject** — kept in sync across `backend/`, `web/`, `deploy/`: `.env.dev.example` (ready-to-use dev defaults) and `.env.prod.example` (same shape; secrets as `{{change-me}}`, non-security values prod-sane). Real `.env` files are gitignored. A new setting is added to `Settings` (`backend/app/core/config.py`) with a default that follows the direction rule, then surfaced in all four backend-relevant templates (`backend/` + `deploy/`, dev + prod).
