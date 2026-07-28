# Web — `mebel-pro/web`

The web client. Vite build, TypeScript everywhere, Pinia for state, Vue Router
for routing, Tailwind v4 for styling. Package manager: **pnpm**.

## Target shape vs. current state

The target — a static SEO landing + three Vue SPAs (**client** / **workshop** /
**superadmin**) sharing primitives, the API client, tokens, and i18n — and the
rationale live in [`docs/architecture.md`](../docs/architecture.md). This file
covers only the **current build state**:

- **Static landing exists** — `web/landing/index.html`, its own Vite entry
  (`build.rollupOptions.input.landing` → `dist/landing/index.html`), served at
  the apex by the Caddy edge; _not_ part of the Vue tree.
- **The Vue side is three role SPAs** — `web/client/index.html`,
  `web/workshop/index.html`, and `web/admin/index.html`, each mounting its own
  entry under `src/apps/<role>/main.ts` with role routes in
  `src/apps/<role>/routes.ts`. Shared code lives under `src/shared/`.

## Toolchain

| Concern      | Tool                                                                                                     |
| ------------ | -------------------------------------------------------------------------------------------------------- |
| Runtime / PM | Node **22+**, **pnpm** (`packageManager` pinned; `engine-strict`)                                        |
| Build / dev  | **Vite 7** (`@vitejs/plugin-vue`)                                                                        |
| Framework    | Vue **3.5** (`<script setup lang="ts">`, Composition API)                                                |
| Routing      | Vue Router 4 (`createWebHistory`)                                                                        |
| State        | Pinia (setup-style stores)                                                                               |
| Styling      | Tailwind CSS **v4** (`@tailwindcss/vite`; config-less, `@import "tailwindcss"` in `src/assets/main.css`) |
| Types        | TypeScript (project references: `tsconfig.{app,node,vitest}.json`); `vue-tsc` for `.vue`                 |
| Lint         | **ESLint 9** flat config (`eslint-plugin-vue`, `@vue/eslint-config-typescript`, prettier-skip)           |
| Format       | **Prettier** (no semicolons, single quotes, width 100)                                                   |
| Unit tests   | **Vitest** + `@vue/test-utils` + jsdom                                                                   |
| HTTP         | native `fetch` wrapper — `src/shared/api/client.ts` (no axios)                                           |

E2E tests live in the sibling `e2e/` package (Playwright), not here.

## Commands

```bash
pnpm install                 # install (use --frozen-lockfile in CI)
pnpm dev                     # Vite dev server, :5173, /api proxied → :8000
pnpm build                   # vue-tsc --build && vite build  → dist/

pnpm test                    # run unit tests once (test:watch / test:coverage exist)

pnpm typecheck               # vue-tsc --build --force (no emit)
pnpm lint                    # eslint . --fix
pnpm lint:check              # eslint . (no fix — CI)
pnpm format                  # prettier --write src/
pnpm format:check            # prettier --check src/
```

Pre-push gate: `pnpm lint:check && pnpm format:check && pnpm typecheck && pnpm test && pnpm build`.

Adding deps: `pnpm add <pkg>` / `pnpm add -D <pkg>`. If a dep needs a postinstall build script, add it to `pnpm.onlyBuiltDependencies` in `package.json` (already lists `esbuild`).

## Layout

```
web/
  landing/index.html        # static SEO landing entry
  client/index.html         # client SPA entry
  workshop/index.html       # workshop SPA entry
  admin/index.html          # superadmin SPA entry
  vite.config.ts            # MPA inputs, role history fallback, `@` alias, /api proxy
  vitest.config.ts          # merges vite config; jsdom env; excludes e2e/**
  tsconfig*.json            # root references → app / node / vitest projects
  env.d.ts                  # Vite client types
  eslint.config.ts          # flat config
  nginx.conf                # used by the Docker image to serve dist/ (SPA history fallback)
  Dockerfile                # node:22 build (corepack→pnpm) → nginx:alpine runtime
  .env.dev.example          # build-time env shape (dev); .env.prod.example mirrors it
  src/
    apps/
      client/main.ts        # client app bootstrap
      client/routes.ts      # client route inventory
      workshop/main.ts      # workshop app bootstrap
      workshop/routes.ts    # workshop route inventory
      admin/main.ts         # superadmin app bootstrap
      admin/routes.ts       # superadmin route inventory
    shared/                 # shared shell, views, stores, API client, primitives
      api/client.ts         # fetch wrapper: api.get/post/put/patch/del/blob, ApiError, withQuery
      app/                  # framework-agnostic helpers (authInit, clientUi, downloadBlob, scrollLock, …)
      components/           # shared presentational components (+ __tests__/ colocated specs)
      composables/          # shared composition functions (use*)
      stores/               # Pinia stores — one file per domain (setup style)
      views/                # route-level components (shared across roles for now)
    assets/main.css         # `@import "tailwindcss"`; @theme tokens go here
```

## Conventions

- **SFCs**: `<script setup lang="ts">` + Composition API only. No Options API, no class components.
- **Imports**: use the `@/` alias for anything under `src/` (e.g. `@/stores/health`). Relative imports only within a feature folder.
- **Routing**: register routes in the owning role file under `src/apps/<role>/routes.ts`.
  Route-level components currently live in `src/shared/views/`; move toward role-owned
  views as feature modules mature. Lazy-load (`() => import(...)`) everything except the
  initial route. Keep the `:pathMatch(.*)*` 404 route last. For links inside shared
  views, use `useRolePath()` from `src/shared/app/paths.ts` instead of hard-coded
  role-prefixed URLs; dev mounts apps under `/client`, `/workshop`, and `/admin`, while
  production is host-routed. Inside a role route file, write **absolute production paths**
  (`/workshop/orders/new`) everywhere — `path`, `redirect`, and any target a `beforeEnter`
  guard returns. `normalizeRoleRoutes` strips the dev base off all three, so a raw literal is
  correct in both environments; a `useRolePath()` call there would double the base.
