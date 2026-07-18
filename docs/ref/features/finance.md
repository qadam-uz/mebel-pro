---
title: Finance
status: draft
owner: shape
updated: 2026-07-18
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

## Debts (Qarzdorlik)

Who owes whom, per counterparty — derived, never stored. **A balance is never a number
somebody typed: it is always the sum of its story.** Every balance is a read-time fold
over append-only ledgers; voiding any source row self-corrects the balance with no sync
step. Debts are **workshop-level** (a supplier serves every branch) and visible only to
the **owner and `manage_finance` grantees** — `view_finance_reports` alone does not
unlock them.

Sign convention everywhere: **positive = they owe us, negative = we owe them**. The UI
never shows a bare sign — it says the words (*Bizga qarzi* / *Bizning qarzimiz*), color
paired with text.

The supplier fold:

> supplier balance = Σ payments (recorded expenses linked to the supplier)
> − Σ deliveries (priced stock-ins from the supplier)
> ± Σ adjustments (recorded, signed)

Three sources feed it:

- **Deliveries** — `stock_in` transactions carrying a purchase total
  ([`inventory.md`](../entities/inventory.md)). Pre-pricing history rows carry no price
  and contribute zero — a supplier's true position on go-live day is entered as one
  opening-balance adjustment, not backfilled.
- **Payments** — any `recorded` expense with a `supplier_id`, whatever its category.
- **Adjustments** — the signed
  [counterparty adjustment](../entities/finance.md#counterparty-adjustment): opening
  balances and events that are neither a delivery nor a payment (discounts, returns,
  offsets). An adjustment never moves stock or cash — the warehouse *Adjust* operation
  (quantity, no money) is a different record entirely; in the UI they are named
  distinctly: *Zaxira tuzatish* (quantity) vs *Qarz tuzatish* (money).

**The statement (akt sverka).** Per counterparty, any date range: chronological rows —
deliveries, payments, adjustments — each with the running balance after it, plus an
opening balance folding everything before the range. This is the reconciliation ritual
Uzbek businesses already run on paper, rendered live; any disputed number resolves by
reading the statement line by line, never by "the system says so". Within one day, rows
order by entry time; same-second entries fall back to the natural business order (goods,
then money, then corrections).

**Accounting model — hybrid on purpose.** The finance summary stays **cash-basis**; debts
are an **accrual overlay**. A delivery of materials is *not* an expense — the expense
happens when cash leaves. Nothing double-counts: a stock-in's value feeds only the debt
fold; a payment feeds both the expense summary and the fold. Shipping debts changes zero
existing report semantics.

### Operations (owner or `manage_finance`)

- **List supplier debts** — every supplier with its derived balance; search, an
  "only with debt" filter (the default), sorted most-we-owe first; totals for both
  directions.
- **Read a statement** — the akt sverka above, for any date range.
- **Record an adjustment** — party (one supplier or one client), amount, business date
  (backdating allowed, future rejected), **mandatory note**. The form asks the direction
  in words (*Qarzimiz oshadi* / *Qarzimiz kamayadi*); the system derives the sign.
- **Void an adjustment** — mandatory reason; the fold self-corrects. No edit, no delete.

## UX

A **Moliya** nav group in the workshop app. The income · expenses · net summary is not a
page of its own — it lives on the workshop home (**Asosiy**) dashboard as KPI tiles
(visible with `manage_finance` or `view_finance_reports`). The group's own pages:

- **Income & expenses** (`/workshop/finance/expenses`, with an income deep-link at
  `/workshop/finance/income`; `manage_finance`) — one page, two tabs. The active branch
  comes from the topbar context picker (the app-wide convention) — there is no per-page
  branch filter, no branch field in the forms, and no branch column in the tables. New
  records stamp the context branch; editing preserves the record's original branch.
  Workshop-level rows (`branch_id` null) stay visible to the owner in every branch
  context, labelled *ustaxona-keng* — scoping must not hide HQ costs. The date range is
  the app-wide date-range picker: one trigger opening preset shortcuts (today / last
  7 days / this month / last month / last 30 days / all) beside a calendar for custom
  spans; every filter auto-applies — there is no separate apply button.
  Each tab carries its own create action at the right end of its filter row; both open
  modal dialogs. The
  date column pairs the business date with the entry timestamp beneath it — a backdated
  record shows when it was actually keyed in.
  - *Income* — table: date, type, order # (when `order_payment`), method, amount, note,
    status, action menu. Filters: date range, type, method, status, min / max
    amount. **+ Income** → modal form (type → if `order_payment`, a searchable order
    picker scoped to the context branch; amount; method; date; note; receipt). An
    order payment derives its branch from the picked order server-side. Row actions: Edit
    (modal) · Void (dialog with a mandatory reason). No Delete.
  - *Expenses* — table: date, category, vendor, amount, description (first 60
    chars), receipt indicator, status, action menu. Filters: date range, category,
    status, min / max amount. **+ Expense** → modal form (category, amount, date,
    an optional **supplier picker** that links the expense into the supplier's debt fold
    and fills the vendor text with the supplier's name when blank, free-text vendor,
    description, receipt, and — owner only — an *Ustaxona darajasida* checkbox
    that records the cost workshop-level with no branch, the HQ-rent case). Row actions:
    Edit (modal) · Void (dialog with a mandatory reason). No Delete.
- **Debts** (`/workshop/finance/debts`; owner or `manage_finance`) — the Qarzdorlik page.
  Two summary tiles (our total debt to suppliers / theirs to us), search, the
  "only with debt" toggle (default on), and per-row balances in words + color. A row
  opens the **statement** (akt sverka): date range via the shared picker, columns
  *Sana · Hujjat · Qarzimiz + · Qarzimiz − · Qoldiq* with a running balance and an
  opening-balance row when a range is set. Statement actions: **To'lov qilish** (opens
  the expense modal on the ledger page with the supplier pre-picked) and **Tuzatish
  kiritish** (the adjustment form — direction in words, amount, date, mandatory note);
  adjustment rows carry their own void action. The dashboard adds a
  *Ta'minotchilarga qarzimiz* KPI tile, and the Ombor suppliers tab shows each
  supplier's balance to users who could open this page anyway.
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
- **Voided rows and debts** — a voided supplier-linked expense or adjustment leaves the
  debt fold automatically; the balance re-derives. No cleanup job exists or is needed.
- **Wrong-looking balance** — corrected with a *Qarz tuzatish* adjustment (noted,
  auditable), never by faking a payment or a delivery: forcing the number through another
  ledger would corrupt the cash report or the warehouse to fix the debt page.
- **Supplier deactivated with an open balance** — the balance stays visible and payable;
  deactivation only hides the supplier from new stock-ins.
- **Workshop currency is and always will be UZS (v1)** — finance numbers are integer tiyin
  per [`architecture.md`](../../architecture.md). The frontend converts for display only.

## Next

- [`orders.md`](orders.md) — the order income settles and the production stamps these
  reports read.
- [`access-management.md`](access-management.md) — where `manage_finance` /
  `view_finance_reports` are granted.
