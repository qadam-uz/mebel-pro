# Web — `mebel-pro/web`

The web client. Vite build, TypeScript everywhere, Pinia for state, Vue Router
for routing, Tailwind v4 for styling. Package manager: **pnpm**.

## Shape

A static SEO landing + three Vue SPAs (**client** / **workshop** /
**superadmin**) sharing primitives, the API client, tokens, and i18n — see
[`docs/architecture.md`](../docs/architecture.md) for the rationale and
[`DESIGN.md`](./DESIGN.md) for the per-app entries, dev URLs, and the design
system. Current state:

- **Static landing** — `web/landing/index.html`, its own Vite entry
  (`build.rollupOptions.input.landing` → `dist/landing/index.html`), served at
  the apex by the Caddy edge; _not_ part of the Vue tree.
- **Three Vue SPAs** — each its own HTML entry + `main.ts` under
  `src/apps/<app>/`: `client.html` → `apps/client`, `workshop.html` →
  `apps/workshop`, `admin.html` → `apps/admin`. Shared code (API client, auth
  store, design tokens, UI primitives, i18n, format helpers) lives once under
  `src/shared/`. Dev URLs, entries, build outputs, and prod hosts are tabulated
  under **Commands** and **Layout**.
- **Placeholder screens** — every documented route exists, but most views are
  `PlaceholderView` stubs (real login + change-password + Telegram-login
  screens and a working `NotificationBell` are built). Fill the stubs per app;
  keep shared concerns in `src/shared/`.
- **HTML prototype** lives in `web/prototypes/prototype-full/` — the design
  reference (ported into `src/shared/assets/design-system.css`), not a Vite
  entry. Port screens from it; don't wire it into the build.

## Toolchain

| Concern      | Tool                                                                                                     |
| ------------ | -------------------------------------------------------------------------------------------------------- |
| Runtime / PM | Node **22+**, **pnpm** (`packageManager` pinned; `engine-strict`)                                        |
| Build / dev  | **Vite 7** (`@vitejs/plugin-vue`, `vite-plugin-vue-devtools`)                                            |
| Framework    | Vue **3.5** (`<script setup lang="ts">`, Composition API)                                                |
| Routing      | Vue Router 4 (`createWebHistory`)                                                                        |
| State        | Pinia (setup-style stores)                                                                               |
| Styling      | Tailwind CSS **v4** (`@tailwindcss/vite`; config-less, `@import "tailwindcss"` in `src/assets/main.css`) |
| Types        | TypeScript (project references: `tsconfig.{app,node,vitest}.json`); `vue-tsc` for `.vue`                 |
| Lint         | **ESLint 9** flat config (`eslint-plugin-vue`, `@vue/eslint-config-typescript`, prettier-skip)           |
| Format       | **Prettier** (no semicolons, single quotes, width 100)                                                   |
| Unit tests   | **Vitest** + `@vue/test-utils` + jsdom                                                                   |
| HTTP         | native `fetch` wrapper — `src/shared/api/client.ts` (no axios)                                           |
| i18n         | lightweight reactive dictionary — `src/shared/i18n` (Uzbek-only v1; no vue-i18n)                         |

E2E tests live in the sibling `e2e/` package (Playwright), not here.

## Commands

```bash
pnpm install                 # install (use --frozen-lockfile in CI)
pnpm dev                     # Vite dev server, :5173, /api proxied → :8000
pnpm build                   # vue-tsc --build && vite build  → dist/
pnpm preview                 # serve the production build locally

pnpm test                    # run unit tests once
pnpm test:watch              # watch mode
pnpm test:coverage           # with v8 coverage

pnpm typecheck               # vue-tsc --build --force (no emit)
pnpm lint                    # eslint . --fix
pnpm lint:check              # eslint . (no fix — CI)
pnpm format                  # prettier --write src/
pnpm format:check            # prettier --check src/
```

