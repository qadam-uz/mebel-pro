---
title: Catalog & inventory
status: draft
owner: shape
updated: 2026-05-14
order: 50
---

# Catalog & inventory

Materials, branch material selections, branch pricing, and the warehouse. **Materials** are
platform-wide master records (one per spec); each **branch material selection** is what a
branch carries from that catalog, with the branch's own per-sheet price and min-stock;
**branch pricing** drives every order's price (cutting model + edge-banding rates); **stock**
is reserved / consumed / released automatically by the order state machine, plus stock-in,
adjust, and transfer done by staff and the owner.

## Materials (platform master catalog)

Materials live at the platform level. Workshops do not define materials; they pick from this
catalog.

**Operations (platform operator):**

- **Create / edit a material** — type (`dsp` / `mdf` / `plywood` / `natural_wood` / `other`),
  name, thickness, colour, optional decor code, sheet length × width
  (`length ≥ width` — the long side is the grain direction), grain direction (yes / no),
  optional image. No price at this level — price is per-branch. One master record per spec.
- **Activate / deactivate** at the platform level. `inactive` is invisible to new branch
  selections and to clients; existing branch selections keep referencing the master (history
  preserved). No delete.
- **List / get** — operators see all; workshop users see the active subset via the "add to
  branch selection" picker; clients see only what their branch carries (and only when active
  at both levels).

A platform-level edit to a material does not touch existing orders (snapshots — see
[`architecture.md`](../../architecture.md#data-model-invariants)).

### UX (superadmin app)

The platform's **Materials** screen:

- **List** — table: image thumbnail, type, name, thickness, colour / decor, sheet size, grain
  indicator, status, branches-carrying count, action menu. Type / status filter.
  **+ Material**. Empty: "No materials in the catalog yet."
- **Form dialog** — type, name, thickness, colour + decor code, sheet length × width
  (validated `length ≥ width`, both within sane bounds), grain (yes / no select), image upload
  (drag-drop, progress, preview).
- Row actions: Edit · Activate / Deactivate (confirm) · "Branches carrying" drawer (read-only
  list). No Delete.

## Branch material selection

A branch carries a subset of the platform catalog. The `(branch, material)` selection holds
the branch's per-sheet price, its min-stock threshold, and whether the material is currently
visible to clients shopping at this branch.

**Operations (owner, or `manage_catalog` on the branch):**

- **Add a material to the branch** — picks a platform-`active` material; the workshop sets
  the per-sheet price and the `min_stock` threshold (≥ 0). Adding also creates the branch's
  stock item for that material (zero on hand).
- **Edit price or min-stock** — price changes do not touch existing orders (snapshots).
- **Activate / deactivate** at the branch level. `inactive` is invisible to clients shopping
  at this branch and not selectable in a new cutting; existing stock and history stay. No
  delete.

Visibility for read:
- Owner and granted staff see all (including `inactive`) for branches in scope.
- Clients see materials `active` at **both** the platform level and the branch level.

### UX (workshop app)

Under a branch's **Materials** tab (and an owner-wide "Materials" view across the workshop's
branches with a branch filter):

- **List** — table: image thumbnail (from the master), type, name, thickness, colour / decor,
  sheet size, the branch's price, grain indicator, status, action menu. Branch filter.
  **+ Material** → catalog picker (search across all platform-`active` materials, type /
  thickness filter, single-select) → per-branch form (price, min-stock).
- Row actions: Edit (price, min-stock) · Activate / Deactivate for clients (confirm). No
  Delete.

In the **client app** cutting wizard's material step: a searchable grid of the branch's
active selection — each card shows the master's name, type, thickness, colour, sheet size,
grain indicator, image, **and the branch's price per sheet** (only shown when the material
source is `shop`); single-select.

## Branch pricing

A branch has one pricing row, created with the branch itself.

**Operations (owner only — not delegable in v1):**

- **Set / update the pricing row** — `cutting_model` (`per_sheet` or `per_cut`),
  `cutting_rate_tiyin`, and `edge_banding_rates` (a rate per banding thickness; e.g. 0.4 mm,
  2.0 mm). The actor is recorded.

Order pricing reads this row at creation and at re-pricing time, and **snapshots** the values
onto the order and its items. Later changes do not touch existing orders. A part using a
banding thickness with no rate makes order pricing fail with `missing_edge_rate` — the owner
adds the rate.

### UX (workshop app)

Under a branch's **Pricing** tab:

- **Pricing form** — radio between `per_sheet` ("price per sheet, regardless of cut count")
  and `per_cut` ("price per cut"); rate field below it (labelled with the unit per the chosen
  model). Edge-banding rates: a small grid — thickness (mm) | rate per metre — with add /
  remove rows. Save button + unsaved-changes guard.
- Validation: rates ≥ 0; at least one edge-banding row if the branch's typical parts use
  banding (soft warning).
