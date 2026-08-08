---
title: Catalog & inventory
status: draft
owner: shape
updated: 2026-08-08
order: 50
---

# Catalog & inventory

The two-level material catalog, the manufacturers behind it, what each branch carries and
prices, the warehouse, and the suppliers stock comes from. The platform owns **dekorlar** —
identity only: manufacturer, `tur`, code, name, photo, grain. A branch owns the **format**:
its own thicknesses and sheet or tape sizes, its price, its threshold. A branch material —
one dekor in one format at one branch — *is* the material everything downstream points at.
**Stock** is moved in by the warehouseman and **auto-decremented by the order state machine**
as production completes — there is no reservation. The order ↔ stock contract is owned by
[`orders.md`](orders.md) → *The stock seam*; this doc is the warehouse mechanics behind it.

## Manufacturers (platform master list)

Who makes a decor — Kronospan, Egger, Rehau, and so on. A separate platform-scoped
list: a dekor's identity includes its manufacturer (Egger H1334 and Kronospan H1334 are
two dekorlar). Curated by platform operators.

**Operations (platform operator):**

- **Create / edit a manufacturer** — `name` (unique, case-insensitive), optional
  `country` and `note`. A rename recomputes the folded search key of every dekor it makes.
- **Activate / deactivate** at the platform level. `inactive` is invisible to new
  dekor creates and to the branch attach picker; existing dekorlar of an
  inactive manufacturer keep referencing it (history preserved). No delete.
- **List / get** — operators see all; workshop users and clients see only the
  manufacturers attached to the dekorlar they can already see, surfaced as a dropdown
  filter.

Creating a manufacturer is a side-trip from the dekor-create form (inline-add), the
same shape as suppliers' inline-add from the arrival form.

## Dekorlar (platform identity catalog)

