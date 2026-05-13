# docs/ structure — the authoritative spec

`SKILL.md` summarizes the tree; this file governs. For each folder: what belongs, what doesn't
(and where it goes instead), the naming convention, the depth limit. Then: the served-docs
constraints in full, the full routing map (with templates and the cross-links to make), and the
rules for evolving the tree.

Contents: the tree · conventions everywhere · the served-docs constraints · per-folder spec
(index.md · the canon at the top of docs/ · ref/ and its subfolders · assets/ · misc/) · how
decisions are recorded · the full routing map · evolving the tree.

## The tree

```
README.md                # the ONLY README in the repo, at the root: "what this is + see docs/"
docs/
├── index.md             # Getting Started — vision in a paragraph + a numbered "Read in this order" ladder. The ONLY index.md allowed under docs/.
│
│ # THE CANON — flat at the top of docs/. High-level decisions & specs everyone works from. Lean.
├── scope.md
├── personas.md
├── journeys.md
├── domain-model.md      # ubiquitous language + the high-level entity map; per-entity detail → ref/entities/
├── architecture.md
├── envelope.md
├── nfr.md
├── access.md            # auth / authz / tenancy — the one cross-cutting concern that earns its own canon doc today
├── open-questions.md
│                        #   (decisions + their rationale live inside whichever canon or feature doc owns the area — no separate ADR / decisions/ register)
│                        #   No `spec/` subdirectory; the canon is the flat top-level of docs/.
│
├── ref/                 # everything else that's still documentation — detailed, look-it-up.
│   ├── features/
│   │   └── <domain>.md      # ONE FILE PER COHESIVE DOMAIN — orders.md, cutting.md, catalog-inventory.md, workshop.md, notifications.md, platform.md.
│   │                        #   Each page owns its domain's rules, endpoints, UX, edge cases.
│   │                        #   Trivial CRUDs (worker registry, password change, …) are SECTIONS inside the right home, not solo files.
│   ├── entities/
│   │   └── <context>.md     # ONE FILE PER BOUNDED CONTEXT — sales.md, catalog.md, inventory.md, cutting.md, identity.md, workshop.md, support.md.
│   │                        #   Each page lists its entities with fields/states/invariants. Not one file per entity.
│   ├── api/                 # endpoint reference (build-pipeline output) — when it earns its own corner
│   ├── jobs/                # background jobs / cronjobs — when it earns its own corner
│   ├── runbooks/            # operational procedures — when it earns its own corner
│   └── integrations/        # third-party / external systems — when it earns its own corner
├── assets/              # images & diagrams docs embed — the only place binary files live
└── misc/                # research, PDFs, exports, scratch, temporary — not the documentation
```

Outside `docs/`:

- **`web/DESIGN.md`** — the deterministic design system for the frontend (tokens, primitives,
  composed components, the shell, route maps for the three SPAs, accessibility baseline). Lives
  in the web repo, not under `docs/`. There is no `docs/ref/ux/`.

## Conventions that apply everywhere

