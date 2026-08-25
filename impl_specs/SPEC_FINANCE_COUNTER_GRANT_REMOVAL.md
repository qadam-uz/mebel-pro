# Finance: retire the `record_order_payment` grant; make the ledger total honest

Status: approved for implementation · Owner: Abrorjon Berdiyorov · Written: 2026-08-22
Repo: `mebel-pro`. Owner decision (2026-08-22): the workshop's cashier is simply given
**`manage_finance`** — they may record, edit and void payments and expenses, and the
end-of-day question ("who took how much, what was spent") is answered by the ledger that
already exists: date filter + **Kim yozgan** filter + the *jami* line under the filters, with
the rows beneath as the detail. No new permission, no shift-close entity, no cash/card split,
no new screen. The owner explicitly asked for the **smallest** shape that handles real life.

That decision makes the `record_order_payment` grant (shipped 2026-08-21 in PR #123,
**already on `main` and in production**) surface nobody uses: one more checkbox in the
owner's Ruxsatlar panel, a section in three docs, a second authz branch in the backend.
This spec removes it and keeps the one useful thing it brought — the **To'lov qabul qilish**
action on the order page — for `manage_finance`.

Two findings the implementer must not undo:

- The ledger **already** shows a period total: `FilterStatus` under the `.mp-filters` bar
  renders `{count} ta {noun} · jami {total}` from `periodTotalTiyin` in
  `web/src/shared/views/WorkshopFinanceExpensesView.vue`. Do not add a second "Jami" strip.
- The ledger rows already carry *kiritilgan {sana} · {xodim}* and the **Kim yozgan** filter
  (`recorded_by_user_id`). These stay exactly as they are — they are the end-of-day report.

## 0. Process rules

- Read `backend/AGENTS.md` and `web/AGENTS.md` before touching either project; docs edits go
  through the **docs-management** skill; test placement through **testing-practices**.
- One spec = one PR, on a fresh feature branch off `origin/main`
  (`feat/finance-retire-counter-grant`). Do **not** build on `feat/catalog-page-ux` — it
  carries unrelated uncommitted catalog work.
- Full check gates green per touched project (`backend/`, `web/`; `e2e/` typecheck — no
  e2e spec references the grant, verify with grep). Commit on the feature branch; do not
  push, do not open a PR.
- The web gate does not run Playwright: grep `e2e/tests/` for `To'lov qabul qilish` and
  `record_order_payment` before and after; nothing should match, nothing should drift.

## 1. Backend — remove the grant

### 1.1 Enum + migration

- `app/models/enums.py`: delete `Permission.RECORD_ORDER_PAYMENT` and its comment.
- New Alembic migration (revises `b3c9f7d21a48`, hand-written — autogenerate does not see
  enum values), `retire_record_order_payment_permission`:
  - `upgrade()`: `DELETE FROM permission_grants WHERE permission = 'record_order_payment'`.
    Postgres cannot drop a value from an enum type in place; the value stays in the DB type,
    **unused and unreadable by the code** (the `Permission` StrEnum no longer carries it,
    which is why the grants must be deleted first — a surviving row would fail to load).
    Say exactly this in the migration docstring, the way `b3c9f7d21a48` documents its own
    asymmetric downgrade. Do **not** rebuild the enum type; the orphan value is the boring
    choice and costs nothing.
  - `downgrade()`: `ALTER TYPE permission ADD VALUE IF NOT EXISTS 'record_order_payment'`
    (idempotent; the grants themselves are not restorable and the docstring says so).
- Do not edit or delete `b3c9f7d21a48` — it has run in prod.

### 1.2 Authorization sites

- `app/modules/finance/service.py`: delete `ORDER_PAYMENT_WRITE_PERMISSIONS`; the
  `create_income` path that resolved the order target with it uses `WRITE_PERMISSIONS`
  (i.e. `manage_finance`) like every other ledger write.
- `app/modules/sales/service.py` `get_order_finance_target(..., permissions=...)`: keep the
  `permissions: frozenset[Permission]` parameter **only if** it still has more than one
  caller-distinct value after this change; otherwise collapse it back to the single-grant
  `can_access_branch` check and update its docstring (line ~984 names the cashier — remove
  that sentence either way).
- `app/modules/access/authz.py` `can_access_branch_any`: remove it **if** it has no callers
  left after the above (also drop the export in `app/modules/access/api.py`). If a caller
  remains, keep it but rewrite the docstring so it no longer cites the cashier as its reason.
- The order detail's read-only **settlement** block: wherever the backend lists the
  permissions that may read `settlement` on the order (grep `VIEW_FINANCE_REPORTS` in
  `app/modules/sales/`), drop `RECORD_ORDER_PAYMENT` from the set; `manage_finance` and
  `view_finance_reports` remain.

### 1.3 Tests — `backend/tests/test_finance_order_payments_api.py`

- Delete `test_cashier_records_a_payment_but_can_neither_edit_nor_void_it` and
  `test_payment_cap_and_branch_scope_hold_for_the_cashier_too` (they test the grant).
- `test_ledger_names_who_handled_the_money_and_filters_by_them` (line ~719) creates a
  `RECORD_ORDER_PAYMENT` grant for a second actor: re-grant that actor `MANAGE_FINANCE`
  instead — the assertion (two different `recorded_by_name`s, `recorded_by_user_id` filter
  narrows) is about provenance, not the grant, and must keep passing.
