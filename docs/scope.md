---
title: Scope
status: stable
owner: shape
updated: 2026-09-05
order: 20
---

# Scope

What v1 covers and what it deliberately doesn't. v1 is the smallest system a real workshop and
a real customer can use end to end — a minimal ERP for a furniture-cutting business: the
self-serve surface the workshop hands its own customers, the workshop floor the staff runs,
the warehouse the inventory moves through, and the books the accountant closes. The "out"
list below carries as much weight as the "in" list: where v1 ships a manual path instead of
an integration (payments, refunds), that's a considered substitution.

## In scope

- **Identity & access** — platform operators provision workshops; owners manage staff with
  per-branch permissions; clients sign in through the platform's Telegram bot (walk-ins may be
  registered at the counter by workshop staff). Tenant-isolated, revocable,
  brute-force-protected.
- **Workshops & branches** — multi-branch workshops; each branch picks the formats it carries
  from the platform-curated product catalog and sets its own prices, workers, and settings.
- **Warehouse & inventory** (the ERP core) — per-branch stock with arrivals and adjustments,
  arrivals grouped under a supplier invoice carrying the document's discount, automatic
  consumption driven by orders, and low-stock surfacing. There is no reservation balance in v1.
- **Optimized cutting** — multiple cutting-optimization algorithms run against the same input
  in one request; the platform returns the best result and **names the winning algorithm**.
  Output includes the per-panel layout, panel count, waste, cut and edge-banding length, and a
  print-ready cutting map.
- **Orders** — orders from a finalized cutting result — placed by the client, or by workshop
  staff on behalf of a walk-in client — with **frozen pricing** and a small production workflow
  (verify → cut → band → ready → collected, pickup-only) that a branch collapses into one
  **Tayyor** action, operator revert, and reasoned cancellation. The order tracks production
  only — it moves no money and holds no stock.
- **Finance & accounting** — a workshop money ledger: income (incl. order payments) and
  expenses (incl. staff salary) recorded by hand, worker-production reports the accountant
  uses to compute pay, and revenue / expense / net reporting by branch and period — enough
  to close a month inside the system.
- **Cross-cutting** — file storage, full audit log, in-app notifications inbox, and a
  platform-ops console (scheduled jobs, error monitor, manual triggers).

## Out of scope (v1) — explicit

- **Online payment gateways** and **BNPL** — v1 records income and refunds manually; an
  order moves no money.
- **Automatic payroll / compensation engine** — v1 stores no pay rates and computes no
  salary; it reports raw per-worker production and the accountant books salary as an
  expense by hand.
- **Client-side post-placement order modification** — a client's wrong order is cancelled
  (with a reason) and re-ordered. Staff with `manage_orders` do have a pre-production
  revision path (`new`/`confirmed` only) that re-freezes pricing at current rates — see
  [`ref/features/orders.md`](ref/features/orders.md) → Revising a placed order.
- **SMS, email, and bot notifications** — v1 is in-app only.
- **Delivery fulfilment** — v1 is **pickup-only**. The delivery model (address capture,
  fixed-fee zones, driver flow, distance-based pricing, the `process_delivery` grant) is
  designed but gated out of v1.
- **Per-stage production on the floor** — worker assignment, the two start taps, and the
  Kesish / Krom station screens are implemented, but the product's first plan (**Start**)
  includes **simple mode only**: every branch closes an order with one **Tayyor** tap, and the
  owner-facing mode switch was removed on 2026-09-05. That choreography returns with a future
  plan, which adds full mode rather than replacing simple
  ([`ref/features/orders.md`](ref/features/orders.md#production-mode) owns the decision). No
  billing or subscription mechanics are built — "Start" is a package name with no entity,
  column, or gate behind it.
- **Delegating workshop-wide controls to non-owner staff** — owner-only in v1.
- **Inter-branch stock transfers** — each branch's stock is independent in v1 (arrivals and
  adjustments only); there is no branch-to-branch transfer. Moving material is booked by hand
  as an adjustment at each branch if it ever needs to happen.
- **Workshop-side audit viewer** — the audit log is recorded everywhere, but v1 surfaces a
  viewer only in the superadmin app; workshop owners get no in-app audit screen yet.
- **Operator browsing of workshop orders** — the platform operator provisions, blocks, and
  monitors; v1 has no cross-workshop order view and operators don't read order contents.
  **Counts yes, contents no**: platform-wide aggregates over orders — how many were placed
  today, this week, this month, this year — are in scope and drive the admin dashboard, because
  a tally carries no client, panel, price, or workshop identity. Anything that resolves an
  individual order, or breaks a total down per workshop, is not.
- **A marketplace** — public workshop cards, open catalogs and price comparison, or any
  cross-workshop browsing or search in the client app. The client app is a tool a workshop
  hands its own customers: they enter through that workshop's link and the app stays scoped
  to it ([`ref/features/client-entry.md`](ref/features/client-entry.md)). This is a
  positioning decision, not a backlog item — a first screen listing a workshop's competitors
  is a screen its owner will not recommend, and recommendation is the growth channel v1 has.
  Revisit when the platform itself brings the demand a marketplace would allocate; until
  then nothing may be built toward it, and nothing may make the pivot harder.
- **Advanced cutting** — alternative results, async mode for very large jobs, manual layout
  edits, multiple panel sizes, 3D nesting, CNC paths.
- **Advanced orders** — batching, reorder, templates, partial fulfilment, post-completion
  complaints, client ratings.
- **Multi-currency** — local currency only.
- **Automatic purchase orders, procurement planning, remnant tracking, barcode scanning** —
  future. Supplier **payables** are in v1: an arrival is recorded as a supplier invoice, and
  what the workshop still owes each supplier is derived from those invoices, the expenses paid
  against them, and manual adjustments. What stays out is everything *upstream* of the arrival
  — expected deliveries, purchase orders, aging reports.

## Next

[`domain-model.md`](domain-model.md) — the ubiquitous language and the entity map the roles share.
