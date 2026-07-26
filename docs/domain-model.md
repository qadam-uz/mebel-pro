---
title: Domain model
status: stable
owner: shape
updated: 2026-07-26
order: 45
---

# Domain model

The language and the main nouns the system is built around. Per-entity detail — fields, states,
invariants, child entities, relationships — lives in [`ref/entities/`](ref/entities/), one page
per bounded context.

## The main aggregates

- **Platform user** — the team running the platform.
- **Workshop user** — a workshop's person. Carries credentials and a set of permission
  grants; the owner is one of these, with full scope. **There is no separate "worker"
  entity and no role** — a cutter or edge bander is just a workshop user holding the
  production grant; one person may hold every grant. The system stores no pay rates.
- **Client** — the workshop's customer; global to the platform, picks a branch per order.
  Optionally carries a preferred branch that seeds new cutting drafts.
- **Workshop** — one furniture-cutting business; the tenant. Has many branches.
- **Branch** — a physical location of a workshop. Owns its stock, prices, and the
  selection it carries from the material catalog.
- **Manufacturer** — a platform-wide master record naming who made a material (Egger,
  Kronospan, Rehau, …). Material identity includes the manufacturer.
- **Material** — a platform-wide master record of one of two kinds: a **panel** (a
  cuttable board) or an **edge** (edge-banding tape). Every material names its
  manufacturer. Branches pick which they carry and set their own price.
- **Stock item** — a branch's on-hand balance for one material. **Supplier** — where
  stock arrived from (lightweight, added on demand; distinct from manufacturer).
  **Supplier invoice** — one arrival document grouping the stock-ins that came in on it,
  carrying the discount the supplier put on the paper; what the workshop owes is folded
  over these, not over individual arrivals.
- **Cutting result** — the output of an optimization run; names the winning algorithm.
  Reports panels needed per panel material and edge metres needed per edge material.
- **Order** — a client's request for panels cut at a branch. Aggregates the parts,
  the per-side edge picks, the status history, and the cutter / edger who completed
  it (the inputs the production reports read). It holds no money and no stock.
- **Income** — money the workshop received; an order payment carries the order it
  settles.
- **Expense** — money the workshop spent: overheads, consumables it buys, and staff
  salary (computed by the accountant, not the system).

## Next

[`access-patterns.md`](access-patterns.md) — who can do what to those nouns: principals, the access model, and tenancy.
