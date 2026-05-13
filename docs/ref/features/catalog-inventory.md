---
title: Catalog & inventory
status: draft
owner: shape
updated: 2026-05-13
order: 50
---

# Catalog & inventory

Materials, branch material selections, branch pricing, and the warehouse. **Materials** are
platform-wide master records (one per spec); each **branch material selection** is what a branch
carries from that catalog, with the branch's own per-sheet price and min-stock; **branch
pricing** drives every order's price (cutting model + edge-banding rates); **stock** is reserved
/ consumed / released automatically by the order state machine, plus stock-in / adjust /
transfer done by staff and the owner.

## Materials (platform master catalog)

Materials live at the platform level. Workshops do not define materials; they pick from this
catalog.

### Endpoints

| Endpoint | Caller | What |
|---|---|---|
| `create-material` / `update-material` | platform operator | type (`dsp`/`mdf`/`plywood`/`natural_wood`/`other`), name, thickness_mm, color, decor_code?, sheet_length × sheet_width (`length ≥ width` — the long side is the grain direction), grain_direction (bool), image (optional). No price at this level — price is per-branch. One master record per spec. |
| `toggle-material-status` | platform operator | `active ↔ inactive` at the platform level. `inactive` is invisible to new branch selections and to clients; existing branch selections keep referencing the master (history preserved). No delete. |
| `list-materials` / `get-material` | platform operator (admin view, all); workshop owner & staff via the "add to branch selection" picker (active only); clients only via their branch's active selection | |

A platform-level edit to a material does **not** touch existing orders (snapshots).

### UX (superadmin app)

The platform's **Materials** screen:

- **List** — table: image thumbnail, type, name, thickness, color/decor, sheet size, grain
  indicator, status, branches-carrying count, action menu. Type / status filter. "+ Material".
  Empty: "No materials in the catalog yet."
- **Form dialog** — type, name, thickness, color + decor_code, sheet length × width (validated
  `length ≥ width`, both within sane bounds), grain (yes/no select), image upload (drag-drop,
  progress, preview).
- Row actions: Edit, Activate/Deactivate (confirm), "Branches carrying" drawer (read-only list).
  No Delete.

## Branch material selection

A branch carries a subset of the platform catalog. The (branch, material) selection holds the
branch's per-sheet price, its min-stock threshold, and whether the material is currently
visible to clients shopping at this branch.

### Endpoints

| Endpoint | Caller | What |
|---|---|---|
| `add-branch-material` | owner or `manage_catalog` on the branch | material_id (must be `active` at the platform level), price (entered in UZS, stored as integer tiyin), min_stock (≥ 0). Creates the selection record and the material's `stock_item` for the branch (zero on hand). |
| `update-branch-material` | same | edit price and/or min_stock. |
| `toggle-branch-material-status` | same | `active ↔ inactive` at the branch level. `inactive` is invisible to clients shopping at this branch and not selectable in a new cutting; existing stock and history stay. No delete. |
| `list-branch-materials` / `get-branch-material` | owner/staff see all (incl. inactive) for branches in scope; clients see materials `active` at **both** levels, for any branch they browse | |

A price change does **not** touch existing orders (snapshots).

### UX (workshop app)

Under a branch's **Materials** tab (and an owner-wide "Materials" view across the workshop's
branches with a branch filter):

- **List** — table: image thumbnail (from master), type, name, thickness, color/decor, sheet
  size, this branch's price, grain indicator, status, action menu. Branch filter. "+ Material"
  → catalog picker (search across all platform-`active` materials, type / thickness filter,
  single-select) → per-branch form (price, min_stock).
- Row actions: Edit (price, min_stock), Activate/Deactivate for clients (confirm). No Delete.

In the **client app** cutting wizard's material step: a searchable grid of the branch's active
selection — each card shows the master's name, type, thickness, color, sheet size, grain
indicator, image, **and the branch's price per sheet** (only shown when material source is
`shop`); single-select.

## Branch pricing

### Endpoints

| Endpoint | Caller | What |
|---|---|---|
| `get-branch-pricing` / `update-branch-pricing` | **owner only** (not delegable in v1) | sets `cutting_model` (`per_sheet` or `per_cut`), `cutting_rate_tiyin` (UZS → tiyin), and `edge_banding_rates` (a rate UZS/metre → tiyin for each banding thickness, e.g. 0.4 mm, 2.0 mm). One pricing row per branch (created with the branch). Records `updated_by_user_id`. |

Order pricing reads this at creation / re-pricing time and **snapshots** the values onto the
order/order-items. A part using a banding thickness with no rate makes order pricing fail with a
clear error — the owner must add the missing rate.

### UX (workshop app)

Under a branch's **Pricing** tab:

- **Pricing form** — radio between `per_sheet` ("price per sheet, regardless of cut count") and
  `per_cut` ("price per cut"); rate field below it (in UZS, labelled with the unit per the
  chosen model). Edge-banding rates: a small grid — thickness (mm) | rate (UZS / metre) — with
  add/remove rows. Save button + unsaved-changes guard.
