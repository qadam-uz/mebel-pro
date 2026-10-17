---
title: Cutting
status: draft
owner: shape
updated: 2026-10-17
order: 40
---

# Cutting

A client's drawings and the output of optimisation runs. A **drawing** is a parts list grouped
into material groups by substrate and thickness — it names no workshop, no decor and no price;
those are chosen when it is ordered ([`orders.md`](../features/orders.md#placing-an-order)). It
lives as a [cutting draft](#cutting-draft) until it is ordered, then inside its order, and as a
[saved drawing](#saved-drawing) when the client keeps a copy for reuse. Results are immutable.
Rules are in [`cutting.md`](../features/cutting.md).

## The drawing's content

One shape, shared by the draft, the saved drawing and an order's frozen copy — so a drawing
moves between them without translation.

**Material group** — one entry of `groups`:

| Field | Type | Notes |
|---|---|---|
| `group_ref` | UUID | stable within the drawing; parts point here |
| `name` | text? | the client's label («Korpus», «Fasad»); null renders as `{TYPE} {thickness} · {n}`. Two groups of one substrate and thickness are normal — a white carcass and a wood front — so the name is how the order step tells them apart |
| `type` | enum `decor_type` | required; **panel-shaped values only** |
| `thickness_mm` | numeric | required, > 0. Part dimensions are designed for it, so the order step never changes it — it filters the decors offered |
| `sheet_length_mm` / `sheet_width_mm` | int? / int? | optional, both or neither; `length ≥ width`, normalized on write. When set, the drawing shows an estimate and the order step preselects a format of this size |
| `source` | enum | `manual` — edited, and optimised at the order step · `map` — a 2D-Place layout, locked ([`cutting.md`](../features/cutting.md#map-groups)) |
| `map` | json? | `map` groups only: `file_name`, `kerf_mm` and `edge_trim_mm` derived from the layout, the sheet size, and every sheet with its placements and offcuts |

**Part** — one entry of `parts`: `part_ref` (UUID), `group_ref`, optional display `name`
(`null` renders `D{row}`), `length_mm`, `width_mm`, `quantity`, `follow_grain` (bool, default
**`true`** — *follows the grain if the decor has one*,
[`cutting.md`](../features/cutting.md#grain)), `thickened` (bool, default `false`,
staff-only), and per side `edge_<top|bottom|left|right>` — `null` or `{ "thickness_mm": 2 }`.
**A side names a tape thickness, never a tape**: the tape's decor is chosen per group at the
order step, and its width follows from the group's thickness, doubled on a thickened part.

Invariants: 1..100 part rows and ≤ 300 pieces; every `group_ref` names a group of the same
drawing; a `map` group's parts are exactly the parts its layout places — names, edges and
`thickened` may change, nothing else; an empty group is legal in a draft and refused at the
order step.

## Cutting draft

A drawing not yet ordered — **«Qoralama»** on screen. Private to its client — or, when minted
by workshop staff for a walk-in, to that workshop's staff until the order is placed. Persists
indefinitely; a client holds at most 50 self-made drafts.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `client_id` | UUID | the client who owns it |
| `name` | text? | editable label; a MAP import seeds it from the file name, extension stripped (`AFZAL.map` → `AFZAL`) |
| `groups` / `parts_snapshot` | json | [the drawing's content](#the-drawings-content) |
| `order_setup` | json? | the order step's choices so far: `branch_id`, and per `group_ref` a material choice — `catalog` + `branch_material_id` · `workshop` + optional `note` · `customer` + a customer-board spec (staff only) — and a kromka choice — `catalog` + tape decor · `workshop`. Null until the order step starts. Prefilled by a [re-order](../features/orders.md#re-ordering) and, for a copy of a saved drawing, from its last order at the same branch |
| `created_via_workshop_id` | UUID? | null for a self-made draft; the minting workshop when staff created it for a walk-in. Staff access is workshop-scoped, the draft is hidden from the client until the order is placed, and it is outside the 50-draft cap. Its `order_setup.branch_id` is the staffer's branch, frozen at creation. Unfinished ones are listed on the workshop's **Qoralamalar** surface |
| `revision_of_order_id` | UUID? | set only on an order's revision draft ([`orders.md`](../features/orders.md#revising-a-placed-order)), unique per order; its only exits are apply and discard |
| `reorder_of_order_id` / `from_saved_drawing_id` | UUID? / UUID? | provenance, copied onto the order at placement: the order this draft repeats, or the saved drawing it was copied from |
| `chosen_result_id` | UUID? | the result the order step computed for the current content and `order_setup`; any change to either clears it |
| `created_at` / `updated_at` | timestamps | |

**There is no branch column.** A drawing is workshop-agnostic until its order step picks a
branch. The old `preferred_branch_id` scoped the catalog and the saw settings; both now belong
to the order step, and a pin only preselects its first step.

Invariants: owned by the client whether self-made or staff-minted; never visible beyond the
access rules in [`cutting.md`](../features/cutting.md#access); every reference in
`order_setup` is re-checked against the branch's current catalog before use — a stale one is
cleared, never honoured; at most one chosen result; on order placement — or a revision apply —
the chosen result becomes `confirmed` and bound, the content moves onto the order, and the
draft is deleted; a self-made draft is deletable by its client at any time, a staff-minted one
by its workshop's staff (cascades to results, panels, placements).

## Saved drawing

A drawing the client keeps for reuse — **«Saqlangan chizma»**. An usta rarely reuses one
client's drawing for another, so an ordered drawing simply lives in its order; only what the
usta deliberately saves lands here. A saved drawing is **an independent, decor-less copy**:
ordering it copies it into a new draft, and nothing done to a draft or an order reaches it.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `client_id` | UUID | owner |
| `name` | text | required; prefilled from the source's name |
| `groups` / `parts_snapshot` | json | [the drawing's content](#the-drawings-content); a `map` group keeps its layout and stays locked |
| `saved_from_order_id` | UUID? | the order it was saved from, when it was |
| `created_at` / `updated_at` | timestamps | |

How often it was ordered, and when last, is **derived** from the orders carrying its id in
`from_saved_drawing_id` — never stored.

Invariants: private to its client — no workshop reads it; editable by its client only; saving
copies the content as it is at that moment, and a later edit to the source does not follow;
never carries a branch, a decor, a price or an `order_setup`; at most 200 per client
(anti-abuse — raise it when a real usta reaches it); deleting one never touches an order.

## Customer board

Sheets the client brings — **theirs, not the branch's** — for one material group of one order.
Recorded by staff only: at the order step of a walk-in draft, or on a `new` / `confirmed` order
([`orders.md`](../features/orders.md#customer-material)). The client app never offers it; a
client says so in an «Ustaxona belgilaydi» note or by phone. Never listed in any catalog,
never stocked, never offered to anyone else.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` / `branch_id` | UUID | the order's workshop and branch |
| `name` | text? | staff-typed; null falls back to «Mijoz materiali» plus the size |
| `type` / `thickness_mm` | enum `decor_type` / numeric | copied from the group — panel-shaped only; the service rejects `kromka` and a CHECK backs it |
| `length_mm` / `width_mm` | int / int | the client's sheet size; required, > 0, `length ≥ width`, normalized on write. A `map` group's board must match its layout's sheet size exactly |
| `has_grain` | bool | decides rotation for the group's parts that follow the grain |
| `created_at` | timestamp | |

**The client brings every sheet the group needs.** The result says how many; the order shows
it as «Olib kelasiz: N ta list»; the group's material line is not charged, while cutting and
banding labour are. A client bringing only some of a group's sheets is a catalog material
with an own-sheet count on the order — the existing claim
([`orders.md`](../features/orders.md#pricing)) — so the board needs no shortfall price and no
substitute format any more.

A board id and a branch-material id come from disjoint UUID namespaces, so every dict that
keys on "a material" — `own_panel_counts`, `material_snapshots`, `panels_used_by_material`,
price overrides — takes either without a second key shape.

Invariants: panel-shaped only; no [`stock_item`](inventory.md#stock-item) exists for it and no
stock movement names it; immutable after creation — a wrong one is replaced; never deleted.

## Cutting result

The output of one optimisation run for one drawing at one branch with one set of material
choices — computed at the order step, or by staff when they resolve an order's materials. A
run may evaluate several providers internally but persists only the validated, engine-scored
winner. The engine/provider version is stamped for audit; replacing a solver later doesn't
touch past results.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `draft_id` | UUID? | the draft it came from; null once `confirmed` (the result outlives the draft through `order_id`) |
| `algorithm_name` / `algorithm_version` | text | internal audit stamp for the optimised groups: `cutting-engine/native`, `cutting-engine/packingsolver` or `cutting-engine/hybrid` plus version; `imported-2dplace-map` / `map-1` when every group is a MAP group. Not a client-visible choice |
| `status` | enum | `candidate` (the draft's or the pending order's current result) · `confirmed` (bound to an order) |
| `complete` | bool | `false` while its order still has groups whose material the workshop has not chosen («Ustaxona belgilaydi»): the result then covers only the resolved groups. Confirming an order requires `true` |
| `kerf_mm` / `edge_trim_mm` | int | the branch settings the **optimised** groups ran with. A MAP group keeps the pair derived from its own layout, in `groups_snapshot` |
| `panels_used_by_material` | json | `{ "<material_id>": 3, … }` — sheets per panel material (≤ 20 each); a key is a branch-material id or a [customer-board](#customer-board) id |
| `waste_percentage` | numeric | 0.0–1.0, weighted across every panel material in the result |
| `total_cut_length_mm` / `total_edge_length_mm` | int | feed the pricing metrics |
| `edge_length_by_material` | json | `{ "<kromka branch_material_id>": 12500, … }` — geometric length per tape in integer millimetres; UI and pricing display metres |
| `groups_snapshot` / `parts_snapshot` | json | the drawing's content at run time, so the result renders after its draft is gone |
| `material_snapshots` | json | display and spec facts copied at run time for every material the result references, branch materials and customer boards alike — `manufacturer_name`, `type`, `code`, `name`, `thickness_mm`, `length_mm`, `width_mm`, `tape_width_mm`, `has_grain`, `finished_sides`, plus `customer_supplied` on a board. **Frozen history is never rewritten**, so older rows carry the Uzbek vocabulary (`tur`, `kod`, `nomi`, `tolali`, `qalinlik_mm`, `uzunlik_mm`, `eni_mm`, `kromka_eni_mm`) and the oldest the pre-reshape English one (`decor_code`, `color`, `panel_length_mm`, `panel_width_mm`, `edge_width_mm`); the label formatter and the sheet-size resolver behind every drawn map read **all three**, newest key first |
| `edge_length_shop_by_material` / `edge_length_own_by_material` | json | source-split geometric edge length per kromka branch material, integer millimetres |
| `edge_consumed_shop_by_material` / `edge_consumed_own_by_material` | json | source-split consumption per kromka branch material, integer millimetres; includes the branch's `edge_overhang_mm` once per banded side ([`workshop.md`](workshop.md)) |
| `edge_banded_sides_by_material` | json | `{ "<kromka branch_material_id>": { "shop": 4, "own": 2 } }` — banded-side counts feeding consumption and the stock math |
| `own_panel_counts` | json | the order's own-sheet claims projected onto this layout, clamped to the sheets it uses; frozen once `confirmed` |
| `order_id` | UUID? | the order it is bound to |
| `created_at` / `confirmed_at` | timestamps | |

**How the groups are laid out.** Manual groups mapped to the **same** branch material are
optimised together and share sheets — they are one physical board, and the client split them
only to keep the list readable. A MAP group is never optimised: its placements are copied
from its layout onto the format chosen for it, which must match the layout's sheet size. Each
group's parts follow the grain rule against the decor chosen for it
([`cutting.md`](../features/cutting.md#grain)).

Lifecycle: `candidate` when computed → `confirmed` when its order is confirmed or placed by
staff (`order_id`, `confirmed_at`, `draft_id` cleared). A pending order's candidate is
replaced when staff resolve its materials; `confirmed` results are kept forever.

Invariants: **immutable** after creation — only `status`, `order_id`, `confirmed_at` and
`draft_id` change; a `confirmed` result is `complete` and has a non-null `order_id`; a
`candidate` belongs to a draft or to a `new` order; each material in
`panels_used_by_material` counts ≤ 20 sheets; the placements cover every part-instance of the
groups the result covers, exactly once; a result carries enough snapshots to render after its
draft is deleted or the catalog changes.

## Cutting panel

One physical sheet within a result — which material it is, its index within that material,
and how much waste it has.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `cutting_result_id` | UUID | required |
| `branch_material_id` | UUID? | a sheet the branch carries — its [branch material](catalog.md#branch-material), and through its format the sheet size and grain that govern its placements |
| `customer_board_id` | UUID? | a sheet the client brought — a [customer board](#customer-board) instead |
| `source` | enum | `optimizer` · `imported_map` — a MAP group's sheet, copied as laid out |
| `group_ref` | UUID? | the MAP group an `imported_map` sheet belongs to; null on optimised sheets, which may carry several groups' parts |
| `panel_index` | int | 1, 2, 3, … within the result's sheets of this material; unique per (result, material) on each of the two id columns |
| `waste_area_mm2` | bigint | ≥ 0 |
| `cut_count` / `cut_length_mm` | int? / int? | exact engine figures for the sheet; null on `imported_map` and legacy sheets, whose cut path is unknown |
| `offcuts` | json? | display-only rectangles `{ x_mm, y_mm, length_mm, width_mm, usable }`; null on old rows, served as `[]`. Usable offcuts show as client-retained remainders, the rest as waste |

**Exactly one of `branch_material_id` / `customer_board_id` is set** — a DB CHECK. The
`panel_index` uniqueness needs **two** constraints for the same reason: NULLs are distinct in a
unique index, so one constraint over a nullable column stops policing the other kind of sheet.

Invariants: exactly one material id; `panel_index` contiguous from 1 to the material's count;
`group_ref` set exactly when `source = imported_map`; immutable; deleted with its result.

## Cutting placement

One placed part on one panel: which part it is, where it sits (origin bottom-left), the
dimensions as placed, and whether it was rotated 90°.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `cutting_panel_id` | UUID | required |
| `part_ref` | text | the part's id in the result's `parts_snapshot` |
| `part_quantity_index` | int | 1..quantity |
| `x_mm` / `y_mm` | int | origin on the panel, within the usable area |
| `length_mm` / `width_mm` | int | dimensions as placed |
| `rotated` | bool | `true` when turned 90° from the part's nominal orientation |

Invariants: every part-instance of the covered groups appears exactly once; a placement sits
on a sheet of its part's group material; a part the grain rule locks is never `rotated` by the
optimiser — `imported_map` placements are copied as the file laid them out; placements don't
overlap and stay within `panel − 2× edge_trim`; immutable.

## Next

- [`../features/cutting.md`](../features/cutting.md) — drawings, groups, the editor and the
  optimiser.
- [`../features/orders.md`](../features/orders.md#placing-an-order) — the order step that turns
  a drawing into a priced layout.
- [PackingSolver provider spec](https://github.com/BerdiyorovAbrorjon/cutting-engine/blob/main/docs/PACKINGSOLVER_PROVIDER_SPEC.md)
  — internal solver orchestration and audit stamps.
