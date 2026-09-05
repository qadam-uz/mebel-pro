# Web — `mebel-pro/web`

The web client: Vue 3.5 + Vite 7 + TypeScript + Pinia + Vue Router + Tailwind v4 + Vitest,
managed with **pnpm** (`packageManager` pinned, `engine-strict`, Node 22+). HTTP goes through
a native-fetch wrapper, not axios. Versions and scripts live in `package.json` — read it
rather than a table here.

Current build state (rationale in [`docs/architecture.md`](../docs/architecture.md)):

- **Static landing** — `web/landing/index.html`, its own Vite entry, served at the apex by
  the Caddy edge; _not_ part of the Vue tree. `web/index.html` is only a meta-refresh
  redirect to `/landing/`.
- **Three role SPAs** — `web/client/index.html`, `web/workshop/index.html`,
  `web/admin/index.html`, each mounting `src/apps/<role>/main.ts` with routes in
  `src/apps/<role>/routes.ts` and its own chrome in `src/apps/<role>/<Role>Shell.vue`.
  `main.ts` hands `mountRoleApp` that shell plus whatever else only this role needs, as
  `RoleAppOptions` — `onBoot` (after Pinia, before the router), `onRevalidate` (after a 403)
  and `onAfterNavigate`; the bootstrap itself branches on no role. **A role shell must not
  import another role's store or components**: the three SPAs share one chunk, so a single
  cross-role import lands that role's code in all three initial loads. Shared code lives
  under `src/shared/` (api client, stores, components, composables, i18n, app helpers) plus
  the views more than one role routes to; a view only one role reaches lives in
  `src/apps/<role>/views/`. File inventories drift — `ls` before trusting a list.

## Commands

```bash
pnpm dev                     # Vite dev server, :5173, /api proxied → :8000
pnpm build                   # vue-tsc --build && vite build  → dist/
pnpm test [src/path]         # Vitest once; single file/dir first while iterating
pnpm i18n:check              # every LITERAL t()/$t() key resolves in the uz catalog (see Copy)
pnpm lint / pnpm format      # autofix variants; *:check variants are the CI/pre-push form
```

The pre-push gate is owned by the root `AGENTS.md` (lint:check → format:check → typecheck →
i18n:check → test → build; `build` re-runs `vue-tsc`). Fix issues rather than disabling
rules; scope any `eslint-disable` to the line, with a reason. Adding deps: `pnpm add [-D] <pkg>`;
a dep with a postinstall build script must be added to `pnpm.onlyBuiltDependencies` in
`package.json` or its script is silently skipped.

The harness browser preview (`.claude/launch.json`) runs its own Vite on **:5199**
(`--strictPort`) so it never collides with the docker `web` container that owns :5173 —
if you screenshot :5173 while both run, you're looking at the docker container's build,
not the preview. Both proxy `/api` to a backend that must be up separately on :8000.

## Conventions

- **SFCs**: `<script setup lang="ts">` + Composition API only. No Options API, no class components.
- **Imports**: use the `@/` alias for anything under `src/` (e.g. `@/shared/stores/orders`). Relative imports only within a feature folder.
- **Routing**: register routes in the owning role file under `src/apps/<role>/routes.ts`.
  A route component one role reaches lives in `src/apps/<role>/views/`; `src/shared/views/`
  is only for screens two or more roles route to (the cutting editor and result, the drafts
  list, the 404) — grep the three `routes.ts` before putting one there. Lazy-load
  (`() => import(...)`) everything except the initial route. Keep the `:pathMatch(.*)*` 404
  route last. **`meta.chromeless: true`** renders a signed-in route with no shell around it —
  no header, and on the client no bottom tab bar (the cutting editor, the result stage, the
  order confirmation; each carries its own back affordance). It is not `layout: 'auth'`, which
  also turns the auth guard off, nor `layout: 'print'`, which is a document rather than a
  screen; shells ask `isChromelessRoute(route.meta)`, never the layout alone. For links inside shared
  views, use `useRolePath()` from `src/shared/app/paths.ts` instead of hard-coded
  role-prefixed URLs; dev mounts apps under `/client`, `/workshop`, and `/admin`, while
  production is host-routed. Inside a role route file, write **absolute production paths**
  (`/workshop/orders/new`) everywhere — `path`, `redirect`, and any target a `beforeEnter`
  guard returns. `normalizeRoleRoutes` strips the dev base off all three, so a raw literal is
  correct in both environments; a `useRolePath()` call there would double the base.
  Because every route is a lazy `import()` of a content-hashed chunk, a tab left open across a
  deploy holds filenames that no longer exist: the import 404s and vue-router aborts the
  navigation **silently**, so the shell looks alive while every link is dead. `router.onError`
  in `createRoleApp.ts` catches that and hard-loads the *target* route once per path per tab
  (`staleChunkRecovery`). Keep it wired when you touch the bootstrap.
