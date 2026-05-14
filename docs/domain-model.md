---
title: Domain model
status: stable
owner: shape
updated: 2026-05-13
order: 45
---

# Domain model

The language and the main nouns the system is built around. Per-entity detail — fields, states,
invariants, child entities, relationships — lives in [`ref/entities/`](ref/entities/), one page
per bounded context.

## The main aggregates

- **Platform user** — the team running the platform.
- **Workshop user** — a workshop's staff member; the owner is one of these, with full scope.
- **Client** — the workshop's customer; global to the platform, picks a branch per order.
- **Workshop** — one furniture-cutting business; the tenant. Has many branches.
- **Branch** — a physical location of a workshop. Owns its stock, workers, prices, and the
  selection it carries from the material catalog.
- **Material** — a cuttable sheet product. A platform-wide master record (type, thickness,
  colour, sheet size, grain); branches pick which ones they carry and set their own price.
- **Stock item** — a branch's on-hand balance for one material.
- **Cutting result** — the output of an optimization run; names the winning algorithm.
- **Order** — a client's request for panels cut at a branch. Aggregates the parts, the
  payments, the refunds, and the status history.

## Next

[`access-patterns.md`](access-patterns.md) — who can do what to those nouns: principals, the access model, and tenancy.
