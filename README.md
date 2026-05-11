# Mebel Pro

A B2B2C platform for furniture-panel cutting in Uzbekistan: furniture workshops run their operations
(branches, materials, warehouse, workers, pricing, orders) in one system; their customers go online
to optimize a cutting plan and order panels cut to size.

A monorepo: a FastAPI multi-module-monolith backend (Postgres + MinIO/S3), a Vue 3 web repo whose
design is three SPAs (client / seh-workshop / superadmin) plus a static SEO landing page — currently
still the initial single-app scaffold (see `web/CLAUDE.md`) — Playwright E2E tests, and Docker
Compose deployment.

## Where things are

| Path | What |
|---|---|
| `docs/` | **The documentation** — start here. `docs/spec/` is the canon (vision, scope, personas, journeys, domain model, architecture, the `access` and `orders` and `cutting` system concerns, operating envelope, NFRs, open questions — decisions and their rationale live inside whichever of these owns the area); `docs/ref/` is the detail (per-feature specs, the entity catalog, the UX reference). The backend serves it as a live site. Managed via the **docs-management** skill — see `.claude/skills/`. |
| `backend/` | FastAPI service (Python 3.12, async SQLAlchemy 2.0, Alembic, Postgres, MinIO/S3, `uv`). See `backend/CLAUDE.md`. |
| `web/` | Vue 3 / Vite / TypeScript / Tailwind v4 web client (`pnpm`) — target: three SPAs + a static landing; today a single scaffold app. See `web/CLAUDE.md`. |
| `e2e/` | Playwright end-to-end tests (`pnpm`). See `e2e/CLAUDE.md`. |
| `deploy/` | Docker Compose + nginx + Postgres + MinIO orchestration. See `deploy/CLAUDE.md`. |

Root `CLAUDE.md` has the run-it-locally instructions and the per-directory check gates.

## Read the docs

New here? Read `docs/spec/` start to finish (it's meant to fit in one sitting) plus
`docs/spec/domain-model.md`, then dip into `docs/ref/features/` for whatever you're working on.
