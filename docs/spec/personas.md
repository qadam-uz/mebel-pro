---
title: Personas
status: stable
owner: shape
updated: 2026-05-11
order: 30
related:
  - docs/spec/journeys.md
  - docs/spec/access.md
  - docs/ref/ux/information-architecture.md
---

# Personas

Four roles touch v1. They split cleanly into three principal types — three auth surfaces, three
front-end apps (see [`docs/ref/ux/information-architecture.md`](../ref/ux/information-architecture.md)).
Workshop staff capability is not a fixed role but a set of grants — see [`docs/spec/access.md`](access.md).

## Platform operator ("superadmin")

- **Who:** us — the team running the platform.
- **Principal type:** platform user. Login + password. Not bound to any workshop. No permission
  model — full platform scope.
- **App:** the **superadmin app**.
- **Needs:** onboard a workshop and its first owner ([`docs/ref/features/workshop-provisioning.md`](../ref/features/workshop-provisioning.md)); block / unblock a workshop; look across all workshops for incident response; operate the platform — scheduled-jobs console, error monitor ([`docs/ref/features/platform-ops.md`](../ref/features/platform-ops.md)); manage platform users.
- **Does not:** create orders, run a workshop's day-to-day.

## Workshop owner

- **Who:** the person who owns or runs the furniture workshop (the tenant).
- **Principal type:** workshop user, flagged `is_owner`. Login + password (set up by the platform
  operator with `force_password_change`).
- **App:** the **seh** (workshop) app.
- **Capability:** everything in their workshop on every branch — branches, materials, inventory,
  pricing, workers, orders, settings, reports — **plus** the owner-only powers: create workshop
  staff and grant/revoke their permissions ([`docs/ref/features/workshop-user-management.md`](../ref/features/workshop-user-management.md)), force-cancel orders already in production, revert completed refunds. Cannot be created or demoted by anyone except a platform operator.
- **Needs:** stand the workshop up (branches → materials → stock → pricing → workers → staff);
  oversee orders and refund SLA; configure delivery zones and payment-channel settings.

## Workshop staff

- **Who:** branch employees — order desk, warehouse, etc.
- **Principal type:** workshop user, not owner. Login + password (created by the owner with
  `force_password_change`).
- **App:** the **seh** app — but every screen is gated by the staff member's grants; a freshly
  created staff user with no grants can log in and see nothing actionable (mirrors "must have ≥ 1
  grant to be useful").
- **Capability:** the set of `(permission, branch)` grants the owner gave them, drawn from the
  branch-scoped permission catalog: `view_dashboard`, `manage_orders` (full order workflow on the
  branch — status, discount, pay-later, driver, recording payments, processing refunds),
  `manage_catalog`, `manage_inventory`, `manage_workers`. Workshop-wide capabilities (branches,
  pricing, settings, reports, user management) are **not delegable to staff in v1** — owner-only.
- **Needs:** see and progress the orders for their assigned branch(es); record cash/bank payments;
  process refunds; keep catalog / stock / workers current for their branch.

## Client

- **Who:** the workshop's customer — a person or small business that needs panels cut.
- **Principal type:** client — a **separate entity**, not a "user with role=client". Self-registers
  on demand via **Telegram OAuth only**; no password; global to the platform (can order from any
  active branch of any workshop, picks one per order). See [`docs/spec/access.md`](access.md) and [`docs/ref/features/client-onboarding.md`](../ref/features/client-onboarding.md).
- **App:** the **client app**.
- **Needs:** pick a branch; build a parts list and run the cutting optimizer; see the layout, the
  waste %, the price; place an order ([`docs/ref/features/order-placement.md`](../ref/features/order-placement.md)); track it; modify or cancel while it's still early; pay (recorded by staff in v1); see refunds.
- **Context of use:** often on a phone, possibly first-time, comparing options. The cutting wizard
  and the order wizard must work mobile-first.
- **Does not:** see anything about the workshop's internals — stock numbers, other clients, pricing
  config, audit.
