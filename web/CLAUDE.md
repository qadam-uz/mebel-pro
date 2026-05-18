# Web — `mebel-pro/web`

The web client. Vite build, TypeScript everywhere, Pinia for state, Vue Router
for routing, Tailwind v4 for styling. Package manager: **pnpm**.

## Target shape vs. current state

The design [`docs/architecture.md`](../docs/architecture.md) → _Why three SPAs + a static landing_ is:

1. a **static, SEO-optimized landing page** — plain HTML + minimal CSS/JS, served at `/`, _not_ part of this Vue tree;
2. **three Vue SPAs** in this repo, each its own Vite entry, auth surface, and route set — **client** (Telegram-auth customers: cutting + ordering + tracking), **workshop** (login-auth workshop owner & staff, every screen gated by permission grants), **superadmin** (login-auth platform operators);
3. shared UI primitives, the API client, design tokens, and i18n living once in the repo, consumed by all three.

**Current state:** the **static landing exists** — `web/landing/index.html`, its own Vite entry (`build.rollupOptions.input.landing` → `dist/landing/index.html`), served at the apex by the Caddy edge (`deploy/Caddyfile` rewrites `/` → `/landing/index.html`); it is _not_ part of the Vue tree. The Vue side is still the **initial single-app scaffold** (one `index.html`, one `src/main.ts`, one router) — the seed of the **client** app. Pending build work: splitting the Vue side into three entries + extracting shared code; until then, treat the scaffold as the client app and don't add workshop/superadmin screens to it.

**HTML prototype:** the confident UI/UX starting point lives in `web/prototypes/prototype-1/` (`client/`, `workshop/`, `admin/`, `landing/`, shared `assets/`). It is a **design reference**, not part of any Vite entry and not built or served — port screens from it into the Vue SPAs; don't wire it into the build.

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
| HTTP         | native `fetch` wrapper — `src/api/client.ts` (no axios)                                                  |

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

Pre-push gate: `pnpm lint:check && pnpm format:check && pnpm typecheck && pnpm test && pnpm build`.

Adding deps: `pnpm add <pkg>` / `pnpm add -D <pkg>`. If a dep needs a postinstall build script, add it to `pnpm.onlyBuiltDependencies` in `package.json` (already lists `esbuild`).

## Layout

```
web/
  index.html                # Vite entry; mounts #app, loads /src/main.ts
  vite.config.ts            # plugins, `@` → src alias, dev server + /api proxy
  vitest.config.ts          # merges vite config; jsdom env; excludes e2e/**
  tsconfig*.json            # root references → app / node / vitest projects
  env.d.ts                  # ImportMetaEnv augmentation (VITE_* vars)
  eslint.config.ts          # flat config
  nginx.conf                # used by the Docker image to serve dist/ (SPA history fallback)
  Dockerfile                # node:22 build (corepack→pnpm) → nginx:alpine runtime
  .env.example              # build-time VITE_* vars
  src/
    main.ts                 # createApp + Pinia + Router, mount
    App.vue                 # root layout + <RouterView>
    assets/main.css         # `@import "tailwindcss"`; @theme tokens go here
    router/index.ts         # routes (lazy-load non-critical views; 404 catch-all)
    views/                  # route-level components (HomeView, AboutView, NotFoundView, …)
    components/              # reusable presentational components
      __tests__/            # *.spec.ts colocated unit tests
    composables/            # shared composition functions (use*)
    stores/                 # Pinia stores — one file per domain (setup style)
    api/client.ts           # fetch wrapper: api.get/post/put/patch/del, ApiError
```

## Conventions

- **SFCs**: `<script setup lang="ts">` + Composition API only. No Options API, no class components.
- **Imports**: use the `@/` alias for anything under `src/` (e.g. `@/stores/health`). Relative imports only within a feature folder.
- **Routing**: register routes in `src/router/index.ts`. Route-level components live in `views/`; lazy-load (`() => import(...)`) everything except the initial route. Keep the `:pathMatch(.*)*` 404 route last.
- **State**: Pinia setup stores — `defineStore('name', () => { const x = ref(...); ... return { x, ... } })`. One store per domain in `src/stores/`. Component-local state stays in the component; reach for a store only when state is shared across routes/components.
- **Data fetching**: go through `src/api/client.ts` (`api.get<T>('/path')`). Paths are relative to `/api/v1`. It throws `ApiError(status, body)` on non-2xx — handle it where you call. Don't `fetch()` directly in components.
- **Styling**: Tailwind utility classes in templates. Design tokens (`@theme { --color-... }`) and any global CSS go in `src/assets/main.css`. Tailwind v4 has **no `tailwind.config.js`** — it's driven by the CSS file and the Vite plugin. Avoid `<style>` blocks unless genuinely component-scoped and not expressible with utilities.
- **Env vars**: only `VITE_`-prefixed vars reach client code; declare them in `env.d.ts` (`ImportMetaEnv`) and document in `.env.example`. In dev leave `VITE_API_BASE_URL` empty (Vite proxies `/api`); same in prod (the Caddy edge serves the API same-origin under `/api`).
- **Tests**: colocate as `src/**/__tests__/*.spec.ts` (or `*.spec.ts` next to the unit). Use `@vue/test-utils` `mount`; mock `@/api/client` rather than hitting the network. Don't put browser/integration flows here — that's `e2e/`.
- **Clean gate**: `eslint`, `prettier --check`, `vue-tsc`, and the test suite must all pass; `pnpm build` must succeed (it type-checks via `vue-tsc --build`). Fix issues rather than disabling rules; scope any `eslint-disable` to the line with a reason.

## Backend contract

The backend is the FastAPI service in `../backend` — REST JSON under `/api/v1`. In dev, `vite.config.ts` proxies `/api` to `http://localhost:8000`, so run `uv run fastapi dev app/main.py` alongside `pnpm dev`. In prod, the **Caddy edge** (`deploy/Caddyfile`) routes by **subdomain** under one apex `BASE_DOMAIN`: apex → landing; `app.*` → client SPA; `workshop.*` → workshop SPA; `admin.*` → superadmin SPA (+ `/docs`, `/api-docs`, `/api-redoc`). `/api/*` on every SPA subdomain → backend (same-origin, no CORS). The `web` container is a plain nginx static server (`web/nginx.conf`) doing the HTML5-history fallback.

## Design system

[`DESIGN.md`](./DESIGN.md) is the deterministic design contract: tokens, UI primitives, composed components, the shell, route maps for all three SPAs, i18n namespaces, API boundary patterns, and the accessibility baseline. Read it before adding components or screens.

## Related skills

When designing screens, flows, components, or reviewing UI: use the **ui-ux-mastery** skill. For frontend implementation polish, the **frontend-design** skill. For test strategy decisions, **testing-practices**.
