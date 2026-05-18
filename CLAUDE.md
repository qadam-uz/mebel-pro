# Mebel Pro

WE ARE CURRENTLY AT THE STAGE OF DEVELOPING BUSINESS LOGIC,
THE BEST USER EXPERIENCE, AND PROTOTYPING.
CONSIDER THIS WHEN MAKING DECISIONS, GIVING OPTIONS, AND ASKING QUESTIONS.
DON'T BE AFRAID TO MAKE FUNDAMENTAL CHANGES IF NECESSARY.
WE TREAT THE PROTOTYPE (IN THE FORM OF HTML FILES, IN `web/prototypes/`)
AS A SERIOUS, CONFIDENT STARTING POINT — NOT A DRAFT THAT CAN BE THROWN AWAY.
WE TREAT DOCUMENTATION AS THE SOURCE OF TRUTH. ALWAYS KEEP DOCUMENTATION
UP TO DATE, FOLLOWING THE docs-management SKILL GUIDELINES.
IF WHAT I ASK AND WHAT THE DOCS SAY DO NOT AGREE, TELL ME
THE CONFLICT POINTS AND WE'LL CONSOLIDATE THEM TOGETHER.

## Documentation language — English canon, Uzbek mirror

The project keeps **two** documentation trees:

- **`docs/` — the single source of truth, in English.** Both agents and humans
  work from this. All reasoning, planning, editing, and the docs-management
  skill operate **only** here.
- **`docs_uz/` — a read-only Uzbek mirror of `docs/`,** for Uzbek-speaking
  team members. It is a **generated artifact**, not a source.

Hard rules:

- Translation flows **one way only: `docs/` → `docs_uz/`. Never the reverse.**
- **Agents must never treat `docs_uz/` as a source** — don't read it to answer
  questions, don't reason over it, don't let it drive a decision. The only
  permitted write to `docs_uz/` is regenerating a page from its `docs/`
  original after that original changed.
- `docs_uz/` mirrors `docs/` **1:1** — identical paths, structure, code blocks,
  link targets, mermaid node IDs, and **frontmatter (including `title:`) byte
  for byte**.
- **Only the natural-language prose is rendered into Uzbek — for readability,
  not as a full translation.** Keep **every technical and domain term, concept,
  and product/feature/role name in English**: entity and role names, feature
  names, architecture & CS vocabulary (state machine, invariant, idempotent,
  scheduler, queue, cache, tenant, migration, endpoint, schema, optimizer,
  nesting, kerf, grain, seam, snapshot, aggregate, bounded context, edge cases,
  …), status/enum values, identifiers. Translate only the connective sentences
  around them. **When in doubt, keep it English.** The result reads the way an
  Uzbek engineering team actually talks: Uzbek grammar carrying English terms.
- **When you change a `docs/` page, regenerate its `docs_uz/` counterpart** so
  the two stay in sync. If they drift, `docs/` wins. But they should never drift. Keep them in sync.
- Both are served live by the backend — `docs/` at `/docs`, `docs_uz/` at
  `/docs-uz` — and every page links to its counterpart.

Furniture-management application. Monorepo: a FastAPI modular-monolith backend, a
Vue 3 web repo (the design is three SPAs — **client** / **workshop** /
**superadmin** — plus a static SEO landing page; the current `web/` tree is the
initial single-app scaffold, not yet split — see [`web/CLAUDE.md`](web/CLAUDE.md)
and [`docs/architecture.md`](docs/architecture.md)), Playwright E2E
tests, and Docker Compose deployment.

## Repo map

| Path       | What                                                                          | Stack                                                                                 | Details                                                                     |
| ---------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `backend/` | REST API (JSON, `/api/v1`)                                                    | Python 3.12 · FastAPI · async SQLAlchemy 2.0 · Alembic · Postgres · MinIO/S3 · **uv** | [`backend/CLAUDE.md`](backend/CLAUDE.md)                                    |
| `web/`     | Web client (target: 3 SPAs + static landing)                                  | Vue 3 · Vite 7 · TypeScript · Pinia · Vue Router · Tailwind v4 · Vitest · **pnpm**    | [`web/CLAUDE.md`](web/CLAUDE.md)                                            |
| `e2e/`     | End-to-end browser tests                                                      | Playwright · TypeScript · **pnpm**                                                    | [`e2e/CLAUDE.md`](e2e/CLAUDE.md)                                            |
| `deploy/`  | Container orchestration                                                       | Docker Compose · Caddy (edge, auto-HTTPS) · nginx · Postgres · MinIO                  | [`deploy/CLAUDE.md`](deploy/CLAUDE.md)                                      |
| `docs/`    | Project documentation — **English, source of truth** (served live at `/docs`) | Markdown                                                                              | managed via the **docs-management** skill                                   |
| `docs_uz/` | Uzbek **mirror** of `docs/` — derived, read-only (served live at `/docs-uz`)  | Markdown                                                                              | generated from `docs/`; never a source — see _Documentation language_ above |

Each subproject is self-contained with its own toolchain and `CLAUDE.md` —
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

E2E: `cd e2e && pnpm install && pnpm install:browsers && pnpm test` (boots the dev stack itself; needs `uv` + a reachable Postgres — see `e2e/CLAUDE.md`).

## Per-directory check gates (run before pushing)

- `backend/`: `uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest`
- `web/`: `pnpm lint:check && pnpm format:check && pnpm typecheck && pnpm test && pnpm build`
- `e2e/`: `pnpm typecheck && pnpm test`

CI mirrors these. `.github/workflows/ci.yml` runs the per-directory gates (backend, web, e2e typecheck) and a docker-build smoke job on every PR and every push to `main`; on a green push to `main` it then SSHes to the VPS and runs `deploy/scripts/deploy.sh`, which `git fetch`s the commit and brings the prod stack up (no registry, no rsync). Auto-HTTPS via the Caddy edge. See [`deploy/CLAUDE.md`](deploy/CLAUDE.md).

The prod stack does **not** run its own Postgres / MinIO — the VPS already provides them on an external Docker network (`infra-net`); the backend joins that network and reaches them by service name. Local dev still spins up its own data services via `compose.yaml`.

## Development workflow

Feature work follows: **brainstorm → write docs (on a feature branch) → human review of docs → break into a plan → execute → review/fix → verify → human verify.** Supporting skills: **software-architecture** (system/tech decisions, recorded inline in the doc that owns the area — no separate ADR register), **ui-ux-mastery** (screens, flows, UX specs), **frontend-design** (frontend implementation polish), **docs-management** (anything under `docs/`), **testing-practices** (where a given test belongs). Reach for them as the workflow indicates.

## Conventions

- Work happens on feature branches off `main`; commit only when asked.
- API surface is owned by the backend (`/api/v1`); the web client talks to it through `web/src/api/client.ts`. In every environment the API is same-origin under `/api` (Vite proxy in dev, Caddy edge in prod) — don't hardcode `localhost:8000` in app code.
- Keep env contracts in sync: `backend/.env.example`, `web/.env.example`, `deploy/.env.example`. Real `.env` files are gitignored.
- Pin versions (Docker image tags, `packageManager`, `requires-python`, lockfiles are committed). Don't introduce `latest`.
- Add new dependencies via the project's tool (`uv add`, `pnpm add`) so the lockfile updates.