- **State**: Pinia setup stores — `defineStore('name', () => { const x = ref(...); ... return { x, ... } })`. One store per domain in `src/shared/stores/`. Component-local state stays in the component; reach for a store only when state is shared across routes/components.
- **Data fetching**: go through `src/shared/api/client.ts` — `api.get/post/put/patch/del/blob`,
  plus `ApiError` and `withQuery`. Paths are relative to `/api/v1`. It throws
  `ApiError(status, body)` on non-2xx — handle it where you call. Don't `fetch()` directly in
  components. The API is same-origin `/api` in every environment (Vite proxy in dev, Caddy
  edge in prod; the prod `web` container is a plain nginx static server). Dev-proxy details:
  the target is `API_PROXY_TARGET ?? http://localhost:8000` (the Docker dev stack sets it to
  the backend service), and `/docs`, `/api-docs`, `/api-redoc` are proxied too. Footgun: Node
  resolves `localhost` to `::1` first — a backend bound IPv4-only (which includes a plain
  `fastapi dev`, default host `127.0.0.1`, and `uvicorn --host 0.0.0.0`) can surface as an
  empty-body 500 from `:5173/api` that looks like a backend crash. Fix: run the backend with
  `--host '::'`, or point `API_PROXY_TARGET` at `http://127.0.0.1:8000`.
- **Styling**: Tailwind utility classes in templates. Design tokens (`@theme { --color-... }`) and any global CSS go in `src/assets/main.css`. Tailwind v4 has **no `tailwind.config.js`** — it's driven by the CSS file and the Vite plugin. Avoid `<style>` blocks unless genuinely component-scoped and not expressible with utilities.
- **Copy**: every user-facing string lives in `src/shared/i18n/locales/<locale>/<namespace>.json`
  and reaches the screen through **`$t('ns.section.key')`** in templates (global injection is on —
  no import), `useI18n()` in `<script setup>`, or `translate()` / `translatePlural()` from
  `@/shared/i18n` in plain modules. Two catalogs are maintained: **`uz`** is the source, **`ru`**
  its translation with the same key set; **`uz-Cyrl`** is derived from `uz` by
  `i18n/transliterate.ts` and is never hand-written — a word the rules get wrong goes in
  `i18n/overrides/uz-Cyrl.json`. Adding a namespace means adding its file to *both* locale
  `index.ts` files. A module-level `const LABELS = {...}` of copy is a bug: it freezes at
  whatever locale was active when the module first evaluated — export a function instead.
  Two holes in `pnpm i18n:check`, both by design: it only sees **literal** keys (a
  `t(item.labelKey)` or built-up key is skipped — rename such a key and the raw path renders
  through a green gate), and it validates against **`uz` only** (a key missing from `ru`
  ships silently and falls back at runtime — keeping `ru` complete is on the author). Copy
  rules and the term glossary are in [`DESIGN.md`](./DESIGN.md).
- **Env vars**: only `VITE_`-prefixed vars reach client code. Add one only when the browser genuinely needs public build-time config; document it in `.env.dev.example` + `.env.prod.example`.
- **Tests**: colocate as `src/**/__tests__/*.spec.ts` (or `*.spec.ts` next to the unit). Use `@vue/test-utils` `mount`; mock `@/shared/api/client` rather than hitting the network. Don't put browser/integration flows here — that's `e2e/`. **E2E locators track UI copy** — changing labels/dialogs means grepping `e2e/tests/` (see root `AGENTS.md`).

## UX bar — every screen clears these

Structure before skin: know the user's job, the screen's states, and the keyboard path before
choosing components or colors. Never polish a screen whose structure is wrong.
[`DESIGN.md`](./DESIGN.md) is the design system — tokens, surfaces, type, component
contracts, copy rules, glossary; **read it before designing or reviewing UI**. Its rules plus
this bar **outrank the design handoff** (DESIGN.md names the three palette values that
deliberately sit off the handoff hex to clear the contrast floor); nothing else does.

- **Every state is designed, not just the populated one**: empty (first-run), empty (no
  results), loading (skeletons sized like the real content — reserve space so nothing jumps),
  error (named cause + retry), success. Every load that can hang gets a timeout → error path;
  no infinite spinners.
- **An empty-state icon names the thing that is missing — a noun** (`box`, `inbox`, `layers`,
  `scissors`). Never an action glyph (`plus`, `edit`, `arrow`): the tile sits exactly where a
  button would, so an action glyph inside it reads as a control and gets clicked.