- Keep every other test in the file (payable-orders, settlement on income rows, one-query
  resolution). Add nothing new for removal; the existing `manage_finance` create/edit/void
  tests in `test_finance_api.py` already cover the surviving path. Run the whole backend
  suite — `test_access_*` / permission-catalog tests may enumerate `Permission` values.

## 2. Web — remove the grant, keep the counter action

- `src/shared/app/workshopPermissions.ts`: delete `recordOrderPayment` and its comment.
- `src/shared/app/workshopUi.ts` `PERMISSION_CODES`: drop `'record_order_payment'`.
- `src/shared/stores/workshop.ts` `permissionCatalog`: drop `'record_order_payment'` and
  its comment (this is what the owner's Ruxsatlar panel iterates).
- `src/shared/i18n/locales/{uz,ru}/workshopAdmin.json` → `permission.record_order_payment`:
  delete in **both** locales (`pnpm i18n:check` must stay green).
- `src/shared/views/WorkshopOrderDetailView.vue`:
  - `canViewSettlement` (≈ line 141–143): `[p.manageFinance, p.viewFinanceReports]`.
  - `canRecordPayment` (≈ line 150): `permissions.canAnyOnBranch([p.manageFinance], …)` —
    or the single-permission helper if one exists. The **To'lov qabul qilish** dialog, the
    balance prefill, the server cap, several-payments-per-order — all unchanged.
  - Rewrite the nearby comment that explains the cashier; the reason the action lives here
    is still true (the counter is one person; sending them to Moliya to search the order
    they have open is four steps) — say that, without the grant.
- Grep `src/` for any remaining `record_order_payment` / `recordOrderPayment`; zero hits.

## 3. Web — the *jami* line counts recorded money only

`periodTotalTiyin` in `WorkshopFinanceExpensesView.vue` (≈ line 157) sums every loaded row.
With the status filter at its default (`recorded`) that is right; with **Hammasi** selected
it adds voided rows into a money figure, which is wrong — a voided row is not money.

- Sum only rows whose `status === 'recorded'`. The count in the same line stays the number
  of rows shown (a user who asked for "all" sees 14 rows, total of the 11 recorded).
- When the filter is `voided`, the total is therefore 0 — acceptable and truthful; do not
  special-case it.
- Unit test: `src/shared/app/__tests__/financeLedger.spec.ts` (or the nearest existing
  spec for this view's helpers) — if `periodTotalTiyin` is inline in the view, extract a
  pure `ledgerRecordedTotalTiyin(rows)` into `src/shared/app/financeLedger.ts` and test
  it there: mixed recorded/voided rows → recorded sum; empty → 0.

## 4. Docs (docs-management skill)

- `docs/ref/features/access-management.md`:
  - Permission catalog: delete the `record_order_payment` row.
  - "What each permission unlocks in the sidebar": delete its row.
  - Anywhere else the grant is named (grep) — remove; do not leave a tombstone sentence.
  - `manage_finance` row: its text already says it records income incl. order payments;
    add the half-sentence that it also carries the **To'lov qabul qilish** action on an
    order page it can open (i.e. when the holder also has `view_orders`/`manage_orders`).
- `docs/ref/features/finance.md`:
  - Replace the "Who may record a payment" subsection with two or three sentences: every
    ledger write is `manage_finance`'s; the counter's entry point is the **To'lov qabul
    qilish** action on the order page (link `orders.md` → *The money seam*), prefilled and
    capped by the balance; the cashier role is `manage_finance`, deliberately — the shop is
    small, the person at the till is the person who keeps the books, and the audit trail
    (who recorded, who edited, who voided, with reasons) is the control. One line on the
    end-of-day read: date filter + *Kim yozgan* + the *jami* line, rows beneath as detail.
  - UX → Income & expenses: the paragraph on the *kiritilgan · xodim* line and the *Kim
    yozgan* filter stays. Add one sentence that the `FilterStatus` line under the filters
    states the period's **recorded** total for the active filters (voided rows are listed
    when asked for but never summed).
  - `updated:` front-matter → 2026-08-22.
- `docs/ref/features/orders.md` → *The money seam*: drop `record_order_payment` from both
  sentences (settlement readers; the action's grant). Keep the rationale sentence "whoever
  books a payment must not be able to erase it"? **No** — that was the grant's rationale and
  the owner has reversed it; replace with: editing and voiding happen in the finance module
  with a reason and an audit trail.
- Run the docs-management skill's link/orphan checks as it prescribes.

## 5. Verification

- Gates: `backend/` full chain; `web/` full chain; `e2e/` `pnpm typecheck`.
- Runtime (verify skill, docker stack, `bash deploy/seed-demo.sh` if the stack is empty):
  1. Ruxsatlar panel of a workshop user no longer offers the grant.
  2. A `manage_finance` + `view_orders` user opens an order with a balance → sees the
     settlement and **To'lov qabul qilish**, records a part payment, the settlement re-reads.
  3. The same user on `/workshop/finance/income`, status = Hammasi, with at least one
     voided row in the period → the *jami* figure equals the recorded rows' sum.
  4. `alembic upgrade head` on a DB that holds a `record_order_payment` grant: the grant is
     gone, the user's other grants are intact, the app boots. (Create the grant by SQL
     before upgrading — the API can no longer create it.)

## 6. Out of scope (owner-decided, do not build)

- Any new permission (`record_expense`, `operate_till`, …).
- A stored shift close / till count / difference record.
- A `card` money method or any cash-vs-card split in reports.
- A per-staff end-of-day table or a new Kassa page; the ledger with *Kim yozgan* is the
  report.