- **State**: Pinia setup stores — `defineStore('name', () => { const x = ref(...); ... return { x, ... } })`. One store per domain in `src/shared/stores/`. Component-local state stays in the component; reach for a store only when state is shared across routes/components.
- **Data fetching**: go through `src/shared/api/client.ts` (`api.get<T>('/path')`). Paths are relative to `/api/v1`. It throws `ApiError(status, body)` on non-2xx — handle it where you call. Don't `fetch()` directly in components.
- **Styling**: Tailwind utility classes in templates. Design tokens (`@theme { --color-... }`) and any global CSS go in `src/assets/main.css`. Tailwind v4 has **no `tailwind.config.js`** — it's driven by the CSS file and the Vite plugin. Avoid `<style>` blocks unless genuinely component-scoped and not expressible with utilities.
- **Env vars**: only `VITE_`-prefixed vars reach client code. Add one only when the browser genuinely needs public build-time config; document it in `.env.dev.example` + `.env.prod.example`. API origin is not configurable — dev uses the Vite `/api` proxy and prod uses the Caddy same-origin `/api` edge.
- **Tests**: colocate as `src/**/__tests__/*.spec.ts` (or `*.spec.ts` next to the unit). Use `@vue/test-utils` `mount`; mock `@/api/client` rather than hitting the network. Don't put browser/integration flows here — that's `e2e/`.
- **Clean gate**: `eslint`, `prettier --check`, `vue-tsc`, and the test suite must all pass; `pnpm build` must succeed (it type-checks via `vue-tsc --build`). Fix issues rather than disabling rules; scope any `eslint-disable` to the line with a reason.

## Backend contract

The backend is the FastAPI service in `../backend` — REST JSON under `/api/v1`. In dev, `vite.config.ts` proxies `/api` to `http://localhost:8000`, so run `uv run fastapi dev app/main.py` alongside `pnpm dev`. The API is same-origin in every environment (no CORS); prod subdomain routing is owned by [`docs/architecture.md`](../docs/architecture.md) (topology) and `deploy/Caddyfile`. The `web` container is a plain nginx static server (`web/nginx.conf`) doing the HTML5-history fallback.

## Design system

[`DESIGN.md`](./DESIGN.md) is the design system itself — tokens, surfaces, type, components,
copy rules, and the glossary. It describes **what the system is**; the rules for building
against it are below, so the two do not drift into one document that is half specification and
half instruction. Read `DESIGN.md` before designing or reviewing UI. For frontend
implementation polish use the **frontend-design** skill (when your harness provides it); for
where a test belongs, **testing-practices**.

## UX bar — every screen clears these

Structure before skin: know the user's job, the screen's states, and the keyboard path before
choosing components or colors. Never polish a screen whose structure is wrong.

- **Every state is designed, not just the populated one**: empty (first-run), empty (no
  results), loading (skeletons sized like the real content — reserve space so nothing jumps),
  error (named cause + retry), success. Every load that can hang gets a timeout → error path;
  no infinite spinners.
- **An empty-state icon names the thing that is missing — a noun** (`box`, `inbox`, `layers`,
  `scissors`). Never an action glyph (`plus`, `edit`, `arrow`). `.client-empty-icon` uses
  accent-on-accent-soft, the same language as a primary button, so an action glyph inside it
  reads as a control and gets clicked.
- **The keyboard reaches and operates everything** a mouse can, in an order matching the
  layout. Visible `:focus-visible` ring with ≥3:1 contrast — never `outline: none` with
  nothing in its place. Modals trap focus and return it to the trigger on close.
- **Every input has a visible, persistent label** — a placeholder is a hint, never a label.
  Errors sit next to their field, name the fix in plain language, and never clear the form.
  Validate on blur or submit, not per keystroke. A rejected field carries all three signals —
  the danger border, `aria-invalid`, and an `aria-describedby` message — and the message stays
  **readable**: a field that opens a popover anchors it clear of its own error text, because a
  message the operator can't see is the same as no message.
- **Every action gives visible feedback within ~100ms**; submit buttons disable + show
  progress during async work so they can't double-fire. Destructive actions name their
  consequence ("Delete 3 files", not "OK"); prefer undo over a confirmation nag.
- **Color is never the only signal** (pair with text/icon/position); text contrast ≥ 4.5:1
  (≥3:1 for large text and UI marks). Touch targets ≥ 44×44 px of hittable area.
- **One primary action per screen**, visually dominant. Body text stays at the 14px base
  (dense back-office by design); captions never below 10.5px. No horizontal page scroll on
  any viewport (self-contained scrollable tables excepted).
- **Motion is cause-and-effect, not decoration**: ~150–300ms, `transform`/`opacity` only,
  gone under `prefers-reduced-motion` (the global CSS already honors it).

## Building against the system

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

### Verifying UI work

The check gates are necessary, not sufficient. Run the app, seed realistic data
(`bash deploy/seed-demo.sh`), and drive the affected flow in a browser before calling it done —
a green test run never shows a wrong layout, a broken empty state, or mangled copy. Where CSS
is the subject, a screenshot confirms intent but only the computed or rendered value confirms
effect: read `getComputedStyle` / the measured rect, not the picture.

