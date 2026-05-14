---
title: Finance
status: draft
owner: shape
updated: 2026-05-14
order: 55
---

# Finance

The workshop's small-ERP back office: per-user compensation, workshop expenses, and the
payroll runs that aggregate work into pay. Rules — how compensation maps to a payroll entry,
how a run is generated / adjusted / finalized, what reports the data feeds — live in
[`finance.md`](../features/finance.md). Production stamps that payroll reads from are on the
order ([`sales.md`](sales.md)).

## Compensation policy

How a workshop user is paid. History-tracked: when the owner updates a user's policy, the
current row is closed (`effective_until` set) and a new row starts. Payroll reads the policy
that was in effect at *each* production-completion timestamp, so mid-period rate changes are
honoured fairly without rewriting history.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_user_id` | UUID | required |
| `type` | enum | `salary` / `per_sheet` / `per_cut` / `per_metre_banding` / `per_delivery` / `commission` / `mixed` |
| `salary_tiyin` | bigint? | per `salary_period` (only when `type` includes salary) |
| `salary_period` | enum? | `month` / `biweek` / `week` (only when `salary_tiyin` is set; v1 default `month`) |
| `per_sheet_tiyin` | bigint? | rate per sheet cut (only when `type` includes `per_sheet`) |
| `per_cut_tiyin` | bigint? | rate per cut (only when `type` includes `per_cut`) |
| `per_metre_banding_tiyin` | bigint? | rate per metre of edge banding (only when `type` includes `per_metre_banding`) |
| `per_delivery_tiyin` | bigint? | rate per delivery (only when `type` includes `per_delivery`) |
| `commission_percent` | numeric? | percent of completed-order revenue at the user's home branch (only when `type` includes `commission`); `0 ≤ percent ≤ 100` |
| `effective_from` | date | required |
| `effective_until` | date? | null = current; closed when superseded |
| `created_by_user_id` | UUID | the owner who set this policy |
| `created_at` | timestamp | |

Invariants: at most **one row per workshop user with `effective_until IS NULL`** (the current
policy); `effective_until > effective_from` when set; the rate columns populated must match
the declared `type` (`mixed` allows multiple non-null rate columns; pure-type rows have
exactly the corresponding rate column set); all rate amounts are integer tiyin; created /
updated **only by the workshop owner** (owner-only carve-out); never deleted (the row is
closed and a new one starts).

## Expense

A workshop cost not driven by orders or payroll — rent, utilities, supplies, raw consumables
(paint, glue, hardware — *not* sheet materials from the catalog, which are priced into
orders).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required |
| `branch_id` | UUID? | nullable — workshop-level costs (e.g., HQ rent) have no branch |
| `category` | enum | `rent` / `utilities` / `raw_materials` / `supplies` / `transport` / `equipment` / `marketing` / `taxes_and_fees` / `other` |
| `amount_tiyin` | bigint | > 0 |
| `incurred_on` | date | required; the date the cost was incurred |
| `description` | text | required; short human description |
| `vendor` | text? | who was paid (optional free text) |
| `receipt_file_id` | UUID? | → [file](support.md#file) — optional receipt scan |
| `status` | enum | `recorded` / `voided` |
| `voided_reason` | text? | required when `status = voided` |
| `recorded_by_user_id` | UUID | the staff user (with `manage_finance`) who recorded it |
| `voided_by_user_id` / `voided_at` | UUID? / timestamp? | required when voided |
| `created_at` / `updated_at` | timestamp | |

Lifecycle: `recorded` (the normal state) → `voided` (with a mandatory reason). A voided
expense does **not** appear in reports. **No delete**; the row is kept for audit.

Invariants: `amount_tiyin > 0`; `branch_id` belongs to the same workshop when set; `incurred_on`
not in the future; recorded and voided only by users holding `manage_finance` on the relevant
branch (or workshop-wide); voiding requires a reason and a user; never deleted.

## Payroll run

A period's payroll aggregation for one workshop.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required |
| `period_start` / `period_end` | date | required; `period_end ≥ period_start` |
| `status` | enum | `draft` / `finalized` |
| `gross_total_tiyin` | bigint | sum of the run's entries' `gross_tiyin`; recomputed on entry changes; ≥ 0 |
| `paid_total_tiyin` | bigint | sum of the run's entries' `paid_tiyin`; recomputed on payment record |
| `generated_by_user_id` / `generated_at` | UUID / timestamp | the operator who ran "Generate draft" |
| `finalized_by_user_id` / `finalized_at` | UUID? / timestamp? | set when `→ finalized` |
| `reverted_by_user_id` / `reverted_at` / `revert_reason` | UUID? / timestamp? / text? | set when an owner reverts a finalized run; the run goes back to `draft`; previous payments are flagged but kept |
| `created_at` / `updated_at` | timestamp | |

Lifecycle: `draft` (generated, adjustable, re-generatable) → `finalized` (numbers locked,
entries are payable, the owner can still revert). A reverted run is **back at `draft`** with
the revert metadata recorded; entries become editable again; recorded payments are preserved
but flagged "applied to a reverted run."

Invariants: `period_end ≥ period_start`; **at most one `finalized` run per workshop per
calendar period** is a soft guideline, not enforced — operators can overlap if needed (e.g.,
adjustments after the fact); generated and finalized by users holding `manage_finance` at the
workshop scope; **reverting is owner-only**; never deleted.

## Payroll entry

One entry per workshop user per payroll run, with the breakdown of how the gross was
computed.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `payroll_run_id` | UUID | required |
| `workshop_user_id` | UUID | required; `(payroll_run_id, workshop_user_id)` unique |
| `breakdown` | json | `{ salary_tiyin, per_sheet: { sheets, rate_breakdown[], subtotal_tiyin }, per_cut: { … }, per_metre_banding: { metres_by_thickness, subtotal_tiyin }, per_delivery: { deliveries, subtotal_tiyin }, commission: { revenue_base_tiyin, percent, subtotal_tiyin } }` — present only the components in effect |
| `adjustments` | json | list of `{ reason, signed_amount_tiyin, added_by_user_id, added_at }` — bonuses / deductions added while the run is `draft` |
| `gross_tiyin` | bigint | sum of breakdown subtotals + adjustments; ≥ 0 (an entry can't go negative; deductions exceeding the gross are capped) |
| `paid_tiyin` | bigint | sum of `completed` payments against this entry; `0 ≤ paid_tiyin ≤ gross_tiyin` |
| `created_at` / `updated_at` | timestamp | |

Lifecycle: created when the run is generated; mutable while the run is `draft` (adjustments
can be added / removed); locked when the run is `finalized`; `paid_tiyin` continues to evolve
as payments are recorded against it (an entry is conceptually `paid` when
`paid_tiyin = gross_tiyin`).

Invariants: `(payroll_run_id, workshop_user_id)` unique (DB); rate breakdown reflects the
compensation policy in effect at each production-completion timestamp (history-correct
payroll); `paid_tiyin ≤ gross_tiyin`; adjustments only added while the parent run is `draft`;
never deleted.

## Payroll payment

A record of money paid to a worker for a payroll entry. Same v1 pattern as order payments —
the system *tracks* money; the workshop *moves* it offline; staff *record* it.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `payroll_entry_id` | UUID | required |
| `amount_tiyin` | bigint | > 0; ≤ the entry's remaining (`gross_tiyin − paid_tiyin`) |
| `method` | enum | `cash` / `bank_transfer` / `other` |
| `paid_at` | date | when the money actually changed hands |
| `note` | text | **mandatory** — cash receipt #, bank reference, or other concrete identifier |
| `receipt_file_id` | UUID? | → [file](support.md#file) — optional receipt scan |
| `recorded_by_user_id` | UUID | the staff user with `manage_finance` who recorded it |
| `revert_flag` | bool | `true` if the run this belongs to has been reverted since this payment was recorded; default `false` |
| `created_at` | timestamp | |

Invariants: `amount_tiyin > 0`; sum of payments per entry ≤ the entry's `gross_tiyin`
(enforced atomically when recording); `note` mandatory; recorded only against entries on a
`finalized` run; never deleted. When the parent run is reverted, `revert_flag = true` is set
on each existing payment, but the rows are kept (the money moved in the real world — the
operator must re-attach in the next run or void via a fresh entry adjustment).
