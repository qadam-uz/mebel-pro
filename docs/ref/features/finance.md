---
title: Finance
status: draft
owner: shape
updated: 2026-07-09
order: 55
---

# Finance

The workshop's money ledger: **income** the workshop takes (chiefly order payments),
**expenses** it incurs (including staff salary), and the **reports** that tell the owner
whether the workshop is profitable. v1 *tracks* money — it never moves it. There is no
payment gateway and **no automatic payroll**: the accountant records every income and
expense by hand and does the salary arithmetic themselves, using the production reports the
system provides.

## Problem

Today money is receipts in a folder and a notebook. The shop doesn't know its net at
month-end without hours of arithmetic, and "Asror cut 23 panels, multiply by his rate" is
done on paper. v1 closes the loop with the smallest possible ledger: income in, expenses
out, the raw production counts an accountant needs to compute pay — and one report that ties
revenue, expenses, and net together. The system deliberately does **not** compute salaries;
rates are a human contract the accountant applies.

## Income

Money the workshop received. Recorded by a user with `manage_finance`. Every income has a
**type**; one type is **`order_payment`** and carries the order it settles, the rest
(`other`) carry none.

### Operations (`manage_finance`)

- **Record an income** — `type`; `order_id` (**required iff `order_payment`**, must be an
  order of a branch in scope); `amount_tiyin` (> 0; the client paid the full order amount or
  a part of it); `method` (`cash` / `bank_transfer` / `other` — exactly these three; a
plastic-card or terminal payment ("karta") is recorded as `bank_transfer`, there is no
separate `card` method); `received_on` (date);
  optional `note` (bank reference / receipt id) and receipt scan. The recording user is
  logged. Several order payments may be recorded for one order (advance then balance); their
  running sum is validated **≤ the order's `total_tiyin`**.
- **Edit an income** — only while `recorded`; audited.
- **Void an income** — `status = voided` with a **mandatory reason** (used to correct a
  mistake, e.g. a client disputes "I paid, it's not marked"). A voided income doesn't appear
  in reports and doesn't count toward an order's paid total. No delete; the row is kept.

### What the client sees

For an order, the **paid total** is the sum of its `recorded` `order_payment` incomes and
the **balance** is `order.total_tiyin − paid total`. The client app surfaces this only when
the order is `ready` or `completed` ([`orders.md`](orders.md)); a discrepancy is resolved
out-of-system — the client calls the workshop, the accountant voids / re-records.

## Expenses

Money the workshop spent — rent, utilities, consumables it buys, and **staff salary**
(computed by the accountant from the production reports below, then booked here).

### Categories (platform-defined enum)

`rent` · `utilities` · `raw_materials` · `supplies` · `transport` · `equipment` ·
`marketing` · `taxes_and_fees` · `salary` · `other`.

### Operations (`manage_finance`)

- **Record an expense** — `branch_id` (nullable; a workshop-level cost like HQ rent has no
  branch), `category`, `amount_tiyin`, `incurred_on`, `description`, optional `vendor`,
  optional receipt scan. The recording user is logged.
- **Edit an expense** — only while `recorded`; audited.
- **Void an expense** — `status = voided` with a **mandatory reason**. Voided expenses are
  excluded from reports. No delete.

## Worker-production reports

The system does **not** calculate pay. It exposes the raw production each worker did, read
straight from the order stamps ([`orders.md`](orders.md) → *Production stamps*) — the
accountant multiplies by whatever rate the contract says and books a `salary` expense.

A report over a **period** and **branch(es)**, grouped by workshop user:

| Column | Source |
|---|---|
| Panels cut · cut count | Σ `panels_used_snapshot` / `cut_count_snapshot` over orders where the user is `cutter_user_id` and `cut_completed_at` is in the period |
| Orders banded · metres of banding | count + Σ `edge_length_snapshot` over orders where the user is `edger_user_id` and `edge_completed_at` is in the period |
| Metres of banding broken down | grouped by **edge material** (and rolled up by thickness too, since thickness is a property of the material — read from the material at report time) |

Credit is dated by the completion stamp, so it falls in the period the work was done
regardless of when the order was collected. A job reverted ([`orders.md`](orders.md))
clears its stamp, so reverted work doesn't appear. Read-only; `view_finance_reports` (or
`manage_finance`).

