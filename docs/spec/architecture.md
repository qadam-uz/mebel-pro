---
title: Architecture
status: stable
owner: shape
updated: 2026-05-11
order: 50
related:
  - docs/spec/envelope.md
  - docs/spec/nfr.md
  - docs/spec/domain-model.md
  - docs/spec/access.md
  - docs/ref/ux/information-architecture.md
---

# Architecture

The technical shape of the system, the few decisions that are expensive to change, and the
cross-cutting concerns — everything else is kept cheap to change. Calibrated to the operating
envelope ([`docs/spec/envelope.md`](envelope.md)): a Tier-2 internal/business SaaS for a modest
population of furniture workshops and their customers, money-bearing on one axis, run by a small
team. So: no microservices, no queues on the hot path, no caching layer until something is *measured*
slow, boring widely-known tech (FastAPI · SQLAlchemy · Postgres · Vue · Tailwind).

## Topology

```
                         ┌────────────────────────────────────────────────────┐
   Internet              │  edge — Caddy (deploy/Caddyfile)                     │
  ───────────▶  ───────▶ │  terminates HTTPS · auto-renews the Let's Encrypt   │
                         │  cert · only published service in prod              │
                         │   /            → static SEO landing (1 HTML)        │
                         │   /app/client  → client SPA  (static dist)          │
                         │   /app/seh     → workshop SPA (static dist)         │
                         │   /app/admin   → superadmin SPA (static dist)       │
                         │   /api         → FastAPI backend                    │
                         │   /docs · /api-docs · /api-redoc → backend (Basic)  │
                         └──────────────────────────┬─────────────────────────┘
                                     ┌──────────────▼─────────────┐
                                     │  FastAPI app (1 process)   │
                                     │  modular monolith — see    │
                                     │  "The module map" below    │
                                     │  + in-process scheduler    │
                                     │  + live docs site (/docs)  │
                                     └───┬───────────────┬────────┘
                                ┌────────▼──────┐  ┌─────▼──────────┐
                                │  PostgreSQL   │  │  MinIO / S3    │
                                │  (single DB)  │  │  (file store)  │
                                └───────────────┘  └────────────────┘
   external: Telegram Login (OAuth) — client authentication only
```

- **One backend process** — a FastAPI app (Python 3.12, async end-to-end: asyncio + asyncpg +
  SQLAlchemy 2.0, Alembic migrations, pydantic-settings). It also renders the `docs/` tree as a live
  site (see *Cross-cutting concerns → Documentation site*). Scale by adding replicas behind the Caddy edge
  if load ever demands; v1 needs one. Toolchain & layout: [`backend/CLAUDE.md`](../../backend/CLAUDE.md).
- **One database** — PostgreSQL, shared by all modules; each module owns its tables (see below).
- **One file store** — MinIO (S3-compatible): material images, workshop logos, refund/delivery
  receipts, cutting PDFs. The `files` module owns it; other modules attach/detach by id.
- **In-process scheduler** — background jobs (expire draft cuttings, notify pay-later overdue, notify
  stale refunds, prune expired sessions, daily low-stock summary) run inside the FastAPI app, not a
  separate worker fleet. See [`docs/ref/features/platform-ops.md`](../ref/features/platform-ops.md).
- **Three SPAs + a static landing** — see *Why three SPAs* below; route maps in [`docs/ref/ux/information-architecture.md`](../ref/ux/information-architecture.md). The API is same-origin under `/api`.
- **One external integration in v1** — Telegram Login (OAuth), client authentication only. Payment
  gateways, BNPL, SMS/email, a Telegram notification bot, geocoding are v1.1+ ([`docs/spec/scope-v1.md`](scope-v1.md)).
- **Deployment** — Docker Compose: Postgres + MinIO + the FastAPI app + the **web** container
  (nginx serving the built SPA bundles and the static landing) + a **Caddy edge** in front (the only
  published service in prod — it terminates HTTPS and auto-provisions/renews a Let's Encrypt
  certificate). The app container runs `alembic upgrade head` on start. Production deploys are
  automated: a push to `main` runs a GitHub Actions workflow that rsyncs the repo to the server and
  `docker compose … up -d --build`s the prod stack (no CI checks — the per-directory check gates run
  locally before the push). Full detail: [`deploy/CLAUDE.md`](../../deploy/CLAUDE.md).

