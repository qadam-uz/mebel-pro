---
title: Material catalog
status: stable
owner: shape
updated: 2026-05-11
order: 16
related:
  - docs/spec/cutting.md
  - docs/spec/orders.md
  - docs/ref/entities/catalog/material.md
  - docs/ref/entities/inventory/stock-item.md
  - docs/ref/features/inventory-management.md
---

# Material catalog

## Problem

A branch cuts a specific set of board products — particular types, thicknesses, decors, sheet sizes,
each with a price. Customers need to browse and pick one to start a cutting; the optimizer needs the
sheet size and grain; the order needs the price. The catalog is per branch (the same product may be
priced differently, or absent, elsewhere). Materials are never destroyed — old orders snapshot them.

## User stories

- As a **workshop owner / staff with `manage_catalog`**, I want to add a material with its
  properties, price, and a sample image so customers can choose it.
- As the same, I want to edit a material's details or price, knowing existing orders won't change.
- As the same, I want to deactivate a material that's discontinued so customers can't pick it, while
  keeping it for old orders.
- As a **client**, I want to browse a branch's active materials with prices and properties when
  starting a cutting.

## Requirements

1. `create-material` (owner or `manage_catalog` on the branch): branch_id (in scope), type
   (`dsp` / `mdf` / `plywood` / `natural_wood` / `other`), name, thickness_mm, color, decor_code?,
   sheet_length_mm + sheet_width_mm (one standard size; `length ≥ width` — the long side is the grain
   direction), price (entered in UZS, stored as integer tiyin), grain_direction (bool), image
   (filevault attach, optional). Creates the material's `stock_item` for the branch (zero on hand).
2. `update-material` (same): edit any of the above; a price change does **not** touch existing orders
   ([`docs/spec/architecture.md`](../../spec/architecture.md)).
3. `toggle-material-status` (same): `active ↔ inactive`. `inactive` materials are invisible to
   clients and not selectable in a new cutting. No delete.
4. `list-branch-materials` / `get-material`: owner/staff see all (incl. inactive) for branches in
   scope; clients see `active` only, for any branch they're browsing.
5. Every mutating action writes an audit-log row; status changes also write a status-change-log row.

## UX

In the **seh app**, under a branch's **Materials** tab (and an owner-wide "Materials" view across the
workshop's branches with a branch filter):

- **Materials list** — table: image thumbnail, type, name, thickness, color/decor, sheet size,
  price, grain indicator, status, action menu. Branch filter (defaults to the current branch in the
  switcher). "+ Material". Empty: "No materials in this branch yet."
- **Material form dialog** — type, name, thickness, color + decor_code, sheet length × width
  (validated `length ≥ width`, both within sane bounds), price in UZS (converted to tiyin on send),
  grain (yes/no select), image upload (drag-drop, progress, preview).
- Row actions: Edit, Activate/Deactivate (confirm). No Delete.
- Inline errors mapped from `error.code` (e.g. invalid dimensions).

In the **client app**, the cutting wizard's material step shows a searchable grid of the branch's
active materials — each card: name, type, thickness, color, sheet size, **price per sheet** (only
shown when the material source is `shop`), grain indicator, image; single-select. Empty: "This
branch hasn't published any materials yet — pick another branch." (See [`docs/ref/features/cutting-optimization.md`](cutting-optimization.md).)

- States: loading (skeletons), empty (no materials), error (`trace_id`), image-upload in progress /
  failed.
- Accessibility: the grid cards are real radio options with labels; image-only thumbnails have alt
  text; the deactivate action is danger-styled.

Shared patterns (data table, file uploader, searchable card grid): [`docs/ref/ux/components.md`](../ux/components.md).

## Entities touched

- [`docs/ref/entities/catalog/material.md`](../entities/catalog/material.md) — created, edited, status-toggled.
- [`docs/ref/entities/inventory/stock-item.md`](../entities/inventory/stock-item.md) — created with the material (zero on hand).
- [`docs/ref/entities/workshop/branch.md`](../entities/workshop/branch.md) — the owning branch.
- [`docs/ref/entities/support/file.md`](../entities/support/file.md) — the material image.
- [`docs/ref/entities/support/action-log.md`](../entities/support/action-log.md), [`docs/ref/entities/support/status-change-log.md`](../entities/support/status-change-log.md).

## Edge cases

- **Deactivate a material with stock on hand** — allowed; the stock item stays (history); the
  material is just hidden from clients.
- **A material referenced by old orders, then deactivated** — orders are unaffected (they snapshot
  it).
- **Sheet width entered larger than length** — rejected (the long side must be the grain direction).
- **Edit price while a client has a cutting draft open** — the draft's later order will price at the
  price as of order confirmation (re-read), not the draft moment.
- **Image upload fails** — the material can still be saved without an image; the upload is retryable.

## Out of scope

- Multiple sheet sizes per material — v1 is one ([`docs/spec/open-questions.md`](../../spec/open-questions.md) Q7).
- Remnant / offcut tracking — future.
- Supplier records, price comparison, auto purchase orders — future.
- Barcode / QR on materials — future.

## Open questions

- Delegating `manage_catalog` is already in the v1 grant catalog; no open question specific to this
  feature.