- **The keyboard reaches and operates everything** a mouse can, in an order matching the
  layout, with the visible focus affordance DESIGN.md specifies. Modals trap focus and return
  it to the trigger on close.
- **Every input has a visible, persistent label** — a placeholder is a hint, never a label.
  Errors sit next to their field, name the fix in plain language, and never clear the form.
  Validate on blur or submit, not per keystroke. A rejected field carries all three signals —
  the danger border, `aria-invalid`, and an `aria-describedby` message — and the message stays
  **readable**: a field that opens a popover anchors it clear of its own error text, because a
  message the operator can't see is the same as no message.
- **Every action gives visible feedback within ~100ms**; submit buttons disable + show
  progress during async work so they can't double-fire. Prefer undo over a confirmation nag.
- No horizontal page scroll on any viewport (self-contained scrollable tables excepted).
- **Motion is cause-and-effect, not decoration**: ~150–300ms, `transform`/`opacity` only,
  gone under `prefers-reduced-motion` (the global CSS already honors it).

Contrast floors, touch targets, type scale, colour pairing, one-primary-action — the rest of
the bar is DESIGN.md's rules and its Do's & Don'ts checklist.

## Building against the system

### Token names are stable; their values are not

The palette is remapped **in place** — a token keeps its name and takes a new value. So
`text-accent` means graphite where it once meant the old brand colour, `bg-accent-soft` is an
orange tint, and `font-mono` no longer changes the font family at all. Nothing breaks and nothing
fails a gate: a class that was correct before a retheme can be wrong after it and still lint,
typecheck, build, and pass every unit test. Treat a token-value change as a **visual** change —
after one, open the affected screens and read the computed value, because this class of defect is
invisible to the check gates by construction.

### Measuring under the root zoom

Desktop paints at `zoom: 90%` on the root (≥769px), which splits the units the DOM reports:
`getBoundingClientRect()` and `window.inner*` are **painted** pixels, while `offsetHeight` and
anything written into `style.top/left` are **local** pixels the browser then scales. An overlay
positioned straight from a measured rect lands at 90% of its anchor. Measure through
`overlayRect()` / `overlayViewport()` (`shared/app/overlayGeometry.ts`) — never
`getBoundingClientRect()` directly — so the whole calculation stays in one unit.

Viewport units have the same split and no helper can hide it: `100dvh` / `100vw` resolve
against the **unzoomed** viewport and the result is then scaled by the zoom, so a `100dvh`
panel paints 90% of the screen. Full-bleed surfaces use the **`--app-vh` / `--app-vw`** tokens
(`assets/main.css`, declared beside the `zoom` rule) instead of raw viewport units — they carry
the compensation, and the ratio behind it (`--app-zoom`) is written down once. Raw `vh` / `vw`
are still fine for a *cap* that only needs to stay under the viewport
(`max-height: min(90vh, …)` on a modal).

Media queries are zoomed too: the `lg` / `xl` / `2xl` breakpoints are **pre-divided** by the
zoom ratio (922 / 1152 / 1382), so a hand-written `@media (min-width: 1024px)` fires 11%
later than the `lg:` utility — use the utility, or the pre-divided numbers.

### The workshop frame scrolls in two places

At **≥921px** the workshop shell is a fixed frame: the sidebar and the content column each
scroll on their own inside `var(--app-vh)`, and the document does not scroll at all. Below 921px
the frame is off and the page scrolls as any other page does. Three consequences, each of which
has to be carried deliberately:

- **`scrollLock` pins `document.body`, which under the frame is not the scroller.** The body pin
  (`position: fixed` + the `body.modal-open` class) is what stops iOS Safari scrolling behind a
  modal, but it cannot reach an inner scroller — so the `body.modal-open` rule in
  `assets/main.css` pins the frame's content scroller as well. Every overlay goes through
  `shared/app/scrollLock.ts`; none rolls its own `overflow: hidden`.
- **`@media print` has to reset the frame** to `height: auto; overflow: visible`, or a printed
  document — the akt sverka, say — clips to one screen's worth of rows.
- **A teleported popover has to hear the inner scroller.** A `scroll` event does not bubble, so a
  listener on `window` never fires for an element that scrolls; the shared overlays register
  their reposition handler in the **capture** phase (`addEventListener('scroll', …, true)`),
  which does see it. Drop that flag and every dropdown detaches from its trigger the moment the
  content column moves.

### Popovers escape their container

