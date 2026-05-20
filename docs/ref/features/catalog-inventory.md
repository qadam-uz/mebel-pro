---
title: Catalog & inventory
status: draft
owner: shape
updated: 2026-05-20
order: 50
---

# Catalog & inventory

The platform material catalog, what each branch carries and prices, the warehouse, and the
suppliers stock comes from. **Materials** are platform-wide master records of two kinds —
**sheets** and **edges**; a workshop only *selects* which it carries. **Stock** is moved in
by the warehouseman and **auto-decremented by the order state machine** as production
completes — there is no reservation. The order ↔ stock contract is owned by
[`orders.md`](orders.md) → *The stock seam*; this doc is the warehouse mechanics behind it.

## Materials (platform master catalog)

Materials live at the platform level. Workshops do not define materials; they pick from this
catalog. Two **kinds** in v1:

| Kind | What it is | Measured in | Has |
|---|---|---|---|
| `sheet` | a cuttable board (DSP / MDF / plywood / …) | sheets | type, thickness, colour / decor, sheet length × width (`length ≥ width` = grain direction), grain yes/no, image |
| `edge` | edge-banding tape applied to a panel's sides | metres | thickness, colour / decor, image |

**Operations (platform operator):**

- **Create / edit a material** — `kind` + the fields for that kind. One master record per
  spec. No price at this level — price is per-branch.
- **Activate / deactivate** at the platform level. `inactive` is invisible to new branch
  selections and to clients; existing branch selections keep referencing the master
  (history preserved). No delete.
- **List / get** — operators see all; workshop users see the active subset via the
  "add to branch selection" picker; clients see only what their branch carries.

