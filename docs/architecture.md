---
title: Architecture
status: stable
owner: shape
updated: 2026-08-15
order: 70
---

# Architecture

The system's situation, the technical shape that follows from it, and the invariants and
conventions every module respects.

## Operating envelope

**Tier 2 — internal/business SaaS.** Multi-tenant, modest scale, run by a small team. Not
high-traffic, not regulated — but it moves money on one axis, so that axis gets real rigor.

| Axis                | Where we are                                                                                                                                                                                            | Consequence                                                                                                                                                                                                            |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Scale**           | Tens of workshops · low hundreds of branches · low thousands of clients · low tens of thousands of orders/year. Flat-to-modest growth. Read-heavy. Hottest op: cutting (≤ 300 parts, synchronous, 10 s). | One Postgres, one FastAPI process (replicas if needed). No sharding, no cache layer until something is _measured_ slow.                                                                                                |
| **Criticality**     | Money (recorded income / expenses) and real stock movement back the orders. A wrong balance or a lost stock decrement is real harm.                                                                     | Integer-tiyin money (never float); atomic stock decrement / restore; append-only audit; idempotent seams; money tracked, not moved (recorded by hand in v1, no order-held payments).                                   |
| **Security**        | Public on the internet. Holds personal data, staff credentials, and operational business records. Worth attacking.                                                                                      | Hard authn/authz on every request; opaque DB-backed sessions with instant revocation; password hashing + lockout; least-privilege admin scope; multi-tenant isolation at the service layer on every read and write.   |
| **Latency**         | Back-office-ish — "a second or two" is fine. The one visible expensive op is cutting (10 s budget, synchronous; bigger jobs rejected, not queued in v1).                                                 | No async/queue on the hot path; cutting runs in-process within budget; background jobs on an in-process scheduler.                                                                                                     |
| **Lifespan × team** | Years; moderate change; ~2-person team.                                                                                                                                                                 | Modular monolith, boring tech (FastAPI · SQLAlchemy · Postgres · Vue · Tailwind), structure two people can operate at 3 a.m.                                                                                           |

**Not built for:** high traffic (no multi-region / cache / CDN — capacity work happens _if_ it's
needed); regulatory or audit-grade guarantees (the audit log is useful, not tamper-evident);
real-money movement in v1 (no gateway, no auto-refund, no settlement); offline operation; heavy
analytics / BI (dashboards are operational-DB aggregates).

## Current stage

**Production** — the app is deployed for real users and real workshop data. The bundled SPAs
are still the only API consumers, so internal API contracts may move with a coordinated deploy,
but database history is append-only once applied: create forward-only migrations, never rewrite
an applied migration to "clean up" history, and treat data removal or destructive backfills as
explicit production operations. Docs stay the source of truth, security defaults stay locked, and
the check gates run before shipping.

## Topology

```mermaid
flowchart TD
    Net([Internet])
    Edge["<b>Caddy edge</b><br/>terminates HTTPS · auto-renews Let's Encrypt<br/>only published service in prod"]
    App["<b>FastAPI app</b> (1 process)<br/>modular monolith · in-process scheduler<br/>+ live docs site (/docs)"]
    DB[("PostgreSQL<br/>single DB")]
    Files[("MinIO / S3<br/>file store")]
    TG([Telegram Gateway<br/>client OTP delivery only])

    Net ==>|HTTPS| Edge
    Edge ==> App
    App ==> DB
    App ==> Files
    App -.->|send verification code| TG
```

Caddy (config in `deploy/Caddyfile`) routes by **subdomain** under a single apex
(`BASE_DOMAIN`, e.g. `mebel-pro.uz`):

| Host                    | Target                                                                                                    |
| ----------------------- | --------------------------------------------------------------------------------------------------------- |
| `mebel-pro.uz`          | static SEO landing (1 HTML)                                                                               |
| `app.mebel-pro.uz`      | client SPA (+ `/api/*` → backend)                                                                         |
| `workshop.mebel-pro.uz` | workshop SPA (+ `/api/*` → backend)                                                                       |
| `admin.mebel-pro.uz`    | superadmin SPA (+ `/api/*` → backend, + `/docs` · `/api-docs` · `/api-redoc` → backend, HTTP Basic-gated) |

