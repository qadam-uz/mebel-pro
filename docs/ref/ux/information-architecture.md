---
title: Information architecture
status: stable
owner: shape
updated: 2026-05-12
related:
  - docs/spec/personas.md
  - docs/spec/architecture.md
  - docs/ref/ux/components.md
---

# Information architecture

The navigation model, the route inventory, and the shell, across the three apps + the landing page.
The "why three apps" decision is [`docs/spec/architecture.md`](../../spec/architecture.md); per-feature screen detail (states, layouts, interactions) lives in each `ref/features/*` doc's **UX** section; shared component specs are in [`docs/ref/ux/components.md`](components.md).

> **Static UI prototypes (temporary):** clickable mockups of every surface below, in four candidate design systems, live under `docs/misc/` — [compare all four](../../misc/prototype-variants.html) (or jump straight in: [Aurora](../../misc/prototype/index.html) · [Carbon](../../misc/prototype-b/index.html) · [Terra](../../misc/prototype-c/index.html) · [Mono](../../misc/prototype-d/index.html)). No backend — canned data, navigation/tabs/modals/wizards all work; built to look at while we settle the visual direction. **To be cleaned up once a variant is chosen** (the others removed; the keeper either deleted or, if worth keeping, promoted to a real `ref/ux/` page with its assets in `docs/assets/`).

## The surfaces

| Surface | Audience | Auth | Tech | Built from |
|---|---|---|---|---|
| **Landing** | the public / prospective workshops & clients | none | a single static SEO-optimized HTML file (plain markup + minimal CSS/JS) — *not* part of the Vue repo | served at `/` by the Caddy edge |
| **Client app** | clients | Telegram OAuth | Vue 3 / Vite SPA | the `web/` repo, client entry |
| **Seh (workshop) app** | workshop owner & staff | login + password | Vue 3 / Vite SPA | the `web/` repo, seh entry — every screen gated by the user's permission grants ([`docs/spec/access.md`](../../spec/access.md)) |
| **Superadmin app** | platform operators | login + password | Vue 3 / Vite SPA | the `web/` repo, superadmin entry |

The API is same-origin under `/api/v1`. The three SPAs share, in the repo, the UI primitives, the
`fetch`-based API client, the design tokens, and the i18n strings ([`docs/ref/ux/components.md`](components.md)); each app has its own routes, views, and stores.

> Not a product surface, but also on the edge: the backend serves the project's live documentation at `/docs` and the OpenAPI UIs at `/api-docs` / `/api-redoc` — internal, HTTP-Basic-gated ([`docs/spec/architecture.md`](../../spec/architecture.md) → *Cross-cutting concerns → Documentation site*).

## Route inventory

(Indicative paths; the exact prefixing of each SPA is a build detail. What matters is the structure.)

### Landing (static)