A **dekor** is one decor of one manufacturer: `tur`, `kod`, `nomi`, photo, `tolali`. It
carries **no thickness, no size and no price**. Those are branch facts, and a platform
operator cannot know what a given workshop's supplier sells — that is the whole reason the
old single `materials` table was split. `tur` (`ldsp` / `dsp` / `mdf` / `fanera` / `yogoch` /
`kromka` / `boshqa`) is the one axis that replaced the old panel-vs-edge `kind` **and** the
old panel `type`: kromka was never a substrate, only a shape, so the two were never
independent. Field-level detail is in [`catalog.md`](../entities/catalog.md#dekor).

**Operations (platform operator):**

- **Create / edit a dekor** — six fields and no more: manufacturer, `tur`, optional `kod`,
  required `nomi`, `tolali`, optional image. Nothing is typed twice: **there is no stored
  name**, and every display string is composed by one server-side formatter and sent as
  `label`, so the admin table, the workshop table, the cutting picker and a printed PDF can
  never disagree about what a material is called.
- **Activate / deactivate** at the platform level. `inactive` is invisible to new branch
  attachments and to clients; existing branch materials keep referencing the dekor
  (history preserved). No delete.
- **List / get** — operators see all, with a **branch-usage count** per dekor; workshop users
  see the active subset through the attach picker; clients see only formats their branch
  carries. The catalog runs to hundreds of rows, so every list — the platform table, a
  branch's own table, and the attach picker — **pages server-side**: filtering and search run
  on the backend and the list grows by a *load-more* control, never a whole-table load.
  Filters are search, `tur`, manufacturer and status.

**Two dekorlar are the same when their codes match.** Uniqueness is `(manufacturer, tur, kod)`
case-insensitively when there is a code, and `(manufacturer, tur, nomi)` when there is not:
a maker's decor code identifies the decor, and a code-less decor falls back to its name. Note
what is *no longer* part of identity — thickness and sheet size. One dekor now covers every
format of that decor; adding an 18 mm sheet next to a 16 mm one is a branch action, not a new
platform row.

A platform-level edit never touches existing orders (snapshots —
[`architecture.md`](../../architecture.md#data-model-invariants)).

### Bilingual search

Uzbek is written in both Cyrillic and Latin, the Latin orthography has three interchangeable
apostrophe shapes (`o'`, `oʻ`, `o‘`), and the same decor is routinely typed `yong'oq`,
`yongoq`, `ёнғоқ` or `yongok`. A plain `ILIKE` over the raw name finds none of those from
each other, and the operator typing the query has no idea which spelling the catalog was
entered in.

So every dekor stores a **folded search key** — `nomi`, `kod` and the manufacturer name run
through one folding function — and the incoming query is folded the same way. Search is then a
plain `ILIKE` over that key. The fold, in order:

1. casefold;
2. Cyrillic → Latin, longest match first (`ш`→`sh`, `ў`→`o`, `ғ`→`g`, `қ`→`q`, `ъ`/`ь`→ dropped, …);
3. drop every apostrophe shape;
4. drop every remaining non-alphanumeric character;
5. fold the confusable Latin pairs **`q`→`k`** and **`x`→`h`**.

Step 5 runs **after** step 2 on purpose, so Cyrillic `қ` (→ `q` → `k`) and Latin `q` land on
the same letter. The visible consequence: `yong'oq` folds to **`yongok`**, not `yongoq` — the
key is a normalisation, never a readable word, and nothing but the matcher ever sees it. The
query is **tokenised and ANDed**: the key is a concatenation with its separators folded away,
so `egger sonoma` as one blob would never match `sonomah1334egger`; each word is matched on its
own and all must hit.

This is why every catalog **search box over the catalog** posts its query to the server and
shows what comes back verbatim: re-filtering that page by raw text on the client would
silently drop the very rows the fold was built to find. One surface still filters locally —
the cutting editor's edge picker, which loads the branch's whole tape list once and narrows it
in the dialog ([`cutting.md`](cutting.md)); it therefore does **not** get the fold, and a
Cyrillic query there finds nothing. Worth closing when that picker next moves.
The key is recomputed on every dekor write and on a manufacturer rename.

Chosen over a Postgres trigram index or a search extension because the corpus is hundreds of
rows per query, the transformation is deterministic, and one pure function is testable without
a database. Revisit if the catalog reaches the tens of thousands, or if ranked
relevance (rather than "matches / doesn't") becomes a requirement.

## Branch materials (what a branch carries)

A **branch material** is one dekor in one format at one branch — thickness plus sheet
`uzunlik × eni`, or, for kromka, thickness plus tape width. It holds the branch's price, its
low-stock alert threshold and its branch-level visibility, and **everything downstream points
at it**: the stock item, the cutting panel, the order line. Attaching a format creates the
branch's stock item for it (zero on hand).

**Operations (owner, or `manage_catalog` on the branch):**

- **Attach a dekor in one or more formats** — the two-step flow below.
- **Edit price, threshold or format** — never touches existing orders (snapshots).
- **Activate / deactivate** at the branch level. `inactive` is invisible to clients and
  not selectable in a new cutting; stock and history stay. No delete.

Clients see a format when the dekor and the branch material are **both** `active`. Price and
stock are not conditions: an unpriced or out-of-stock row is listed and labelled, never
hidden.

### Attaching a dekor to a branch

**Step one picks the dekor; step two picks its formats.** The old flow multi-selected
platform rows and then priced them, because a platform row *was* a format. It cannot work
that way now: the decision "do I stock this decor" and the decision "in which thicknesses and
sizes" are different questions with different answers.

- **Step one — dekor picker.** The platform-`active` catalog, searched and filtered
  server-side by `tur` and manufacturer. A dekor the branch **already carries stays in the
  list**, labelled with how many of its formats the branch carries: carrying 18 mm is no
  reason to hide the row from someone adding 16 mm.
- **Step two — formats.** Thickness on one axis, size (or tape width) on the other, both
  multi-select; the cross product becomes the rows to create, and combinations the branch
  already carries render disabled. Sizes are normalized so `uzunlik ≥ eni`, so 1830×2750 and
  2750×1830 are one format.

The chips offered are **standard sets per `tur`, hard-coded in the web client** — suggestions
covering the common case, not a platform fact and not a settings knob:

| `tur` | Qalinlik (mm) | O'lcham / lenta eni (mm) |
|---|---|---|
| `ldsp`, `dsp` | 10 · 16 · 18 · 25 | 2750×1830 · 2800×2070 · 2440×1830 |
| `mdf` | 3 · 8 · 16 · 18 | 2800×2070 · 2440×1220 |
| `fanera` | 4 · 6 · 9 · 12 · 18 | 2440×1220 · 1525×1525 |
| `kromka` | 0.4 · 0.8 · 1 · 2 | lenta eni 19 · 22 · 35 · 42 |
| `yogoch`, `boshqa` | — | — |

`yogoch` and `boshqa` deliberately carry no standard set: there is no common sheet size for
solid timber or for the "everything else" bucket, and inventing one would prefill the table
with formats nobody stocks.

Beneath the standard chips sits a visually separated **"Nostandart · faqat sizda"** group:
the thicknesses and sizes *this branch already uses* for this dekor that aren't in the
standard set, derived from its own rows. Plus an inline **+ qo'shish** for a size or thickness
that appears nowhere yet. **Nothing is submitted for approval** — a custom format is simply
this branch's row, which is what "the branch owns the format" means. The group is rendered
apart rather than merged so a branch can tell at a glance which of its formats are its own
peculiarity.

Attaching is **one transaction**. Every format is validated before anything is written, so a
rejection leaves nothing behind; a format a concurrent attach already registered is **skipped,
not rejected** — the picker had shown it as carried, so a collision is a race, not user error.
The response names what it created and what it skipped.

### Price and threshold are optional

Two earlier rules are **deliberately reversed here**, both for the same reason: a branch
registers its format list first — often the whole supplier price list in one sitting — and
learns the numbers afterwards.

- **Price is no longer required on attach.** The old rule was "step two cannot be skipped:
  nothing attaches without a real price." It blocked the common case, so the operator either
  invented a price or didn't register the material at all — and an invented price is worse
  than a missing one, because it can be sold at. `price_tiyin` now defaults to `0`, `0` means
  **unpriced** (never free), and the gap is made visible instead of prevented: an unpriced row
  carries a **"Narx yo'q"** warning pill wherever it appears.
- **Unpriced rows are listed to clients, not hidden.** They were excluded from every
  client-facing listing, on the reasoning that a client should never pick something the branch
  cannot quote. In practice a branch prices a handful of the formats it registers: one branch
  carrying 518 formats offered clients two, the owner saw a full catalog, and neither screen
  explained the difference. Clients now browse the whole shelf with the gap labelled, and the
  money is guarded one step later — confirming an order that sells an unpriced material is
  refused until staff price it ([`orders.md`](orders.md)). Revisit if clients start ordering
  unpriced materials often enough that the pricing step becomes the bottleneck.
- **`min_stock` defaults to `0`.** The column default is `0`, the API default is `0`, and
  leaving the input empty saves `0` — a row with no monitoring rather than a refused attach.
  The attach form still **prefills** 5 for a sheet and 50 m for a tape, editable per row,
  because a threshold of `0` alerts only once the material is gone; the prefill is a UI
  suggestion, not a rule the API enforces. Existing rows are never backfilled — rewriting
  thresholds on live materials would fire a notification wave.

## Branch pricing

One pricing row per branch, created with the branch. Order pricing reads it at creation
and snapshots the values onto the order; later changes don't reach existing orders.

- `cutting_rate_tiyin` — the labour rate charged per cut panel (no per-cut model in v1;
  the only model is per panel).
- `edge_banding_rate_tiyin` — the labour rate per metre of tape applied. One rate,
  thickness-independent in v1.
- Edge **material** cost is separate — it's the per-metre `price_tiyin` of each `kromka`
  [branch material](#branch-materials-what-a-branch-carries) (raw material). Order
  total = material + labour, summed per metre per `shop` side.

**Owner only** (not delegable in v1). A part using a tape the branch doesn't
carry makes order pricing fail (`branch_does_not_carry_edge`) — the owner attaches that
tape format to the branch.

## Suppliers

Who the workshop buys material from. Lightweight and **created on demand**: when
recording an arrival the warehouseman picks an existing supplier or adds one inline
(name, optional phone / note). Workshop-scoped, never deleted (deactivated if unused).
Supplier ≠ manufacturer: the supplier is the workshop's buying counterparty, the
manufacturer is who made the material — a supplier can carry many manufacturers' tape,
and vice versa.

No purchase-order flow in v1 — the *money* for a purchase is a separate
[`finance.md`](finance.md) expense the accountant records. The supplier is also a **debt
counterparty**: its invoices and the payments made against them fold into a derived balance on
the Qarzdorlik page ([`finance.md`](finance.md) → *Debts*).

## Inventory

A branch holds one stock item per **branch material** — per format, not per dekor, because
16 mm and 18 mm of the same decor are different things on the shelf. A single `on_hand`
balance in the material's stock unit (**sheet count** for panel-shaped turlar, **integer
millimetres** for `kromka`; UI displays tape stock as metres) and a `min_stock` threshold in
the same unit. **No `reserved`, no `available`, no reservation** — the order never holds
stock; it only decrements it.

**Operations:**

- **Record an arrival** (owner, or `manage_inventory` on the branch) — one **supplier
  invoice** ([`inventory.md`](../entities/inventory.md#supplier-invoice)) with a line per
  material. The header carries the supplier (existing or added inline), the invoice date
  (today by default, editable), and an auto-assigned `K-…` number; each line carries a
  branch material, a positive quantity in its stock unit, and
  a **required unit purchase price** (integer tiyin, per sheet for panels, per metre for
  tape). The server stores each line's price on its own transaction row and computes the
  authoritative line total (tape: `quantity_mm × unit price // 1000`, mirroring sale-side
  edge pricing); the invoice carries the document-level discount and surcharge. The invoice
  and every line commit **together or not at all** — a failure on line three leaves no invoice
  and no stock movement. Each line then moves stock exactly as a lone arrival always did:
  `on_hand += qty`.

  The grouping exists because the accountant negotiates in invoice totals, not in individual
  arrivals: a supplier's discount lives on the document as a whole, and a per-material row can
  never carry it. Grouping is what lets the debt fold ([`finance.md`](finance.md) → *Debts*)
  land on the same number the supplier's own paper says. Invoices are never voided or edited
  after creation — a wrong arrival is corrected with an *Adjust*, like any other stock mistake.
- **List arrivals** (same caller) — the branch's invoices, newest first, filterable by
  supplier, by free text over number / supplier / note, and by derived payment status.
- **Last price** (same caller) — read-only lookup powering each arrival line's prefill:
  the most recent priced stock-in for the material at this branch, preferring the
  selected supplier's most recent when one exists. Derived from the transaction ledger
  at read time; no stored "latest price" column exists.
- **Adjust** (same caller) — signed delta with a **mandatory note**; a *decrease* can't
  take `on_hand` below 0 (a typed stock-out that would go negative is almost certainly a
  typo); an increase is always allowed, including out of a negative balance. The single tool for stock-takes and **waste write-offs** of every kind
  — damage and accidents, a master's production error, an edge-roll remnant too short
  to band, or material a cancelled-mid-production order physically consumed. Waste is
  recorded as a quantity correction, not classified by cause (cause analytics is
  deferred).
- **Consume / restore** (system) — driven entirely by the order state machine.

**The order seam.** Per [`orders.md`](orders.md): `shop` panel items are **consumed**
when the order's **Cutting done** is marked; `shop` edge consumed length (geometric
banded length + the standard per-side trim overhang) is decremented in **integer
millimetres**, per edge material, when **Banding done** is marked. A revert re-increments
exactly what its step decremented. `own`-source panels and `own`-source edge sides never
touch stock.

The seam **never blocks the worker**. The panels are already cut when *Cutting done* is
marked, so the consume records history, not intent — it proceeds even when the balance
goes negative, and even when the material was dropped from the branch catalog after the
order was placed (in which case the branch's stock row is created at zero and the material
stays **out** of the catalog: what is offerable to new clients is a different question from
what physically moved). The worker sees an informational **warning** — *"Omborda qoldiq
yetarli emas"* — and the transition completes. See
[`inventory.md`](../entities/inventory.md) for why negative is the honest state and how it
heals.

**Projected balance & the verify warning.** There is no reservation, so a meaningful
"will we have enough?" needs the demand already in flight. For a material at a branch:

> projected = `on_hand` − Σ (that material's demand from active orders ahead that have
> not yet decremented it)

— panels are still owed by orders in `confirmed`/`cutting`; edge millimetres (per edge
material) by orders in `confirmed`/`cutting`/`edge_banding`. When an operator verifies
an order ([`orders.md`](orders.md)), a `shop` material whose projected balance won't
cover this order raises a **warning** so they can prompt the warehouseman — it
**never blocks** approval (some workshops buy per order).

**Low-stock and negative balances.** Low stock is a **state on the row, not an event**: the
Ombor row marks itself and the «Kam qolgan materiallar» filter collects them, and the Asosiy
dashboard counts them. It raises no notification — the alert fired on every movement past the
threshold and read as noise rather than news, so the workshop asked for it gone (QAD-182).

Going **negative** is different: it is a discrete thing that happened, not a level. A `consume`
that drives the balance below zero fires a notification to the branch's `manage_inventory`
grantees and the owner — nobody is blocked, but the books going negative must not be silent.

## UX (workshop app)

The active branch comes from the topbar context picker (shared across the
workshop app) — there is no per-page branch filter, and the table drops the
now-redundant branch column:

- **Material katalogi** (`manage_catalog`) — the branch's own materials, **grouped by
  dekor**: one photo + identity line per dekor, its formats as indented rows beneath
  (o'lcham×qalinlik, narx, min qoldiq, qoldiq, holat, ⋯ menu). A group collapses. The
  grouping mirrors how the shelf is actually organised — one decor, several thicknesses —
  and stops the identity columns repeating on every row. A row whose price is unset carries
  a **"Narx yo'q"** warning pill; the row is still there, still stockable, and still listed to
  clients — the pill is the same one they see. Filters: search, `tur`, status; the table pages
  with a *load-more* control.
  **+ Material** opens the two-step attach sheet (dekor picker → format chips + price /
  threshold table). Row: Edit (modal) · client visibility toggled by a status switch in the
  row itself. No Delete.
- **Settings** (owner only) — the branch's settings in one place. Today it holds **Prices**
  — the cutting rate (`cutting_rate_tiyin`, per panel) and the edge-banding labour rate
  (`edge_banding_rate_tiyin`, per metre, all thicknesses); it's the home future branch
  settings land in. Edits the branch's [Branch pricing](#branch-pricing) row. Save +
  unsaved-changes guard; "not set yet" empty state on a new branch (the rates start unset).
  The raw edge **material** price lives on each `kromka` branch material — not here;
  the edge **trim overhang** is a fixed system constant ([`orders.md`](orders.md#pricing)),
  not a branch setting.
- **Stock** (`manage_inventory`) — table: material (label + image + manufacturer
  chip), on-hand, min-stock, unit; low-stock rows highlighted (chip + colour), and a
  "low-stock only" toggle chip. A **negative** balance escalates from the low-stock warning
  treatment to danger — its own chip, its own marker line ("kirim yozilmagan"), and it sorts
  to the top of the table, because it is a state that wants an arrival recorded rather than
  a minus sign to scroll past. The **Ombor qiymati** tile counts negative balances
  negatively rather than clamping them away. Two page actions each open a modal: **Kirim** (the arrival
  form, below) and **Adjust** (a signed quantity with a **required leading + or −** — "-2"
  writes off, "+5" adds — live-filtered as typed, plus the mandatory reason; this supersedes
  the earlier direction-toggle design in favour of one explicit signed entry).
- **Kirimlar** (`manage_inventory`) — the branch's arrivals as documents, not as loose rows:
  `K-0007` · supplier · date · N pozitsiya · total · a payment-status pill
  (*To'langan* / *Qisman* / *To'lanmagan*, with the outstanding amount beneath a partial).
  Search and a payment-status filter sit in the toolbar. A row expands to its lines
  (material, quantity, unit price, line total) with the skidka / ustama and the final total
  beneath them.

  The **arrival form** is a header — supplier, date, and the `K-…` badge the number will take
  — over a line table with **+ Material qo'shish**, closing on a totals block:
  *Oraliq jami* → *Chegirma* → *Ustama* → *Jami*. Each line's price field **prefills** with the
  last price paid — supplier-specific when the picked supplier has priced history, otherwise
  the material's overall latest — with a provenance hint underneath (price · date · supplier;
  "birinchi kirim" when no history). A prefill never overwrites a price the user has typed —
  a later supplier change only updates the hint. A live line total renders in the row so the
  warehouseman can check each one against the paper in hand; entry time must not grow.

  Two footer actions: **Saqlash**, and **Saqlash va xarajat yozish**, which saves the arrival
  and opens the expense modal prefilled against it ([`finance.md`](finance.md)). The second
  button is what makes the link get used — without it staff record the payment separately and
  never attach it. It appears only for users who could open the finance ledger anyway.
- **Transactions** (`manage_inventory`) — full log: type (`stock_in` /
  `consume` / `restore` / `adjust`, shown as localized labels), signed quantity,
  balance-after, unit price and total (stock-in rows only), order link (for
  consume/restore), supplier (for stock_in), actor, note, date-time; filtered by the
  shared date-range picker and a **material filter** — one material's stock-in rows
  read as its purchase-price history; read-only. The dashboard shows an
  **Ombor qiymati** tile: on-hand valued at each material's latest purchase price
  (tape: mm × per-metre), derived at read time, summed over the branches in view.
- **Suppliers** (`manage_inventory`) — simple list (name, phone, note, status);
  add / edit in a modal dialog · block (reversible). Mostly reached inline from the arrival form.
  The list itself is a shared lookup that `manage_finance` may also **read**, because the
  expense form attributes spending to a supplier; creating and editing one stays here.

The **cutting material picker** — the same component in the client and workshop apps — reads
this same catalog, branch-scoped and grouped by dekor; it is specified in
[`cutting.md`](cutting.md). Both apps list every format the branch carries, unpriced ones
included and marked; stock is not a filter either, so an out-of-stock or negative-balance
material is still pickable.

States: loading (skeletons); empty (nothing attached yet → "add materials to this
branch"); error (`trace_id`). Accessibility: low-stock and "Narx yo'q" are chip + colour, not
colour alone; modals manage focus; owner-only controls are visibly gated for non-owners.

## Edge cases

- **Platform deactivates a manufacturer** — existing dekorlar keep referencing it
  (history preserved); the manufacturer disappears from the new-dekor form; no
  branch can attach a new dekor under that manufacturer; stock untouched.
- **Platform deactivates a dekor branches carry** — existing branch materials keep
  referencing it (history preserved); hidden from clients; no new branch can attach it;
  stock untouched.
- **Branch deactivates a format still platform-active** — hidden from clients at
  that branch; stock/history stay; the dekor's other formats and other branches unaffected.
- **Material referenced by old orders, then deactivated** — orders unaffected
  (snapshots).
- **Sheet width entered larger than length** — **normalized, not rejected**: 1830×2750 and
  2750×1830 are the same sheet, so the server swaps them and the row's format is stored one
  way only. Not applicable to `kromka`, which has a tape width and no length.
- **A format the branch already carries is re-selected** — the chip renders disabled, and if
  a concurrent attach got there first the server **skips** that format and reports it in the
  response rather than failing the batch.
- **Wrong format shape for the `tur`** — `kromka` with a sheet size, or a panel-shaped dekor
  with a tape width, is rejected with a message naming the material. The rule needs `tur`,
  which lives on `dekorlar`, so it is a service-layer check, not a DB constraint.
- **A dekor attached with no price** — allowed; the row shows **"Narx yo'q"** everywhere it
  appears, clients included, and can be ordered. The order cannot be **confirmed** until the
  price exists ([`orders.md`](orders.md)).
- **`shop` material short when an operator verifies an order** — a **warning**,
  never a block; the operator prompts the warehouseman ([`orders.md`](orders.md)).
- **Order cancelled mid-production after material was consumed** — stock is **not**
  auto-restored (it was physically cut); the warehouseman records an `adjust`
  write-off if the count needs correcting.
- **Edge-roll remnant too short to band a side** — it can't be joined to the next
  roll (the seam would show), so the master discards it and records an `adjust`
  write-off. Unlike the per-side trim overhang ([`orders.md`](orders.md#pricing)),
  which the client pays, a remnant is unattributable to any single order and is
  **absorbed by the workshop** — never billed.
- **Operator reverts a completed job** — the system `restore`s exactly the quantity
  that step consumed; for edges, one restore per edge material the step had
  consumed. This works from a negative balance too — a restore only raises it.
- **Adjust below 0** — rejected. Only the order-driven `consume` may take a balance
  negative; a human typing a stock-out that would is corrected, not recorded.
- **Cutting or banding done with nothing on the shelf** — the transition **succeeds** and
  the balance goes negative by the consumed quantity; the worker gets a warning toast, the
  branch's `manage_inventory` grantees get a notification. Recording the arrival afterwards
  returns the balance to the correct positive number with no manual adjustment.
- **Cutting or banding done for a material removed from the branch catalog** — same: the
  consume is recorded against a stock row created at zero, and the material is **not**
  silently re-added to the branch catalog. Putting it back is a deliberate catalog action.
- **Arrival line for a branch-deactivated material** — allowed (the row still
  exists); it just won't be offered to clients until reactivated.
- **`own`-source order** — no inventory interaction at all; an order with only
  `own` panels and `own` edges skips the seam entirely.
- **Add a supplier inline that already exists by name** — the picker prefers the
  existing one; near-duplicates are a manual cleanup, not enforced in v1.

## Next

- [`orders.md`](orders.md) — the state machine that consumes / restores stock and
  the pricing snapshot rule.
- [`finance.md`](finance.md) — the expense side of buying material from a supplier.