A platform-level edit never touches existing orders (snapshots —
[`architecture.md`](../../architecture.md#data-model-invariants)).

## Branch material selection

A branch carries a subset of the catalog. The `(branch, material)` selection holds the
branch's stock unit price, its min-stock threshold, and the client-visibility flag. Adding a
material creates the branch's stock item for it (zero on hand).

**Operations (owner, or `manage_catalog` on the branch):**

- **Add a material** — pick a platform-`active` material; set the per-unit price (per sheet
  for a `sheet`, per metre for an `edge`) and `min_stock` (≥ 0).
- **Edit price or min-stock** — never touches existing orders (snapshots).
- **Activate / deactivate** at the branch level. `inactive` is invisible to clients and not
  selectable in a new cutting; stock and history stay. No delete.

Clients see a material only when it is `active` at **both** the platform and branch level.

## Branch pricing

One pricing row per branch, created with the branch. It — **not** the per-metre edge
material price — is what an order is priced from; the order snapshots it at creation
([`orders.md`](orders.md) → *Pricing*).

- `cutting_model` (`per_sheet` / `per_cut`) + `cutting_rate_tiyin`.
- `edge_banding_rates` — an all-in rate per banding thickness (e.g. `0.4`, `2.0`). This is
  the **price** of banding; the `edge` material it consumes is tracked separately as stock
  (its per-metre selection price is a cost reference, not used in v1 order pricing).

**Owner only** (not delegable in v1). A part using a banding thickness with no rate makes
order pricing fail (`missing_edge_rate`) — the owner adds the rate.

## Suppliers

Who the workshop buys material from. Lightweight and **created on demand**: when recording a
stock-in the warehouseman picks an existing supplier or adds one inline (name, optional
phone / note). Workshop-scoped, never deleted (deactivated if unused). No purchase-order or
accounts-payable flow in v1 — the *money* for a purchase is a separate
[`finance.md`](finance.md) expense the accountant records; the supplier here only labels
where stock came from.

## Inventory

A branch holds one stock item per material it carries — a single `on_hand` balance in the
material's unit (sheets or metres) and a `min_stock` threshold. **No `reserved`, no
`available`, no reservation** — the order never holds stock; it only decrements it.

**Operations:**

- **Stock-in** (owner, or `manage_inventory` on the branch) — material (must be in the
  branch's selection), positive quantity, a supplier (existing or added inline), optional
  receipt file. `on_hand += qty`.
- **Adjust** (same caller) — signed delta with a **mandatory note**; `on_hand` can't go
  below 0. Used for stock-takes and write-offs (including material a cancelled-mid-production
  order physically consumed).
- **Consume / restore** (system) — driven entirely by the order state machine.

**The order seam.** Per [`orders.md`](orders.md): `shop` sheet items are **consumed** when
the order's **Cutting done** is marked; `shop` edge material is **consumed** when **Banding
done** is marked; an operator **revert** of either step **restores** exactly what it
consumed. `own`-source items never touch stock.

**Projected balance & the verify warning.** There is no reservation, so a meaningful "will
we have enough?" needs the demand already in flight. For a material at a branch:

> projected = `on_hand` − Σ (that material's demand from active orders ahead that have not
> yet decremented it)

— sheets are still owed by orders in `confirmed`/`cutting`; edge metres by orders in
`confirmed`/`cutting`/`edge_banding`. When an operator verifies an order
([`orders.md`](orders.md)), a `shop` material whose projected balance won't cover this order
raises a **warning** so they can prompt the warehouseman — it **never blocks** approval
(some workshops buy per order).

**Low-stock.** When `on_hand ≤ min_stock` after any change, a notification fires to the
branch's `manage_inventory` grantees and the owner; the daily summary repeats it.

## UX (workshop app)

Under a branch's tabs (and owner-wide views with a branch filter):

- **Materials** (`manage_catalog`) — table from the master (image, kind, type/thickness,
  colour/decor, sheet size for sheets, the branch's unit price, status). **+ Material** →
  catalog picker (kind + search) → per-branch form (price, min-stock). Row: Edit ·
  Activate / Deactivate. No Delete.
- **Pricing** (owner only) — cutting model + rate; an edge-banding-rate grid (thickness |
  rate per metre, add/remove). Save + unsaved-changes guard; "pricing not set yet" empty
  state on a new branch.
- **Stock** (`manage_inventory`) — table: material (name + image), on-hand, min-stock,
  unit, last updated; low-stock rows highlighted (chip + colour). Per-row **Record
  stock-in** → modal (qty, supplier picker with inline add, receipt upload). Inline
  min-stock. **Adjust** → modal (signed delta + mandatory reason). **Transactions** — full
  log: type (`stock_in` / `consume` / `restore` / `adjust`), signed quantity, balance-after,
  order link (for consume/restore), supplier (for stock_in), actor, note, date; read-only.
- **Suppliers** (`manage_inventory`) — simple list (name, phone, note, active); add / edit /
  deactivate. Mostly reached inline from stock-in.

In the **client app** cutting wizard's material step: the branch's active `sheet` selection
as a searchable grid (name, type, thickness, colour, sheet size, grain, image, **and the
branch's price per sheet** only when the item's source is `shop`); single-select. Edge
banding is chosen per side as a thickness in the wizard ([`cutting.md`](cutting.md)); the
matching `edge` material and its stock are resolved server-side.

States: loading (skeletons); empty (no selection yet → "add materials to this branch");
error (`trace_id`). Accessibility: low-stock is chip + colour, not colour alone; modals
manage focus; owner-only controls are visibly gated for non-owners.

## Edge cases

- **Platform deactivates a material branches carry** — existing selections keep referencing
  it (history preserved); hidden from clients; no new branch can add it; stock untouched.
- **Branch deactivates a material still platform-active** — hidden from clients at that
  branch; stock/history stay; other branches unaffected.
- **Material referenced by old orders, then deactivated** — orders unaffected (snapshots).
- **Sheet width entered larger than length** — rejected at platform creation (long side is
  the grain direction). Not applicable to `edge` materials.
- **`shop` material short when an operator verifies an order** — a **warning**, never a
  block; the operator prompts the warehouseman ([`orders.md`](orders.md)).
- **Order cancelled mid-production after material was consumed** — stock is **not**
  auto-restored (it was physically cut); the warehouseman records an `adjust` write-off if
  the count needs correcting.
- **Operator reverts a completed job** — the system `restore`s exactly the quantity that
  step consumed.
- **Adjust below 0** — rejected.
- **Stock-in for a branch-deactivated material** — allowed (the selection still exists); it
  just won't be offered to clients until reactivated.
- **`own`-source order** — no inventory interaction at all.
- **Add a supplier inline that already exists by name** — the picker prefers the existing
  one; near-duplicates are a manual cleanup, not enforced in v1.

## Next

- [`orders.md`](orders.md) — the state machine that consumes / restores stock and the
  pricing snapshot rule.
- [`finance.md`](finance.md) — the expense side of buying material from a supplier.
