# prototype-full Product / UX review

Date: 2026-06-02  
Scope: `docs/` canon specs and `web/prototypes/prototype-full` only. `docs_uz/` was not used as source material.

## Method

- Read all canon docs in `docs/` plus all `docs/ref/features/*` and `docs/ref/entities/*`.
- Static-reviewed all `prototype-full` pages, shared shell files, CSS, and seed data.
- Ran the static prototype locally at `http://127.0.0.1:8001/`.
- Browser-checked representative client, workshop, and superadmin pages at desktop `1440x900` and mobile `390x844`.
- Checked prototype seed invariants for material kinds, order states, references, income methods, completed pickup stamps, and production stamps.

## Overall verdict

The three-app split is directionally correct and most core product rules are represented well:

- Client app correctly starts ordering from cutting, keeps pickup-only scope, shows frozen order totals, and gates settlement figures until `ready` / `completed`.
- Workshop app mostly respects grant-based access, branch scoping, the linear order state machine, no payment/delivery status columns, and read-only settlement visibility for finance grants.
- Superadmin app correctly avoids workshop financials and focuses on provisioning, platform health, jobs, errors, users, and platform catalog.

However, the prototype is not yet clean enough as an implementation handoff. The main issues are a missing superadmin Catalog surface, several keyboard/accessibility failures, a workshop order-board logic bug, mobile overflow on important operational pages, and terminology drift around `panel` / `list` and cutting-service pricing.

## Findings

### P1. Superadmin Catalog is missing the Manufacturers surface

Evidence:

- Docs require two Catalog registries: **Manufacturers** and **Materials** in `docs/ref/features/platform.md:20-44`.
- Docs require manufacturer create/edit/deactivate operations and inline-add from material create in `docs/ref/features/catalog-inventory.md:19-38`.
- Prototype sidebar has only `Materiallar` under Catalog in `web/prototypes/prototype-full/assets/admin-shell.js:51-54`.
- `admin/materials.html` has a Manufacturer `<select>` only, with no inline-add action in `web/prototypes/prototype-full/admin/materials.html:60-63` and `:177-180`.

Why it matters:

The platform operator cannot perform the required first step for adding new brands. This will push implementers toward either hardcoded manufacturers or adding them ad hoc inside the material form, both of which conflict with the documented platform catalog model.

Suggested fix:

- Add `admin/manufacturers.html` under the Catalog section.
- Table columns: name, country, materials count, status, action menu.
- Actions: `+ Manufacturer`, Edit, Activate / Deactivate, no Delete.
- Add status and country filters.
- Add an inline `+ Manufacturer` affordance inside `admin/materials.html` that opens the same dialog and preserves the in-progress material form.

### P1. Workshop Orders board silently loses terminal-filter results

Evidence:

- Docs define the workshop board columns as only active workflow states in `docs/ref/features/orders.md:281-290`.
- Prototype also defines only active columns in `web/prototypes/prototype-full/workshop/orders.html:81-84`.
- The filter strip includes `Tugatilgan` / `completed` in `web/prototypes/prototype-full/workshop/orders.html:33-40`.
- Browser check: clicking `Tugatilgan` while in Board mode shows five empty active columns and no empty-state message, while switching to Table mode shows `ORD-2026-000072`.

Why it matters:

The user has selected a valid filter and the app appears to say there are no completed orders. In operations software this is a trust problem, not just a view-mode detail.

Suggested fix:

- When a terminal status filter is selected in Board mode, automatically switch to Table mode, or render a terminal-results lane/list below the board.
- Alternative: hide terminal status chips while Board mode is active and keep them only in Table mode.
- Add an explicit empty state whenever the current board has zero visible cards but the filtered result set is non-empty.

### P1. Clickable cards and rows are not consistently keyboard-operable

Evidence:

- Docs explicitly require keyboard-navigable board/actions and managed focus in `docs/ref/features/orders.md:328-332`.
- Client order cards are clickable `<article>` elements in `web/prototypes/prototype-full/client/orders.html:130-142`.
- Client cutting draft cards use a clickable `<div class="main">` in `web/prototypes/prototype-full/client/cutting-drafts.html:112-124`.
- Workshop order board cards are clickable `<article>` elements in `web/prototypes/prototype-full/workshop/orders.html:215-229`.
- KPI cards and table rows use `onclick` on non-interactive containers across dashboard, inventory, users, and admin pages.

Why it matters:

Keyboard users cannot reliably open primary objects. It also makes focus styling, screen-reader semantics, and nested action menus fragile.

Suggested fix:

- Use real anchors for navigation cards/rows and real buttons for actions.
- For dense rows, prefer a first-cell anchor plus a separate action-menu cell instead of making the whole `<tr>` clickable.
- If a full-card target is kept, add `role`, `tabindex`, Enter/Space handlers, visible focus, and clear nested-menu event guards. The anchor approach is cleaner.

### P1. Modal focus management is incomplete

Evidence:

