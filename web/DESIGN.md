# Design system

> App structure, i18n, auth and dev/build live in [`web/AGENTS.md`](./AGENTS.md);
> this file is the visual design system only.

The deterministic design-system contract for the three Mebel Pro SPAs. It is a
high-fidelity port of `web/prototypes/prototype-full/assets/app.css` — the same
tokens and the same semantic component classes, used **verbatim**. The
prototype is the visual source of truth; the Vue apps must look identical to it.

## The rule

> **Use the prototype's semantic component classes for components; use Tailwind
> utilities only for one-off layout.** The look comes from the design system,
> not from utility soup.

- The stylesheet lives at `src/shared/assets/design-system.css` (ported
  verbatim from the prototype; only the `.mk` brand-icon `url()` was repointed
  to `/favicon.svg` in `web/public/`).
- `src/shared/assets/app.css` is the entry each app's `main.ts` imports — it
  pulls in Tailwind (`@import "tailwindcss"`) **and** the design system, then
  adds the client notification-bell styles that were inline in the prototype's
  `client-shell.js`.
- Tailwind v4 is config-less (driven by the Vite plugin + the CSS file). Reach
  for utilities for spacing/flex/grid on one-off page layout; for anything that
  is a recognised component, use its class below.

## Fonts

Loaded via a Google Fonts `<link>` in each app's HTML `<head>`
(`client.html`, `workshop.html`, `admin.html`):

| Token         | Stack                                                                  | Used for                  |
| ------------- | ---------------------------------------------------------------------- | ------------------------- |
| `--f-display` | `'Source Serif 4', 'Charter', 'Iowan Old Style', Georgia, serif`       | headings, KPIs, numbers   |
| `--f-ui`      | `'Hanken Grotesk', system-ui, -apple-system, 'Segoe UI', Roboto, sans` | body / UI (default)       |
| `--f-mono`    | `'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace`              | ids, amounts, timestamps  |

## Tokens (`:root` CSS variables)

All defined once in `design-system.css`. Reference them directly in scoped
styles and inline `style=""`; never hardcode hex.

- **Surface** — `--bg` `--elev` `--sunk` `--deep` `--deep-2` `--deep-3`
- **Ink (text)** — `--ink-12` `--ink-10` `--ink-8` `--ink-7` `--ink-6` `--ink-4`
  `--ink-2`, plus `--line` / `--line-strong` (hairlines)
- **Semantic** — `--accent` `--accent-h` `--accent-tint` `--accent-soft`
  `--accent-ring`; `--success(/-tint/-soft)` `--warn(...)` `--info(-tint)`
  `--olive(-tint)` `--danger(/-tint/-soft)`
- **Radii** — `--r-xs` `--r-sm` `--r` `--r-lg` `--r-xl`
- **Elevation** — `--sh-1` `--sh-2` `--sh-3` `--sh-4`, focus `--ring`
- **Fonts** — `--f-display` `--f-ui` `--f-mono`

## Component-class catalog

Each is owned by `design-system.css`; the shared UI primitives in
`src/shared/ui/` wrap the most-used ones.

| Class(es)                              | What it is                                              | Primitive            |
| -------------------------------------- | ------------------------------------------------------- | -------------------- |
| `.btn` + `.btn-{primary,acc,outline,ghost,deep,danger,success}` `.btn-{sm,lg,block}` | buttons | `AppButton`          |
| `.card` `.card-h` `.card-b(.flush)`    | content card with optional header                       | `AppCard`            |
| `.pill` `.p-*`                         | status badge with a dot                                 | `StatusBadge`        |
| `.kpi` `.kpis`                         | dashboard metric tile grid                              | —                    |
| `.tbl`                                 | data table (sticky head, clickable rows, `.amt`/`.id`)  | `DataTable`          |
| `.filters` `.chip(.on/.ghost)` `.chips`| filter strip + toggle chips                             | `FilterBar` / `FilterChip` |
| `.field` `.field-row` `.hint` `.err`   | form control with label/hint/error                      | `FormField`          |
| `.scrim` `.modal(.wide)` `.modal-{h,b,f}` | focus-managed dialog + backdrop                      | `AppModal`           |
| `.toast`                               | transient notification                                  | `ToastHost` + `useToast` |
| `.empty` / `.st-empty`                 | friendly empty state                                    | `EmptyState`         |
| `.st-error` (`.trace`)                 | error state with `trace_id` + retry                     | `ErrorState`         |
| `.sk` `.sk-line`                       | shimmering loading skeletons                            | `LoadingSkeleton`    |
| `.tabs` `.tab(.on)`                    | tab bar                                                 | `AppTabs`            |
| `.stepper` `.st(.on/.done)`            | wizard progress                                         | `AppStepper`         |
| `.tl` `.step`                          | vertical timeline (order history)                       | —                    |
| `.menu-wrap` `.menu` `.mi` / `.nd-*`   | dropdown + notification dropdown                        | `NotificationBell`   |
| `.cl-bell-*`                           | client-app notification dropdown                        | `NotificationBell variant="client"` |
| `.app` `.sb-*` `.tb-*` `.br-picker`/`.br-pop` `.drawer` | workshop/admin shell (sidebar + topbar + branch picker) | app `*Layout.vue`    |
| `.hdr` `.hdr-nav` `.user-btn` `.container(.-narrow)` | client header + page container             | `ClientLayout`       |
| `.auth-wrap` `.auth-card` `.tg-btn` `.pw-meter` `.pw-reqs` | sign-in / password screens          | `PasswordLogin` / `ChangePassword` / `TelegramLoginView` |
| `.board` `.board-col` `.board-card`    | orders kanban                                           | —                    |
| `.q-card` `.queue-grid`                | cutter/edger production queue cards                     | —                    |
| `.sheet` `.bar` `.matrix` `.opt(-row)` `.banner` `.sw(-N)` `.spark` `.chart` `.row-item` `.secret-box` | cutting result, progress, grants matrix, radio options, banners, swatches, charts, list rows, one-time secret | — |

Pagination (`AppPagination`) and `AppTabs`/`AppStepper` use the design-system
classes plus minimal layout utilities.