## Why a modular monolith — not microservices

**Decision:** build the backend as **one FastAPI application**, code organized **layer-first**
(`app/models/`, `app/schemas/`, `app/services/`, `app/api/routes/` — one file per resource, mirrored
across the layers), with **modules as logical groupings** of those files by bounded context — not as
directories. The structural rules that make it a *modular* monolith: a module's code calls another
module's **service functions** directly (in-process, within the caller's transaction where one is
lent) — and never touches another module's tables or ORM models; routes thin, services fat; "The
module map" below is the contract for which file belongs to which module. No per-module package tree,
no hexagonal layering, no portal/embassy indirection — the framework + the layered directories give
the structure, and the one rule that matters ("don't reach into another module's tables") is held by
convention + review.

**Why, against the envelope:** tens of workshops, low-thousands of clients, flat growth, a two-ish
person team, money-bearing on one axis but not regulated, one bounded synchronous hot operation
(cutting). Nothing here pressures for distribution. Alternatives weighed and rejected:
*microservices* — the operational cost (many deploys, network boundaries, distributed transactions,
cross-service observability) buys nothing at this scale; pure over-engineering. *Per-module
hexagonal + portal/embassy* (the old codebase's shape, ported) — in a FastAPI + SQLAlchemy stack the
framework already gives the structure; the extra layers collapse into pass-through code without
buying anything the convention + review don't. *Per-module Python packages* (`app/orders/…`,
`app/identity/…`) — plausible, but it fights the FastAPI/SQLAlchemy grain (Alembic autogenerate wants
all models reachable; routers/schemas/services naturally read layer-first) and the boundary it'd
enforce is the table-access rule, which a directory wall doesn't actually enforce anyway; layer-first
+ the module map gets the navigability for less. *Flat, no logical modules at all* — the domain has
clear bounded contexts; naming them (the module map below) and holding the no-cross-module-tables
line keeps the codebase navigable as it lives for years.