Each SPA stays same-origin with its API (no CORS).

The prod edge additionally fronts one unrelated project on the same VPS (**taqsim**, its own
domain) — a Caddyfile change here redeploys the edge for both projects; the coupling and its
failure mode are documented in the repo's `deploy/AGENTS.md`.

- **One FastAPI process** — Python 3.12, async end-to-end (asyncio + asyncpg + SQLAlchemy 2.0,
  Alembic, pydantic-settings). Also renders `docs/` as a live site.
- **One PostgreSQL** — shared by all modules; each module owns its tables.
- **One MinIO / S3** — decor photos, logos, and receipt attachments. The `support` module owns
  stored files; others attach/detach by id. Cutting PDFs are generated on demand from immutable
  cutting-result rows, not stored as file records in v1.
- **In-process scheduler** — platform maintenance jobs that stay inside the app process; in v1,
  this prunes expired sessions and expired OTP challenges.
- **Three SPAs + a static landing.** API same-origin under `/api`.
- **One external integration** — Telegram Gateway, used only to deliver client sign-in OTP codes.
- **Deployment** — Docker Compose: Postgres + MinIO + FastAPI + nginx-served web + Caddy edge
  (the only published service in prod — HTTPS + Let's Encrypt). Push to `main`.

## Backend modules

The backend is a **module-first modular monolith**. Modules share one FastAPI process, one
SQLAlchemy metadata registry, one Postgres database, and one request transaction; they do not
import another module's private ORM model implementation or private service functions. A module
may call another module only through that module's public API (`api.py`) or stable contracts
(`contracts.py`).

Cross-module behavior goes through `api.py`. If a same-transaction SQL query needs another
module's table class, it imports that class from the owning module's `contracts.py`, never from
the owning module's private `models.py` — that keeps the remaining persistence coupling explicit
without adding repository layers that would only forward SQLAlchemy calls in this envelope. The
per-module file conventions (naming, route placement, the `import_all_models()` registry, the
retired layer-first packages) are working instructions and live in the repo's
`backend/AGENTS.md`.

| Module | Owns |
|---|---|
| `access` | platform/workshop/client identity, sessions, OTP, password gates, permission checks |
| `client_portal` | client profile, public branch browsing, client-visible catalog reads |
| `workshop` | workshops, branches, branch context, workshop settings |
| `catalog` | manufacturers, platform dekorlar, branch materials (format + price), branch pricing |
| `inventory` | stock items, suppliers, stock transactions, stock consume/restore seams |
| `cutting` | cutting drafts, optimizer results, panel layouts, PDFs |
| `sales` | orders, order state transitions, frozen price snapshots, order status events |
| `finance` | income, expenses, settlement summaries, finance and production reports |
| `support` | files, audit/status logs, notifications inbox |
| `platform` | workshop provisioning orchestration, jobs, error monitor, platform users |

App-facing routes may compose module APIs, but they do not become domain owners. A client-portal
route that browses public branches still reads through `workshop`/`catalog`; a workshop route that
shows an order cutting plan still reads through `sales`/`cutting`.

## Three SPAs + a static landing

A static SEO landing page at `/` (plain HTML, indexable) plus a Vue 3 / Vite repo building
**three SPAs**, each its own entry, auth surface, and route set: **client** (Telegram OTP-auth
customers — cut, order, track), **workshop** (workshop owner & staff — every screen permission-gated),
**superadmin** (platform operators — provisioning, blocks, jobs console, error monitor). The
three audiences barely overlap, and a marketing page needs to be indexable — a single SPA can't
do both well. Shared primitives, the API client, design tokens, and i18n live once in the repo.
Design system: web/DESIGN.md

## Data-model invariants

Three rules every module respects.

- **Integer-tiyin money.** Every currency value — DB column, API field, intermediate computation
  — is integer tiyin (1 UZS = 100 tiyin). The frontend converts for display only. Money is the
  high-criticality axis; float currency is a bug waiting to happen.
- **No deletes for business entities.** Workshops, branches, dekorlar, branch materials, workshop and
  platform users go to an `inactive` / `blocked` status — there is no `DELETE` path, and no
  `deleted_at` / `is_deleted` flag; the active state is the status enum. History (orders, audit,
  status events, cutting results) is kept forever; deletion would orphan it.
- **A 2xx response means the write is committed.** The request transaction commits before the
  response is sent (the DB session dependency is `scope="function"`); a client may act on a
  success response immediately — its next request must see the write. The default FastAPI
  dependency scope commits *after* the response, which loses this guarantee: a success could
  reach the client while its write still fails to commit, and an immediate follow-up request
  (verify after OTP send, an authed call after login) races the commit.

## Quality requirements

The non-feature requirements the shape above has to satisfy. Where a feature/entity doc owns the
specifics, this section just states the requirement.

### Audit & traceability

- Every mutating use case writes an append-only `action_log` row; every order status transition
  writes an append-only `status_change_log` row.
- Every API response carries `X-Trace-ID`; errors include `trace_id` in the body. Unexpected
  500s use a generic public message unless `DEBUG=true`, where the response message is the
  scrubbed exception text.

### Performance budgets

- API reads: p95 < 500 ms under expected load.
- Cutting optimisation: 10 s hard timeout, synchronous; > 300 parts rejected (the caps' owning
  table: [`ref/features/cutting.md`](ref/features/cutting.md) → Limits); ≤ 30 parts target
  < 1 s.
- PDF generation: synchronous, in-process; seconds, not minutes.

### Observability

- Structured logging (structlog) with the trace id on every line.
- `GET /api/v1/healthz` (liveness) and `GET /api/v1/readyz` (DB check) — both unauthenticated.
- Application errors recorded by the `platform` error monitor (code, count, last occurrence) —
  surfaced in the superadmin app.

### Internationalization

Three locales in the client and workshop SPAs: **`uz`** (Latin, the default), **`uz-Cyrl`**, and
**`ru`**. Only two catalogs are maintained — `uz` is the source every string is written in, `ru`
is its translation, and `uz-Cyrl` is *derived* from `uz` by transliteration at load time, with an
overrides file for the handful of words the rules get wrong. A hand-maintained third script would
drift from the Latin the first time anyone fixed one sentence and not the other.

The locale is a **device preference** (`localStorage`), not a stored user attribute: it must
resolve synchronously before the first paint, and no principal carries a locale column. It is
never sniffed from `navigator.language` — a Russian-localised OS is the norm here and says
nothing about which language the operator wants their tools in, so the app stays Uzbek until
someone chooses otherwise.

Two things stay outside the catalogs. **User data** — branch, decor, client and workshop names
— renders as entered, in whatever language it was typed. **Server-rendered documents** (the
cutting-plan PDF and the akt sverka) are still Uzbek-only: they carry no locale channel, and their
column widths are tuned to Uzbek string widths. A Russian-speaking user gets a Russian interface
and an Uzbek printout until that is closed.

Money, dates, phones (`+998XXXXXXXXX`) and dimensions (millimetres) keep fixed display
conventions across all three locales; only the unit words change (`so'm` / `сўм` / `сум`). The
superadmin app is deliberately not localized — its audience is the platform's own operators.

Type needs no per-locale handling: both app faces ship a real Cyrillic subset, so there is no
font substitution and no locale-conditional family. Copy rules and the term glossary are the
design system's:
[`web/DESIGN.md`](https://github.com/qadam-uz/mebel-pro/blob/main/web/DESIGN.md).

## Next

Into the detail:

- [`ref/features/`](ref/features/) — feature specs.
- [`ref/entities/`](ref/entities/) — entities by bounded context.
