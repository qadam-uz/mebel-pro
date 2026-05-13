---
title: Scope
status: stable
owner: shape
updated: 2026-05-13
order: 20
---

# Scope

What v1 covers and what it deliberately doesn't. v1 is the smallest system a real workshop and
a real customer can use end to end — a minimal ERP for a furniture-cutting business: the
storefront the customer sees, the workshop floor the staff runs, the warehouse the inventory
moves through, and the books the accountant closes. The "out" list below carries as much weight
as the "in" list: where v1 ships a manual path instead of an integration (payments, refunds),
that's a considered substitution.

## In scope

- **Identity & access** — platform operators provision workshops; owners manage staff with
  per-branch permissions; clients self-register via social login. Tenant-isolated, revocable,
  brute-force-protected.
- **Workshops & branches** — multi-branch workshops; each branch picks what it carries from a
  platform-curated material catalog and sets its own prices, workers, delivery zones, and
  settings.
- **Warehouse & inventory** (the ERP core) — per-branch stock with arrivals, adjustments, and
  inter-branch transfers; reservations and consumptions driven automatically by orders;
  low-stock surfacing.
- **Optimized cutting** — multiple cutting-optimization algorithms run in parallel; the
  platform returns the best result and **names the winning algorithm**. Output includes the
  per-sheet layout, sheet count, waste, cut and edge-banding length, and a print-ready cutting
  map.
- **Orders** — client-placed orders from a finalized cutting result, with **frozen pricing**,
  full production workflow, recorded payments (cash / bank, one shot or advance + balance), and
  offline-recorded cancellations and refunds.
- **Finance & accounting** — workshop-wide money-in / money-out journal, end-of-day
  reconciliation, and revenue / refund / outstanding reporting by branch, period, and channel —
  enough for an accountant to close a month inside the system.
- **Cross-cutting** — file storage, full audit log, in-app notifications inbox, and a
  platform-ops console (scheduled jobs, error monitor, manual triggers).

## Out of scope (v1) — explicit

- **Online payment gateways** and **BNPL** — v1 records payments and refunds manually.
- **SMS, email, and bot notifications** — v1 is in-app only.
- **Maps & distance-based delivery pricing** — v1 uses fixed-fee zones.
- **Delegating workshop-wide controls to non-owner staff** — owner-only in v1.
- **Operator-created orders** — orders are always client-placed.
- **Advanced cutting** — alternative results, async mode for very large jobs, manual layout
  edits, multiple sheet sizes, 3D nesting, CNC paths.
- **Advanced orders** — batching, reorder, templates, partial fulfilment, post-completion
  complaints, client ratings.
- **Multi-currency** — local currency only.
- **Supplier management, automatic purchase orders, remnant tracking, barcode scanning** —
  future.

## Next

[`personas.md`](personas.md) — the four roles touching v1 and what each needs.