Anything that opens over the page — dropdown, action menu, date picker — **teleports to
`<body>`, is `position: fixed`, and is placed from `overlayRect()` of its trigger**
(`ProjectDropdown`, `DateField`, `ActionMenu`). Rendering it absolutely inside its own row or
card looks fine until the ancestor clips: `.table-wrap` is `overflow-x: auto`, and per spec one
non-`visible` axis makes the other a scroll container too, so a panel inside it both **grows the
wrapper's `scrollHeight`** — focusing an item then scrolls rows under the opaque sticky header —
and **gets clipped**. Flipping the panel up doesn't save it: on a short table there is no room
in either direction. Leaving the container is the only fix that holds at every table height.

Teleporting moves the panel out of the trigger's subtree, so two things stop working unless you
carry them across: an outside-click handler that tests only the wrapper will close the menu on
the panel's own `pointerdown` (test the panel too), and a `keydown` handler bound to the wrapper
never sees Esc pressed with focus inside the panel (bind it on both).

### Building from a design handoff — run the prototype, don't read it

A handoff from Claude Design arrives as a bundle of `.dc.html` prototypes (the repo keeps the
latest in the untracked `.design-handoff/`). **They are runnable.** Serve the folder and click
through the real thing:

```bash
cd .design-handoff && python3 -m http.server 8899
# → http://localhost:8899/<name>.dc.html — self-contained, no build, no network
```

Reading the HTML instead of running it does not work (it has failed here twice): the markup is
a template language with `{{ }}` bindings whose values live in a `<script type="text/x-dc">`,
so a screen's real shape only exists once that script has run. The rules, in order:

1. **Screenshot the prototype screen first, then the app screen, then compare them side by
   side.** Not the source — the screens. Do this before writing any code for that screen, and
   again before saying it is done.
2. **A diff of the handoff is not a work list.** When a second bundle arrives it is tempting
   to diff it against the last one and build the hunks. That answers "what did the designer
   change", and the question is "where does the app differ from the design". Everything the
   app never got right *and* the designer did not touch this round is invisible to a diff —
   structurally, not by accident. It has cost a full round here: the cutting map's parts were
   filled accent-peach against the prototype's white, the offcut had no fill, the waste had a
   danger-red outline instead of a hatch and the sheet frame was orange — five element-level
   mismatches, none of them in the diff, all of them on a screen that had already been called
   done. Diff to learn intent; scope from the screen.
3. **Scope is the screen, not the change.** If a screen is in play, every element on it is in
   play — including the parts nobody edited this round. Before calling one done, walk it as an
   inventory rather than an impression: background, border, every label, every mark, offcut,
   waste, frame — tick each against the prototype. An impression checks that the blocks are
   present; only the inventory catches the element that was always wrong.
4. **Measure, don't eyeball.** For anything carrying a number *or a colour* — focus rings,
   border weights, glyph geometry, fills — read `getComputedStyle` (or the SVG attribute) on
   both sides. A 3px focus-ring difference is invisible in scaled screenshots, and so is a
   fill you have stopped looking at because you are checking layout.
5. **A noticed anomaly is a finding, not a note to self.** "That looks off, I will come back to
   it" is how the map's fill survived a round: it was seen, written down mid-work and dropped.
   Either resolve it or put it in the report. There is no third option.
6. **When the measurement disagrees with the screen, believe neither yet — get a third look.**
   The browser pane renders large and scales the capture down (a 1px border vanishes), and
   `getComputedStyle` through the pane has returned stale values. Shrink the viewport to
   ~1280×700 so the screenshot is near 1:1 and look again. "The CSS is right by construction"
   is where real defects hide — a global `:focus-visible` rule and a utility overriding the
   focus colour in a later cascade layer have both bitten here.
7. **Where the repo does more than the design depicts, keep the capability and match the
   frame.** Say so in a comment at the deviation — every one of these is a judgement someone
   will otherwise re-litigate.
8. **Deviate only for the UX bar above, and write down which line of it forced you.** The bar
   outranks the handoff; nothing else does. "It seemed better" is not a reason — take it to the
   owner instead.
9. **Do not delete working behaviour because the prototype omits it.** A prototype is a sketch
   of a screen, not an inventory of a product.

A handoff is finished when every screen it names has been walked as an inventory and every
element ticks — not when the tasks the spec listed are closed. The spec and the diff are both
descriptions of the design; the prototype is the design.

### Verifying UI work

Launch/seed/drive recipe (including browser login and its gotchas) → the **verify** skill.
Where CSS is the subject, a screenshot confirms intent but only the computed or rendered
value confirms effect: read `getComputedStyle` / the measured rect, not the picture.

`vue-tsc` does **not** catch a component used in a template but never imported — it renders as
nothing, silently, through a green typecheck. Only opening the screen finds it.
