---
title: Catalog & inventory
status: draft
owner: shape
updated: 2026-08-22
order: 50
---

# Catalog & inventory

The material catalog, the manufacturers behind it, what each branch carries and prices, the
warehouse, and the suppliers stock comes from. The platform owns the **product** in two
layers: a **decor** is pattern identity (manufacturer, code, name, photo, grain), and a
**decor format** is one concrete product of it (substrate, thickness, sheet size or tape
width, finished faces). A branch owns the **commercial decision** — a branch material is
"we carry this format, at this price, with this threshold", and *is* the material everything
downstream points at. **Stock** is moved in by the warehouseman and **auto-decremented by the order state machine**
as production completes — there is no reservation. The order ↔ stock contract is owned by
[`orders.md`](orders.md) → *The stock seam*; this doc is the warehouse mechanics behind it.

## Manufacturers (platform master list)

Who makes a decor — Kronospan, Egger, Rehau, and so on. A separate platform-scoped
list: a decor's identity includes its manufacturer (Egger H1334 and Kronospan H1334 are
two decors). Curated by platform operators.

**Operations (platform operator):**

- **Create / edit a manufacturer** — `name` (unique, case-insensitive), optional
  `country` and `note`. A rename recomputes the folded search key of every decor it makes.
- **Activate / deactivate** at the platform level. `inactive` is invisible to new
  decor creates and to the branch attach picker; existing decors of an
  inactive manufacturer keep referencing it (history preserved). No delete.
- **List / get** — operators see all; workshop users and clients see only the
  manufacturers attached to the decors they can already see, surfaced as a dropdown
  filter.

Creating a manufacturer is a side-trip from the decor-create form (inline-add), the
same shape as suppliers' inline-add from the arrival form.

## Decors (platform identity catalog)