- Docs require modal focus management in `docs/ref/features/catalog-inventory.md:189-191` and `docs/ref/features/orders.md:328-332`.
- Shared `openModal()` only toggles classes in `web/prototypes/prototype-full/assets/app.js:34-43`.
- `confirmAction()` creates `role="dialog"` but does not focus the dialog, trap Tab, restore focus on close, or consistently wire Escape/close cleanup in `web/prototypes/prototype-full/assets/app.js:125-165`.
- `showSecret()` focuses the close button once, but still lacks a general focus trap / return-focus helper in `web/prototypes/prototype-full/assets/app.js:171-220`.

Why it matters:

The most sensitive flows use modals: destructive confirms, discounts, staff assignment, password resets, one-time secrets, material creation, and workshop provisioning. Losing focus here is a direct UX and accessibility failure.

Suggested fix:

- Create one shared modal helper with: `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, initial focus, Tab trap, Escape close, focus return, and background inert/`aria-hidden`.
- Make `openModal`, `confirmAction`, and `showSecret` use the same helper.
- Add a reason-field validation focus jump when destructive confirms require a reason.

### P1. Mobile overflow leaks to the whole page on operational screens

Evidence from browser sweep at `390x844`:

- `workshop/dashboard.html` scrolls horizontally to `714px`; the sales chart/card header overflows.
- `workshop/finance.html` scrolls horizontally to `714px`; finance tables leak page-wide overflow.
- `admin/dashboard.html` scrolls horizontally to `714px`; the recent-workshops table leaks page-wide overflow.
- CSS table-scroll rule only catches a few direct-child shapes in `web/prototypes/prototype-full/assets/app.css:299-305`.
- Dashboard chart/card pieces are in `web/prototypes/prototype-full/workshop/dashboard.html:183-224`.

Why it matters:

These are repeated daily-use pages. On mobile/tablet, users should scroll table regions intentionally, not get a whole page that pans sideways.

Suggested fix:

- Introduce a shared `.table-wrap` component and wrap every data table with it.
- Remove reliance on brittle `:has()` direct-child selectors for responsive tables.
- Ensure `.page`, `.card`, `.card-b`, `.two-col`, and chart headers have `min-width: 0`.
- For dashboard chart headers, stack the period selector below the title on narrow screens.

### P2. Client Branches page has a flow-start CTA despite being a passive directory

Evidence:

- Docs say Branches is a passive directory and "not the start of the flow; no per-branch CTAs" in `docs/ref/features/orders.md:273-274`.
- Prototype page correctly says it is informational in `web/prototypes/prototype-full/client/branches.html:47-49`.
- The same page still has a primary `Yangi chizma` CTA in the header in `web/prototypes/prototype-full/client/branches.html:42-44`.

Why it matters:

Even though it is not per-branch, the primary button makes this page feel like an alternate order entry point. That weakens the intended mental model: order starts from a cutting result, branch is chosen only at placement.

Suggested fix:

- Remove the page-level `Yangi chizma` CTA from Branches.
- Keep the passive directory copy and search.
- If an affordance is needed, use a low-emphasis text link back to saved cuttings, not a primary action.

### P2. Terminology drift: `list` / `Listlar` and `Chizma xizmati`

Evidence:

- Canon terminology uses `panel` / panels, not legacy list/sheet wording.
- `client/cutting.html` still shows `Listlar` in the algorithm comparison table in `web/prototypes/prototype-full/client/cutting.html:307-311`.
- Edge picker help says `shu listdan` in `web/prototypes/prototype-full/client/cutting.html:1222-1225`.
- `workshop/finance.html` shows production report header `List` and uses `w.sheetsCut` in `web/prototypes/prototype-full/workshop/finance.html:93-99` and `:183-190`.
- Client order creation/detail sometimes labels cutting service as `Chizma xizmati` in `web/prototypes/prototype-full/client/order-new.html:264`, `:399`, and `client/order-detail.html:103-105`, while other places say `Kesish xizmati`.

Why it matters:

Users will infer that `Chizma xizmati` means design/drawing work, not the branch's cutting labour rate. `List` also reintroduces legacy vocabulary the docs intentionally moved away from.

Suggested fix:

- Use `Panel` / `Panellar` everywhere for physical boards.
- Use `Kesish xizmati` for the branch cutting rate everywhere.
- Reserve `Chizma` for the cutting draft/result/PDF artifact.
- Rename seed/display aliases from `sheetsCut` to `panelsCut` or compute a display alias at render time.

### P2. Edge pricing loses the raw-material vs labour split after checkout

Evidence:

- Docs define edge raw material and edge-banding labour as separate price components in `docs/ref/features/catalog-inventory.md:88-95` and `docs/ref/features/orders.md:187-195`.
- Order checkout gives a branch-level breakdown, but detail pages collapse `Krom yopishtirish` into one subtotal in `web/prototypes/prototype-full/client/order-detail.html:103-108`, `:148-160`, and `web/prototypes/prototype-full/workshop/order-detail.html:164-170`.

Why it matters:

If a client or accountant checks why a total differs between branches, the collapsed row hides the distinction between edge tape price and labour rate.

Suggested fix:

- On client and workshop order detail, render `Krom materiali` and `Krom yopishtirish xizmati` as sub-lines under the edge section when applicable.
- Keep the total row collapsed if needed, but expose the two sources in the details panel.

### P2. Docs & API navigation is not explicit enough

Evidence:

- Docs require links out to `/docs`, `/api-docs`, and `/api-redoc` in `docs/ref/features/platform.md:97-107`.
- Prototype has one link to `/docs` labelled `Hujjatlar & API`, with helper text listing the other paths, in `web/prototypes/prototype-full/assets/admin-shell.js:65-68`.

Why it matters:

The text says API references exist, but the user cannot directly open them from the nav. Platform operators will assume the API docs are hidden or broken.

Suggested fix:

- Replace the single link with a small `Docs` menu containing three explicit external links: `Docs`, `API docs`, and `ReDoc`.
- Keep the "separate HTTP-Basic prompt" label on the group.

### P2. Workshop branch picker can expose inactive branches

Evidence:

- Access docs say grants on inactive branches are inert and branch pickers hide inactive entries in `docs/ref/features/access-management.md:178-180`.
- `myBranches()` returns every branch for an owner in `web/prototypes/prototype-full/assets/workshop-shell.js:39-47`.
- Branch picker options filter only by `myBranches()` and then label inactive states in `web/prototypes/prototype-full/assets/workshop-shell.js:242-255`.

Why it matters:

The current seed has `temporarily_closed`, not `inactive`, so this is latent. Once an inactive branch exists, the owner can scope pages to it through the picker even though docs say inactive branches should be hidden/inert.

Suggested fix:

- Filter branch-picker options to active plus `temporarily_closed` if temporary closure visibility is useful.
- Keep inactive branches visible only on branch management/detail surfaces, not global operational scoping.

### P3. Search and filter inputs rely on placeholders instead of labels

Evidence:

- Browser scan found unlabeled visible inputs/selects in client cutting, client orders, client branches, workshop shell search, workshop orders filters, workshop finance filters, workshop inventory filters, admin search, and admin materials search.
- Examples: `client/branches.html:51`, `workshop/orders.html:42-51`, `admin/materials.html:29-40`, and topbar search in `assets/admin-shell.js:91-98` / `assets/workshop-shell.js:289-297`.

Why it matters:

Placeholders disappear once the user types and are not a reliable accessible name. This is easy to fix in implementation and should be handled before building Vue components.

Suggested fix:

- Add visible compact labels where space allows.
- For global topbar search and obvious filter strips, at minimum add `aria-label` and keep the placeholder as an example, not the only name.

### P3. Icon and visual-token consistency needs a cleanup pass

Evidence:

- Shared CSS says structural icons should use the injected inline icon set in `web/prototypes/prototype-full/assets/app.css:81-84`.
- Raw glyphs still appear in controls, e.g. `⬇ Chizmani PDF olish` in `client/order-detail.html:195`, `⬇ Chizma (PDF)` in `workshop/order-detail.html:222`, completed PDF action in `workshop/order-detail.html:324`, and `⏳ Hisoblanmoqda...` in `client/cutting.html:1472`.
- One-off warm/raw colours exist in otherwise cool-token UI, e.g. topbar background `rgba(250, 248, 243, .82)` in `assets/app.css:164-165`, plus local raw green/brown tints in `client/order-new.html:62-63` and `client/branches.html:84`.
- Notification copy varies: workshop dropdown uses `Hammasini o'qildi` in `assets/workshop-shell.js:305-309`, while other screens use longer variants.

