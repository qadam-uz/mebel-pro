---
title: Catalog & inventory
status: draft
owner: shape
updated: 2026-09-08
order: 50
---

# Catalog & inventory

The material catalog, the manufacturers behind it, what each branch carries and prices, the
warehouse, and the suppliers stock comes from. The **product** is described in two layers: a
**decor** is pattern identity (manufacturer, code, name, photo, grain), and a **decor format**
is one concrete product of it (substrate, thickness, sheet size or tape width, finished
faces). Both layers are a **library** — pre-filled by the platform from the manufacturers'
own catalogs, and extended by any workshop that needs a row the library lacks, for itself
only ([*Decor formats*](#decor-formats-the-library-and-the-workshops-own)). A branch owns the
**commercial decision** — a branch material is "we carry this format, at this price", and *is*
the material everything downstream points at. **Stock** is moved in by the warehouseman and
**auto-decremented by the order state machine** as production completes — there is no reservation. The order ↔ stock contract is owned by
[`orders.md`](orders.md) → *The stock seam*; this doc is the warehouse mechanics behind it.

## Manufacturers

Who makes a decor — Kronospan, Egger, Rehau, and so on. A separate list: a decor's identity
includes its manufacturer (Egger H1334 and Kronospan H1334 are two decors). The library is
curated by platform operators; a workshop that buys from a maker the library does not carry
adds it itself, inline from its own decor form, and only that workshop sees it
([*Decor formats*](#decor-formats-the-library-and-the-workshops-own)).

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
same shape as suppliers' inline-add from the arrival form — on the platform form and on the
workshop's own alike.

## Decors (pattern identity)

A **decor** is one *pattern* of one manufacturer: `code`, `name`, photo, `has_grain` — the
word on screen stays «Dekor». It carries **no substrate, no thickness, no size and no price**.
What the pattern physically *is* belongs to its
[formats](#decor-formats-the-library-and-the-workshops-own):
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

A workshop creates its own decors from the same five fields, entered from the attach sheet
rather than the admin app, and edits the ones it owns; the library's rows stay read-only to
it ([*Decor formats*](#decor-formats-the-library-and-the-workshops-own)).

**Two decors are the same when their codes match.** Uniqueness is `(manufacturer, code)`
case-insensitively when there is a code, and `(manufacturer, name)` when there is not: a
maker's decor code identifies the decor, and a code-less decor falls back to its name. It is
checked **per owner** — the library's rows against the library, a workshop's own against its
own — so a workshop entering a decor the platform later adds does not collide with it. Note
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

So every decor stores a **folded search key**, and the incoming query is folded the same way.
The fold, in order:

1. casefold;
2. Cyrillic → Latin, longest match first (`ш`→`sh`, `ў`→`o`, `ғ`→`g`, `қ`→`q`, `ъ`/`ь`→ dropped, …);
3. strip diacritics, so `yonģoq` and `yongoq` are one word;
4. drop every apostrophe shape;
5. drop every remaining non-alphanumeric character;
6. fold the confusable Latin pairs **`q`→`k`** and **`x`→`h`**.

Step 6 runs **after** step 2 on purpose, so Cyrillic `қ` (→ `q` → `k`) and Latin `q` land on
the same letter, and step 3 runs after it too — `ё` decomposes into a letter plus a mark, and
has to have become `yo` before anything strips marks. The visible consequence: `yong'oq` folds
to **`yongok`**, not `yongoq` — the key is a normalisation, never a readable word, and nothing
but the matcher ever sees it.

**The key is spaced words, not one blob.** It is `" " + the folded words + " "` of the decor's
name, code and manufacturer name, plus the **substrate words of its active formats** (`ldsp`,
`kromka`, …) — which is what makes «лдсп» and `ldsp sonoma` queries on a table whose rows
carry no substrate of their own. A part with more than one word also contributes its whole
separator-less fold, so a query `h1145` still finds a code stored `H 1145` or `H-1145`. The
wrapping spaces are load-bearing: a word start is then a plain `LIKE '% son%'`, which is what
makes ranking expressible in SQL at all. Because the substrate words are a fact about the
formats, the key is rebuilt on every decor write, on a manufacturer rename, **and** whenever
one of the decor's formats is created or changes status.

**One matcher, every surface.** The query is split on whitespace, each token folded, and **all
tokens must match** — `egger sonoma` and `sonoma egger` both find the same row, and
`egger kronospan` finds nothing. A token matches when it is a substring of the key **or** when
it is a dimension the row is sold in, matched by *value*: `18` finds the 18 mm rows and never
the 1830 mm ones, `2800x2070` (or `×`, or `*`) finds that sheet size in either orientation.
Where the row is a format — the branch table, the warehouse, both client pickers — the number
is matched on the row; where the row is a decor — the platform list, the attach picker — it
means "has an active format like that".

Results are **ranked**, lowest band first, then by the surface's own order:

| Band | Means |
| --- | --- |
| 0 | the query **is** the code — `h1145` typed at `H-1145` |
| 1 | the code starts with the query — `h11` |
| 2 | every token starts a word in the key — `son` at `Sonoma` |
| 3 | matched somewhere else: mid-word, or only by a dimension |

**Two fallbacks, and they only run when the first found nothing.** A result never says which
tier produced it — a fallback result is simply the result.

1. **Keyboard layout.** A query written entirely in one script is retyped through the other
   keyboard and searched again: «Ыщтщьф» is `Sonoma` with ЙЦУКЕН still active. A mixed-script
   query is someone typing deliberately and is left alone.
2. **Typos.** `pg_trgm` *strict* word similarity per token (≥ 0.3): each token is scored
   against the closest whole word of the key, ordered by similarity, capped at 20 rows — so
   `sanoma` finds Sonoma while `egger kronospan` stays the empty result it honestly is. Whole
   words rather than any extent of the key is what makes that second half true. This is the
   one place the catalog depends on a Postgres extension; where it is absent the tier is
   skipped and the search reports no rows rather than failing. Trigrams need letters to work
   with — a wrong letter in a four-letter word is below any threshold worth setting.

*Why the extension is now accepted.* This document used to rule out trigrams on the grounds
that the corpus is hundreds of rows, the fold is deterministic, and a pure function is
testable without a database — with the explicit revisit trigger *"if ranked relevance rather
than 'matches / doesn't' becomes a requirement"*. It did: an operator typing `son` expects
Sonoma above a decor that merely contains those letters, and a client one letter off expects
the board anyway. Ranking is still pure SQL over the folded key; only the typo tier needs
`pg_trgm`, it runs only on the zero-result path, and it is fenced behind a capability check so
its absence degrades rather than breaks. Revisit if the catalog reaches the tens of thousands
of decors, where the last tier's cap starts hiding real answers.

**Every catalog search box posts its query to the server** and shows what comes back verbatim:
re-filtering that page by raw text in the browser would silently drop the very rows the fold
was built to find. One surface legitimately filters locally — the cutting editor's tape
picker, which loads the branch's whole tape list once and narrows it in the dialog
([`cutting.md`](cutting.md)) — and it now runs a TypeScript port of the same fold, tokens and
ranking, so a Cyrillic query and a typo find there what they find everywhere else.

## Decor formats — the library and the workshop's own

A **decor format** is one concrete product of a decor — the thing a supplier actually sells:
substrate (`ldsp` / `lmdf` / `dsp` / `mdf` / `fanera` / `yogoch` / `kromka` / `boshqa`),
thickness, sheet `length × width` **or** tape width, and, for the laminated boards, how many
faces are finished. `LDSP · 18 mm · 2800×2070 · 2 tomonlama` is a format; so is
`Kromka · 0.8 mm · 22 mm`. Field-level detail is in
[`catalog.md`](../entities/catalog.md#decor-format). Substrates print in one order wherever
they are listed — chips, filters, admin select, format rows: **LDSP · LMDF · DSP · MDF ·
Fanera · Yog'och · Kromka · Boshqa**, the two laminated boards first because they are almost
everything a workshop buys.

**Only LDSP and LMDF carry finished faces.** They are the two laminated boards — chipboard and
MDF with the decor pressed onto them — and one finished face is a different product at a
different price, so the count belongs to the format's identity. Raw DSP, raw MDF, plywood,
timber, tape and the "everything else" bucket have no finished face to count: `finished_sides`
is empty there, and sending it is refused by name (`decor_format_shape_mismatch`). It was
required on `dsp` and `mdf` until 2026-09-08, when `lmdf` was added and the laminate got a
substrate of its own; the migration emptied the field on the DSP and MDF rows that carried it.

**A finished-faces note is printed only when a board is one-sided.** Two finished faces is
what a board is unless someone says otherwise, so printing it costs width on every line to say
nothing and buries the exception it exists to mark; `1 tomonlama` is the note, and two is
silence. The rule holds wherever a format is *displayed* — the composed label, the branch
table, the attach sheet's o'lcham rows — and the two forms that *enter* it are the exception:
the platform's decor-format screen and the workshop's own o'lcham block, where the field is
being typed rather than read.

**The platform maintains a library; a workshop adds what the library lacks.** Platform
operators enter manufacturers, decors and formats from the makers' own catalogs, so that a
workshop does not type Egger's three hundred decors by hand. When the library lacks
something — a manufacturer nobody else buys from, a local decor, a 16 mm of a decor the
library has only in 18 — the workshop enters it itself, from the attach sheet, in the same
session it was attaching materials in
([*Attaching a decor*](#attaching-a-decor-to-a-branch)). Nothing is moderated, nothing waits,
nothing is promoted into the library.

**What a workshop adds is visible to that workshop alone** — its branches, its staff and the
clients pinned to its branches. One rule carries it at all three levels: a manufacturer, a
decor or a format is visible to a workshop when it belongs to the library *or* to that
workshop, and everything else does not exist for it — not listed, not attachable, and not
fetchable by id, which answers "not found" rather than "not yours" so an id cannot confirm
that a row exists somewhere else. A workshop's own format may hang off its own decor or off a
**library** decor, which is the common case: the pattern is in the library, the size the
workshop buys is not.

**A workshop never gets a second copy of a format the library already has.** Asked for a shape
that an active visible format already covers, the server refuses by name and returns that
format's id, and the sheet ticks the existing row instead of creating a twin — silently, since
the operator asked to carry the size, not to own a copy of it
([*Attaching a decor*](#attaching-a-decor-to-a-branch)). They get the material either way, and
the id everything downstream points at stays the library's.
The one case that does create an own row is a **retired** library twin: the platform stopped
listing that product, the workshop still buys it, and its own row is the honest record of
that.

**This settles a rule this document twice stated the other way.** Until 2026-08-22 the branch
owned the format — thickness and size were columns on the branch's own row — and formats were
moved up to the platform so that one physical product would have one id everywhere, the
foundation cross-workshop analytics, a central price-list import and board↔tape pairing were
expected to need. The cost accepted with it was that a branch needing an unlisted size
**waits**, and the revisit trigger was "if branches start waiting often". On 2026-09-07 the
owner reversed it from the other end and dropped the shared-identity goal itself: there is no
marketplace and no cross-workshop analytics on the roadmap, so the wait was being paid for a
benefit nothing was collecting, and it cost the workshop more than the shared identity ever
paid back. Ownership is now a column on the same rows rather than a return to branch-owned
formats — the library keeps its shared ids for every workshop that finds what it needs there,
and the schema keeps the door open at zero cost. Revisit if the product ever does need
cross-workshop identity: the answer then is a merge of own rows into the library, not another
reshape of where formats live.

**Operations (platform operator):**

- **Create a format** on a decor — substrate, thickness, then the pair that substrate implies:
  size for panel-shaped, tape width for `kromka`, plus `finished_sides` (1 or 2) for
  `ldsp` / `lmdf`. Sizes are **normalized** so `length ≥ width`: 1830×2750 and
  2750×1830 are one format. A wrong shape for the substrate is refused by name
  (`decor_format_shape_mismatch`), and a duplicate is refused naming the row that already
  exists (`decor_format_exists`).
- **Activate / deactivate** — the *only* mutation. See [*Three levels of off*](#three-levels-of-off).
- **List** a decor's formats — active first, then by substrate, thickness and size.

**Operations (workshop owner, or `manage_catalog` on the branch):**

- **Create a decor with its formats** — one act, one transaction: the manufacturer (picked
  from what the workshop can see, or named inline and created with it), the decor's five
  identity fields, and **at least one** format. A bad format anywhere in the list leaves no
  decor and no manufacturer behind.
- **Add a format to a decor it can see** — its own or the library's, subject to the twin rule
  above.
- **Edit its own decor** — the same five fields; the library's decors are read-only to it, and
  another workshop's do not exist for it.

Formats are **immutable for everyone**: a workshop can no more re-dimension its own format
than the platform can. **There is no edit.** Branch rows, stock, cutting panels and order
history all resolve through a format id, so silently re-dimensioning one would rewrite what
those rows mean. A format entered wrong is **deactivated and re-created correctly** by the
platform, or — for a workshop's own — left alone while the branch retires its row and attaches
the right one.

Both create forms offer **standard sets per substrate as quick-fill chips**, hard-coded in the
web client — a typing shortcut for the common case, not a platform fact and not a settings
knob:

| Substrate | Qalinlik (mm) | O'lcham / lenta eni (mm) |
|---|---|---|
| `ldsp`, `dsp` | 10 · 16 · 18 · 25 | 2750×1830 · 2800×2070 · 2440×1830 |
| `mdf`, `lmdf` | 3 · 8 · 16 · 18 | 2800×2070 · 2440×1220 |
| `fanera` | 4 · 6 · 9 · 12 · 18 | 2440×1220 · 1525×1525 |
| `kromka` | 0.4 · 0.8 · 1 · 2 | lenta eni 19 · 22 · 35 · 42 |
| `yogoch`, `boshqa` | — | — |

`yogoch` and `boshqa` deliberately carry no standard set: there is no common sheet size for
solid timber or for the "everything else" bucket, and inventing one would prefill the form
with formats nobody sells. The same sets serve the platform's format form and the workshop's
own o'lcham block — one table, so a size means the same thing on both.

**The raw board and the laminated one are never the same substrate.** `dsp` is not `ldsp`, and
`mdf` is not `lmdf`: chipboard and fibreboard without the decor pressed on are different
products at different prices, bought for different parts of the same wardrobe. `dsp` prints
its own label, «DSP» / «ДСП», instead of borrowing LDSP's — while it borrowed it, the two were
indistinguishable on every screen and every document — and `lmdf` («LMDF» / «ЛМДФ») was split
off `mdf` on 2026-09-08 for the same reason, taking the finished-faces field with it.

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

## Branch materials (what a branch carries)

A **branch material** is one [format](#decor-formats-the-library-and-the-workshops-own) — the
library's or the workshop's own — carried by one branch. It holds three facts — that the
branch carries it, its price, its branch-level visibility — and **everything downstream points
at it**: the stock item, the cutting panel, the order line. Attaching a format creates the
branch's stock item for it (zero on hand).

**Operations (owner, or `manage_catalog` on the branch):**

- **Attach one decor's formats** — one or more o'lchamlar of one decor, through the two-step
  flow below.
- **Edit the price** — never touches existing orders (snapshots).
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

**One decor at a time: step one picks it, step two prices its o'lchamlar.** The decision "do I
stock this decor" and the decision "in which thicknesses and sizes" are different questions
with different answers, so they are different steps — and the sheet holds exactly one answer
to the first at a time. It closes on save, and «+ Material» is the way to the next decor.

- **Step one — decor picker.** Every `active` decor the workshop can see — the library plus
  its own — searched and filtered server-side by substrate and manufacturer (substrate here
  means "has an active format of this substrate"). A row of the workshop's own decor carries a
  muted **«Sizniki»** chip after its name. **Search reaches the o'lcham numbers here too**: a
  numeric token means
  "sold in an active format with this thickness or panel dimension", matched by value through
  the decor's formats, so `18` and `sonoma 18` find what a price list names (the platform's own
  decor table is the one list where a bare number matches nothing). **Every row is a door** —
  press it and step two opens on that decor. There is no checkbox and no «Davom etish»: one
  press, one decor, one screen forward. The row's count is plain text — `3 o'lcham` when the
  branch carries none, `2/3 o'lcham bor` while it carries some, `Hammasi bor` when nothing is
  left to add — and a fully carried decor is a door like every other, because "show me what I
  already carry" is a real reason to open one. A decor the branch **already carries stays in
  the list**: carrying 18 mm is no reason to hide the row from someone adding 16 mm. Formats
  are fetched for the decor that was opened, not for the page — a hundred decors' formats is a
  payload nobody reads.
- **Step two — «O'lchamlar va narx».** A header naming the decor (swatch, name, manufacturer,
  «Sizniki» when it is the workshop's own) and a back arrow to the list, which kept its search
  and its place. Under it **one table, o'lcham and narx**: a checkbox per active format —
  `LDSP · 2800×2070×18 mm`, `Kromka · 0.8×22 mm` — and a price input with its unit beside it,
  board substrates first and kromka last. Ticking a row enables its price and the first one
  takes focus; the price may be left empty (see [*Price is optional*](#price-is-optional)).
  Formats the branch already carries **stay in the list, disabled and labelled «Allaqachon
  bor»**: hiding them would leave the operator wondering whether the size exists at all, which
  is the exact question the sheet is there to answer. The footer counts what is ticked —
  «Qo'shish (n)», disabled at nothing — and on success the sheet **closes** with
  «{dekor} · {n} ta o'lcham qo'shildi» while the table behind it reloads.

**This reverses the batch attach of 2026-09-06.** Step one was multi-select — «Filtrdagi
hammasi», an «n ta tanlandi» line, a per-decor disclosure panel — and step two was a
cross-decor price table with quick-pick chips that ticked one o'lcham under every selected
decor at once, all of it built for registering a supplier's price list in one sitting. On
2026-09-08 the owner chose the smaller shape: the batch screen asked the operator to hold two
questions at once, its cheapest mistake was a row that can be deactivated but never deleted,
and the second question — the prices — is the one the sheet actually exists to answer. Revisit
if a workshop registers hundred-format price lists often enough that pressing «+ Material»
again is the bottleneck; the answer then is an import, not a second selection model.

**What the search does not find, the sheet lets the workshop enter — without leaving it.**

- **«+ Yangi dekor»**, in step one, opens a create step between pick and price: the
  manufacturer (existing or named inline), name, optional code, grain, optional photo, and an
  o'lchamlar block where the substrate chips and the standard sets compose one format at a
  time into a list — **at least one**. The button sits quietly in the footer, and the
  **«Dekor topilmadi» empty state carries it as its own primary action** with the footer copy
  hidden while that state shows: one control for one intent, never two on one screen. What was
  typed into the search is what the operator was looking for, so it arrives prefilled as the
  decor's name. Saving lands on step two with the new decor's formats ticked and the price
  fields waiting — the sheet was opened to attach materials, and it still ends by attaching
  them.
- **«+ Boshqa o'lcham»**, under the rows in step two, composes one more format for the decor in
  hand — the library's as readily as the workshop's own — from the same block: substrate,
  thickness, size or tape width, and «1 tomonlama» where the substrate has finished faces to
  count. The new row appears ticked and unpriced.

**A size that already exists is silently that size.** The operator has no way of knowing which
rows the library happens to list, and being told they guessed a duplicate teaches them nothing
they could have acted on. So a composed shape that matches a row already on screen simply ticks
that row and puts the cursor in its price; a shape the server already holds comes back as
`decor_format_exists` naming it, and the sheet ticks that row the same way, appending it to the
list first if the list had not shown it. Nothing is created, nothing is said. The single case
that does speak is a row the branch **already carries** — there is nothing left to add, so a
quiet «Sizda bor» stands beside it for a moment while the composer keeps its values. Until
2026-09-08 every one of these paths announced itself («Bu o'lcham allaqachon bor —
belgilandi»).

**The footer never scrolls away.** All three screens of the sheet are a fixed header, fixed
filters and a fixed footer around **one** scrolling region. It shipped as a single scrolling
column, and with thirty decors in the list the «+ Yangi dekor» and «Bekor» buttons sat below
the fold: the way out of a list that did not have what the operator wanted was the one thing
that list pushed off screen. The frame is the modal contract in
[`web/DESIGN.md`](https://github.com/qadam-uz/mebel-pro/blob/main/web/DESIGN.md), not this
sheet's own trick.

The «Nostandart · faqat sizda» group of the branch-owned era does not come back: what a
workshop enters here is a real decor and a real format, listed and searched beside the
library's, not an annex to a branch row.

Attaching is **one transaction**. Every format is validated before anything is written, so a
rejection leaves nothing behind; a format whose own status — or its decor's, or its
manufacturer's — went `inactive` between the listing and the save is refused by name
(`decor_format_inactive`), and one a concurrent
attach already registered is **skipped, not rejected** — the picker had shown it as carried,
so a collision is a race, not user error. The response names what it created and what it
skipped.

### Price is optional

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
Price is the only number the sheet asks for. A per-format **low-stock threshold** used to sit
beside it — optional, `0` meaning monitoring off — and it was retired on 2026-09-08 (owner:
"kam qoldiq siyosatini olib tashlaymiz … ortiqcha"): a branch registering hundreds of formats
set a threshold on almost none of them, so the column, its input on three forms and its own
«Kam» state earned nothing, while the state that actually needs a person — a **negative**
balance — needs no threshold to be found. The column is dropped, not defaulted away. Revisit
only with a workshop that keeps reorder points per material and misses them; the answer then
is a reorder report, not a number typed into the attach form.

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
millimetres** for `kromka`; UI displays tape stock as metres), and nothing else — no
threshold, **no `reserved`, no `available`, no reservation**: the order never holds stock; it
only decrements it.

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

**The order seam.** Per [`orders.md`](orders.md): `shop` panel items are **consumed** at the
order's **cutting completion**; `shop` edge consumed length (geometric banded length + the
branch's per-side glue-and-trim overhang) is decremented in **integer millimetres**, per
edge material, at its **banding completion**. A revert re-increments exactly what its step
decremented. `own`-source panels and `own`-source edge sides never touch stock.

**When those completions happen is the branch's
[production mode](orders.md#production-mode)**, and it is the only thing the mode changes
here. A `full`-mode branch taps them separately — **Cutting done**, then **Banding done**. A
`simple`-mode branch (the default) taps **Tayyor** once, which runs both completions in one
transaction, so panels and edges decrement together at that moment. Same demands, same
transactions, same restores. The mode exists precisely because this seam hung off per-stage
taps that paper-run shops never made, which quietly froze the warehouse.

The seam **never blocks the worker**. The panels are already cut when the completion is
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
an order ([`orders.md`](orders.md)), a `shop` material this order would take **below zero**
raises a **warning** so they can prompt the warehouseman — it
**never blocks** approval (some workshops buy per order).

**Negative balances.** One predicate, one word, everywhere: a row needs attention when
`on_hand < 0`. The Ombor row marks itself **«Manfiy»**, the «Manfiy» filter chip collects
them, and the Asosiy work list raises the material that went negative with the arrival that
clears it. There is no level between "enough" and "negative": the per-format threshold that
used to define one was retired ([*Price is optional*](#price-is-optional)), and with it the
«Kam» state on every surface.

Going negative is a discrete thing that happened, not a level, so it also **notifies**: a
`consume` or an invoice void that drives the balance below zero raises it with the branch's
`manage_inventory` grantees and the owner — nobody is blocked, but the books going negative
must not be silent. That is the only inventory alert; the threshold alert that fired on every
movement past a number read as noise rather than news and was removed with it (QAD-182).

## UX (workshop app)

The active branch comes from the sidebar's branch picker (shared across the
workshop app) — there is no per-page branch filter, and the table drops the
now-redundant branch column:

- **Material katalogi** (`manage_catalog`) — the branch's own materials, **grouped by
  manufacturer, then by decor**: a section row per manufacturer, one photo + identity line per
  decor under it, its o'lchamlar as rows beneath that, in the order
  **tur · o'lcham · narx · holat**. It shows the one number the branch
  **sets** — the price — and deliberately **not the balance it is judged
  against**: that is Ombor's, and carrying it here made the two screens near-copies of each
  other while leaving the catalog with a column it could not act on (no arrival, no
  correction) and could not even show to half its audience, since reading stock takes
  `manage_inventory` and the catalog takes `manage_catalog`. The row's edit modal links out
  to the material's full page for anyone holding the other grant. The substrate pill leads because one decor group
  routinely holds a kromka and two board o'lchamlar at once, so it is what splits a group
  internally rather than a repeat of its heading. The pill is a **neutral chip with a
  coloured dot**, and the dot marks the substrate *family* — board, MDF, wood, tape, or
  unclassified — not one hue per enum member: the word beside it is the identity, so the dot
  only has to separate the families at a glance. Its colours sit deliberately off the status
  ramp, because a green, amber or red dot would read as a state in a table that carries real
  ones. (It previously wore the app's production-stage colours, two shades of one orange,
  which left six of the seven substrates looking identical.) The grouping mirrors how the shelf is
  actually organised — one maker, a few decors, several thicknesses — and stops the identity
  columns repeating on every row.
  **The manufacturer is a level of the table, not a word on every line.** The server already
  orders rows by manufacturer, decor and thickness, but with no break between makers and the
  maker's name repeated in every decor label the page read as one undifferentiated list. A
  **section row** now opens each manufacturer — its name in display type, a count line
  («{n} dekor · {m} o'lcham»), on the `sunk` fill, sticky under the table head while its rows
  scroll — and the decor headings beneath it drop the repeat, subtitling themselves with their
  o'lcham count alone. A **manufacturer chip row** under the filter bar («Barchasi 7 · Egger 3
  · Kastamonu 2») is the same fact as a filter, one press away. Sections survive *load-more*:
  a section row is emitted when the manufacturer changes between consecutive rows, so a page
  boundary inside one maker does not print its heading twice.
  **Inside a decor, board o'lchamlar come first and kromka last**, then thickness — the tape
  is the accessory to the boards it matches, and reading it between two sheet sizes breaks the
  ladder.
  A decor the workshop entered itself carries the **«Sizniki»** chip on its heading and a ⋯
  menu with one item, **«Dekorni tahrirlash»** — identity is editable, its o'lchamlar are not
  ([*Decor formats*](#decor-formats-the-library-and-the-workshops-own)), so the menu sits on
  the heading and never on a format row. A library decor has neither.
  A row whose price is unset carries a **"Narx yo'q"** warning pill **in the Narx column**,
  where it replaces the figure rather than joining it — an unpriced row used to print
  «0 so'm», a number nobody chose, which is precisely the gap the pill exists to report. The
  row is still there, still stockable, and still listed to clients; the pill is the same one
  they see. The group heading repeats the count (`1 ta narxsiz`), because a folded group
  would otherwise take its unpriced rows out of sight on the one screen that can price them.
  A group collapses from its heading — `chevron-down`, rotated while open. The heading sits
  on the `track` fill rather than `sunk`, because `sunk` is the row-hover fill and a hovered
  o'lcham row was indistinguishable from the heading above it.
  Filters: search, substrate, manufacturer, status. The balance filter belongs to Ombor and
  stays there — the same reasoning that keeps the balance off this table: a filter over a
  number the page does not show is one nobody can verify.
  **Search reaches the o'lcham numbers**:
  a token matches the decor's search key **or** the row's own thickness and panel
  dimensions, by value rather than as a substring — `18` finds the 18 mm rows without
  dragging in the 1830 mm ones, and `sonoma 18` narrows to one decor's 18 mm o'lchamlar.
  The attach sheet's picker has the same arm, one join further out (an active format of the
  decor with that value); only the platform decor list lacks it — `search_key` is a decor
  fact, and that table has no format in reach.
  The **manufacturer** filter — the chip row above — offers what the branch **carries**, not
  what the library holds: the same endpoint serves both through a `scope`, because handing the
  attach sheet's list to this table would name brands that match no row on screen. It is
  hidden until the branch carries a second brand: «Barchasi» plus one manufacturer cannot
  narrow anything.
  **Status defaults to `Faol`** — a deactivated o'lcham is
  hidden from clients, so it is not what the operator opened the page to read — on a
  segmented control, which is also why the default is safe: the `Faol emas` segment is the
  visible way back to a material just switched off. The toggle itself updates the loaded row
  in place rather than refetching, so nothing vanishes under the cursor; the filter reapplies
  on the next load. Because `Faol` is the baseline, "is a filter on?" is measured against the
  defaults — comparing to `Hammasi` would light the result-count line on every load and hide
  the first-run empty state behind a no-results one. The table pages with a *load-more*
  control.
  **+ Material** opens the attach sheet (decor picker → the decor's o'lchamlar, with a price
  per checked row — and «+ Yangi dekor» for what neither the library nor the workshop has
  yet). Row: Edit (modal — the price; the format is not editable, and a link leads to the
  material's full detail page for anyone holding `manage_inventory`) · client visibility
  toggled by a status switch in the row itself. No Delete.
- **Settings** (owner only) — the branch's settings in one place. Today it holds **Prices**
  — the cutting rate (`cutting_rate_tiyin`, per panel) and the edge-banding labour rate
  (`edge_banding_rate_tiyin`, per metre, all thicknesses); it's the home future branch
  settings land in. Edits the branch's [Branch pricing](#branch-pricing) row. Save +
  unsaved-changes guard; "not set yet" empty state on a new branch (the rates start unset).
  The raw edge **material** price lives on each `kromka` branch material — not here.
  The edge **glue-and-trim overhang** is a branch setting too, but it sits with the branch's
  other shop-floor millimetres on the branch form ([`workshop.md`](workshop.md)), not with
  the rates.
- **Stock** (`manage_inventory`) — the **warehouse, not the catalog**. Its columns are
  **tur · dekor · o'lcham · mavjud · yetarlilik**: the identity is three columns rather than
  one composed `LDSP Egger H1137 · Kulrang eman · 2800×2070×18 mm` string, because a shelf is
  read *down* a column («qaysi kromkalar?», «shu dekorning qaysi o'lchamlari bor?») and one
  ragged line forces that reading sideways. The dekor cell draws the decor's **own uploaded
  photo**, with the hashed swatch only as a fallback for a decor nobody ever gave one
  — this row used to draw the swatch unconditionally, so a real image never reached the
  shelf. Zaxira shows what reality holds, the catalog shows what the branch decided.
  The last column is **«Yetarlilik»** (`Yetarli` / `Manfiy`), not «Holat»: the
  catalog's own last column is also a status, and there it means *client visibility*
  (`Faol` / `Faol emas`). One word on two adjacent screens for the health of a balance and
  for whether clients can see the material at all names neither — each column names the
  question it answers instead. By default the table lists only materials that have actually moved (at least one stock transaction), because
  attaching a format mints a zero-balance row and a branch that registered 518 formats got a
  tab of 518 zeroes. A «Butun katalog» toggle chip opens it to every attached material.
  **Search and the «Manfiy» chip always query the whole catalog** regardless of the scope
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

  Table: material (label + image + manufacturer chip), on-hand, unit, yetarlilik. A
  **negative** balance is the one state the column reports, and it reports it in danger — its
  own «Manfiy» chip, its own marker line ("kirim yozilmagan"), and it sorts to the top of the
  table, because it is a state that wants an arrival recorded rather than a minus sign to
  scroll past. The **Ombor qiymati** figure counts negative balances negatively rather than
  clamping them away.

  The material's **name links to its own page** — `/workshop/inventory/materials/<branch
  material id>`. A material is opened from a row, a colleague's link or a reload, so it is a
  page and not a dialog; it also carries its own branch, which the server derives from the
  material rather than reading off the topbar (`GET /workshop/inventory/materials/{id}/stock`).

  The page reads: the label, format line and status pill, then three figures — *Qoldiq*
  (danger when negative) · *Oxirgi narx* with its provenance (date · supplier, or
  "birinchi kirim" when the material was never
  priced) · *Qiymat*, on-hand valued at that last price and shown only when both halves are
  real. The page **edits nothing about the material itself**: the threshold that used to stand
  second of four, editable in place through a pencil, went with the low-stock policy
  ([*Price is optional*](#price-is-optional)), and the price is the catalog's.

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
    `№ 482 917` number (a `consume`, or the `restore` of a reverted step).

  A correction booked from the page switches to *Tuzatishlar*, so the row explaining the new
  balance is the one on screen. The window is the last 100 movements and the page **says so**
  when it is full; **Barcha harakatlar** hands off to the Tranzaksiyalar tab filtered to this material, which remains
  the flat audit journal. Page actions **Kirim yozish** (a link to the arrival page, material
  pre-picked) and **Tuzatish** (the correction dialog — one field and a reason, so it stays a
  dialog).

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
  consume/restore — the order's own `№ 482 917` number, which the movement carries), the
  `K-…` faktura link to the document's page (for stock_in and
  stock_in_void), supplier (for stock_in), actor, note, date-time; filtered by the
  shared date-range picker and a **material filter** — one material's stock-in rows
  read as its purchase-price history; read-only. The same read derives **Ombor qiymati** —
  on-hand valued at each material's latest purchase price (tape: mm × per-metre), summed over
  the branches in view. It is the **fourth card of Asosiy's KPI row**
  ([`workshop.md`](workshop.md)), where it took the seat the retired low-stock count left:
  what the warehouse is worth is a number an owner reads daily, and it was already computed
  and reaching no screen.
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
branch"); error (`trace_id`). Accessibility: «Manfiy» and "Narx yo'q" are chip + colour, not
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
- **A branch needs a size the library has not entered** — it enters it, from the attach sheet:
  «+ Boshqa o'lcham» on a library decor it can see, «+ Yangi dekor» when the pattern is
  missing too. The row belongs to that workshop and no other workshop ever sees it.
- **The size the workshop is about to enter already exists** — the server refuses the twin and
  the sheet ticks the existing row instead, so the workshop carries the library's format
  rather than a private copy of it. An *inactive* library twin does not block: the platform
  stopped listing the product, the workshop still buys it, and its own row records that.
- **A workshop's own decor was entered wrong** — it **edits the decor**: name, code, grain,
  photo and manufacturer are its own to fix, and the branch rows keep pointing at the same
  formats.
- **A workshop's own format was entered wrong** — nothing is edited, exactly as for a library
  format: the branch attaches the right o'lcham and deactivates the row carrying the wrong
  one. The stray format stays visible only to that workshop, which is the whole blast radius.
- **A workshop asks to see or fix another workshop's own row** — there is no such row for it.
  Reads answer "not found" rather than "not yours", so an id cannot be probed for existence,
  and an attach naming a foreign format is refused the same way.
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
