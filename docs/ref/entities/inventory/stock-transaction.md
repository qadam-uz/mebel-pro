---
title: Stock transaction
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/ref/entities/inventory/stock-item.md
  - docs/ref/features/inventory-management.md
---

# Stock transaction

## What it is

One audit row for one change to a [stock item](stock-item.md): a stock-in, an order reserve/consume/
release, a branch-to-branch transfer leg, or a manual adjustment. The transaction log is the
auditable history of how a balance got where it is. Append-only.

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `stock_item_id` | UUID | the stock item changed | required; → stock item |
| `type` | enum | `stock_in` / `reserve` / `release` / `consume` / `transfer_in` / `transfer_out` / `adjust` | required |
| `quantity` | int | signed change in sheets (or in `reserved`, for reserve/release) | non-zero |
| `balance_after` | json | snapshot `{ on_hand, reserved, available }` after the change | |
| `order_id` | UUID? | the order, for `reserve` / `release` / `consume` | → order; null otherwise |
| `transfer_id` | UUID? | groups the `transfer_out` + `transfer_in` legs of one transfer | null for non-transfers |
| `actor_user_id` | UUID? | the workshop user, for `stock_in` / `adjust` / `transfer_*`; null when the system did it (`reserve` / `release` / `consume`) | → workshop user |
| `note` | text? | e.g. supplier note, transfer reason, adjustment reason | required for `adjust` |
| `created_at` | timestamp | | |

## States / lifecycle

No lifecycle — write once, never update (append-only audit row).

## Invariants

- A transaction always matches the change actually applied to the stock item in the same atomic
  operation — invariant.
- `reserve` / `release` / `consume` carry an `order_id` and no `actor_user_id` (the system did it on
  an order transition); `stock_in` / `adjust` / `transfer_*` carry an `actor_user_id` — service rule.
- The two legs of a transfer share a `transfer_id` and net to zero across branches — service rule.
- `adjust` requires a `note` — service rule.
- Never updated or deleted — append-only ([`docs/spec/architecture.md`](../../../spec/architecture.md)).

## Relationships

- belongs to → [`docs/ref/entities/inventory/stock-item.md`](stock-item.md) (many-to-one)
- references (logical) → [`docs/ref/entities/sales/order.md`](../sales/order.md), [`docs/ref/entities/identity/workshop-user.md`](../identity/workshop-user.md)

## Owner

[`docs/ref/features/inventory-management.md`](../../features/inventory-management.md).