## Finance summary

Computed by the backend over a period (date range) and a branch filter (or
workshop-wide), and surfaced on the workshop home (**Asosiy**) dashboard as KPI tiles —
there is no standalone finance-reports page. Read-only; visible with
`view_finance_reports` or `manage_finance`.

- **Income** — sum of `recorded` income in the period, split `order_payment` vs `other`.
- **Expenses** — sum of `recorded` expenses by category and total, in the period.
- **Net** — income − expenses.
- **Per-branch breakdown** — the three lines above, per branch.

## UX

A **Moliya** nav group in the workshop app. The income · expenses · net summary is not a
page of its own — it lives on the workshop home (**Asosiy**) dashboard as KPI tiles
(visible with `manage_finance` or `view_finance_reports`). The group's own pages:

- **Income & expenses** (`/workshop/finance/expenses`, with an income deep-link at
  `/workshop/finance/income`; `manage_finance`) — one page, two tabs. The date range is
  the app-wide date-range picker: one trigger opening preset shortcuts (today / last
  7 days / this month / last month / last 30 days / all) beside a calendar for custom
  spans; every filter auto-applies — there is no separate apply button.
  Each tab carries its own create action at the right end of its filter row; both open
  modal dialogs. The
  date column pairs the business date with the entry timestamp beneath it — a backdated
  record shows when it was actually keyed in.
  - *Income* — table: date, type, order # (when `order_payment`), method, amount, note,
    status, action menu. Filters: date range, type, method, branch, status, min / max
    amount. **+ Income** → modal form (type → if `order_payment`, a searchable order
    picker scoped to the branch; amount; method; date; note; receipt). Row actions: Edit
    (modal) · Void (dialog with a mandatory reason). No Delete.
  - *Expenses* — table: date, category, branch, vendor, amount, description (first 60
    chars), receipt indicator, status, action menu. Filters: date range, category, branch,
    status, min / max amount. **+ Expense** → modal form (category, branch, amount, date,
    vendor, description, receipt). Row actions: Edit (modal) · Void (dialog with a
    mandatory reason). No Delete.
- **Worker production** (`/workshop/finance/production`, `view_finance_reports` or
  `manage_finance`) — the shared date-range picker + branch picker (auto-applied); table
  per worker (panels, cuts, orders banded, metres per edge material listed one line per
  material, with a thickness rollup). The accountant books pay through the Expense form's
  `salary` category — the report page itself is read-only (the earlier "record salary
  expense" shortcut was dropped as redundant). Empty: "No production in this period."

Because the income / expense ledgers require `manage_finance`, a `view_finance_reports`-only
user sees the home summary tiles and worker-production report, but not the ledger pages.

States: dashboards, lists, and detail all have loading / empty / error; mutating actions
confirm; mandatory reasons block submit until filled; receipt upload uses the shared
file-upload UX. Accessibility: forms are labelled; status badges pair colour with text;
void is danger-styled and names its effect.

## Edge cases

- **Client disputes a payment** — the accountant voids the wrong income (reason) and
  re-records the correct one; the order's paid total / balance updates accordingly.
- **Order cancelled after the client paid** — no refund entity; the accountant records an
  **expense** for the money returned (category `other` or `raw_materials` for spent
  material) and, if appropriate, voids the income with a reason.
- **A worker did production but the order was later cancelled** — the stamp (and thus the
  production-report credit) **stays** if the job had completed; it disappears only if the
  job was reverted. The accountant decides whether to pay for it.
- **Order payment exceeds the order total** — rejected; the running sum of an order's
  recorded payments is validated ≤ `total_tiyin`.
- **Voiding an income/expense already in a past report** — allowed; reports are
  period-scoped recomputations, so the current period reflects the void.
- **Workshop currency is and always will be UZS (v1)** — finance numbers are integer tiyin
  per [`architecture.md`](../../architecture.md). The frontend converts for display only.

## Next

- [`orders.md`](orders.md) — the order income settles and the production stamps these
  reports read.
- [`access-management.md`](access-management.md) — where `manage_finance` /
  `view_finance_reports` are granted.