`/` — the marketing page. Sections: hero (what Mebel Pro is), the customer pitch (cut your panels
online), the workshop pitch (run your shop in one place), how it works, contact / sign-in entry
points (deep links into the client app's sign-in and the seh/superadmin login). SEO: real `<title>`,
meta description, structured headings, no JS required to read the content, fast.

### Client app

| Route | Purpose | Feature |
|---|---|---|
| `/auth/telegram` | Telegram sign-in (auto-register) | [`client-onboarding.md`](../features/client-onboarding.md) |
| `/c/branches` | branch picker (also the home) | [`order-placement.md`](../features/order-placement.md) |
| `/c/cutting/new` | cutting wizard (material → parts → result) | [`cutting-optimization.md`](../features/cutting-optimization.md) |
| `/c/cutting/drafts` | my drafts (last 7 days) | [`cutting-optimization.md`](../features/cutting-optimization.md) |
| `/c/cutting/:id` | draft / result view (SVG + metrics + PDF) | [`cutting-optimization.md`](../features/cutting-optimization.md) |
| `/c/orders/new?cutting=:id` | order create wizard | [`order-placement.md`](../features/order-placement.md) |
| `/c/orders` | my orders | [`order-placement.md`](../features/order-placement.md) |
| `/c/orders/:id` | order detail (overview / cutting / payments / refunds / timeline) | [`order-placement.md`](../features/order-placement.md), [`order-fulfillment.md`](../features/order-fulfillment.md) |
| `/c/orders/:id/modify` | modify wizard | [`order-modification.md`](../features/order-modification.md) |
| `/c/profile` | Telegram-synced profile + sessions | [`client-onboarding.md`](../features/client-onboarding.md) |

### Seh (workshop) app

Login: `/login`, `/login/forced-change`. After login: role-aware home (owner → `/seh/dashboard`;
staff → their first available screen). Nav items are shown only if the current user can use them.

| Route | Purpose | Visibility | Feature |
|---|---|---|---|
| `/seh/dashboard` | KPIs, status donut, timeseries, refund SLA, low-stock, audit highlights | `view_dashboard` (any granted branch) / owner | [`order-fulfillment.md`](../features/order-fulfillment.md) |
| `/seh/orders` | branch order queue (board / table) | `manage_orders` on a branch / owner | [`order-fulfillment.md`](../features/order-fulfillment.md) |
| `/seh/orders/:id` | order detail + workflow actions + modify/cancel | `manage_orders` on the order's branch / owner | [`order-fulfillment.md`](../features/order-fulfillment.md), [`order-modification.md`](../features/order-modification.md), [`order-cancellation-and-refunds.md`](../features/order-cancellation-and-refunds.md) |
| `/seh/refunds` | pending refund queue | `manage_orders` / owner | [`order-cancellation-and-refunds.md`](../features/order-cancellation-and-refunds.md) |
| `/seh/branches` + `/:id` (tabs: overview / materials / stock / workers / pricing / staff / orders) | branch CRUD + per-branch sub-views | owner (CRUD); staff see only sub-views they have a grant for | [`branch-management.md`](../features/branch-management.md), [`material-catalog.md`](../features/material-catalog.md), [`inventory-management.md`](../features/inventory-management.md), [`worker-management.md`](../features/worker-management.md), [`branch-pricing.md`](../features/branch-pricing.md) |
| `/seh/materials` | workshop-wide material list (branch filter) | `manage_catalog` / owner | [`material-catalog.md`](../features/material-catalog.md) |
| `/seh/inventory` | workshop-wide stock + transactions (branch filter); transfer (owner) | `manage_inventory` / owner | [`inventory-management.md`](../features/inventory-management.md) |
| `/seh/workers` | workshop-wide worker list (branch filter) | `manage_workers` / owner | [`worker-management.md`](../features/worker-management.md) |
| `/seh/settings/workshop` | workshop profile, delivery zones, payment channels | owner | [`workshop-provisioning.md`](../features/workshop-provisioning.md) |
| `/seh/settings/users` + `/:id` (tabs: profile / permissions / sessions / audit) | workshop user management + grants | owner | [`workshop-user-management.md`](../features/workshop-user-management.md) |
| `/seh/audit` (tabs: action log / status changes) | audit viewer | owner / `view_reports` | [`audit-log.md`](../features/audit-log.md) |
| `/seh/profile` | me, change password, my sessions | any workshop user | [`workshop-user-management.md`](../features/workshop-user-management.md) |

### Superadmin app

Login: `/login`, `/login/forced-change`. Home: `/admin/workshops`.

| Route | Purpose | Feature |
|---|---|---|
| `/admin/workshops` + `/:id` (tabs: profile / settings / branches / block) | workshop provisioning, settings, block/unblock | [`workshop-provisioning.md`](../features/workshop-provisioning.md) |
| `/admin/users` | platform users management | [`platform-ops.md`](../features/platform-ops.md) |
| `/admin/orders` (cross-workshop, read-only — incident response) | look across all workshops' orders | [`order-fulfillment.md`](../features/order-fulfillment.md), [`tenancy`](../../spec/access.md) |
| `/admin/audit` (tabs: action log / status changes; workshop filter) | cross-workshop audit | [`audit-log.md`](../features/audit-log.md) |
| `/admin/platform/jobs` | scheduled-jobs console | [`platform-ops.md`](../features/platform-ops.md) |
| `/admin/platform/errors` | error monitor | [`platform-ops.md`](../features/platform-ops.md) |
| `/admin/profile` | me, change password, my sessions | [`platform-ops.md`](../features/platform-ops.md) |

## The shell

All three SPAs share one shell shape (it's a shared component — [`docs/ref/ux/components.md`](components.md)):

- **Top bar** — brand mark; an app-specific context control (seh: a **branch switcher** for staff
  with multiple granted branches, a static branch chip otherwise; superadmin: a **workshop selector**
  on workshop-scoped screens; client: none — the client picks a branch per order); the **notification
  bell** ([`notifications-inbox.md`](../features/notifications-inbox.md)); the language switcher (Uzbek only in v1); the user/avatar menu (profile, change password, logout).
- **Side nav** — sectioned per app; in the seh app, items appear only if the current user can use
  them (owner sees everything); collapses to a drawer on mobile; on the client app it's a bottom tab
  bar on mobile.
- **Main** — a page header (title, breadcrumb, the primary action), the content (lists / tables /
  forms / wizards), a trailing toast region.
- **Footer** — minimal: build version + a trace-id copy affordance.

Page-level patterns (used across features): **list page** (filter strip + table/cards + paginator +
row→detail), **detail page** (header with status + meta + action set; a tab strip for sub-views),
**form/wizard** (step indicator, validated form, a sticky summary with running totals, a sticky
back/continue/save footer), **empty state** (icon + headline + body + primary action), **error
boundary** (`error.code` → localized message + `trace_id` in monospace + retry).

## Auth & role-aware routing

- Any unauthenticated visit to a protected route → the app's sign-in (`/auth/telegram` for the client
  app; `/login` for the seh and superadmin apps).
- `force_password_change` on a workshop/platform user → `/login/forced-change`, which blocks all
  other navigation until the password is changed.
- The seh app derives the visible nav and the available actions on each screen from the current
  user's `is_owner` flag and permission-grant set ([`docs/spec/access.md`](../../spec/access.md)); a route the user can't use redirects to their home with a toast. Backend checks are authoritative; the UI just doesn't surface what won't work.
- On a `401`, the API client attempts a single token refresh and replays; a second `401` logs the
  user out. See [`docs/spec/access.md`](../../spec/access.md).

## Out of scope (v1)

- `ru` / `en` locales (keys are kept generic so adding them is mechanical).
- Payment-gateway return/redirect UIs, BNPL flows — placeholder slots only ([`docs/spec/scope-v1.md`](../../spec/scope-v1.md)).
- Map/geocoder widgets for delivery addresses — manual lat/lng.
- A Telegram notification bot surface — nothing in the apps; sign-in only.