- Validation: rates ≥ 0; at least one edge-banding row if the branch's selection / typical parts
  use banding (soft warning).
- States: loading, error (`trace_id`), "pricing not set yet" empty state on a new branch (with a
  prompt to configure it before taking orders).
- Staff with no owner role see the same data read-only with a "owner only" note on the edit
  controls.

## Inventory

### Endpoints

| Endpoint | Caller | What |
|---|---|---|
| `stock-in` | owner or `manage_inventory` on the branch | material_id (must exist in the branch's selection), quantity > 0, supplier note?, receipt file? → `on_hand += qty`; writes a `stock_in` transaction with the actor. |
| `adjust-stock` | same | signed delta + **mandatory note** → `on_hand += delta` (bounded — can't go below `reserved` or 0); writes an `adjust` transaction. |
| `get-branch-stock` / `list-stock-transactions` | owner or `manage_inventory` on the branch; clients never see stock numbers | per-material balances + a filterable transaction log. |
| `transfer-stock` | **owner only** (not delegable in v1) | from_branch, to_branch (both in the workshop), material (must exist in both branches' selections), qty (≤ source `available`) → `on_hand` down on source, up on destination; writes paired `transfer_out` + `transfer_in` with the same `transfer_id`. Reserved stock cannot be transferred. |
| `reserve` / `consume` / `release` | system (driven by order state machine) | atomic, row-lock the stock rows (`FOR UPDATE`); see [`orders.md`](orders.md) → *Warehouse contract*. |

**Low-stock:** when `available ≤ min_stock` after any change, a notification fires to the
branch's `manage_inventory` grantees + the owner; the daily summary repeats it.

### UX (workshop app)

Under a branch's **Stock** tab (and an owner-wide view with a branch filter):

- **Current stock** — table: material (name + image, from master), on-hand, available, reserved,
  min-stock, last updated; low-stock rows highlighted (danger chip + color). Row click → drawer
  with the last ~30 transactions for that material. Per-row "Record stock-in" → modal (qty,
  supplier note, delivery-doc upload). Set min-stock inline (or in the branch-material form).
- **Transactions** — full log: type (`stock_in` / `reserve` / `release` / `consume` /
  `transfer_in` / `transfer_out` / `adjust`), quantity (signed), balance-after, order link (for
  reserve/consume/release), actor, note, date; filters: type, date range, material. Read-only.
- **Transfer** (owner only) — form: from-branch, to-branch, material (only those carried by
  both), quantity (validated ≤ source available), reason note. Confirms the move. Staff see the
  tab disabled with an "owner only" tooltip.
- **Adjust stock** action — modal with signed delta + mandatory reason; warns it changes the
  recorded count.

States: loading (skeletons), empty (branch has no selection yet → "add materials to this
branch" link), error (`trace_id`), "insufficient stock" surfaced on a failed transfer/adjust.
Accessibility: low-stock is signalled by chip + color, not color alone; modals manage focus.
Component specs in [`web/DESIGN.md`](../../../web/DESIGN.md).

## Edge cases (whole feature)

- **Platform deactivates a material that branches carry** — existing branch selections keep
  referencing it (history preserved); the material is hidden from clients automatically; no new
  branch can add it to its selection; stock is untouched.
- **Branch deactivates a material that's still platform-active** — hidden from clients at that
  branch; stock and history stay; other branches that carry it are unaffected.
- **Material referenced by old orders, then deactivated (at either level)** — orders unaffected
  (snapshots).
- **Sheet width entered larger than length** — rejected at platform creation (long side must be
  the grain direction).
- **Edit a branch's price while a client has a cutting draft open** — the draft's later order
  prices at the price as of order confirmation (re-read), not the draft moment.
- **Image upload fails (platform creation)** — the material can still be saved without an
  image; the upload is retryable.
- **Reserve loses a race for the last sheet** — the second confirmation gets
  `insufficient_stock`; the order stays `new` (or, if money already moved, `confirmed` with
  `reserve_status = failed` + owner alert).
- **Cancel a `shop` order in production** — material was already consumed; no release; the loss
  is the workshop's.
- **Adjust below `reserved`** — rejected (can't make committed stock disappear).
- **Transfer reserved stock** — rejected (only `available` can move).
- **Stock-in for a material the branch's selection deactivated** — allowed (the selection still
  exists); the material just won't be offered to clients until reactivated.
- **Add to a branch's selection a material the branch already had and then removed** — there is
  no remove (only deactivate), so this case becomes "reactivate the existing selection," which
  preserves the stock history and the previous min-stock.
- **`own`-source order** — no inventory interaction at all.
- **Change the cutting model with orders in flight** — those orders keep their snapshot; only
  new orders (and re-priced modifications) use the new model.
- **A part needs an edge-banding thickness with no rate** — order pricing fails
  (`missing_edge_rate`); the owner adds the rate.
