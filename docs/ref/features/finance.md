---
title: Finance
status: draft
owner: shape
updated: 2026-05-14
order: 55
---

# Finance

The workshop's small-ERP back office: **compensation** policies on workshop users,
**expenses** the workshop incurs, **payroll runs** that compute and disburse pay, and the
**finance reports** that tell the owner whether the workshop is profitable. v1 follows the
same pattern as order payments — the system *tracks* money, the workshop *moves* it offline,
and staff *record* the disbursement.

## Problem

Today, payroll is on paper or in a spreadsheet — a tally of "Asror cut 23 sheets this week,
multiply by his rate, pay him on Friday." Expenses are receipts in a folder. The owner
doesn't know the workshop's net at the end of the month without a couple of hours of
arithmetic. The system already knows everything that matters — orders, who cut what, when —
so v1 closes the loop: rates on the user, expenses entered, payroll generated from the
production stamps, and a single report that shows revenue, expenses, payroll, and the line
that ties them together.

## Compensation

Every workshop user carries a **compensation policy** that says how they're paid. The owner
sets it (owner-only carve-out — rate values are contractually sensitive).

Types (one per active policy, but a policy can be `mixed`):

| Type | Driven by | Example |
|---|---|---|
| `salary` | a flat amount per pay period | office manager — 5 000 000 sum / month |
| `per_sheet` | sheets cut, taken from the order's cutter snapshot | cutter — 50 000 sum × sheets in the period |
| `per_cut` | cut count, from the cutter snapshot | cutter on a cut-rate plan |
| `per_metre_banding` | metres of edge banding applied, from the edger snapshot | edge bander — 1 500 sum × metres in the period |
| `per_delivery` | deliveries completed, from the order's delivery stamp | driver — 30 000 sum × deliveries |
| `commission` | a percent of completed-order revenue at the user's home branch | branch manager — 1.5 % × revenue |
| `mixed` | a stack of the above | per_sheet for cutting + per_metre_banding for the orders this person also banded |

A policy has rate values (tiyin), an `effective_from` date, and an `effective_until` (open
when active). When the owner updates a user's policy, the **current policy is closed** at
"now" and a new one starts. Payroll **reads the policy that was in effect at each completion
timestamp** — so a mid-period rate change is honoured fairly without rewriting history.

A workshop user can also have **no policy** — fine for a user who has never been paid yet
(just created), or who is on a non-paid arrangement.

The policy is set, edited, and viewed under the workshop user's **Compensation** tab — the
nav lives in [`access-management.md`](access-management.md); the rules live here.

## Expenses

Workshop costs not driven by orders or payroll: rent, utilities, supplies, raw consumables
the workshop buys (paint, glue, hardware — *not* sheet materials from the catalog, which are
priced into orders).

### Categories (platform-defined enum)

`rent` · `utilities` · `raw_materials` · `supplies` · `transport` · `equipment` ·
`marketing` · `taxes_and_fees` · `other`.

### Operations (`manage_finance`)

- **Record an expense** — `branch_id` (nullable; an expense without a branch is a
  workshop-level cost like rent for HQ), `category`, `amount_tiyin`, `incurred_on` (the
  date), `description`, optional `vendor`, optional `receipt_url`. Recording user is logged.
- **Edit an expense** — only while `recorded`; status, category, branch, amount, date,
  description, vendor, receipt. Audited.
- **Void an expense** — sets `status = voided` with a **mandatory reason**. A voided expense
  doesn't appear in reports. No delete; the row is kept for audit.

### Read

`manage_finance` and `view_finance_reports` both see the list. Filters: date range, category,
branch, status, min / max amount.

## Production credit (driven by orders)

Per [`orders.md`](orders.md), every order carries the production stamps payroll reads:

- `cutter_user_id`, `cut_started_at`, `cut_completed_at`, `sheets_used_snapshot`,
  `cut_count_snapshot` — taken at the `cutting →` next-state transition.
- `edger_user_id`, `edge_started_at`, `edge_completed_at`, `edge_length_snapshot` — taken at
  the `edge_banding → ready` transition; absent when the order had no banded parts.
- `driver_user_id`, `driver_started_at`, `delivered_at` — taken at the delivery transitions.

The order is the single home — no separate `production_record` table in v1.

If an order is **cancelled after** a phase completed, that phase's credit **stays** (the work
was done). If `shop` material was consumed, the resulting loss is recorded as a
`raw_materials` expense separately. **Cancellation during `cutting`** (force-cancel before
the cutter taps "Cut done") is the exception: no piece-rate credit for partial cutting in
v1; the owner can record a discretionary bonus on the next payroll if warranted.

## Payroll runs

A payroll run aggregates pay for a period.

States: `draft` → `finalized`. Each entry within a finalized run is independently `unpaid` →
`paid` (partials allowed; entries become `paid` only when fully covered).

### Operations

- **Generate a draft run** (`manage_finance`) — input: `period_start`, `period_end`. The
  system computes **one entry per workshop user with non-zero pay in the period**:
  - **Salary lines** — salary rate × the fraction of the period the policy was in effect.
  - **Piece-rate lines** — for each component (`per_sheet`, `per_cut`,
    `per_metre_banding`, `per_delivery`), sum over orders the user was the cutter / edger /
    driver and the relevant completion timestamp fell in the period; multiply by the rate
    that was in effect at *each* completion. The breakdown is preserved on the entry (orders
    count + total quantity per component).
  - **Commission lines** — percent × revenue from completed orders at the user's home branch
    in the period.
  - **Adjustments line** — zero on generate; the operator adds bonuses / deductions before
    finalising.
- **Adjust an entry** (`manage_finance`, only while the run is `draft`) — add an adjustment
  line: signed amount + **mandatory reason**. Recomputes the entry's gross.
