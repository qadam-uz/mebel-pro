---
title: Domain model
status: stable
owner: shape
updated: 2026-05-11
order: 45
related:
  - docs/spec/architecture.md
  - docs/spec/access.md
  - docs/ref/entities/sales/order.md
  - docs/ref/entities/cutting/cutting-result.md
---

# Domain model

The ubiquitous language and the high-level entity map. Per-entity detail (fields, states,
invariants) lives in [`docs/ref/entities/`](../ref/entities/) — this page names the words and the
shape; it does not restate the field lists.

## Ubiquitous language

| Term | Meaning |
|---|---|
| **Platform operator** ("superadmin") | The principal that runs the platform and provisions workshops. Not a workshop user. Modelled as a **platform user**. |
| **Workshop** | A tenant — one furniture-cutting business. (Was "organization" in the old codebase.) Has exactly one **owner**, many branches, many workshop users, settings. |
| **Workshop owner** | The workshop user with `is_owner` — full control of the workshop, plus owner-only powers (user management, force-cancel, refund revert). Cannot be created/demoted except by a platform operator. |
| **Workshop user** | A staff member of a workshop. Login + password. Capability = the owner-flag, or a set of **permission grants**. |
| **Permission grant** | A `(workshop user, permission, branch?)` row. Branch-scoped for operational permissions; the owner needs none. See [`docs/spec/access.md`](access.md). |
| **Client** | The customer. A **separate entity** from workshop users. Telegram-OAuth identity only; global to the platform; picks a branch per order. |
| **Branch** | A physical location of a workshop. Owns its material catalog, warehouse stock, workers, and pricing. Status: `active` / `temporarily_closed` / `inactive`. |
| **Material** | A cuttable sheet product in a branch's catalog — type (DSP/MDF/plywood/…), thickness, color/decor, one standard sheet size, price per sheet, grain (yes/no). Per branch. |
| **Stock item** | A branch's warehouse balance for one material: on-hand, reserved, available, min-stock. |
| **Stock transaction** | An audit row for a stock movement: `stock_in` / `reserve` / `release` / `consume` / `transfer_in` / `transfer_out` / `adjust`. |
| **Worker** | A physical employee of a branch (cutter / driver / assembler / …). Not a system user. |
| **Branch pricing** | A branch's cutting model (`per_sheet` or `per_cut`) + rate, plus edge-banding price per thickness. |
| **Cutting result** | The output of a 2D guillotine optimization run: sheet layouts, waste %, sheets used, cut length, edge-length-by-thickness. Lifecycle `draft` → `confirmed` → `invalidated`. Immutable once written; algorithm version stamped. |
| **Cutting sheet** / **placement** | A sheet within a cutting result; a part's position (x, y, rotated) on a sheet. |
| **Order** | A client's request for panels cut to size at a branch. Owns its items, payments, status history, cancellation, refunds. Carries a **snapshot** of pricing and the confirmed cutting result. Status machine `new` → `pending_payment` → `confirmed` → `in_production` → `ready` → (`in_delivery`) → `completed` / `cancelled`. See [`docs/spec/orders.md`](orders.md). |
| **Order item** | One part line of an order: dimensions, quantity, edge banding, grain, material snapshot, price snapshot. |
| **Order payment** | A payment record against an order: `full` / `advance` / `balance` / `pay_later_settlement`; method `cash` / `bank_transfer` (gateway methods are v1.1); status `pending` / `completed` / `failed` / `refunded`. |
| **Order status event** | One row per order status transition (who, from→to, reason, metadata). The order's audit trail. |
| **Order cancellation** | The single cancel event for an order (who, role, reason, whether a refund is required). |
| **Order refund** | A refund record against a payment: amount, method, status `pending` / `completed` / `failed`, mandatory note (bank ref / receipt). Manual in v1. |
| **Material source** | `own` (client brings their material — cutting service only) or `shop` (workshop supplies material — stock reserved/consumed). |
| **File** | A stored blob (MinIO/S3) optionally attached to an entity — material image, workshop logo, refund/delivery receipt, cutting PDF. |
| **Action log** / **status change log** | The audit log: who did what (action log), and entity state transitions (status change log). Append-only. |
| **Notification** | An in-app inbox item for a principal (order status changed, refund stale, low stock, workshop blocked, …). |
| **Money** | Always integer **tiyin** (1 UZS = 100 tiyin). Never float. |

## Entity map (high level)

Grouped by domain (the `ref/entities/` folders). Cross-domain references are by id, not FK
ceremony — see [`docs/spec/architecture.md`](architecture.md).

- **identity** — `platform user`, `workshop user`, `permission grant`, `client`, `session` (covers
  both staff and client sessions). → [`docs/ref/entities/identity/`](../ref/entities/identity/)
- **workshop** — `workshop` (incl. settings), `branch`, `worker`. → [`docs/ref/entities/workshop/`](../ref/entities/workshop/)
- **catalog** — `material`, `branch pricing`. → [`docs/ref/entities/catalog/`](../ref/entities/catalog/)
- **inventory** — `stock item`, `stock transaction`. → [`docs/ref/entities/inventory/`](../ref/entities/inventory/)
- **cutting** — `cutting result`, `cutting sheet`, `cutting placement`. → [`docs/ref/entities/cutting/`](../ref/entities/cutting/)
- **sales** — `order`, `order item`, `order payment`, `order status event`, `order cancellation`,
  `order refund`. → [`docs/ref/entities/sales/`](../ref/entities/sales/)
- **support** — `file`, `notification`, `action log`, `status change log`. → [`docs/ref/entities/support/`](../ref/entities/support/)

Relationships at a glance:

```
platform user ─provisions─▶ workshop ──owns──▶ branch ──┬─stocks──▶ material ──tracks──▶ stock item ──▶ stock transaction
       ▲ (separate auth)              │                 ├─prices──▶ branch pricing
       │                             │                 └─employs─▶ worker
workshop owner / staff ──grants──▶ permission grant (─scoped to─▶ branch)
client ──places──▶ order ──┬─contains──▶ order item
   (Telegram only)         ├─confirms───▶ cutting result ──▶ cutting sheet ──▶ cutting placement
                           ├─has────────▶ order payment ──▶ order refund
                           ├─has────────▶ order status event
                           └─if cancelled▶ order cancellation
file ─attaches to─▶ {material | workshop | order | order refund | cutting result}
action log / status change log ─capture─▶ every mutation
notification ─targets─▶ {platform user | workshop user | client}
```

When the set of entities changes, update this map and the relevant `ref/entities/` page in the same
edit.