- **Filenames:** kebab-case, descriptive, **stable** — `order-flow.md`, not `OrderFlow.md`,
  `ORDER_FLOW.md`, or `orderflow.md`. A filename is part of a URL (see "The served-docs
  constraints"); renaming breaks links. Do it deliberately, and leave a redirect.
- **Depth:** at most two levels under `docs/` (`docs/ref/entities/sales.md` is the floor; with
  one-page-per-context entity pages, you don't need a third level). Deeper means the grouping
  is wrong — flatten or regroup. The canon lives flat at the top of `docs/` (one level).
- **Frontmatter:** every `.md` under `docs/` except `misc/` carries it (schema in
  `references/authoring.md`). Required keys: `title`, `status`, `owner`, `updated`. Optional:
  `order`, `related`.
- **Cross-link minimally.** Each doc ends with a "Next" line (2–4 links) where one helps;
  inline links only at critical points; `related:` frontmatter is optional. When you do link,
  link **by path** — `docs/ref/entities/sales.md` — never "the order doc" or "see above."
- **No `README.md` under `docs/`. No additional `index.md` under `docs/` either.** Only the
  repo root has a `README.md`; only the docs root has an `index.md`. The backend renders the
  section overviews from the tree.
- **No `_template.md` files in `docs/`.** Templates live in this skill's `assets/templates/`;
  copy from there.

## The served-docs constraints

The backend renders `docs/` as a browsable site — markdown → HTML on the fly, behind the app's
auth, with the nav built from the tree + frontmatter. The implications:

- **`docs/index.md` is the home.** The backend picks up `docs/index.md` (or, failing that,
  `docs/README.md` — don't use README) as the page rendered at `/docs`. Keep it short and
  ladder-shaped: a one-paragraph vision, then a numbered list of "read in this order" — canon
  first, features next, entities & open-questions last.
- **A path is a URL.** `docs/ref/features/orders.md` → `/docs/ref/features/orders`;
  `docs/architecture.md` → `/docs/architecture`. Treat a doc's path like a public API:
  stable. If you must rename or move, leave a redirect.
- **`title` is the page heading and the nav label.** Every doc has one. Make it the real title
  of the thing, not the filename echoed back.
- **`order:` sets position within a section.** Optional integer; lower comes first; absent
  means title-ordered. Use it where the reading order matters; skip it where it doesn't. Do not
  encode order in filename prefixes (`01-…`) — that puts the order *in the URL*, so reordering
  breaks links.
- **`status: draft` shows.** The site badges non-`stable` docs; mislabelling a half-written doc
  `stable` is not OK.
- **Images:** in `docs/assets/`, referenced by relative path; the backend serves that folder
  static. Organize `assets/` however stays navigable. Nothing binary in the canon or `ref/`.
- **`misc/` isn't rendered.** It's a drawer, not a section. Don't link a doc to a `misc/` file
  as its source of truth.

## Per-folder spec

### `docs/index.md` — the Getting Started landing

- **Belongs:** a one-paragraph vision statement + a numbered "Read in this order" ladder that
  takes a new contributor through the canon, then features, then entities. Complexity rises
  down the list. Optionally: a short "Run it locally" pointer to the repo root README + how the
  docs are served.
- **Doesn't:** the full vision rationale (that's woven into the canon docs), per-feature
  detail, or any reference content. Keep it tight (≤ 80 lines is a good ceiling).
- **The test:** *will a new contributor open this, read it in ~2 minutes, and know exactly
  what to read next?*
- **Naming:** literally `index.md`. The only `index.md` under `docs/`.

### The canon — flat at the top of `docs/`

- **Belongs:** the high-level decisions and specs **everyone works from**, each as a single
  flat file under `docs/`: product framing (`scope`, `personas`, `journeys`), the domain
  model (`domain-model` — the words and the high-level shape), the system view (`architecture`,
  `envelope`, `nfr`), the open-questions register (`open-questions`), and a canon doc for any
  *cross-cutting* concern that genuinely earns one (today: `access.md`). **The decisions and
  their rationale live inside these docs**, woven in where each belongs — there is no separate
  ADR genre and no `decisions/` folder.
- **Doesn't:** per-feature behaviour and UX (→ `ref/features/`); per-entity field lists
  (→ `ref/entities/`); exhaustive technical reference (→ `ref/`); not-really-documentation
  (→ `misc/`). A canon doc *states what must be true — and why it's that way* — and links out
  for detail.
- **The test:** *is this a high-level decision or spec everyone works from?* If no, it's not
  canon. The whole canon should be readable in one sitting; if it isn't, something escaped
  into the wrong layer — find it and pull it down to `ref/`.
- **Shape:** flat files only — `docs/<canon>.md`. There is no `spec/` subdirectory.
- **Naming:** `kebab-case.md`; concern docs are named for the concern (`access.md`), not
  "spec" anything.

### Recording decisions (no ADR register)

There is **no ADR genre and no `decisions/` folder**. A consequential, costly-to-reverse
decision is recorded **inside the doc that owns the area**: `architecture.md` for topology /
stack / data-model calls, `domain-model.md` for the domain shape, `scope.md` for in/
out-of-scope calls, `access.md` (or another canon concern doc) for that concern's calls, or a
`ref/features/<domain>.md` when the decision is bounded to that one feature domain. Woven into
that doc's prose with: the **forces** in play (the operating envelope, the constraints, what's
costly to reverse), the **alternatives** weighed and why they lost, the **consequences**
accepted (what it makes easier, what it costs, what it forecloses), and the concrete **revisit
trigger** (a number, an event, a date — not "periodically"). A doc that states a normative
call also states why it's that call. When the decision is overtaken, fix that doc in place and
bump `updated` — git keeps the history; a served site shouldn't carry a known-wrong call.

### `ref/` — everything else that's still documentation

- **Belongs:** the detailed, look-it-up material, organized into the subfolders below.
- **Doesn't:** the high-level canon (→ flat `docs/<canon>.md`); binaries (→ `assets/`);
  scratch (→ `misc/`); frontend design system (→ `web/DESIGN.md`).
- **Shape:** the named subfolders below; if something genuinely doesn't fit one, that's a
  signal. Avoid loose files directly in `ref/`.

#### `ref/features/`

One working spec **per cohesive feature domain**, not per CRUD. Group related features into a
single page. Each page is the **single home** for its domain — rules, endpoints, UX, edge
cases, all on one page:

- `orders.md` — placement + fulfilment + modification + cancellation/refunds + the warehouse
  contract + the pricing rules + the per-screen UX (not eight files).
- `cutting.md` — rules · algorithm · lifecycle · API · UX, on one page.
- `catalog-inventory.md` — materials + branch pricing + stock + transactions.
- `workshop.md` — provisioning + branch CRUD + workers + workshop users + audit.
- `notifications.md` — the inbox.
- `platform.md` — superadmin (jobs, errors, platform users).

Each page follows the `feature` template: problem · domain rules · user stories · endpoints ·
UX · edge cases. The `build` pipeline decomposes these into work. **Trivial CRUDs** (a list
with create/edit/deactivate behind a permission — worker registry, password reset, etc.) are
**sections inside the right page**, not their own files. Named for the domain — `orders.md`,
`workshop.md`.

The "Out of scope" section that the old template required is **dropped** — out-of-scope for v1
lives in `docs/scope.md`. A feature page doesn't repeat it.

#### `ref/entities/`

The entity catalog — **one page per bounded context**, not one per entity:

- `sales.md` — order, order item, order payment, order status event, order cancellation, order refund.
- `catalog.md` or `workshop.md` — materials, branch pricing, branch, worker (group as fits the
  domain).
- `inventory.md` — stock item, stock transaction.
- `cutting.md` — cutting result, cutting sheet, cutting placement.
- `identity.md` — platform user, workshop user, permission grant, client, session.
- `support.md` — file, notification, action log, status change log.

Each entity gets an H2 (`## <Entity name>`) inside the page, with: what it is · fields (table) ·
states/lifecycle · invariants. Use the `entity` template once per entity *inside* the page.
This is the **single home** for "what is an X"; the canon and `ref/features/` link to the page
(or section), never redefine.

When the set of entities or contexts changes, update `docs/domain-model.md`'s map in the same
edit.

#### Other `ref/` subfolders

- **`ref/api/`** — endpoint reference; **`ref/jobs/`** — background jobs and cronjobs;
  **`ref/runbooks/`** — operational procedures; **`ref/integrations/`** — third-party /
  external systems. Mostly produced by the `build` pipeline against running code; can be long;
  can be generated / derived. Keep each internally structured. Add the subfolder when it earns
  one — don't pre-create empty ones.

### `assets/` — images & diagrams

- **Belongs:** the image, diagram, and exported-figure files that the canon and `ref/` docs
  embed. The backend serves this folder as static files; docs reference assets by relative
  path.
- **Doesn't:** anything not embedded by a doc (→ `misc/`); markdown (→ the canon or `ref/`).
- Organize for navigability — mirroring the using doc's path is one good convention; flat with
  descriptive filenames is fine while the set is small.

### `misc/` — the drawer

- **Belongs:** research notes, PDFs, vendor docs, exports, one-off scripts, screenshots not
  embedded anywhere, temporary working files, the occasional dead doc you want to keep visible
  (stamped "superseded by … / dropped because …" at the top). Things that aren't *the
  documentation* but that you don't want loose in the repo root or lost.
- **Doesn't:** anything the canon or `ref/` should own. If a `misc/` file becomes a source of
  truth, that's a sign it should be distilled into a real doc — do that, then the `misc/`
  original is background material or can go.
- **No rules:** no required frontmatter, no naming convention, not part of the rendered site,
  not audited. It's a drawer.

## The full routing map

| You have… | Path | Template | Inline-link if critical | Notes |
|---|---|---|---|---|
| Product vision + Getting Started ladder | `docs/index.md` | — | links into the canon, ordered | The home page. Keep it short. |
| Scope / non-goals for v1 | `docs/scope.md` | — | none required | The "out" list matters as much as the "in" list. |
| A user role | `docs/personas.md` | — | none required | One file, a section per role. |
| An end-to-end workflow spanning features | `docs/journeys.md` | — | none required | Cross-feature flows only. |
| Ubiquitous-language term / the high-level entity map | `docs/domain-model.md` | — | `ref/entities/<context>.md` per bounded context (in the map only) | Canon — the lean view. Per-entity detail → `ref/entities/`. |
| The architecture overview (topology, stack, cross-cutting concerns) | `docs/architecture.md` | — | `envelope.md`, `web/DESIGN.md` (for the route map / why three SPAs reference) | Canon. Carries the topology / stack / data-model **decisions and their rationale** inline. |
| The operating envelope | `docs/envelope.md` | — | none required | Canon. The system's "not built for" statement. |
| A non-functional requirement | `docs/nfr.md` | — | links *out* to `access.md` / `architecture.md` only where a requirement points at the design that satisfies it | A terse requirements checklist. |
| Auth / authz / tenancy that every feature obeys | `docs/access.md` | `canon.md` (when created from scratch) | the canon doc(s) the rule depends on | The one cross-cutting concern that earns a canon doc today. |
| A *new* system-wide concern that genuinely earns its own canon doc | `docs/<concern>.md` | `canon.md` | sparingly to the entity context page or the feature page | **High bar** — most "concerns" are really feature domains and belong in `ref/features/`. The canon doc carries that concern's **decisions and their rationale** inline. |
| A consequential, costly-to-reverse decision | **the canon or feature doc that owns the area** | (none — no ADR template) | n/a | **No separate ADR / `decisions/` register.** When the decision is overtaken, fix the doc in place and bump `updated`. |
| An open question / revisit trigger | `docs/open-questions.md` | — | none required | Each question gets an owner and a concrete revisit trigger. |
| A cohesive feature domain | `docs/ref/features/<domain>.md` | `feature.md` | the canon doc(s) whose rules this feature relies on (`access.md`, `architecture.md`), and the entity context page | The build pipeline's unit. The **single home** for everything about the domain — rules + UX. |
| A trivial CRUD | a section in the right `docs/ref/features/<domain>.md` | (no separate template — write it inline) | none required | Don't create a solo file for it. |
| Per-feature UX | the **UX** section of `docs/ref/features/<domain>.md` | (part of `feature.md`) | `web/DESIGN.md` (for component specs) | The design system fills it. |
| The frontend design system | **`web/DESIGN.md`** | — | n/a (not under docs/) | Tokens, primitives, composed components, the shell, route maps, accessibility baseline. |
| An entity definition | a section in `docs/ref/entities/<context>.md` | `entity.md` | the other entity sections it relates to | The single home for "what is an X." Update `docs/domain-model.md`'s map when the set changes. |
| API / job / runbook / integration detail | `docs/ref/api/` · `ref/jobs/` · `ref/runbooks/` · `ref/integrations/` | — | links to the feature/concern it implements | Mostly build-pipeline output. |
| An image or diagram | `docs/assets/…` | — | n/a | The only place binary files live. |
| Research notes, scratch, a dead doc to keep visible | `docs/misc/` | — | n/a | Not the documentation. |
| Raw ideation / brainstorm output | distil into the relevant `docs/<canon>.md` or `docs/ref/features/*`; promising-but-not-now → a line in `docs/open-questions.md`; otherwise drop, or park in `misc/` | — | n/a | Raw notes are not a doc. |
| A doc that's now wrong and dead | delete it (git keeps history) — or move to `docs/misc/` with a "superseded by …" banner | — | n/a | Fix any `related:` links and `assets/` references that now dangle. |

If an output fits no row: it's either not doc-worthy (→ `misc/` or nothing), or you've found a
real gap — see below.

## Evolving the tree

Adding a `ref/` subfolder, or a new canon doc, is a deliberate act — same test as any
architecture move: *what concrete present need does this serve, and does it pull its weight?*
If the honest answer is "it felt tidier," don't. When you do change the structure:

- make the **smallest** change that fits — a new file before a new subfolder; a new `ref/`
  subfolder before a new top-level folder under `docs/`;
- a new top-level folder under `docs/` is a *high* bar — `ref/`, `assets/`, `misc/`, plus the
  flat canon files and the single `index.md`, is meant to be the whole list. The flat canon
  layout exists *because* a `spec/` subdirectory wasn't pulling its weight — don't reintroduce
  it;
- a new canon doc (a new file flat at `docs/`) is also a high bar — most things belong in
  `ref/features/`; the canon test is *every contributor has to read this*;
- never fork the structure per-feature or per-team — one tree, one set of conventions;
- if it's a significant reshape, record the decision (with its rationale and revisit trigger)
  in `architecture.md` — or in `domain-model.md` if it's the entity tree — and watch the URLs:
  a reshape that moves files needs redirects;
- update the repo-root `README.md` only if the top-level shape changed; the backend handles the
  rest.

What does **not** need ceremony — the tree working as designed: a new `ref/features/<x>.md`
when a new cohesive domain genuinely emerges, a section added to an existing entity page or
feature page, a decision (with its rationale) recorded inside `architecture.md` / a feature
doc / `scope.md`, an image in `assets/`, an edit to `docs/index.md` when the canon list
changes.
