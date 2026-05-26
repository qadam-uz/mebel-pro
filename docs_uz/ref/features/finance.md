---
title: Finance
status: draft
owner: shape
updated: 2026-05-25
order: 55
---

# Finance

Workshop'ning money ledger'i: workshop oladigan **income** (asosan order payment'lar),
u qiladigan **expenses** (jumladan staff salary), va owner'ga workshop foydali yoki yo'qligini
aytadigan **reports**. v1 money'ni *track* qiladi — u hech qachon uni move qilmaydi. Payment
gateway yo'q va **automatic payroll yo'q**: accountant har bir income va expense'ni qo'lda
record qiladi va salary arifmetikasini system bergan production report'lardan foydalanib
o'zi qiladi.

## Problem

Bugun money — bu papkadagi receipt'lar va daftar. Shop oy oxiridagi net'ini soatlab
arifmetikasiz bilmaydi, va "Asror 23 panel kesdi, uning rate'iga ko'paytir" qog'ozda
qilinadi. v1 loop'ni eng kichik mumkin bo'lgan ledger bilan yopadi: income in, expenses
out, accountant pay'ni hisoblashga muhtoj raw production count'lar — va revenue, expenses,
net'ni bog'lab beradigan bitta report. System ataylab salary'larni **compute qilmaydi**;
rate'lar — bu accountant qo'llaydigan inson contract'i.

## Income

Workshop qabul qilgan money. `manage_finance`'li user record qiladi. Har bir income'ning
**type**'i bor; bitta type **`order_payment`** va u settle qiladigan order'ni olib yuradi,
qolganlari (`other`) hech narsa olib yurmaydi.

### Operations (`manage_finance`)

- **Record an income** — `type`; `order_id` (**`order_payment` bo'lsa va faqat shunda
  required**, scope'dagi branch order'i bo'lishi shart); `amount_tiyin` (> 0; client to'liq
  order amount'ni yoki uning bir qismini to'ladi); `method` (`cash` / `bank_transfer` /
  `other` — aniq shu uchtasi; plastic-card yoki terminal payment ("karta") `bank_transfer`
  sifatida record qilinadi, alohida `card` method yo'q); `received_on` (date); optional
  `note` (bank reference / receipt id) va receipt scan. Record qiluvchi user log qilinadi.
  Bitta order uchun bir nechta order payment record qilinishi mumkin (avval advance keyin
  balance); ularning running sum'i **order'ning `total_tiyin`'idan ≤** bo'lishi validate
  qilinadi.
- **Edit an income** — faqat `recorded` paytida; audited.
- **Void an income** — **mandatory reason** bilan `status = voided` (xatoni tuzatish uchun
  ishlatiladi, masalan client "to'ladim, marked emas" deb dispute qiladi). Voided income
  report'larda ko'rinmaydi va order'ning paid total'iga sanalmaydi. Delete yo'q; row
  saqlanadi.

### What the client sees

Order uchun **paid total** — uning `recorded` `order_payment` income'larining yig'indisi va
**balance** — `order.total_tiyin − paid total`. Client app buni faqat order `ready` yoki
`completed` bo'lganda surface qiladi ([`orders.md`](orders.md)); discrepancy out-of-system
hal qilinadi — client workshop'ga qo'ng'iroq qiladi, accountant void / re-record qiladi.

## Expenses

Workshop sarflagan money — rent, utilities, u sotib oladigan consumable'lar, va **staff
salary** (accountant tomonidan quyidagi production report'lardan compute qilinadi, keyin shu
yerda book qilinadi).

### Categories (platform-defined enum)

`rent` · `utilities` · `raw_materials` · `supplies` · `transport` · `equipment` ·
`marketing` · `taxes_and_fees` · `salary` · `other`.

### Operations (`manage_finance`)

- **Record an expense** — `branch_id` (nullable; HQ rent kabi workshop-level cost'ning
  branch'i yo'q), `category`, `amount_tiyin`, `incurred_on`, `description`, optional `vendor`,
  optional receipt scan. Record qiluvchi user log qilinadi.
- **Edit an expense** — faqat `recorded` paytida; audited.
- **Void an expense** — **mandatory reason** bilan `status = voided`. Voided expense'lar
  report'lardan istisno qilinadi. Delete yo'q.

## Worker-production reports

System pay'ni **calculate qilmaydi**. U har bir worker qilgan raw production'ni expose
qiladi, to'g'ridan-to'g'ri order stamp'lardan o'qiladi ([`orders.md`](orders.md) →
*Production stamps*) — accountant contract aytgan rate'ga ko'paytiradi va `salary` expense
book qiladi.

**Period** va **branch(es)** bo'yicha report, workshop user bo'yicha grouped:

| Column | Source |
|---|---|
| Panels cut · cut count | Σ `panels_used_snapshot` / `cut_count_snapshot` over orders where the user is `cutter_user_id` and `cut_completed_at` is in the period |
| Orders banded · metres of banding | count + Σ `edge_length_snapshot` over orders where the user is `edger_user_id` and `edge_completed_at` is in the period |
| Metres of banding broken down | grouped by **edge material** (and rolled up by thickness too, since thickness is a property of the material — read from the material at report time) |

Credit completion stamp bo'yicha sanaladi, shuning uchun order qachon collect qilinganidan
qat'i nazar ish bajarilgan period'ga tushadi. Reverted job ([`orders.md`](orders.md)) o'z
stamp'ini clear qiladi, shuning uchun reverted work ko'rinmaydi. Read-only;
`view_finance_reports` (yoki `manage_finance`).

## Finance reports

Period selection (date range; presets: this month, last month, YTD, custom) va branch
filter (yoki workshop-wide). Read-only.

- **Income** — period'dagi `recorded` income yig'indisi, `order_payment` vs `other` split.
- **Expenses** — period'da category bo'yicha va total, `recorded` expense yig'indisi.
- **Net** — income − expenses.
- **Per-branch breakdown** — yuqoridagi uch satr, per branch.

## UX

Workshop app'da top-level **Finance** nav item (`manage_finance` yoki
`view_finance_reports`'li har kimga ko'rinadi).

- **Dashboard** (`/workshop/finance`, `view_finance_reports` yoki `manage_finance`) — Income ·
  Expenses · Net KPI card'lar + timeseries; branch filter; date-range picker; list'larga
  drill-down.
- **Income** (`/workshop/finance/income`, mutate uchun `manage_finance`; `view_finance_reports`
  read-only) — table: date, type, order # (`order_payment` bo'lganda), method, amount, note,
  status, action menu. Filters: date range, type, method, branch, status, min / max amount.
  **+ Income** → form (type → agar `order_payment` bo'lsa, branch'ga scoped order picker;
  amount; method; date; note; receipt). Row actions: Edit · Void (reason). Delete yo'q.
- **Expenses** (`/workshop/finance/expenses`, xuddi shu permission'lar) — table: date,
  category, branch, vendor, amount, description (first 60 chars), receipt indicator, status,
  action menu. Filters: date range, category, branch, status, min / max amount. **+ Expense** →
  form (category, branch, amount, date, vendor, description, receipt). Row actions: Edit ·
  Void (reason). Delete yo'q.
- **Worker production** (`/workshop/finance/production`, `view_finance_reports` yoki
  `manage_finance`) — period + branch picker; per worker table (panels, cuts, orders banded,
  metres by edge material with a thickness rollup); o'sha worker uchun `category = salary` ga pre-set Expense form ochadigan
  "record salary expense" shortcut (accountant amount'ni to'ldiradi). Empty:
  "No production in this period."

States: dashboard'lar, list'lar va detail'larning hammasida loading / empty / error;
mutating action'lar confirm qiladi; mandatory reason'lar to'ldirilgunicha submit'ni block
qiladi; receipt upload shared file-upload UX'dan foydalanadi. Accessibility: form'lar labelled;
status badge'lar colour'ni text bilan juftlaydi; void danger-styled va o'z effektini nomlaydi.

## Edge cases

- **Client disputes a payment** — accountant noto'g'ri income'ni void qiladi (reason) va
  to'g'risini re-record qiladi; order'ning paid total / balance shunga ko'ra update bo'ladi.
- **Order cancelled after the client paid** — refund entity yo'q; accountant qaytarilgan
  money uchun **expense** record qiladi (category `other` yoki sarflangan material uchun
  `raw_materials`) va, agar mos bo'lsa, income'ni reason bilan void qiladi.
- **A worker did production but the order was later cancelled** — stamp (va shu bilan
  production-report credit) job complete bo'lgan bo'lsa **qoladi**; u faqat job revert
  qilingan bo'lsa yo'qoladi. Accountant uning uchun to'lash kerakmi qaror qiladi.
- **Order payment exceeds the order total** — reject qilinadi; order'ning recorded
  payment'larining running sum'i `total_tiyin`'dan ≤ validate qilinadi.
- **Voiding an income/expense already in a past report** — ruxsat etiladi; report'lar
  period-scoped recomputation'lar, shuning uchun joriy period void'ni aks ettiradi.
- **Workshop currency is and always will be UZS (v1)** — finance raqamlari integer tiyin,
  [`architecture.md`](../../architecture.md) bo'yicha. Frontend faqat display uchun convert
  qiladi.

## Next

- [`orders.md`](orders.md) — income settle qiladigan order va bu report'lar o'qiydigan
  production stamp'lar.
- [`access-management.md`](access-management.md) — `manage_finance` /
  `view_finance_reports` qayerda grant qilinadi.