**Consequences:** one deploy, one DB, one log stream; refactoring across module lines is cheap
(it's all one process); a small team holds the whole thing in its head. Costs: module boundaries are
a convention, not a wall — review keeps them honest; a single hot module can't be scaled
independently without first being extracted (no such pressure exists). **Revisit when** a module
develops a scaling/fault-isolation need the rest doesn't share, or the team outgrows one-codebase-
one-deploy coordination — not on vibes, not on a schedule; the module boundaries are exactly where
you'd cut.

### The module map

A "module" is the set of files — across `app/models/`, `app/schemas/`, `app/services/`,
`app/api/routes/` — for one bounded context. This table is the authoritative mapping; cross-module
work goes through the owning module's **service** layer (never its tables/models).

| Module | Owns | Notes |
|---|---|---|
| `identity` | platform users, workshop users, permission grants, clients, sessions; login/logout/refresh; Telegram OAuth; brute-force lockout; the authz checks | The auth/authz core — [`docs/spec/access.md`](access.md). |
| `workshop` | workshops + settings, branches, workers | The tenant structure. |
| `catalog` | materials, branch pricing | Per branch. |
| `inventory` | stock items, stock transactions; reserve / consume / release / transfer / stock-in / adjust | Atomic stock ops (row-lock). Reserve/consume/release driven by `orders`. |
| `cutting` | cutting results, sheets, placements; the optimizer; PDF; draft cleanup | Synchronous, ≤ 100 parts, 5 s; results are immutable snapshots — [`docs/spec/cutting.md`](cutting.md). |
| `orders` | orders, items, payments, status events, cancellations, refunds; the state machine; pricing snapshot; modify; recording payments; refund tracking | The highest-criticality module; orchestrates `cutting`, `inventory`, `catalog` — [`docs/spec/orders.md`](orders.md). |
| `files` | file blobs + entity attachments (MinIO/S3) | Other modules attach/detach by id; a mutating attach borrows the caller's transaction. |
| `audit` | the action log + the status-change log | Every mutating use case writes here; append-only. |
| `notifications` | the in-app inbox; unread counts; mark-read | Populated by the producing modules; polled by the SPAs — see *Cross-cutting concerns → Notifications*. |
| `platform` | scheduled-jobs console, error monitor, platform-user management | Superadmin-app surfaces; no business entities of its own — [`docs/ref/features/platform-ops.md`](../ref/features/platform-ops.md). |

Dependency direction: `orders` → `cutting`, `inventory`, `catalog`, `audit`, `notifications`,
`files`; `catalog`/`inventory`/`cutting` → `workshop`, `audit`; `workshop` → `identity`, `audit`;
everything → `identity` (authz). The only cycle among business modules is the narrow, deliberate
`identity ↔ workshop` seam (who-belongs-to-which-tenant).

## Why three SPAs + a static landing

**Decision:** the web deliverable is (1) a single **SEO-optimized static landing page** — one HTML
file, plain markup + minimal CSS/JS, *not* part of the Vue repo, served at `/`; and (2) a **Vue 3 /
Vite repo (`web/`)** building **three SPAs**, each its own entry, auth surface, and route set:
**client app** (Telegram-auth customers — cutting + ordering + tracking), **seh (workshop) app**
(login-auth workshop owner & staff — every screen gated by the user's permission grants;
[`docs/spec/access.md`](access.md)), **superadmin app** (login-auth platform operators — workshop
provisioning, block/unblock, cross-workshop incident lookup, platform users, scheduled-jobs console,
error monitor). Shared UI primitives, the API client, the design tokens, and i18n live once in the
repo; each app has its own routes/views/stores. Detail & route maps: [`docs/ref/ux/information-architecture.md`](../ref/ux/information-architecture.md).

**Why:** the three audiences barely overlap, and a public marketing page needs to be indexable —
which an SPA shell is bad at. Alternatives rejected: *one SPA, role-gated* (the old shape) — ships
every audience's code to every user, bloats the customer's bundle with admin/ops screens, mixes auth
surfaces, and still doesn't solve the landing page; *one SPA + a separate landing, staff & platform
sharing the SPA* — the platform-operator surface is genuinely different (no tenant scope, ops
tooling) and tiny, not worth bundling into the staff app; *SSR/Nuxt for the landing* —
over-engineered for a mostly-static page. **Consequences:** each app ships only its own code; auth
surfaces don't mix; the marketing page is fast and indexable. Costs: three build entries / deploy
artifacts (one repo); shared code needs deliberate placement; the landing is maintained outside the
Vue tooling. **Revisit when** two apps converge enough that separate maintenance is pure overhead,
or the landing grows to need a framework, or a fourth audience appears.

## Data model — shape & invariants

- **UUID primary keys everywhere.** Cross-module references are UUID + a logical "lives in module X"
  contract — *not* a DB foreign key across module boundaries (FKs are fine *within* a module).
- The invariants below are enforced across the model. They are architectural decisions, so the *why*
  lives here; `orders.md`, `cutting.md`, `nfr.md`, and the entity docs **link here, never restate**.

| Invariant | What | Why |
|---|---|---|
| **Integer-tiyin money** | every currency value — DB column, API field, intermediate computation — is integer tiyin (1 UZS = 100 tiyin); the frontend converts for display only | money is the high-criticality axis; floating-point currency is a bug waiting to happen |
| **Soft delete only** | workshops, branches, materials, workers, workshop/platform users go to an `inactive`/`blocked` status — there is no `DELETE` path for them; history (orders, audit, status events, confirmed/invalidated cutting results) is kept forever | old orders, the audit trail, and old cutting PDFs reference these; deletion would orphan history. (The one exception: *draft* cutting results — anti-abuse cruft, pruned after 7 days.) |
| **Snapshot pricing** | when an order is created (or re-priced on modify), every price component, the material details & unit prices used, and the cutting-result reference are copied onto the order/order-items; later catalog/pricing/zone changes never reach existing orders; order items also snapshot the input parts | an order's "what it cost / how it was cut" must not drift when the workshop edits its catalog or rates afterwards — [`docs/spec/orders.md`](orders.md) |
| **Immutable cutting results** | a `cutting_result` (with its sheets & placements) is written once and never mutated — only its `status` flips `draft → confirmed → invalidated` and the `order_id`/timestamps get set; the algorithm version is stamped on it | the PDF the shop floor cut from, and the metrics the order was priced on, must stay exactly as they were even when the optimizer is replaced — [`docs/spec/cutting.md`](cutting.md) |
| **Append-only audit & history** | `action_log`, `status_change_log`, `order_status_event` — write, never update or delete | the trail is the asset; its value is that it stays intact |
| **Optimistic locking on order transitions** | a `version` column on `orders`; a transition that loses the race is rejected and retried | concurrent workshop edits must serialize, not clobber |
| **Atomic stock operations** | reserve / consume / release row-lock the stock row (`FOR UPDATE`) for the duration | two confirmations can't double-spend the last sheet — [`docs/spec/orders.md`](orders.md) |

## Cross-cutting concerns

- **Authentication, authorization & tenancy** — three principal types, three auth surfaces; opaque
  DB-backed sessions with instant revocation; coarse-grained per-branch workshop permissions;
  multi-tenant isolation checked at the service layer on every read and write. The single home:
  [`docs/spec/access.md`](access.md).
- **API surface** — REST/JSON under `/api/v1`. List responses wrap items in `content`; paginated
  responses add `page_number`/`page_size`/`count`. Errors are one envelope: `trace_id` +
  `error{ code, message, fields?, details? }` — `code` machine-readable, `message` user-facing
  (localized server-side). `X-Trace-ID` on every response. The web client talks to it through
  [`web/src/api/client.ts`](../../web/src/api/client.ts); never hardcode `localhost:8000`.
- **Errors** — routes raise `HTTPException` (or a subclass) with a stable `code` for client-facing
  failures; unexpected errors propagate, 500, and are logged + recorded by the error monitor.
- **Audit** — every mutating use case writes an `action_log` row (who, what, when, target,
  before/after where meaningful); every order status transition writes a `status_change_log` row.
  Append-only (see *Data model invariants*); surfaced in the seh app and the superadmin app —
  [`docs/ref/features/audit-log.md`](../ref/features/audit-log.md).
- **Logging & observability** — structlog, with the trace id on every line. `GET /api/v1/healthz`
  (liveness), `GET /api/v1/readyz` (DB check) — both unauthenticated (container healthchecks hit
  them). Application errors are recorded by the `platform` module's error monitor.
- **Documentation site** — the backend renders the repo's `docs/` Markdown tree as a browsable site
  at `/docs` (rendered on the fly, no build step; nav built from the tree + frontmatter; in dev,
  edit a file and refresh). The OpenAPI UIs live alongside it at `/api-docs` (Swagger) and
  `/api-redoc` (ReDoc); the schema is at `/api/v1/openapi.json`. **All four are gated by one HTTP
  Basic credential** (`DOCS_AUTH_USERNAME` / `DOCS_AUTH_PASSWORD`) — these are internal/dev
  surfaces, not product. Implementation: [`backend/CLAUDE.md`](../../backend/CLAUDE.md).
- **Configuration** — `pydantic-settings` ([`backend/app/core/config.py`](../../backend/app/core/config.py)); env / `.env`. Env contracts kept in sync across `backend/.env.example`, `web/.env.example`, `deploy/.env.example`.
- **Background jobs** — the in-process scheduler runs: `expire-stale-draft-cuttings` (drop `draft`
  cutting results > 7 days old, with their sheets/placements), `notify-pay-later-overdue`,
  `notify-stale-refunds` (`pending` refunds > 7 days), `cleanup-expired-sessions`, the daily
  low-stock summary. Console & monitoring: [`docs/ref/features/platform-ops.md`](../ref/features/platform-ops.md).
- **Notifications** — v1's only channel is an **in-app inbox** per principal. Delivery is *pull*:
  the SPAs poll an unread-count endpoint (~30–60 s) and the list endpoint on demand — no
  WebSocket/SSE. A producing module (`orders`, `inventory`, `identity`, `workshop`, `platform`)
  calls the `notifications` module on a notifiable event, asking it to fan out one row per recipient
  with the producer's scope rules applied (it doesn't broadcast); each notification carries an
  `event_code`, the subject entity (`entity_type` + `entity_id` for the deep link), and a small
  denormalized `payload` so the inbox renders without extra lookups. Critical events also fire a
  toast. SMS/email and a Telegram notification bot are v1.1 ([`docs/spec/open-questions.md`](open-questions.md) Q5); whether producers should emit domain events the `notifications` module subscribes to vs. calling it directly is Q11. Inbox screens: [`docs/ref/features/notifications-inbox.md`](../ref/features/notifications-inbox.md); the entity: [`docs/ref/entities/support/notification.md`](../ref/entities/support/notification.md).