A **decor** is one *pattern* of one manufacturer: `code`, `name`, photo, `has_grain` — the
word on screen stays «Dekor». It carries **no substrate, no thickness, no size and no price**.
What the pattern physically *is* belongs to its [formats](#decor-formats-platform-owned):
Egger H1145 is one decor sold as an 18 mm LDSP board *and* as a 0.8 × 22 kromka, sharing one
photo and one name. Field-level detail is in
[`catalog.md`](../entities/catalog.md#decor).

**Operations (platform operator):**

- **Create / edit a decor** — five fields and no more: manufacturer, optional `code`,
  required `name`, `has_grain`, optional image. **No substrate field** — that moved to the
  format. Nothing is typed twice: **there is no stored name**, and every display string is
  composed by one server-side formatter and sent as `label`, so the admin table, the workshop
  table, the cutting picker and a printed PDF can never disagree about what a material is
  called.
- **Activate / deactivate** at the platform level. `inactive` is invisible to new branch
  attachments and to clients; existing formats and branch materials keep referencing the
  decor (history preserved). No delete.
- **List / get** — operators see all, with a **branch-usage count** and an **active-format
  count** per decor; workshop users see the active subset through the attach picker; clients
  see only formats their branch carries. The catalog runs to hundreds of rows, so every list
  — the platform table, a branch's own table, and the attach picker — **pages server-side**:
  filtering and search run on the backend and the list grows by a *load-more* control, never a
  whole-table load. Filters are search, substrate, manufacturer and status; on any
  branch-facing surface the substrate filter means **"has at least one active format of this
  substrate"**, since the decor itself no longer has one.

**Two decors are the same when their codes match.** Uniqueness is `(manufacturer, code)`
case-insensitively when there is a code, and `(manufacturer, name)` when there is not: a
maker's decor code identifies the decor, and a code-less decor falls back to its name. Note
what is *no longer* part of identity — **the substrate**, alongside thickness and sheet size.
While the substrate was in the tuple, a pattern sold as both board and tape needed two rows
that shared a name, a photo and nothing else; the demo catalog carried 14 such twin pairs
among 31 rows, and the reshape merged each pair into one decor with two formats. One decor now
covers every product made in that pattern.

A platform-level edit never touches existing orders (snapshots —
[`architecture.md`](../../architecture.md#data-model-invariants)).

### Bilingual search

Uzbek is written in both Cyrillic and Latin, the Latin orthography has three interchangeable
apostrophe shapes (`o'`, `oʻ`, `o‘`), and the same decor is routinely typed `yong'oq`,
`yongoq`, `ёнғоқ` or `yongok`. A plain `ILIKE` over the raw name finds none of those from
each other, and the operator typing the query has no idea which spelling the catalog was
entered in.

So every decor stores a **folded search key** — `name`, `code` and the manufacturer name run
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
The key is recomputed on every decor write and on a manufacturer rename.

Chosen over a Postgres trigram index or a search extension because the corpus is hundreds of
rows per query, the transformation is deterministic, and one pure function is testable without
a database. Revisit if the catalog reaches the tens of thousands, or if ranked
relevance (rather than "matches / doesn't") becomes a requirement.

## Decor formats (platform-owned)

A **decor format** is one concrete product of a decor — the thing a supplier actually sells:
substrate (`ldsp` / `dsp` / `mdf` / `fanera` / `yogoch` / `kromka` / `boshqa`), thickness,
sheet `length × width` **or** tape width, and, for the board substrates, how many faces are
finished. `LDSP · 18 mm · 2800×2070 · 2 tomonlama` is a format; so is
`Kromka · 0.8 mm · 22 mm`. Field-level detail is in
[`catalog.md`](../entities/catalog.md#decor-format).

**Only the platform creates formats**, from the manufacturer's own catalog. A branch picks
from what exists.

**This reverses a decision this document used to state the other way.** The rule was "a branch
owns the format": thickness and sheet size were columns on the branch's own row, a branch
could invent a size inline from the attach sheet, and the argument was that a platform
operator cannot know what a given workshop's supplier sells. The owner has reversed it,
because the thing that argument optimised for — letting each branch describe its own shelf —
is exactly what stopped the platform from having a product list. With per-branch formats, the
same physical sheet is a different row, with a different id, in every workshop that carries
it; nothing can be counted, priced or paired across workshops. Formats are now platform rows
so that **one physical product has one id everywhere**, which is what cross-workshop
analytics, a central price-list import and board↔tape pairing all need as their foundation.
The accepted cost is that a branch needing a size the platform has not entered **waits** for
it. That cost is deliberately made visible rather than hidden: the attach sheet says so on
screen (see [*Attaching a decor*](#attaching-a-decor-to-a-branch)). Revisit if branches start
waiting often — the measure is how many attach sessions end at that note; the first answer
would be a "request a format" action that notifies platform ops, not a return to
branch-created formats.

**Operations (platform operator):**

- **Create a format** on a decor — substrate, thickness, then the pair that substrate implies:
  size for panel-shaped, tape width for `kromka`, plus `finished_sides` (1 or 2) for
  `ldsp` / `dsp` / `mdf`. Sizes are **normalized** so `length ≥ width`: 1830×2750 and
  2750×1830 are one format. A wrong shape for the substrate is refused by name
  (`decor_format_shape_mismatch`), and a duplicate is refused naming the row that already
  exists (`decor_format_exists`).
- **Activate / deactivate** — the *only* mutation. See [*Three levels of off*](#three-levels-of-off).
- **List** a decor's formats — active first, then by substrate, thickness and size.

**There is no edit.** Branch rows, stock, cutting panels and order history all resolve through
a format id, so silently re-dimensioning one would rewrite what those rows mean. A format
entered wrong is **deactivated and re-created correctly**; branches that attached the wrong
one attach the right one.

The create form offers **standard sets per substrate as quick-fill chips**, hard-coded in the
web client — a typing shortcut for the common case, not a platform fact and not a settings
knob:

| Substrate | Qalinlik (mm) | O'lcham / lenta eni (mm) |
|---|---|---|
| `ldsp`, `dsp` | 10 · 16 · 18 · 25 | 2750×1830 · 2800×2070 · 2440×1830 |
| `mdf` | 3 · 8 · 16 · 18 | 2800×2070 · 2440×1220 |
| `fanera` | 4 · 6 · 9 · 12 · 18 | 2440×1220 · 1525×1525 |
| `kromka` | 0.4 · 0.8 · 1 · 2 | lenta eni 19 · 22 · 35 · 42 |
| `yogoch`, `boshqa` | — | — |

`yogoch` and `boshqa` deliberately carry no standard set: there is no common sheet size for
solid timber or for the "everything else" bucket, and inventing one would prefill the form
with formats nobody sells. These chips used to be the *branch's* attach suggestions; they
moved to this form with the formats themselves.

**`dsp` is not `ldsp`.** They stay separate substrates — chipboard without the laminate is a
different product at a different price — and `dsp` now prints its own label, «DSP» / «ДСП»,
instead of borrowing LDSP's. While it borrowed it, the two were indistinguishable on every
screen and every document.

### Three levels of off

Three different `status` columns can retire a material, at three different levels, and they
mean three different things. Written once, here:

| Level | Who | Means | Effect | Untouched |
|---|---|---|---|---|
| decor `inactive` | platform | the pattern left the catalog | no new attach; hidden from clients | branch rows, stock, history |
| **format `inactive`** | platform | **this product is no longer made** | not offered in a new attach; a small **«Ishlab chiqarishdan chiqqan»** hint on the branch's Zaxira row and in the cutting picker | branch rows, stock, price, **selling the remainder**, arrivals — a supplier may still have it on their shelf |
| branch material `inactive` | branch | "we don't offer this" | hidden from clients; not pickable in a new cutting | stock, history |

**A format's deactivation never cascades into branch rows and never hides anything a branch
still has.** The maker stopping production says nothing about the sheets already on the shelf,
which the branch is entitled to sell down to the last one — so client visibility is *not*
gated on format status, only on the decor's and the branch row's. The branch retires its own
row when the shelf is empty; that is level three, and it is the one clients see. The hint is
there so the branch learns *before* it tries to reorder that this product has stopped being
made — arrivals of it are still recordable, because a supplier's own shelf outlives the
production line.

**A branch that needs a format the platform has not entered asks for it.** The attach sheet
carries the note *«Kerakli o'lcham yo'qmi? Platformaga xabar bering — formatlarni platforma
qo'shadi.»* — there is no self-service escape hatch, and inventing one per branch is the thing
this model exists to prevent.

## Branch materials (what a branch carries)

A **branch material** is one platform [format](#decor-formats-platform-owned) carried by one
branch. It holds four facts — that the branch carries it, its price, its low-stock alert
threshold, its branch-level visibility — and **everything downstream points at it**: the stock
item, the cutting panel, the order line. Attaching a format creates the branch's stock item
for it (zero on hand).

**Operations (owner, or `manage_catalog` on the branch):**

- **Attach one or more formats** — the two-step flow below.
- **Edit price or threshold** — never touches existing orders (snapshots).
- **Activate / deactivate** at the branch level. `inactive` is invisible to clients and
  not selectable in a new cutting; stock and history stay. No delete.

**The format is not editable — it is the row's identity.** There is no "change the thickness"
on a branch material; the dimensions are not the branch's to change. Attaching the correct
format and retiring the wrong row is the operation, and it is the honest one: stock, price
history and orders stay attached to the thing they were actually about.

Clients see a format when the decor and the branch material are **both** `active`. Price and
stock are not conditions: an unpriced or out-of-stock row is listed and labelled, never
hidden. The **format's** own status is not a condition either — see
[*Three levels of off*](#three-levels-of-off).

### Attaching a decor to a branch

**Step one picks the decor; step two picks its formats.** The decision "do I stock this decor"
and the decision "in which thicknesses and sizes" are different questions with different
answers, so they are different steps.

- **Step one — decor picker.** The platform-`active` catalog, searched and filtered
  server-side by substrate and manufacturer (substrate here means "has an active format of
  this substrate"). A decor the branch **already carries stays in the list**, labelled with
  how many of its formats the branch carries against how many the platform offers: carrying
  18 mm is no reason to hide the row from someone adding 16 mm.
- **Step two — the decor's active formats**, as checkable rows — `LDSP · 18 mm · 2800×2070 ·
  2 tomonlama`, `Kromka · 0.8 mm · 22 mm` — with a price and a min-stock input per checked
  row. Formats the branch already carries **stay in the list, disabled and labelled**: hiding
  them would leave the operator wondering whether the size exists at all, which is the exact
  question the sheet is there to answer.

**The branch creates nothing here.** There are no thickness/size chips, no "Nostandart ·
faqat sizda" group and no inline **+ qo'shish** — all three are gone with the move of formats
to the platform. A branch that does not find the size it needs sees the note *«Kerakli
o'lcham yo'qmi? Platformaga xabar bering — formatlarni platforma qo'shadi.»* and asks; the
platform enters the format and it appears in step two.

Attaching is **one transaction**. Every format is validated before anything is written, so a
rejection leaves nothing behind; a format whose own status — or its decor's, or its
manufacturer's — went `inactive` between the listing and the save is refused by name
(`decor_format_inactive`), and one a concurrent
attach already registered is **skipped, not rejected** — the picker had shown it as carried,
so a collision is a race, not user error. The response names what it created and what it
skipped.

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
- **`min_stock` defaults to `0`, and `0` means monitoring off.** The column default is `0`,
  the API default is `0`, the attach form prefills `0`, and leaving the input empty saves
  `0` — a row nobody is watching rather than a refused attach. A row at `0` is therefore
  **never low and never counted**: a branch registering its supplier's whole price list (518
  formats in one real case) would otherwise see every zero-balance row wearing the warning
  pill, and a warning that is everywhere is nowhere. A threshold is a deliberate act — the
  operator sets one on the materials they actually watch, from the catalog form or from the
  stock detail. Existing rows are never backfilled.

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

A branch holds one stock item per **branch material** — per format, not per decor, because
16 mm and 18 mm of the same decor are different things on the shelf. A single `on_hand`
balance in the material's stock unit (**sheet count** for panel-shaped substrates, **integer
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
  edge pricing). The invoice and every line commit **together or not at all** — a failure on
  line three leaves no invoice and no stock movement. Each line then moves stock exactly as a
  lone arrival always did: `on_hand += qty`.

  The grouping exists because the accountant negotiates in invoice totals, not in individual
  arrivals: the whole faktura is one payable, one debt entry, one thing to argue about.
  Grouping is what lets the debt fold ([`finance.md`](finance.md) → *Debts*) land on the same
  number the supplier's own paper says.

  **The document-level discount is not captured.** `discount_tiyin` / `surcharge_tiyin` /
  `note` remain as columns — always 0 / null on anything entered now — but no UI writes them
  and the edit operation refuses them, so `total_tiyin` simply equals the line sum. The
  suppliers in scope do not write a discount line on the faktura, and two live inputs plus a
  four-row totals ladder made every operator read arithmetic that never moved. Revisit the
  moment a supplier starts putting a document-level discount on their paper: the columns and
  the fold already carry it, so only the inputs and the ladder come back.
- **Correct an arrival** (same caller) — supplier and invoice date stay editable while the
  invoice is `recorded`, **and so do the lines**.
  Every reader of the header is derived at read time, so a header edit self-corrects the debt
  fold, the payment status and the list with no sync step.

  A line edit is the harder half, because the movements it changes already have later
  movements behind them carrying `balance_after` snapshots taken against the old quantity.
  So the lines are **rewritten wholesale** rather than diffed — the invoice's stock-in rows
  are dropped, the submitted set is inserted (keeping the arrival's original timestamp and
  recorder, so a typo fix does not push the delivery to the top of the ledger), and every
  touched stock item has its whole chain replayed
  ([`inventory.md`](../entities/inventory.md) → *Stock item*). The correction may land a
  balance **negative** — the paper is being fixed to match a world that already happened —
  and fires the same negative-balance notification a `consume` does. Editing an invoice that
  already carries a **recorded payment** is allowed: the payment stands and the outstanding
  re-derives, because blocking here would trap a genuine correction and finance already
  treats supplier overpayment as warn-not-block.
- **Void an arrival** (same caller) — `status = voided` with a **mandatory reason**. The
  invoice writes one reversal movement per line (`stock_in_void`, the negative of the line's
  quantity, no price) and leaves the debt fold, the payable set and the price history at once.
  A reversal **may take the balance negative** — the paper was wrong but the goods either
  never arrived or already left, and refusing it would leave stock permanently too high — and
  when it does, the same negative-balance notification fires as for a `consume`. Blocked while
  a **recorded** expense references the invoice: money and goods reverse in separate, explicit
  steps, so the payment is voided in [`finance.md`](finance.md) first. Nothing is deleted; a
  voided invoice keeps its place in the list with its own badge.

  This replaces the earlier rule that an invoice is never voided or edited and a wrong arrival
  is corrected with an *Adjust*. An Adjust only fixes the **quantity**: the wrong total kept
  feeding the supplier debt forever, the payment pill stayed wrong, and one typo cost two
  manual corrections in two modules. With lines editable, a void is now the narrower tool —
  the document should never have existed at all. Revisit if voids ever become routine rather
  than exceptional: a shop voiding a large share of its arrivals is describing a data-entry
  problem the arrival form should solve instead.
- **List arrivals** (same caller) — the branch's invoices, newest first, filterable by
  supplier, by invoice date range, by free text over the invoice number, and by derived
  payment status. A payment-status filter matches **recorded** invoices only. `note`
  is deliberately not searched: nothing can enter one any more, so matching it would only
  ever hit legacy rows. The supplier left the search box when it gained a dropdown of its
  own — a typed query means one thing, the document number.
- **Last price** (same caller) — read-only lookup powering each arrival line's prefill:
  the most recent priced stock-in for the material at this branch, preferring the
  selected supplier's most recent when one exists. Derived from the transaction ledger
  at read time; no stored "latest price" column exists. Lines belonging to a **voided**
  invoice are skipped — a voided price was likely the typo that forced the void, and it must
  not become the next suggestion. The same exclusion applies to **Ombor qiymati**.
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
banded length + the branch's per-side glue-and-trim overhang) is decremented in **integer
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
home counts them on its *Kam qolgan material* card, which calls out how many of them are
**negative** rather than merely low. It raises no notification — the alert fired on every
movement past the threshold and read as noise rather than news, so the workshop asked for it
gone (QAD-182).

One predicate serves all three readers: a row is low when `on_hand < 0`, **or** when
`min_stock > 0` and `on_hand ≤ min_stock`. The `on_hand < 0` arm is load-bearing and
independent of the threshold — an unrecorded arrival must stay visible under the filter and
in the card that counts negatives, whether or not anyone set a threshold for that material.

Going **negative** is different: it is a discrete thing that happened, not a level. A `consume`
that drives the balance below zero fires a notification to the branch's `manage_inventory`
grantees and the owner — nobody is blocked, but the books going negative must not be silent.

## UX (workshop app)

The active branch comes from the sidebar's branch picker (shared across the
workshop app) — there is no per-page branch filter, and the table drops the
now-redundant branch column:

- **Material katalogi** (`manage_catalog`) — the branch's own materials, **grouped by
  decor**: one photo + identity line per decor, its o'lchamlar as rows beneath, in the order
  **tur · o'lcham · qoldiq · narx · holat**. The substrate pill leads because one decor group
  routinely holds a kromka and two board o'lchamlar at once, so it is what splits a group
  internally rather than a repeat of its heading. The grouping mirrors how the shelf is
  actually organised — one decor, several thicknesses — and stops the identity columns
  repeating on every row.
  The low-stock threshold is **not a column of its own**: it is the muted second line of
  Qoldiq (`kam qoldiq: 20 m`, or `kam qoldiq: kuzatilmaydi` at `0`), carrying its own name so
  the number never needs a header to be readable, and sitting beside the only figure it is
  ever read against. Without `manage_inventory` there is no stock to show and the threshold —
  a setting the operator still owns — stands alone.
  A row whose price is unset carries a **"Narx yo'q"** warning pill; the row is still there,
  still stockable, and still listed to clients — the pill is the same one they see. The group
  heading repeats the count (`1 ta narxsiz`), because a folded group would otherwise take its
  unpriced rows out of sight on the one screen that can price them.
  A group collapses from its heading — `chevron-down`, rotated while open — and a bar-level
  **Hammasini yig'ish / yoyish** folds them all, which is what makes the decor list itself
  scannable on a branch carrying dozens. The heading sits on the `track` fill rather than
  `sunk`, because `sunk` is the row-hover fill and a hovered o'lcham row was
  indistinguishable from the heading above it.
  Filters: search, substrate, status. **Status defaults to `Faol`** — a deactivated o'lcham is
  hidden from clients, so it is not what the operator opened the page to read — on a
  segmented control, which is also why the default is safe: the `Faol emas` segment is the
  visible way back to a material just switched off. The toggle itself updates the loaded row
  in place rather than refetching, so nothing vanishes under the cursor; the filter reapplies
  on the next load. Because `Faol` is the baseline, "is a filter on?" is measured against the
  defaults — comparing to `Hammasi` would light the result-count line on every load and hide
  the first-run empty state behind a no-results one. The table pages with a *load-more*
  control.
  **+ Material** opens the two-step attach sheet (decor picker → the decor's platform formats,
  with price / threshold per checked row). Row: Edit (modal — price and threshold; the format
  is not editable, and a link leads to the material's full detail page for anyone holding
  `manage_inventory`) · client visibility toggled by a status switch in the row itself. No
  Delete.
- **Settings** (owner only) — the branch's settings in one place. Today it holds **Prices**
  — the cutting rate (`cutting_rate_tiyin`, per panel) and the edge-banding labour rate
  (`edge_banding_rate_tiyin`, per metre, all thicknesses); it's the home future branch
  settings land in. Edits the branch's [Branch pricing](#branch-pricing) row. Save +
  unsaved-changes guard; "not set yet" empty state on a new branch (the rates start unset).
  The raw edge **material** price lives on each `kromka` branch material — not here.
  The edge **glue-and-trim overhang** is a branch setting too, but it sits with the branch's
  other shop-floor millimetres on the branch form ([`workshop.md`](workshop.md)), not with
  the rates.
- **Stock** (`manage_inventory`) — the **warehouse, not the catalog**: by default the table
  lists only materials that have actually moved (at least one stock transaction), because
  attaching a format mints a zero-balance row and a branch that registered 518 formats got a
  tab of 518 zeroes. A «Butun katalog» toggle chip opens it to every attached material.
  **Search and «Kam qolgan materiallar» always query the whole catalog** regardless of the
  chip — the scope exists to cut browse noise, not to hide results, and an operator searching
  for a material is usually about to record its first arrival. A **substrate filter** reads
  one shelf at a time (kromka is a different question from panels), reading each row's
  `decor_format.type`; unlike search it **narrows within the current scope** rather than
  widening it — it is browsing, not a lookup — but it still counts as filtering for the count
  line and the empty state. It offers **one option per substrate**, sent as the plural `types`
  param: the options are now one-to-one with the enum, because `dsp` prints «DSP» and no
  longer shares LDSP's label. (While it did, the filter had to fold the two values into a
  single «LDSP» option — listing them raw printed the same label twice with no way to tell
  them apart.) Rows stay **flat, never grouped by decor**: the tab's spine is state-first
  ordering (negatives on top), a decor group would fight it, and with formats-per-decor near
  one the group headers would make the list longer than the rows they collect. A row whose
  **format** the platform has retired carries a small «Ishlab chiqarishdan chiqqan» hint —
  it stays sellable, stockable and listed
  ([*Three levels of off*](#three-levels-of-off)). Three empty states, because they need
  different advice: no filter match · nothing has moved yet · the branch carries no materials
  at all.

  Table: material (label + image + manufacturer chip), on-hand, min-stock, unit; low-stock
  rows highlighted (chip + colour). A **negative** balance escalates from the low-stock
  warning treatment to danger — its own chip, its own marker line ("kirim yozilmagan"), and
  it sorts to the top of the table, because it is a state that wants an arrival recorded
  rather than a minus sign to scroll past. The **Ombor qiymati** tile counts negative
  balances negatively rather than clamping them away.

  The material's **name links to its own page** — `/workshop/inventory/materials/<branch
  material id>`. A material is opened from a row, a colleague's link or a reload, so it is a
  page and not a dialog; it also carries its own branch, which the server derives from the
  material rather than reading off the topbar (`GET /workshop/inventory/materials/{id}/stock`).

  The page reads: the label, format line and status pill, then four figures — *Qoldiq*
  (danger when negative) · *Kam qoldiq*, editable in place through a pencil control · *Oxirgi narx*
  with its provenance (date · supplier, or "birinchi kirim" when the material was never
  priced) · *Qiymat*, on-hand valued at that last price and shown only when both halves are
  real.

  Beneath them the movement history, **split into the three questions an owner asks in front
  of a shelf** — each has a different context column, and one mixed ledger would make the
  reader do the sorting. They are **tabs**, not stacked sections: three tables under each
  other buried the figures under a scroll. Each tab label carries its **row count**, because
  a tab hides what it is not showing and "where are the write-offs?" must not cost a click to
  answer; the open panel states its **net change** over the window:

  - **Kirimlar** — arrivals, each linked to the faktura it came in on (`K-0019` → the invoice
    page), with supplier, quantity, unit price and resulting balance. A void reversal sits
    here too, marked, because it is the same document's story told backwards.
  - **Tuzatishlar** — corrections, with the actor and the mandatory reason that justifies each.
  - **Chiqimlar** — what production took, each linked to the **order** that took it by its own
    `#26-1-0005` number (a `consume`, or the `restore` of a reverted step).

  A correction booked from the page switches to *Tuzatishlar*, so the row explaining the new
  balance is the one on screen. The window is the last 100 movements and the page **says so**
  when it is full; **Barcha harakatlar** hands off to the Tranzaksiyalar tab filtered to this material, which remains
  the flat audit journal. Page actions **Kirim yozish** (a link to the arrival page, material
  pre-picked) and **Tuzatish** (the correction dialog — one field and a reason, so it stays a
  dialog).

  Editing *Kam qoldiq* here writes the same `branch_material.min_stock` the catalog form
  writes — two doors, one fact, no copy anywhere. The threshold wears **one word on every
  screen** (`Kam qoldiq` as a column or figure, `Kam qoldiq chegarasi` as a form label): it
  used to be *Min* here, *Chegara* in the catalog and *Eng kam qoldiq* on this page's own
  edit control, three names for one number on three screens a click apart. It is gated on
  `manage_inventory` rather than
  `manage_catalog` because the threshold is warehouse policy: the decision "5 emas, 10
  bo'lsin" is made standing in front of the shelf by the person who runs it.

  Both stock operations live **on the material page only**. The Zaxira tab itself carries no
  page-level *Kirim* / *Tuzatish* pair and its rows carry no ⋯ menu: every correction and
  every arrival is about a specific material, so starting anywhere else means being asked
  "which material?" a second time. An operator who arrives with a document rather than a
  shelf in mind starts from **Kirimlar → + Kirim**, which is where a multi-material faktura
  belongs anyway. *Tuzatish* is a signed quantity with a **required leading + or −** — "-2"
  writes off, "+5" adds — live-filtered as typed, plus the mandatory reason; this supersedes
  the earlier direction-toggle design in favour of one explicit signed entry.
- **Kirimlar** (`manage_inventory`) — the branch's arrivals as documents, not as loose rows:
  `K-0007` · supplier · date · N pozitsiya ·
  total · a payment-status pill (*To'langan* / *Qisman* / *To'lanmagan*, with the outstanding
  amount beneath a partial), replaced by a danger **Bekor qilingan** badge on a voided row.
  The toolbar carries the shared date-range picker (opening on **all** — the arrivals list
  is an archive, and a 30-day default would answer "nothing" to most lookups), a supplier
  dropdown, a payment-status filter and a number search; the table pages with a *load-more*
  control. The number is a link to the document's own page, and **+ Kirim** is a link to the
  arrival form — both real links, so middle-click and Cmd-click work.

  A faktura is three pages, not a modal: `/workshop/inventory/invoices/new`, `/:invoice_id`
  and `/:invoice_id/edit`. Entering a whole document is a long typing session, and a form
  that long behind a dialog cannot be linked, reloaded, or left and come back to. Create is
  branch-scoped (the topbar context supplies the branch); the other two are entity-scoped,
  taking the branch from the record so a later context switch cannot retarget the document.

  The **detail page** reads top to bottom as the document does: `K-####` with the payment
  pill, supplier · who recorded it, a danger strip carrying reason · who ·
  when on a voided invoice, the lines (material, quantity, unit price, line total), **Jami**
  as a single line, and the settlement block — paid, outstanding (danger while positive),
  then the linked payments, voided ones struck through and tagged. Branch is not shown: the
  topbar context owns it. Actions: **Xarajat yozish** (the deep link into the finance expense
  modal with the faktura pre-picked, for users who could open the ledger anyway) ·
  **Tahrirlash** · **⋯ → Bekor qilish**. The destructive action sits in the overflow so it
  cannot be hit by a mis-aimed click on its neighbour; a voided invoice offers none of them.
  The void opens a danger confirm naming its effect on stock and requiring a reason before
  the button enables, and lands back on the detail page in its voided state.

  The **arrival form** — the same component for create and edit — is a header (supplier, with
  inline-add on create only; and date) over a line table with
  **+ Material qo'shish**: per-line material combobox, quantity and unit price carrying their
  unit suffixes, a live line total, and a remove control. Each line's price field
  **prefills** with the last price paid — supplier-specific when the picked supplier has
  priced history, otherwise the material's overall latest — with a provenance hint underneath
  (price · date · supplier; *«Birinchi kirim — avvalgi narx yo'q»* when there is none). A
  typed or seeded price is never overwritten by a prefill. The footer carries **Jami** alone:
  with no document-level discount the line sum *is* the total, and a ladder would only
  restate it. Leaving with unsaved edits asks first.

  Actions: **Saqlash** · **Saqlash va xarajat yozish** (create only) · **Bekor**. The second
  save is what makes the invoice→expense link get used — without it staff record the payment
  separately and never attach it; it saves the arrival and opens the expense modal prefilled
  against it ([`finance.md`](finance.md)), and appears only for users who could open the
  finance ledger anyway. A stock row's **Kirim yozish** and the dashboard's negative-balance
  work item both link to the form with `?material=`, so line 1 arrives already picked.
- **Transactions** (`manage_inventory`) — full log: type (`stock_in` / `stock_in_void` /
  `consume` / `restore` / `adjust`, shown as localized labels), signed quantity,
  balance-after, unit price and total (stock-in rows only), order link (for
  consume/restore — the order's own `#26-1-0005` number, which the movement carries), the
  `K-…` faktura link to the document's page (for stock_in and
  stock_in_void), supplier (for stock_in), actor, note, date-time; filtered by the
  shared date-range picker and a **material filter** — one material's stock-in rows
  read as its purchase-price history; read-only. The same read derives **Ombor qiymati** —
  on-hand valued at each material's latest purchase price (tape: mm × per-metre), summed over
  the branches in view. That figure reaches no screen today: Asosiy's KPI row carries four
  cards and this is not one of them.
- **Suppliers** (`manage_inventory`) — simple list (name, phone, note, status);
  add / edit in a modal dialog · block (reversible). Mostly reached inline from the arrival form.
  The list itself is a shared lookup that `manage_finance` may also **read**, because the
  expense form attributes spending to a supplier; creating and editing one stays here.

The **cutting material picker** — the same component in the client and workshop apps — reads
this same catalog, branch-scoped and grouped by decor; it is specified in
[`cutting.md`](cutting.md). Both apps list every format the branch carries, unpriced ones
included and marked; stock is not a filter either, so an out-of-stock or negative-balance
material is still pickable, and a retired format is pickable too, wearing the same
«Ishlab chiqarishdan chiqqan» hint.

States: loading (skeletons); empty (nothing attached yet → "add materials to this
branch"); error (`trace_id`). Accessibility: low-stock and "Narx yo'q" are chip + colour, not
colour alone; modals manage focus; owner-only controls are visibly gated for non-owners.

## Edge cases

- **Platform deactivates a manufacturer** — existing decors keep referencing it
  (history preserved); the manufacturer disappears from the new-decor form; no
  branch can attach a new decor under that manufacturer; stock untouched.
- **Platform deactivates a decor branches carry** — existing formats and branch materials
  keep referencing it (history preserved); hidden from clients; no new branch can attach it;
  stock untouched.
- **Platform deactivates a format branches carry** — nothing is hidden and nothing cascades:
  the branch keeps its row, its stock, its price and its clients, and may sell the remainder
  and even receive more of it. The row and the cutting picker gain the
  «Ishlab chiqarishdan chiqqan» hint, and no branch can attach it any more
  ([*Three levels of off*](#three-levels-of-off)).
- **Branch deactivates a material still platform-active** — hidden from clients at
  that branch; stock/history stay; the decor's other formats and other branches unaffected.
- **Material referenced by old orders, then deactivated** — orders unaffected
  (snapshots).
- **Sheet width entered larger than length** — **normalized, not rejected**: 1830×2750 and
  2750×1830 are the same sheet, so the platform's format is stored one way only. Not
  applicable to `kromka`, which has a tape width and no length.
- **A format the branch already carries is re-selected** — its row renders disabled, and if
  a concurrent attach got there first the server **skips** that format and reports it in the
  response rather than failing the batch.
- **A format the platform entered wrong** — it is **deactivated and re-entered**, never
  edited; branches that attached it attach the corrected one. Nothing downstream is rewritten.
- **Wrong format shape for the substrate** — `kromka` with a sheet size, or a panel-shaped
  substrate with a tape width or without `finished_sides`, is refused on the platform form
  with a named error. The service checks it first for the message; a DB CHECK backs it, which
  became possible only once the substrate moved onto the format row.
- **A branch needs a size the platform has not entered** — it cannot create one. The attach
  sheet says so («Kerakli o'lcham yo'qmi? Platformaga xabar bering») and the branch asks the
  platform, which enters the format for everyone.
- **A format attached with no price** — allowed; the row shows **"Narx yo'q"** everywhere it
  appears, clients included, and can be ordered. The order cannot be **confirmed** until the
  price exists ([`orders.md`](orders.md)).
- **`shop` material short when an operator verifies an order** — a **warning**,
  never a block; the operator prompts the warehouseman ([`orders.md`](orders.md)).
- **Order cancelled mid-production after material was consumed** — stock is **not**
  auto-restored (it was physically cut); the warehouseman records an `adjust`
  write-off if the count needs correcting.
- **Edge-roll remnant too short to band a side** — it can't be joined to the next
  roll (the seam would show), so the master discards it and records an `adjust`
  write-off. Unlike the per-side glue-and-trim overhang ([`orders.md`](orders.md#pricing)),
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
