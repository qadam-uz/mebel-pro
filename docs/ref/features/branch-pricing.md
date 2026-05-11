---
title: Branch pricing
status: stable
owner: shape
updated: 2026-05-11
order: 22
related:
  - docs/spec/orders.md
  - docs/ref/entities/catalog/branch-pricing.md
  - docs/ref/entities/sales/order.md
  - docs/ref/features/order-placement.md
---

# Branch pricing

## Problem

Each branch charges its own way for the cutting service and edge banding. Until that's configured, an
order can't be priced — so a new branch can't take orders. The owner needs to set the cutting model
(per sheet or per cut) and its rate, plus an edge-banding rate per banding thickness, knowing that
later changes won't disturb orders already placed.

## User stories

- As a **workshop owner**, I want to set a branch's cutting model and rate so orders there can be
  priced.
- As the same, I want to set an edge-banding rate per thickness so edge-banded parts price correctly.
- As the same, I want to change pricing later without affecting existing orders.
- As **staff / a client**, I want order pricing to use the branch's current rates at order time —
  not to type a price.

## Requirements

1. `get-branch-pricing` / `update-branch-pricing` (**owner only** — not delegable in v1): for a
   branch in the workshop, set `cutting_model` (`per_sheet` or `per_cut`), `cutting_rate_tiyin`
   (entered in UZS, stored as integer tiyin), and `edge_banding_rates` — a rate (UZS/metre → tiyin)
   for each banding thickness offered (e.g. 0.4 mm, 2.0 mm). There is exactly one pricing row per
   branch (created with the branch). Records `updated_by_user_id` and the time.
2. Order pricing ([`docs/spec/orders.md`](../../spec/orders.md)) reads this at order creation /
   re-pricing time and **snapshots** the values onto the order/order-items; later changes don't reach
   existing orders ([`docs/spec/architecture.md`](../../spec/architecture.md)).
3. A part using a banding thickness with no rate makes order pricing fail with a clear error — the
   owner must add the missing rate. There's no enforced cap on discounts in v1 (the mandatory reason
   + audit are the control — [`docs/spec/orders.md`](../../spec/orders.md)).
4. Staff with no owner role can **view** branch pricing (it's relevant context) but not edit it;
   clients see the resulting prices in the cutting/order wizards, not the config.
5. Every edit writes an audit-log row.

## UX

In the **seh app**, under a branch's **Pricing** tab:

- **Pricing form** — cutting model: a radio between `per_sheet` ("price per sheet, regardless of cut
  count") and `per_cut` ("price per cut"); the rate field below it (in UZS, labelled with the unit
  per the chosen model). Edge-banding rates: a small grid — thickness (mm) | rate (UZS / metre) —
  with add/remove rows. Save with an explicit Save button + an unsaved-changes guard. Owner-only:
  staff see the same data read-only with a "owner only" note on the edit controls.
- Validation: rates ≥ 0; at least one edge-banding row if the branch's materials/typical parts use
  banding (a soft warning, not a hard block); model is one of the two.
- States: loading, error (`trace_id`), "pricing not set yet" empty state on a new branch (with a
  prompt to configure it before taking orders), unsaved-changes warning on navigate-away.
- Accessibility: the model radio group and the rates grid are keyboard-operable with labels; money
  inputs accept UZS and show the unit.

Shared patterns (form with save/dirty guard, small editable grid, money input): [`docs/ref/ux/components.md`](../ux/components.md).

## Entities touched

- [`docs/ref/entities/catalog/branch-pricing.md`](../entities/catalog/branch-pricing.md) — the one row per branch, edited here.
- [`docs/ref/entities/workshop/branch.md`](../entities/workshop/branch.md) — the owning branch.
- [`docs/ref/entities/sales/order.md`](../entities/sales/order.md) — consumes (snapshots) these rates at pricing time.
- [`docs/ref/entities/support/action-log.md`](../entities/support/action-log.md).

## Edge cases

- **Pricing not set on a branch with materials** — clients can browse materials and run cuttings, but
  creating an order fails at pricing time; the seh app flags the branch as "pricing incomplete".
- **A part needs an edge-banding thickness with no rate** — order pricing fails (`missing_edge_rate`
  or similar); the owner adds the rate; the order can then proceed.
- **Change the cutting model with orders in flight** — those orders kept their snapshot; only new
  orders (and re-priced modifications) use the new model.
- **Rate entered with decimals (UZS)** — converted to integer tiyin on send; the server is the
  source of truth.

## Out of scope

- Discount caps / pricing policy enforcement — v1 has none ([`docs/spec/open-questions.md`](../../spec/open-questions.md)).
- Distance-based / dynamic delivery pricing — that's workshop settings + future ([`docs/spec/open-questions.md`](../../spec/open-questions.md) Q6); branch pricing covers cutting + edge banding only.
- Per-material cutting rates — v1 is a single branch-level model.
- Delegating `manage_pricing` to staff — owner-only in v1.

## Open questions

- Delegating `manage_pricing` and adding discount caps — owner: shape — [`docs/spec/open-questions.md`](../../spec/open-questions.md) Q1.
