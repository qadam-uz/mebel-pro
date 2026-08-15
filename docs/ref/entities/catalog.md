---
title: Catalog
status: draft
owner: shape
updated: 2026-08-13
order: 25
---

# Catalog

The catalog is **two levels**. The platform owns **identity** — a [Dekor](#dekor) is one
decor of one manufacturer: what it is, what it's called, what it looks like. A branch owns
**format and price** — a [Branch material](#branch-material) is that dekor in one concrete
thickness and sheet or tape size, carried by one branch. A branch material *is* the material:
stock, cutting panels and order items all point at it, because a 16 mm and an 18 mm sheet of
the same decor are different things to cut, to stock and to price.

The split exists because a platform operator cannot know what a given workshop's supplier
sells. One dekor fans out to as many branch materials as a branch actually carries.
Branch pricing carries the two service rates (per-panel cutting + per-metre edge-banding
labour); the per-metre price on a kromka branch material is the **raw material** price for
that tape. Order pricing combines them: edge cost = material + labour, summed per metre.
Snapshot semantics (a price change never reaches an existing order) live in
[`architecture.md`](../../architecture.md) → *Data model invariants*.

## Manufacturer

Who makes a decor — Kronospan, Egger, Rehau, and so on. A platform-scoped master record:
identity includes the manufacturer, so the same decor code from two makers is two dekorlar.
Created by platform operators on demand from the dekor-create form.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `name` | text | required; unique (case-insensitive) |
| `country` | text? | optional — disambiguates similarly-named brands |
| `note` | text? | optional — short free-text |
| `status` | enum | `active` / `inactive` (soft delete only) |
| `created_at` / `updated_at` | timestamp | |

Invariants: `name` unique; created and edited only by a platform operator; `inactive` invisible
to new dekor creates and to the branch attach picker; existing dekorlar of an `inactive`
manufacturer keep referencing it (history preserved); never deleted. Renaming a manufacturer
recomputes the `search_key` of every dekor it makes — the name is folded into that key.

## Dekor

A platform master record of one decor: manufacturer, what kind of stock it is, its code, its
name, its photo, and whether it has a grain. **No thickness, no size, no price** — those are
per-branch facts on [Branch material](#branch-material).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `manufacturer_id` | UUID | required; references a platform [Manufacturer](#manufacturer) |
| `tur` | enum | `ldsp` / `dsp` / `mdf` / `fanera` / `yogoch` / `kromka` / `boshqa` — what the decor *is*. `kromka` is tape-shaped; every other value is panel-shaped |
| `kod` | text? | the decor code, e.g. `H1334 ST9`; optional |
| `nomi` | text | required — the decor name, e.g. `Sonoma eman` |
| `tolali` | bool | required; `true` when the decor has a grain |
| `image_file_id` | UUID? | → [file](support.md#file) — one photo, shared by every format |
| `holat` | enum | `active` / `inactive` (soft delete only) |
| `search_key` | text | server-maintained folded search key (see below); never an input |
| `created_at` / `updated_at` | timestamp | |

`tur` is the single axis that replaced the old `kind` (panel / edge) **and** the old panel
`type`. The two were never independent — kromka was a shape, not a substrate — so one value
now carries both facts. There is **no texture field**: `tolali` is the grain flag and nothing
else describes the surface.

**Uniqueness is by code when there is one, by name when there is not** — two partial,
case-insensitive unique indexes: `(manufacturer_id, tur, lower(kod))` where `kod` is
non-null, and `(manufacturer_id, tur, lower(nomi))` where `kod` is null. A maker's decor
code identifies the decor when it exists; a code-less decor falls back to its name. Both are
partial indexes and therefore Postgres-only — the SQLite test DB proves the shape of the rule,
never its enforcement.

**There is no stored name.** Every display string is composed by one server-side formatter
and sent as `label`, so the admin table, the picker, the PDF and an order's history all read
the same shape. Nothing hand-writes a material name any more, and nothing can drift from it.

`search_key` is the folded concatenation of `nomi`, `kod` and the manufacturer name; it is
recomputed on every write of the dekor and on a rename of its manufacturer. The folding rules
and why search works this way live in
[`catalog-inventory.md`](../features/catalog-inventory.md#bilingual-search).

Invariants: created and edited only by a platform operator (platform-ops scope; no
workshop-side permission grants it); `inactive` invisible to new branch attachments and to
clients; existing branch materials of an `inactive` dekor keep referencing it (history
preserved); never deleted; editing a dekor never affects existing orders (snapshots).

## Branch material

A dekor in one concrete format, carried by one branch — **this is "the material"**. It holds
the format the branch's own supplier sells, the branch's price, its low-stock alert threshold
and its branch-level visibility. Created when a branch attaches a dekor in one or more
formats; the branch's [`stock_item`](inventory.md#stock-item) is created alongside each row.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `branch_id` | UUID | required |
| `dekor_id` | UUID | required; references a platform [Dekor](#dekor) |
| `qalinlik_mm` | numeric | required, > 0 — thickness (sheets e.g. 16/18; tape e.g. 0.4/2) |
| `uzunlik_mm` / `eni_mm` | int? / int? | **panel-shaped only**, both required there; `uzunlik ≥ eni` (long side = grain direction); null for `kromka` |
| `kromka_eni_mm` | int? | **`kromka` only**, required there; tape width in millimetres; null for panel-shaped |
| `price_tiyin` | bigint | per sell unit (per **sheet** for panel-shaped, per **metre** for `kromka`), integer tiyin, ≥ 0. Default `0` — see *Price 0 means unpriced* |
| `min_stock` | int | low-stock alert threshold, in the material's stock unit (sheet count or tape millimetres); ≥ 0; default `0`. **The only home of the threshold** — [`stock_item`](inventory.md#stock-item) carries no copy |
| `status` | enum | `active` / `inactive` at the branch level (soft delete only) |
| `customer_supplied` | bool | a sheet a walk-in carried in, not something the branch sells. Excluded from every catalog listing; see *Customer-supplied boards* |
| `nomi` | text? | operator-typed board name; overrides the dekor's for the label. Null on a carried format |
| `tolali` | bool? | per-board texture answer — one shared dekor cannot carry it. Null inherits the dekor's |
| `source_draft_id` | uuid? | the drawing the board was recorded on, `ON DELETE SET NULL`. **Provenance, not the scope key** — the draft is deleted when the order is placed |
| `stock_material_id` | uuid? | the branch material the board's *shortfall* is sold from, frozen at creation. Null = the branch carries nothing of that size |
| `created_at` / `updated_at` | timestamp | |

**Format uniqueness.** `(branch_id, dekor_id, qalinlik_mm, uzunlik_mm, eni_mm, kromka_eni_mm)`
is unique per branch, with the three nullable columns collapsed through `COALESCE(…, 0)` —
NULLs are distinct in a Postgres unique index, so a plain constraint would let the same
tape-shaped format in twice. The index is **partial on `NOT customer_supplied`**: uniqueness
is a statement about what a branch *carries*, and every customer board points at one shared
dekor, so two walk-ins bringing the same size to one branch produce an identical tuple that a
full index would reject. Panel sizes are **normalized on write** (`uzunlik ≥ eni`), so
2750×1830 and 1830×2750 are one format, not two rows that cut identically.

**Which format columns apply follows the dekor's `tur`**, and `tur` lives on `dekorlar` where
a table CHECK cannot see it. The DB enforces only the column-local halves — thickness positive,
tape width positive when set, `uzunlik ≥ eni` when both are set — and the service owns the whole
rule: `kromka` requires `kromka_eni_mm` and rejects `uzunlik`/`eni`; every other `tur` requires
both `uzunlik` and `eni` and rejects `kromka_eni_mm`.

**Price 0 means unpriced, not free.** A branch routinely registers its whole format list
before it knows prices, so `price_tiyin` defaults to `0` and attaching without a price is
legal. Responses carry a derived `price_unset` flag, and **every** listing keeps and flags
those rows — client-facing ones included, so a client sees the whole shelf rather than the
priced fraction of it. What stops an unpriced format becoming a free order line sits at order
confirmation, not here ([`orders.md`](../features/orders.md#pricing)). **One exception:** a
customer-supplied board priced at 0 is genuinely free — the branch never sold it — so it never
raises `price_unset`. Its price, when it has one, is the branch's own price for the same size,
which is what bills the shortfall.

**Customer-supplied boards.** A sheet the walk-in brought that the branch does not sell is
still a branch material, because `own_panel_counts`, `material_snapshots`, the optimizer's
panel spec and every order item key on a branch-material id. It differs only in that the branch
does not carry it: no [`stock_item`](inventory.md#stock-item) row is created, every catalog and
portal listing excludes it, and only the drawing named by `source_draft_id` can see it. The
rules that govern it — the seeded `Mijoz` dekor, the sheet-count claim, the substitute that
prices the shortfall — live with the feature in
[`cutting.md`](../features/cutting.md).
`min_stock` is an **alert threshold, not a stock policy** — nothing stops the branch
holding less, nothing reserves the quantity, and the low-stock notification fires when
`on_hand ≤ min_stock`, so `0` warns only once the material is gone. The rules behind both
defaults, and what the attach form prefills, are in
[`catalog-inventory.md`](../features/catalog-inventory.md#attaching-a-dekor-to-a-branch).

Order pricing reads `price_tiyin` for **both** shapes: a sheet's per-sheet price for `shop`
panel parts, and a tape's per-metre price for every `shop` edge metre. The per-metre tape price
is the **raw material rate** — the **edge-banding labour** is a separate per-metre rate on
[Branch pricing](#branch-pricing), added on top. Cutting service is the per-panel rate, also on
Branch pricing.

**Everything downstream points here, not at the dekor.**
[`stock_items`](inventory.md#stock-item), [`cutting_panels`](cutting.md#cutting-panel) and
[`order_items`](sales.md#order-item) each carry a `branch_material_id`.

Invariants: the format tuple is unique per (branch, dekor); price and threshold are integer
and ≥ 0; price integer tiyin (never float); editing price, threshold or format never affects
existing orders (snapshots); created and edited by the workshop owner or a `manage_catalog`
grantee on the branch; the referenced Dekor must be `active` at the platform level when the
row is created (existing rows survive a later platform deactivation); `inactive` invisible to
clients shopping at this branch and not selectable in a new cutting; a client sees a material
at a branch only when **both** the Dekor and the Branch material are `active` **and** the row
is priced; never deleted.

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

- [`catalog-inventory.md`](../features/catalog-inventory.md) — how a branch attaches a dekor,
  prices it, and stocks it.
- [`inventory.md`](inventory.md) — the stock item each branch material owns.