`pnpm dev` serves one Vite entry per app (`vite.config.ts →
build.rollupOptions.input`); open:

| App        | Dev URL                               | Entry                             |
| ---------- | ------------------------------------- | --------------------------------- |
| Landing    | `http://localhost:5173/landing/`      | `landing/index.html` (plain HTML) |
| Client     | `http://localhost:5173/client.html`   | `src/apps/client/main.ts`         |
| Workshop   | `http://localhost:5173/workshop.html` | `src/apps/workshop/main.ts`       |
| Superadmin | `http://localhost:5173/admin.html`    | `src/apps/admin/main.ts`          |

Each SPA uses an HTML5-history router whose base is its entry file
(`createWebHistory('/workshop.html')`, etc.), so deep links like
`/workshop.html/orders` work in dev and prod.

Pre-push gate: `pnpm lint:check && pnpm format:check && pnpm typecheck && pnpm test && pnpm build`.

Adding deps: `pnpm add <pkg>` / `pnpm add -D <pkg>`. If a dep needs a postinstall build script, add it to `pnpm.onlyBuiltDependencies` in `package.json` (already lists `esbuild`).

## Layout

```
web/
  client.html / workshop.html / admin.html   # the three SPA entries (mount #app, load apps/<app>/main.ts)
  landing/index.html        # static SEO landing (plain HTML, its own Vite entry)
  vite.config.ts            # plugins, `@` → src alias, 4 rollup inputs, dev server + /api proxy
  vitest.config.ts          # merges vite config; jsdom env; excludes e2e/**
  tsconfig*.json            # root references → app / node / vitest projects
  env.d.ts                  # ImportMetaEnv augmentation (VITE_* vars)
  eslint.config.ts          # flat config
  nginx.conf                # serves dist/ (history fallback → client.html; edge routes subdomains)
  Dockerfile                # node:22 build (corepack→pnpm) → nginx:alpine runtime
  .env.example              # build-time VITE_* vars
  src/
    shared/                 # the layer all three SPAs build on
      assets/      app.css (entry) + design-system.css (the ported prototype CSS)
      api/         client.ts (fetch + auth + refresh + ApiError) · auth.ts · notifications.ts · storage.ts
      stores/      auth.ts (createAuthStore factory: principal, tokens, can(), branch picker)
      ui/          AppButton AppCard StatusBadge AppModal ToastHost FormField EmptyState
                   ErrorState LoadingSkeleton DataTable FilterBar FilterChip AppPagination
                   AppTabs AppStepper NotificationBell PlaceholderView NotFoundView · auth/{PasswordLogin,ChangePassword}
      composables/ useToast
      i18n/        index.ts (reactive t()) + uz.ts (Uzbek catalog)
      types.ts     core DTOs (Me, Tokens, Notification, …)
      format.ts    fmtTiyin / fmtSum / fmtPhone / fmtDate / initialsOf …
      password.ts  pwStrength
      guards.ts    installAuthGuard(router, …)
      placeholder.ts  lazy placeholder route factory
    apps/<app>/             # one folder per SPA: main.ts, App.vue, router.ts, store.ts, layout/, views/
```

Build outputs and prod hosts — the Caddy edge routes the subdomains:

| App        | Build output         | Prod host (Caddy)       |
| ---------- | -------------------- | ----------------------- |
| Landing    | `dist/landing/`      | `mebel-pro.uz`          |
| Client     | `dist/client.html`   | `app.mebel-pro.uz`      |
| Workshop   | `dist/workshop.html` | `workshop.mebel-pro.uz` |
| Superadmin | `dist/admin.html`    | `admin.mebel-pro.uz`    |

Conventions below say `src/api/client.ts` / `src/router/index.ts` etc. — those
now live under `src/shared/` (client, i18n, stores) and `src/apps/<app>/`
(router, views). Register each app's routes in `src/apps/<app>/router.ts`;
lazy-load all non-initial views; keep the `:pathMatch(.*)*` 404 last.