- States: loading, error (`trace_id`), "pricing not set yet" empty state on a new branch (with
  a prompt to configure it before taking orders).
- Staff with no owner role see the same data read-only with an "owner only" note on the edit
  controls.

## Inventory

A branch holds one stock item per material it carries. Movements are atomic and audited.

**Operations:**

- **Stock-in** (owner, or `manage_inventory` on the branch) — material (must be in the
  branch's selection), positive quantity, optional supplier note and receipt file. Increases
  `on_hand`.
- **Adjust** (same caller) — signed delta with a **mandatory note**. Bounded:
  `on_hand` can't go below `reserved` or 0.
- **Branch-to-branch transfer** (owner only) — from-branch, to-branch (both in the workshop),
  material (must exist in both branches' selections), quantity (≤ source `available`). Writes
  paired `transfer_out` + `transfer_in` rows under one transfer id. **Reserved stock cannot
  be transferred.**
- **Reserve / consume / release** (system) — driven entirely by the order state machine; rows
  are locked with `FOR UPDATE` for atomicity. See [`orders.md`](orders.md) → *Warehouse
  contract*.

**Low-stock.** When `available ≤ min_stock` after any change, a notification fires to the
branch's `manage_inventory` grantees and the owner; the daily summary repeats it.

### UX (workshop app)

Under a branch's **Stock** tab (and an owner-wide view with a branch filter):

- **Current stock** — table: material (name + image from the master), on-hand, available,
  reserved, min-stock, last updated; low-stock rows highlighted (danger chip + colour). Row
  click → drawer with the last ~30 transactions for that material. Per-row "Record stock-in"
  → modal (qty, supplier note, delivery-doc upload). Set min-stock inline (or in the
  branch-material form).
- **Transactions** — full log: type (`stock_in` / `reserve` / `release` / `consume` /
  `transfer_in` / `transfer_out` / `adjust`), quantity (signed), balance-after, order link
  (for reserve / consume / release), actor, note, date; filters: type, date range, material.
  Read-only.
- **Transfer** (owner only) — form: from-branch, to-branch, material (only those carried by
  both), quantity (validated ≤ source `available`), reason note. Confirms the move. Staff see
  the tab disabled with an "owner only" tooltip.
- **Adjust stock** action — modal with signed delta + mandatory reason; warns that it changes
  the recorded count.

States: loading (skeletons); empty (branch has no selection yet → "add materials to this
branch" link); error (`trace_id`); "insufficient stock" surfaced on a failed transfer or
adjust. Accessibility: low-stock is signalled by chip + colour, not colour alone; modals
manage focus.

## Edge cases

- **Platform deactivates a material that branches carry** — existing branch selections keep
  referencing it (history preserved); the material is hidden from clients automatically; no
  new branch can add it; stock is untouched.
- **Branch deactivates a material that's still platform-active** — hidden from clients at
  that branch; stock and history stay; other branches that carry it are unaffected.
- **Material referenced by old orders, then deactivated (at either level)** — orders
  unaffected (snapshots).
- **Sheet width entered larger than length** — rejected at platform creation (long side must
  be the grain direction).
- **Edit a branch's price while a client has a cutting draft open** — the draft's later order
  prices at the price as of confirmation (re-read), not the draft moment.
- **Image upload fails (platform creation)** — the material can still be saved without an
  image; the upload is retryable.
- **Reserve loses a race for the last sheet** — the second confirmation gets
  `insufficient_stock`; the order stays `new` (or, if money already moved, `confirmed` with
  `reserve_status = failed` + owner alert; see [`orders.md`](orders.md)).
- **Cancel a `shop` order while `cutting`** — reservation released; if the cutter physically
  used some sheets, staff record an `adjust-stock` write-off via the cancel dialog. **Cancel
  after `cutting` completes** (in `edge_banding`, `ready`, `in_delivery`) — material already
  consumed; no release; the loss is the workshop's.
- **Adjust below `reserved`** — rejected (can't make committed stock disappear).
- **Transfer reserved stock** — rejected (only `available` can move).
- **Stock-in for a material the branch's selection deactivated** — allowed (the selection
  still exists); the material just won't be offered to clients until reactivated.
- **Add to a branch's selection a material the branch already had and then removed** — there
  is no remove (only deactivate), so this becomes "reactivate the existing selection," which
  preserves the stock history and the previous min-stock.
- **`own`-source order** — no inventory interaction at all.
- **Change the cutting model with orders in flight** — those orders keep their snapshot; only
  new orders (and re-priced modifications) use the new model.
- **A part needs an edge-banding thickness with no rate** — order pricing fails
  (`missing_edge_rate`); the owner adds the rate.

## Next

[`orders.md`](orders.md) — the order state machine that drives reserve / consume / release,
and how the snapshot pricing rule plays out at order time.