Why it matters:

These are polish issues, but this prototype is meant to set the product's design language. Raw glyphs and one-off colours make the future component system harder to normalize.

Suggested fix:

- Replace raw glyphs with `window.icon(...)` / `data-icon` or a shared spinner component.
- Move local colour literals into semantic tokens.
- Standardize notification action copy, e.g. `Hammasini o'qilgan deb belgilash`.
- Keep ellipsis menus as icon buttons with an accessible label, not raw `⋯` text where possible.

## Recommended refactoring sequence

1. Add the missing superadmin Manufacturers surface and inline-add path.
2. Introduce shared implementation primitives before Vue work starts: `Modal`, `MenuButton`, `CardLink`, `TableRowLink`, `TableWrap`, `TopbarSearch`, `FilterSelect`.
3. Fix the workshop Orders board/table mode logic.
4. Normalize pricing and terminology copy across client/workshop/admin.
5. Fix mobile overflow by using `TableWrap` and `min-width: 0` layout constraints.
6. Do a final icon/token/copy pass after the structural issues are fixed.

## Handoff note

The prototype should not be treated as fully canonical yet. The docs remain the source of truth where this report identifies conflicts. The strongest product shape is already visible, but the P1/P2 issues above should be resolved before using `prototype-full` as the implementation blueprint.