## Conventions

- **SFCs**: `<script setup lang="ts">` + Composition API only. No Options API, no class components.
- **Imports**: use the `@/` alias for anything under `src/` (e.g. `@/stores/health`). Relative imports only within a feature folder.
- **Routing**: register routes in `src/router/index.ts`. Route-level components live in `views/`; lazy-load (`() => import(...)`) everything except the initial route. Keep the `:pathMatch(.*)*` 404 route last.
- **State**: Pinia setup stores — `defineStore('name', () => { const x = ref(...); ... return { x, ... } })`. One store per domain in `src/stores/`. Component-local state stays in the component; reach for a store only when state is shared across routes/components.
- **Data fetching**: go through `src/api/client.ts` (`api.get<T>('/path')`). Paths are relative to `/api/v1`. It throws `ApiError(status, body)` on non-2xx — handle it where you call. Don't `fetch()` directly in components.
- **Styling**: Tailwind utility classes in templates. Design tokens (`@theme { --color-... }`) and any global CSS go in `src/assets/main.css`. Tailwind v4 has **no `tailwind.config.js`** — it's driven by the CSS file and the Vite plugin. Avoid `<style>` blocks unless genuinely component-scoped and not expressible with utilities.
- **i18n**: v1 is **Uzbek-only** ([`docs/architecture.md`](../docs/architecture.md) → Internationalization). Strings are namespaced in `src/shared/i18n/uz.ts`; `t('nav.orders')` looks them up. UI strings (nav, statuses, actions, order phases, finance categories) are taken verbatim from the prototype's `data.js` / shells. Adding `ru`/`en` is mechanical — add a sibling catalog and register it.
- **Auth & tokens**: `createAuthStore({ app })` returns a Pinia store holding the principal (`/auth/me`), token state, `can(permission, branchId?)`, and the branch-picker selection. Tokens live in `localStorage` keyed per app (`mp.<app>.tokens`) so the three SPAs don't collide; the workshop branch selection persists at `mp.<app>.branch`. The API client attaches the bearer token, refreshes once on 401 via `/auth/refresh`, otherwise clears tokens and redirects to the app's login. Route guards (`installAuthGuard`) enforce auth, `force_password_change`, and owner-only routes.
- **Env vars**: only `VITE_`-prefixed vars reach client code; declare them in `env.d.ts` (`ImportMetaEnv`) and document in `.env.example`. In dev leave `VITE_API_BASE_URL` empty (Vite proxies `/api`); same in prod (the Caddy edge serves the API same-origin under `/api`).
- **Tests**: colocate as `src/**/__tests__/*.spec.ts` (or `*.spec.ts` next to the unit). Use `@vue/test-utils` `mount`; mock `@/api/client` rather than hitting the network. Don't put browser/integration flows here — that's `e2e/`.
- **Clean gate**: `eslint`, `prettier --check`, `vue-tsc`, and the test suite must all pass; `pnpm build` must succeed (it type-checks via `vue-tsc --build`). Fix issues rather than disabling rules; scope any `eslint-disable` to the line with a reason.

## Backend contract

The backend is the FastAPI service in `../backend` — REST JSON under `/api/v1`. In dev, `vite.config.ts` proxies `/api` to `http://localhost:8000`, so run `uv run fastapi dev app/main.py` alongside `pnpm dev`. The API is same-origin in every environment (no CORS); prod subdomain routing is owned by [`docs/architecture.md`](../docs/architecture.md) (topology) and `deploy/Caddyfile`. The `web` container is a plain nginx static server (`web/nginx.conf`) doing the HTML5-history fallback.

## Design system

[`DESIGN.md`](./DESIGN.md) is the deterministic design system contract.

## Related skills

When designing screens, flows, components, or reviewing UI: use the **ui-ux-mastery** skill. For frontend implementation polish, the **frontend-design** skill. For test strategy decisions, **testing-practices**.
