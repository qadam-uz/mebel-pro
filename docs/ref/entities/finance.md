---
title: Finance
status: draft
owner: shape
updated: 2026-07-18
order: 55
---

# Finance

The workshop's money ledger — **income** received, **expenses** incurred — and the
**counterparty adjustment**, the signed debt correction behind the derived debt balances.
Rules — the income types, the order link, what the client sees, the debt folds and the
worker-production reports the accountant uses to compute salary by hand — live in
[`finance.md`](../features/finance.md). There is no payroll engine and no compensation
policy in v1; salary is just an expense the accountant records.

## Income

Money the workshop received, recorded by a user with `manage_finance`. Typed; the
`order_payment` type carries the order it settles, the rest carry none.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required |
| `branch_id` | UUID? | the branch the money is attributed to; for `order_payment` it is the order's branch |
| `type` | enum | `order_payment` / `other` |
| `order_id` | UUID? | **required iff `type = order_payment`**; null otherwise; an order in the workshop |
| `amount_tiyin` | bigint | > 0 (full order amount or a partial payment) |
| `method` | enum | `cash` / `bank_transfer` / `other` — exactly these three; card/terminal ("karta") is recorded as `bank_transfer` (no `card` value) |
| `received_on` | date | when the money changed hands |
| `note` | text? | bank reference / receipt id |
| `receipt_file_id` | UUID? | → [file](support.md#file) — optional scan |
| `status` | enum | `recorded` / `voided` |
| `voided_reason` | text? | required when `status = voided` |
| `recorded_by_user_id` | UUID | the `manage_finance` user who recorded it |
| `voided_by_user_id` / `voided_at` | UUID? / timestamp? | required when voided |
| `created_at` / `updated_at` | timestamp | |

Lifecycle: `recorded` → `voided` (mandatory reason). A voided income is excluded from
reports and from an order's paid total. No delete; the row is kept for audit.

Invariants: `amount_tiyin > 0`; `order_id` present **iff** `type = order_payment`;
`branch_id` (when set) belongs to the same workshop; for one order, the sum of its
`recorded` `order_payment` incomes is validated **≤ the order's `total_tiyin`**;
`received_on` not in the future; recorded / voided only by users with `manage_finance` on
the relevant branch (or workshop-wide); never deleted.

## Expense

Money the workshop spent — overheads, consumables it buys, and **staff salary** (the
accountant computes it from the worker-production reports and books it here; the system
performs no salary calculation).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required |
| `branch_id` | UUID? | nullable — workshop-level costs (e.g. HQ rent) have no branch |
| `category` | enum | `rent` / `utilities` / `raw_materials` / `supplies` / `transport` / `equipment` / `marketing` / `taxes_and_fees` / `salary` / `other` |
| `amount_tiyin` | bigint | > 0 |
| `incurred_on` | date | required; not in the future |
| `description` | text | required; short human description |
| `vendor` | text? | who was paid (optional free text) |
| `supplier_id` | UUID? | → [supplier](inventory.md#supplier) — optional; a linked expense counts as a **payment to that supplier** in the debt fold, whatever its category. When set and `vendor` is blank, the supplier's name fills `vendor` |
| `receipt_file_id` | UUID? | → [file](support.md#file) — optional scan |
| `status` | enum | `recorded` / `voided` |
| `voided_reason` | text? | required when `status = voided` |
| `recorded_by_user_id` | UUID | the `manage_finance` user who recorded it |
| `voided_by_user_id` / `voided_at` | UUID? / timestamp? | required when voided |
| `created_at` / `updated_at` | timestamp | |

Lifecycle: `recorded` → `voided` (mandatory reason); a voided expense is excluded from
reports. No delete; the row is kept for audit.

Invariants: `amount_tiyin > 0`; `branch_id` belongs to the same workshop when set;
`supplier_id` (when set) is a supplier of the same workshop — inactive suppliers stay
linkable (debt to a deactivated supplier must remain payable); `incurred_on` not in the
future; recorded / voided only by users with `manage_finance` on the relevant branch (or
workshop-wide); voiding requires a reason and a user; never deleted.

## Counterparty adjustment

A **signed debt correction** against exactly one supplier or one client — the pressure
valve of the derived debt balances ([`finance.md`](../features/finance.md) → *Debts*).
It exists for opening balances (pre-system debt history) and real-world events that are
neither a delivery nor a payment (a discount, a return, a mutual offset). It never moves
stock or cash: no stock quantity changes, nothing enters the cash-basis summary — the
amount lives only in the debt fold.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required |
| `supplier_id` | UUID? | → [supplier](inventory.md#supplier); exactly one of the two party fields is set (DB CHECK) |
| `client_id` | UUID? | → client ([identity](identity.md)); the other party option |
| `amount_tiyin` | bigint | signed, non-zero. Sign convention everywhere: **positive = they owe us more, negative = we owe them more** |
| `adjusted_on` | date | business date; not in the future (backdating allowed — opening balances are historical) |
| `note` | text | **required** — the adjustment's document is its explanation |
| `status` | enum | `recorded` / `voided` |
| `voided_reason` | text? | required when `status = voided` |
| `recorded_by_user_id` | UUID | the `manage_finance` user (or owner) who recorded it |
| `voided_by_user_id` / `voided_at` | UUID? / timestamp? | required when voided |
| `created_at` / `updated_at` | timestamp | |

Lifecycle: `recorded` → `voided` (mandatory reason) — the Income/Expense discipline
exactly. Voiding removes it from the fold, so the affected balance self-corrects. Never
edited, never deleted.

Invariants: exactly one of `supplier_id` / `client_id` (DB CHECK); `amount_tiyin ≠ 0`
(DB CHECK); a linked supplier belongs to the same workshop; `note` non-blank; recorded /
voided only by the owner or a `manage_finance` grantee; never deleted. The UI never asks
for a sign — the form asks the direction in words and derives it.

## Next

- [`finance.md`](../features/finance.md) — income types, the order link, the
  worker-production reports, and the finance reports these rows feed.
- [`sales.md`](sales.md) — the order an `order_payment` settles and the production stamps
  the reports read.
