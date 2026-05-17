---
title: Domain model
status: stable
owner: shape
updated: 2026-05-17
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
- **Workshop** — one furniture-cutting business; the tenant. Has many branches.
- **Branch** — a physical location of a workshop. Owns its stock, prices, and the selection
  it carries from the material catalog.
- **Material** — a platform-wide master record of one of two kinds: a **sheet** (a cuttable
  board) or an **edge** (edge-banding tape). Branches pick which they carry and set their
  own price.
- **Stock item** — a branch's on-hand balance for one material. **Supplier** — where
  stock-in came from (lightweight, added on demand).
- **Cutting result** — the output of an optimization run; names the winning algorithm.
- **Order** — a client's request for panels cut at a branch. Aggregates the parts, the
  status history, and the cutter / edger who completed it (the inputs the production reports
  read). It holds no money and no stock.
- **Income** — money the workshop received; an order payment carries the order it settles.
- **Expense** — money the workshop spent: overheads, consumables it buys, and staff salary
  (computed by the accountant, not the system).

## Next

[`access-patterns.md`](access-patterns.md) — who can do what to those nouns: principals, the access model, and tenancy.