- **Re-generate** (`manage_finance`, only while the run is `draft`) — recomputes from
  source data; preserves the operator's adjustments (or warns if they would be lost when
  the source has shifted significantly).
- **Finalize** (`manage_finance`) — locks the numbers; entries become payable. After this,
  no entry can be edited and no adjustment added.
- **Record a payment to an entry** (`manage_finance`) — method (`cash` / `bank_transfer` /
  `other`), amount (≤ entry's outstanding), date, **mandatory `note`** (cash receipt # /
  bank ref / other reference), optional receipt scan. Entry becomes `paid` when the running
  total covers the entry's gross. Partial payments are allowed.
- **Revert a finalized run** (**owner only**, exceptional, audited) — moves it back to
  `draft`; all entries become editable again. Recorded payments are kept (they happened in
  the real world) but flagged as "applied to a reverted run — re-attach in the next run."

### Permission scope

`manage_finance` and `view_finance_reports` are workshop-wide concerns; in the
`(permission, branch)` grant model, grant them on **every branch** of the workshop to give a
user workshop-wide finance scope. The user-management UX presents a single "All branches"
toggle for these two permissions to make this convenient.

## Finance reports

Period selection (date range; presets: this month, last month, YTD, custom). Branch filter
(or workshop-wide).

- **Revenue** — sum of completed orders' totals, minus completed refunds, in the period.
- **Expenses** — sum of `recorded` expenses by category and total, in the period.
- **Payroll cost** — gross of finalized payroll entries (with a sub-line for "paid" vs
  "outstanding").
- **Net** — revenue − expenses − payroll cost.
- **Per-branch breakdown** — the four lines above, per branch.
- **Per-worker output** — for each user with piece-rate or commission pay: cuts done,
  deliveries made, commission base, gross pay, paid status.

Reports are read-only.

## UX

All under a top-level **Finance** nav item in the workshop app (visible to anyone with
`manage_finance` or `view_finance_reports`).

- **Dashboard** (`/workshop/finance`, `view_finance_reports` or `manage_finance`) — the
  reports above as KPI cards + timeseries: Revenue · Expenses · Payroll · Net. Branch
  filter; date-range picker. Drill-down links to the underlying lists.
- **Expenses** (`/workshop/finance/expenses`, `manage_finance` to mutate;
  `view_finance_reports` read-only) — table: date, category, branch, vendor, amount,
  description (first 60 chars), receipt indicator, status, action menu. Filters: date range,
  category, branch, status, min / max amount. **+ Expense** → form dialog (category, branch,
  amount, date, vendor, description, receipt upload). Row actions: Edit · Void (reason). No
  Delete.
- **Payroll** (`/workshop/finance/payroll`, `manage_finance` to mutate;
  `view_finance_reports` read-only) — list of runs (period range, status badge, generated by,
  finalized by, paid / outstanding totals). **+ New run** → period picker. Empty: "No payroll
  runs yet." Row → run detail.
- **Payroll run detail** (`/workshop/finance/payroll/:id`) — header (period, status, totals,
  who generated / finalized); entries table (user, gross, lines breakdown, paid / outstanding,
  action menu). Actions:
  - On a `draft` run: Add adjustment to an entry (signed amount + reason); Re-generate;
    Finalize (confirms total, warns "this locks the numbers").
  - On a `finalized` run: Record payment per entry (modal: method, amount, date, note,
    receipt). Owner-only: Revert run (mandatory reason; warns about open payments).
- **Compensation** is the per-user **Compensation** tab inside the user detail page (lives
  in [`access-management.md`](access-management.md)).

States: dashboards, lists, and detail all have loading / empty / error; mutating actions
confirm; mandatory reasons block submit until filled; the receipt upload supports the same
file-upload UX as elsewhere; the payroll detail's entries table is **virtualised** for
workshops with many staff. Accessibility: forms are labelled; signed-amount adjustment
controls clearly indicate sign; status badges pair colour with text; destructive actions
(void, revert) are danger-styled and name their effect.

## Edge cases

- **Compensation policy changed mid-period** — payroll uses the rate that was in effect at
  each completion timestamp; the entry breakdown notes the split.
- **Cutter completes an order, the order is later cancelled** — the credit stays; the
  consumed material (if any) becomes a `raw_materials` expense to record.
- **Cutter completes an order in period A but the order is `ready` only in period B because
  of `delivery`** — the credit is dated by `cutter_completed_at`, so it falls in period A
  regardless of when delivery happened.
- **Owner reverts a finalized payroll run** — entries become editable; recorded payments are
  preserved but flagged. The operator must re-attach them in the next run (or void them and
  re-record).
- **Workshop blocked while a payroll run is `draft`** — staff can't log in to finalise; the
  run stays `draft` (waiting); platform operator unblocks and the run continues.
- **A user without a compensation policy who did production work** — they appear in the draft
  run with `gross = 0` and a warning row; the owner must set their policy and re-generate
  the draft (or void the warning, since the work is in the past and there's no rate to
  apply).
- **Voiding an expense that was already included in a finalized report** — allowed; the
  reports are time-stamped snapshots, so historic reports don't change; current-period
  reports reflect the void.
- **A finalized run has entries with partial payments and someone reverts it** — owner-only
  action; the payments are kept but the entries can be modified. Auditable trail.
- **Workshop currency is and always will be UZS (v1)** — finance numbers are integer tiyin
  per [`architecture.md`](../../architecture.md). The frontend converts for display only.

## Next

- [`access-management.md`](access-management.md) — where the `manage_finance` /
  `view_finance_reports` grants and the owner-only compensation carve-out are wired.
- [`orders.md`](orders.md) — the production stamps payroll reads from.
