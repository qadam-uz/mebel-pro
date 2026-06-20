# Mebel Pro

Documentation is the source of truth. Always keep it up to date as you work, following the
**docs-management** skill. If what the user asks and what the docs say disagree, tell the user
the conflict points and consolidate them together.

`docs/` is the single source of truth, in English. Agents and humans work only
from it; all reasoning, planning, editing, and the docs-management skill operate
there. It is served live at `/docs`.

Furniture-panel cutting platform — see [`docs/index.md`](docs/index.md) (what
it is) and [`docs/architecture.md`](docs/architecture.md) (the technical shape:
modular-monolith backend, three SPAs + static landing, topology, invariants).
Make sure to ALWAYS read all canon specs at docs/ and read other specs (features, entities) on-demand.
The repo map below is the working layout.

## Repo map

| Path       | What                                                                          | Stack                                                                                 | Details                                                                     |
| ---------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `backend/` | REST API (JSON, `/api/v1`)                                                    | Python 3.12 · FastAPI · async SQLAlchemy 2.0 · Alembic · Postgres · MinIO/S3 · **uv** | [`backend/AGENTS.md`](backend/AGENTS.md)                                    |
| `web/`     | Web client (target: 3 SPAs + static landing)                                  | Vue 3 · Vite 7 · TypeScript · Pinia · Vue Router · Tailwind v4 · Vitest · **pnpm**    | [`web/AGENTS.md`](web/AGENTS.md)                                            |
| `e2e/`     | End-to-end browser tests                                                      | Playwright · TypeScript · **pnpm**                                                    | [`e2e/AGENTS.md`](e2e/AGENTS.md)                                            |
| `deploy/`  | Container orchestration                                                       | Docker Compose · Caddy (edge, auto-HTTPS) · nginx · Postgres · MinIO                  | [`deploy/AGENTS.md`](deploy/AGENTS.md)                                      |
| `docs/`    | Project documentation — **English, source of truth** (served live at `/docs`) | Markdown                                                                              | managed via the **docs-management** skill                                   |

Each subproject is self-contained with its own toolchain and `AGENTS.md` —
**read the relevant one before working in that directory.** There is no
workspace-level package manager; `backend/` uses `uv`, `web/` and `e2e/` each
have their own `pnpm` project.

## Run it locally

Two options:

**A. All in Docker (hot reload):**

```bash
cd deploy && cp .env.dev.example .env && docker compose up --build
# web → http://localhost:5173 · API → http://localhost:8000 · docs → http://localhost:8000/docs · Postgres → :5432 · MinIO → :9000 (console :9001)
```

**B. On the host (data services in Docker):**

```bash
docker compose -f deploy/compose.yaml up -d postgres minio createbuckets
cd backend && uv sync && uv run alembic upgrade head && uv run fastapi dev app/main.py   # :8000 (docs at :8000/docs)
cd web && pnpm install && pnpm dev                                                        # :5173, proxies /api → :8000
```

E2E: `cd e2e && pnpm install && pnpm install:browsers && pnpm test` (boots the dev stack itself; needs `uv` + a reachable Postgres — see `e2e/AGENTS.md`).

## Per-directory check gates (run before pushing)

- `backend/`: `uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest`
- `web/`: `pnpm lint:check && pnpm format:check && pnpm typecheck && pnpm test && pnpm build`
- `e2e/`: `pnpm typecheck && pnpm test`

CI (`.github/workflows/ci.yml`) mirrors these gates and auto-deploys to the VPS on a green push to `main` — see [`deploy/AGENTS.md`](deploy/AGENTS.md) for the CI/CD flow, prod topology, and infra contract.

## Development workflow

Every task is **triaged** into one of two flows before any work starts. The
router lives here (always loaded); the step-by-step procedures live in
`.workflows/playbooks/` and you **MUST read the matching playbook and follow it
exactly** before acting.

