---
title: Domain model
status: stable
owner: shape
updated: 2026-08-07
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
- **Branch** — a physical location of a workshop. Owns its stock, its prices, and the
  formats it carries of the platform's decors.
- **Manufacturer** — a platform-wide master record naming who made a decor (Egger,
  Kronospan, Rehau, …). Dekor identity includes the manufacturer.
- **Dekor** — a platform-wide master record of one decor: its manufacturer, its `tur`
  (`ldsp` / `dsp` / `mdf` / `fanera` / `yogoch` / `kromka` / `boshqa`), its code, its name,
  its photo, whether it has a grain. **Identity only — no thickness, no size, no price.**
- **Branch material** — a dekor in one concrete format (thickness plus sheet size, or
  plus tape width) carried by one branch, at that branch's price. **This is "the
  material"**: stock, cutting sheets and order lines all point here. The platform cannot
  know which formats a workshop's supplier sells, so the branch owns them.
- **Stock item** — a branch's on-hand balance for one branch material. **Supplier** — where
  stock arrived from (lightweight, added on demand; distinct from manufacturer).
  **Supplier invoice** — one arrival document grouping the stock-ins that came in on it,
  carrying the discount the supplier put on the paper; what the workshop owes is folded
  over these, not over individual arrivals.
- **Cutting result** — the output of an optimization run; names the winning algorithm.
  Reports sheets needed per panel format and tape metres needed per kromka format.
- **Order** — a client's request for panels cut at a branch. Aggregates the parts,
  the per-side edge picks, the status history, and the cutter / edger who completed
  it (the inputs the production reports read). It holds no money and no stock.
- **Income** — money the workshop received; an order payment carries the order it
  settles.
- **Expense** — money the workshop spent: overheads, consumables it buys, and staff
  salary (computed by the accountant, not the system).

## Next

[`access-patterns.md`](access-patterns.md) — who can do what to those nouns: principals, the access model, and tenancy.
