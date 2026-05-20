---
title: Scope
status: stable
owner: shape
updated: 2026-05-20
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
  platform-curated material catalog and sets its own prices, workers, and settings.
- **Warehouse & inventory** (the ERP core) — per-branch stock with arrivals and adjustments;
  reservations and consumptions driven automatically by orders; low-stock surfacing.
- **Optimized cutting** — multiple cutting-optimization algorithms run in parallel; the
  platform returns the best result and **names the winning algorithm**. Output includes the
  per-sheet layout, sheet count, waste, cut and edge-banding length, and a print-ready cutting
  map.
- **Orders** — client-placed orders from a finalized cutting result, with **frozen pricing**
  and a small production workflow (verify → cut → band → ready → collected, pickup-only),
  one-step operator revert, and reasoned cancellation. The order tracks production only — it
  moves no money and holds no stock.
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
- **Post-placement order modification** — a wrong order is cancelled (with a reason) and
  re-ordered; there is no edit / re-price path.
- **SMS, email, and bot notifications** — v1 is in-app only.
- **Delivery fulfilment** — v1 is **pickup-only**. The delivery model (address capture,
  fixed-fee zones, driver flow, distance-based pricing, the `process_delivery` grant) is
  designed but gated out of v1.
- **Delegating workshop-wide controls to non-owner staff** — owner-only in v1.
- **Operator-created orders** — orders are always client-placed.
- **Inter-branch stock transfers** — each branch's stock is independent in v1 (arrivals and
  adjustments only); there is no branch-to-branch transfer. Moving material is booked by hand
  as an adjustment at each branch if it ever needs to happen.
- **Workshop-side audit viewer** — the audit log is recorded everywhere, but v1 surfaces a
  viewer only in the superadmin app; workshop owners get no in-app audit screen yet.
- **Operator browsing of workshop orders** — the platform operator provisions, blocks, and
  monitors; v1 has no cross-workshop order view and operators don't read order contents.
- **Advanced cutting** — alternative results, async mode for very large jobs, manual layout
  edits, multiple sheet sizes, 3D nesting, CNC paths.
- **Advanced orders** — batching, reorder, templates, partial fulfilment, post-completion
  complaints, client ratings.
- **Multi-currency** — local currency only.
- **Supplier management, automatic purchase orders, remnant tracking, barcode scanning** —
  future.

## Next

[`personas.md`](personas.md) — the four roles touching v1 and what each needs.