| Task                                                                                                                                                       | Flow                                                                |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| **Trivial** — a localized, low-risk change with no design decisions: typo, copy, comment, config nudge, an obvious one-line fix, a dependency bump          | [`.workflows/playbooks/trivial.md`](.workflows/playbooks/trivial.md) |
| **Complex** — everything else: anything needing a decision, touching >1 module, adding surface (API / schema / entity / feature), or where the "how" isn't obvious | [`.workflows/playbooks/complex.md`](.workflows/playbooks/complex.md) |

- **When in doubt, go complex.** There is no middle tier — medium work runs the full pipeline.
- **Promotion:** if a trivial task reveals a decision, a missing acceptance criterion, a missing/contested requirement, or cross-cutting changes → **stop, switch to complex, restart at its Plan stage.** Never finish a complex task on the trivial flow.
- Worktrees (`.worktrees/`) and per-run scratch (`.workflows/plan.md`, `.workflows/progress.md`) are gitignored; the playbooks under `.workflows/playbooks/` are committed canon.

Use subagents for long-running or fan-out work to keep the main conversation focused.

### Skills are NON-NEGOTIABLE

**Skills are not optional suggestions. Before you act on any task that matches a
trigger below, you MUST invoke the matching skill via the Skill tool — FIRST,
before writing, editing, reviewing, or planning anything in that area. This is a
hard, blocking requirement. Do not rely on memory, do not improvise the skill's
guidance from your own knowledge, and never silently skip a skill. If a task
touches more than one area, load every matching skill. When in doubt, load it.**

| If the task touches…                                                                                                                                                         | You MUST first invoke     |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| Anything under `docs/` — create, edit, move, organize, review docs; ask where a doc belongs; suspect stale/duplicated/orphaned docs                                          | **docs-management**       |
| System/tech decisions, stack/topology, service boundaries, costly-to-reverse architecture choices (recorded inline in the doc that owns the area — no separate ADR register) | **software-architecture** |
| Screens, flows, navigation, UX specs, component design, "this feels off" feedback                                                                                            | **ui-ux-mastery**         |
| Frontend implementation polish                                                                                                                                               | **frontend-design**       |
| Test strategy — where a test belongs, unit vs. integration vs. E2E                                                                                                           | **testing-practices**     |

## Conventions

- Work happens on feature branches off `main`; commit only when asked.
- API surface is owned by the backend (`/api/v1`); the web client talks to it through `web/src/shared/api/client.ts`. In every environment the API is same-origin under `/api` (Vite proxy in dev, Caddy edge in prod) — don't hardcode `localhost:8000` in app code.
- Pin versions (Docker image tags, `packageManager`, `requires-python`, lockfiles are committed). Don't introduce `latest`.
- Add new dependencies via the project's tool (`uv add`, `pnpm add`) so the lockfile updates.

### Convention over Configuration

Prefer sensible behavior baked in over knobs the user must set. **Every config has a default**, and the default's _direction_ is deliberate:

- **Non-security config → default leans to dev.** Convenience for the common local case (e.g. `ENV=dev`, `DEBUG=true`, verbose logs, a dev OTP code present). Running with zero configuration should give a working dev setup.
- **Security config → default leans to prod (fail safe).** The baked-in default is the _locked-down_ one (e.g. an empty `OTP_DEV_CODES`, auth required, no secret bypass). A misconfiguration must err toward refusing access, never toward opening it. Secrets have **no real default** — they're `{{change-me}}` placeholders that must be set.

**Env files come in two committed templates per subproject** — kept in sync across `backend/`, `web/`, `deploy/`:

- **`.env.dev.example`** — ready-to-use dev defaults; copy to `.env` and run, no edits needed.
- **`.env.prod.example`** — same shape; every secret/security value is a `{{change-me}}` placeholder, non-security values carry prod-sane settings.

Real `.env` files are gitignored; only the two `*.example` templates are committed. A new setting is added to `Settings` (`backend/app/core/config.py`) with a default that follows the direction rule above, then surfaced in both templates.
