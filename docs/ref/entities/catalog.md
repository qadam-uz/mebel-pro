---
title: Catalog
status: draft
owner: shape
updated: 2026-09-08
order: 25
---

# Catalog

The catalog is **three levels: the platform's library plus each workshop's own rows on the
first two, and the branch's decision on the third**. A [Decor](#decor) is one pattern of one
manufacturer: what it's called, what it looks like, whether it has a grain. A
[Decor format](#decor-format) is one concrete product of that pattern: substrate, thickness,
sheet size or tape width, finished faces. A [Branch material](#branch-material) is a branch's
commercial decision about one format — *we carry this, at this price*. A
branch material *is* the material: stock, cutting panels and order items all point at it,
because a 16 mm and an 18 mm sheet of the same decor are different things to cut, to stock and
to price.

**Ownership is one nullable column, `workshop_id`, on [manufacturers](#manufacturer),
[decors](#decor) and [decor formats](#decor-format) alike.** `NULL` is a library row the
platform maintains for everyone; a set value is a row one workshop entered for itself. A
workshop sees a row when `workshop_id IS NULL OR workshop_id = <its own>`, at all three levels
of every query, and a row of another workshop does not exist for it — not listed, not
attachable, and not fetchable by id. The forces behind that model, the twin rule that keeps a
workshop from cloning a library format, and why this is a column rather than a return to
branch-owned formats are in
[`catalog-inventory.md`](../features/catalog-inventory.md#decor-formats-the-library-and-the-workshops-own).

**The schema vocabulary is English; the screen stays Uzbek.** The tables are `decors`,
`decor_formats`, `branch_materials` and the enum type is `decor_type`; the word «Dekor» on
screen, every i18n key and every enum *value* are unchanged. Frozen snapshots on orders and
cutting results keep whichever vocabulary they were written with — they are history and are
never rewritten ([`sales.md`](sales.md#order-item)).

Branch pricing carries the two service rates (per-panel cutting + per-metre edge-banding
labour); the per-metre price on a kromka branch material is the **raw material** price for
that tape. Order pricing combines them: edge cost = material + labour, summed per metre.
Snapshot semantics (a price change never reaches an existing order) live in
[`architecture.md`](../../architecture.md) → *Data model invariants*.

## Manufacturer

Who makes a decor — Kronospan, Egger, Rehau, and so on. Identity includes the manufacturer, so
the same decor code from two makers is two decors. Created by platform operators on demand
from the decor-create form, or by a workshop from its own — inline, while it enters a decor
the library lacks.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID? | `NULL` = a library row; set = this workshop's own, visible to it alone |
| `name` | text | required; unique (case-insensitive) **within its owner** |
| `country` | text? | optional — disambiguates similarly-named brands |
| `note` | text? | optional — short free-text |
| `status` | enum | `active` / `inactive` (soft delete only) |
| `created_at` / `updated_at` | timestamp | |

**Uniqueness has two arms, because NULLs are distinct in a unique index.** The library's is
`lower(name) WHERE workshop_id IS NULL`; a workshop's own is
`(workshop_id, lower(name)) WHERE workshop_id IS NOT NULL`. One index cannot cover both, and a
workshop naming a maker the platform later adds must not collide with it.

Invariants: `name` unique within its owner; a library row is created and edited only by a
platform operator, an own row only by its workshop (owner or `manage_catalog` on a branch of
it); `inactive` invisible to new decor creates and to the branch attach picker; existing
decors of an `inactive` manufacturer keep referencing it (history preserved); never deleted.
Renaming a manufacturer recomputes the `search_key` of every decor it makes — the name is
folded into that key.

## Decor

One decor **pattern**: manufacturer, code, name, photo, grain.
**No substrate, no thickness, no size, no price.** What the decor physically *is* belongs to
its [formats](#decor-format): Egger H1145 is one decor sold as an LDSP 18 mm board *and* as a
0.8 × 22 kromka, both sharing this row's photo and name.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID? | `NULL` = a library row; set = this workshop's own, visible to it alone |
| `manufacturer_id` | UUID | required; references a [Manufacturer](#manufacturer) the same owner can see — the library's, or its own |
| `code` | text? | the decor code, e.g. `H1334 ST9`; optional |
| `name` | text | required — the decor name, e.g. `Sonoma eman` |
| `has_grain` | bool | required; `true` when the decor has a grain |
| `image_file_id` | UUID? | → [file](support.md#file) — one photo, shared by every format |
| `status` | enum | `active` / `inactive` (soft delete only) |
| `search_key` | text | server-maintained folded search key (see below); never an input |
| `created_at` / `updated_at` | timestamp | |

There is **no texture field**: `has_grain` is the grain flag and nothing else describes the
surface.

**Uniqueness is by code when there is one, by name when there is not** — partial,
case-insensitive unique indexes on `(manufacturer_id, lower(code))` where `code` is non-null,
and `(manufacturer_id, lower(name))` where `code` is null, **each in two arms**: the library's
predicate gains `AND workshop_id IS NULL`, and a workshop's own pair keys on
`(workshop_id, manufacturer_id, …) WHERE workshop_id IS NOT NULL`. A maker's decor code
identifies the decor when it exists; a code-less decor falls back to its name; and identity is
compared only against rows of the same owner. A clash is refused with `decor_exists`, naming
the decor that already holds the identity so the operator can pick it instead of retyping
around it. **The substrate is deliberately
no longer part of identity**: while it was, a pattern sold as both a board and a tape needed
two rows, and the catalog carried such a twin for nearly every decor it held (14 pairs of the
demo catalog's 31 rows, merged away by the reshape). Both predicates are spelled for Postgres
**and** SQLite — with the predicate dropped, the test DB silently enforces name-uniqueness
between two decors that have different codes, a rule production does not have.

**There is no stored name.** Every display string is composed by one server-side formatter
and sent as `label`, so the admin table, the picker, the PDF and an order's history all read
the same shape. Nothing hand-writes a material name any more, and nothing can drift from it.
A decor's label carries no substrate and no dimensions — a decor has neither.

`search_key` is the folded concatenation of `name`, `code` and the manufacturer name; it is
recomputed on every write of the decor and on a rename of its manufacturer. The folding rules
and why search works this way live in
[`catalog-inventory.md`](../features/catalog-inventory.md#bilingual-search).

Invariants: a library row is created and edited only by a platform operator (platform-ops
scope), an own row only by its workshop, which may never edit a library one; `inactive`
invisible to new branch attachments and to clients; existing formats and branch materials of
an `inactive` decor keep referencing it (history preserved); never deleted; editing a decor
never affects existing orders (snapshots).

## Decor format

One concrete product of a [decor](#decor) — the thing a supplier actually sells and the thing
a branch decides to carry. Entered by a platform operator from the manufacturer's catalog, or
by a workshop for itself, and **immutable either way**.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID? | `NULL` = a library row; set = this workshop's own. An own format may hang off its own decor **or** off a library decor — "the pattern is listed, the size I buy is not" is the common case |
| `decor_id` | UUID | required; → a [Decor](#decor) the owner can see |
| `type` | enum `decor_type` | `ldsp` / `lmdf` / `dsp` / `mdf` / `fanera` / `yogoch` / `kromka` / `boshqa` — what the product *is*, listed and displayed in that order. `kromka` is tape-shaped; every other value is panel-shaped. `lmdf` (laminated MDF) was added 2026-09-08 — forward-only `ALTER TYPE … ADD VALUE`, so the enum is append-only and a value is never renumbered |
| `thickness_mm` | numeric | required, > 0 — sheets e.g. 16/18; tape e.g. 0.4/2 |
| `length_mm` / `width_mm` | int? / int? | **panel-shaped only**, both required there; `length ≥ width` (long side = grain direction), normalized on write; null for `kromka` |
| `tape_width_mm` | int? | **`kromka` only**, required there, > 0; null for panel-shaped |
| `finished_sides` | smallint? | `1` or `2` — how many faces carry the decor. **Required for `ldsp` / `lmdf`**, null for every other type |
| `status` | enum | `active` / `inactive`; the only mutable column |
| `created_at` / `updated_at` | timestamp | |

`type` is the single axis that replaced the old `kind` (panel / edge) **and** the old panel
`type`. The two were never independent — kromka was a shape, not a substrate — so one value
carries both facts. It hangs off the format, not off the decor: a pattern is not made of
anything, a product is.

**One-sided is a different product, not a variant of the two-sided sheet.** One-sided is the
norm for facade LMDF and for the cheap white LDSP used on hidden parts, and it sells at its own
price, so `finished_sides` is part of the format's identity. **Only the laminated boards have
faces to count** — `ldsp` and `lmdf`. Bare `dsp` and bare `mdf` have no laminated face, and
tape, plywood, timber and the "everything else" bucket never did, so the field is null for all
of them. It was required on `dsp` and `mdf` until 2026-09-08, when `lmdf` split the laminate off
`mdf`; the migration that added the value **nulled `finished_sides` on the existing `dsp` and
`mdf` rows**. Frozen history is not rewritten — an order or cutting snapshot keeps whatever it
printed, «1 tomonlama» included.

**Natural key** — `(decor_id, type, thickness_mm, COALESCE(length_mm, 0),
COALESCE(width_mm, 0), COALESCE(tape_width_mm, 0), COALESCE(finished_sides, 0))`, unique per
owner: the library's arm carries `WHERE workshop_id IS NULL`, a workshop's own arm prefixes
`workshop_id` and carries `WHERE workshop_id IS NOT NULL`. The `COALESCE` is load-bearing:
NULLs are distinct in a Postgres unique index, so a plain constraint over the nullable columns
would let the same tape-shaped format in twice. Every predicate is spelled for **both
dialects** (`postgresql_where` + `sqlite_where`), or the SQLite test database enforces a rule
production does not have.

**A workshop may not hold a twin of an *active* library format.** The index cannot say so —
the two rows differ in `workshop_id` — so the service checks the visible set before it
creates: an active twin is refused by name and the caller is handed that format's id to attach
instead ([`catalog-inventory.md`](../features/catalog-inventory.md#decor-formats-the-library-and-the-workshops-own)).
An `inactive` library twin does not block; the workshop's own row is the honest record of a
product the library retired and the workshop still buys.

**The shape rule is a real DB CHECK now**, which it could not be before — `tur` lived on
`dekorlar`, and a `branch_materials` constraint cannot reach another table's column, so the
whole rule had to sit in the service:

```sql
(type = 'kromka' AND tape_width_mm IS NOT NULL
   AND length_mm IS NULL AND width_mm IS NULL AND finished_sides IS NULL)
OR (type <> 'kromka' AND tape_width_mm IS NULL
   AND length_mm IS NOT NULL AND width_mm IS NOT NULL
   AND length_mm >= width_mm
   AND ((type IN ('ldsp', 'lmdf') AND finished_sides IN (1, 2))
        OR (type NOT IN ('ldsp', 'lmdf') AND finished_sides IS NULL)))
```

The service still checks the same rule first, so a wrong shape comes back as a named error
(`decor_format_shape_mismatch`) rather than a 500; the CHECK is the backstop. A duplicate
natural key is refused with `decor_format_exists`, naming the row that already holds it.

**Immutable — there is no edit path for dimensions.** Branch rows, stock, cutting panels and
order history all resolve through this id, so re-dimensioning a format in place would rewrite
what those rows mean. A wrong format is **deactivated and a correct one created**; a branch
that attached the wrong one attaches the right one instead. A workshop's own format is no more
editable than the library's, and it has no status of its own to flip either — the branch
retires its own row instead.

Invariants: created by a platform operator (library) or by the owning workshop (own); the
decor must be visible to that owner and `active` at creation;
dimensions never change after insert; `status` is the only mutable column and its deactivation
**never cascades** into branch rows, stock or history
([`catalog-inventory.md`](../features/catalog-inventory.md#three-levels-of-off)); never
deleted.

## Branch material

A [decor format](#decor-format) one branch has decided to carry — **this is "the material"**.
Three facts and nothing else: that the branch carries this format, its price, and its
branch-level visibility. Created when a branch attaches formats; the
branch's [`stock_item`](inventory.md#stock-item) is created alongside each row.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `branch_id` | UUID | required |
| `decor_format_id` | UUID | required; references a [Decor format](#decor-format) the branch's workshop can see — the library's or its own |
| `price_tiyin` | bigint | per sell unit (per **sheet** for panel-shaped, per **metre** for `kromka`), integer tiyin, ≥ 0. Default `0` — see *Price 0 means unpriced* |
| `status` | enum | `active` / `inactive` at the branch level (soft delete only) |
| `created_at` / `updated_at` | timestamp | |

**The format is the row's identity.** `(branch_id, decor_format_id)` is unique — **full, not
partial**: a branch either carries a format or it does not. (The old index was partial only
because customer-supplied boards lived in this table; they have their own now —
[`cutting.md`](cutting.md#customer-board).) There is **no way to edit the format**: dimensions,
substrate and grain are read through `decor_format` → `decor` and never copied here, so a
branch cannot hold a private idea of what a sheet is. "Change the format" means attaching the
other format and retiring this row — which keeps stock, price history and orders attached to
the thing they were actually about.

**Price 0 means unpriced, not free.** A branch routinely registers its whole format list
before it knows prices, so `price_tiyin` defaults to `0` and attaching without a price is
legal. Responses carry a derived `price_unset` flag, and **every** listing keeps and flags
those rows — client-facing ones included, so a client sees the whole shelf rather than the
priced fraction of it. What stops an unpriced format becoming a free order line sits at order
confirmation, not here ([`orders.md`](../features/orders.md#pricing)).

**A customer-supplied board is not one of these rows.** A sheet a walk-in carried in is not
something the branch carries, prices or stocks; it belongs to the drawing and then to the
order, and it has its own entity — [Customer board](cutting.md#customer-board).

**There is no threshold column any more.** `min_stock` — a per-format low-stock watch level,
`0` meaning off — was dropped on 2026-09-08 along with the whole low-stock policy: branches
set it on almost nothing, and the state worth surfacing, a **negative** balance, needs no
threshold to find ([`inventory.md`](inventory.md#stock-item) carries the predicate;
[`catalog-inventory.md`](../features/catalog-inventory.md#price-is-optional) carries the
decision). Attach and patch stopped accepting the field and the column is gone; the
`inventory.min_stock.update` audit rows already written stay, as every action-log row does.

Order pricing reads `price_tiyin` for **both** shapes: a sheet's per-sheet price for `shop`
panel parts, and a tape's per-metre price for every `shop` edge metre. The per-metre tape price
is the **raw material rate** — the **edge-banding labour** is a separate per-metre rate on
[Branch pricing](#branch-pricing), added on top. Cutting service is the per-panel rate, also on
Branch pricing.

**Everything downstream points here, not at the format.**
[`stock_items`](inventory.md#stock-item) carry a `branch_material_id`;
[`cutting_panels`](cutting.md#cutting-panel) and [`order_items`](sales.md#order-item) carry
either that or a [`customer_board_id`](cutting.md#customer-board), never both and never
neither.

Invariants: one row per (branch, decor format); price is integer and ≥ 0; price
integer tiyin (never float); editing the price never affects existing orders
(snapshots); created and edited by the workshop owner or a `manage_catalog` grantee on the
branch; the referenced Decor format, its Decor and its Manufacturer must all be **visible to
the branch's workshop** and `active` when
the row is created (existing rows survive any later deactivation); `inactive`
invisible to clients shopping at this branch and not selectable in a new cutting; a client
sees a material at a branch when the Decor and the Branch material are both `active` —
**price and stock are not conditions**, and the format's own status is not one either
([`catalog-inventory.md`](../features/catalog-inventory.md#three-levels-of-off)); never
deleted.

## Branch pricing

A branch's service-rate configuration: one rate for cutting a panel, one rate for applying a
metre of edge tape (any thickness). There is one row per branch. Order pricing reads it at
order creation time and snapshots the values onto the order; later changes don't reach
existing orders. Edge **material** cost is separate — it lives on the per-metre `price_tiyin`
of each `kromka` [Branch material](#branch-material).

| Field | Type | Notes |
|---|---|---|
| `branch_id` | UUID | PK; 1:1 with branch |
| `cutting_rate_tiyin` | bigint | the rate per panel cut, ≥ 0 |
| `edge_banding_rate_tiyin` | bigint | the labour rate per metre of tape applied, ≥ 0 (one rate; thickness is the material's property and doesn't change the rate in v1) |
| `updated_at` | timestamp | |
| `updated_by_user_id` | UUID | → workshop user with `is_owner` |

Invariants: exactly one row per branch (DB PK); rates are integer tiyin; only the workshop
owner edits (not delegable in v1). A part using a tape the branch doesn't carry makes order
pricing fail (operational gap; the owner attaches that format to the branch).

## Next

- [`catalog-inventory.md`](../features/catalog-inventory.md) — who creates a format, how a
  branch attaches one, prices it, and stocks it.
- [`inventory.md`](inventory.md) — the stock item each branch material owns.
- [`cutting.md`](cutting.md#customer-board) — the customer board, the sheet a walk-in brings
  that the branch never carries.
