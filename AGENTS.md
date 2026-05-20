# Mebel Pro

WE ARE CURRENTLY AT THE STAGE OF DEVELOPING BUSINESS LOGIC,
THE BEST USER EXPERIENCE, AND PROTOTYPING.
CONSIDER THIS WHEN MAKING DECISIONS, GIVING OPTIONS, AND ASKING QUESTIONS.
DON'T BE AFRAID TO MAKE FUNDAMENTAL CHANGES IF NECESSARY.
WE TREAT THE PROTOTYPE (IN THE FORM OF HTML FILES, IN `web/prototypes/`)
AS A SERIOUS, CONFIDENT STARTING POINT — NOT A DRAFT THAT CAN BE THROWN AWAY.
WE TREAT DOCUMENTATION AS THE SOURCE OF TRUTH. ALWAYS KEEP DOCUMENTATION
UP TO DATE, FOLLOWING THE docs-management SKILL GUIDELINES.
IF WHAT USER ASK AND WHAT THE DOCS SAY DO NOT AGREE, TELL TO USER
THE CONFLICT POINTS AND CONSOLIDATE THEM TOGETHER.

## Documentation language — English canon, Uzbek mirror

- **`docs/`** is the single source of truth, in English. Agents and humans work
  **only** from it; all reasoning, planning, editing, and the docs-management
  skill operate here.
- **`docs_uz/`** is a read-only Uzbek mirror — a generated artifact, never a
  source. **Agents must never read or reason over it.** Translation flows one
  way: `docs/` → `docs_uz/`, never the reverse.
- The mirror is **1:1** with `docs/` — identical paths, structure, code blocks,
  link targets, mermaid node IDs, and **frontmatter (incl. `title:`) byte for
  byte**. Only connective prose is rendered into Uzbek; **every technical/
  domain/feature/role term, status value, and identifier stays English** (when
  in doubt, keep it English). It reads as Uzbek grammar carrying English terms.
- **When you change a `docs/` page, regenerate its `docs_uz/` counterpart in
  the same change** — they must never drift; if they do, `docs/` wins.
- Both are served live: `docs/` at `/docs`, `docs_uz/` at `/docs-uz`, each page
  linking to its counterpart.

Furniture-panel cutting platform — see [`docs/index.md`](docs/index.md) (what
it is) and [`docs/architecture.md`](docs/architecture.md) (the technical shape:
modular-monolith backend, three SPAs + static landing, topology, invariants).
Make sure to ALWAYS read all canon specs at docs/ and read other specs (features, entities) on-demand.
The repo map below is the working layout.

## Prototypes

- `prototype-full` is the "full" version of the prototype, with all features.
- `prototype-{style}` is the "style" version of prototypes, with only the 1-2 pages for each role for defining design system of apps.

## Repo map

| Path       | What                                                                          | Stack                                                                                 | Details                                                                     |
| ---------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `backend/` | REST API (JSON, `/api/v1`)                                                    | Python 3.12 · FastAPI · async SQLAlchemy 2.0 · Alembic · Postgres · MinIO/S3 · **uv** | [`backend/AGENTS.md`](backend/AGENTS.md)                                    |
| `web/`     | Web client (target: 3 SPAs + static landing)                                  | Vue 3 · Vite 7 · TypeScript · Pinia · Vue Router · Tailwind v4 · Vitest · **pnpm**    | [`web/AGENTS.md`](web/AGENTS.md)                                            |
| `e2e/`     | End-to-end browser tests                                                      | Playwright · TypeScript · **pnpm**                                                    | [`e2e/AGENTS.md`](e2e/AGENTS.md)                                            |
| `deploy/`  | Container orchestration                                                       | Docker Compose · Caddy (edge, auto-HTTPS) · nginx · Postgres · MinIO                  | [`deploy/AGENTS.md`](deploy/AGENTS.md)                                      |
| `docs/`    | Project documentation — **English, source of truth** (served live at `/docs`) | Markdown                                                                              | managed via the **docs-management** skill                                   |
| `docs_uz/` | Uzbek **mirror** of `docs/` — derived, read-only (served live at `/docs-uz`)  | Markdown                                                                              | generated from `docs/`; never a source — see _Documentation language_ above |

Each subproject is self-contained with its own toolchain and `AGENTS.md` —
**read the relevant one before working in that directory.** There is no
workspace-level package manager; `backend/` uses `uv`, `web/` and `e2e/` each
have their own `pnpm` project.

## Run it locally

Two options:

**A. All in Docker (hot reload):**

```bash
cd deploy && cp .env.example .env && docker compose up --build
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

Feature work follows: **brainstorm → write docs (on a feature branch) → human review of docs → break into a plan → execute → review/fix → verify → human verify.** Supporting skills: **software-architecture** (system/tech decisions, recorded inline in the doc that owns the area — no separate ADR register), **ui-ux-mastery** (screens, flows, UX specs), **frontend-design** (frontend implementation polish), **docs-management** (anything under `docs/`), **testing-practices** (where a given test belongs). Reach for them as the workflow indicates.
Use subagents with session fork mode for long running jobs to keep main conversation clean and focused.

## Conventions

- Work happens on feature branches off `main`; commit only when asked.
- API surface is owned by the backend (`/api/v1`); the web client talks to it through `web/src/api/client.ts`. In every environment the API is same-origin under `/api` (Vite proxy in dev, Caddy edge in prod) — don't hardcode `localhost:8000` in app code.
- Keep env contracts in sync: `backend/.env.example`, `web/.env.example`, `deploy/.env.example`. Real `.env` files are gitignored.
- Pin versions (Docker image tags, `packageManager`, `requires-python`, lockfiles are committed). Don't introduce `latest`.
- Add new dependencies via the project's tool (`uv add`, `pnpm add`) so the lockfile updates.
