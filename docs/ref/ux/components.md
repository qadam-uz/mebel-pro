---
title: Shared components
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/ref/ux/information-architecture.md
  - docs/spec/personas.md
  - docs/spec/nfr.md
---

# Shared components

The cross-cutting UI inventory the three SPAs share — the design tokens, the primitive set, and the
composed components that the `ref/features/*` UX sections reference rather than re-spec. Per-feature
screens, flows, and states live in those feature docs; this is the toolbox they draw from. The
discipline behind all of it — accessibility, states, interaction integrity — is the **ui-ux-mastery**
practice; [`docs/spec/nfr.md`](../../spec/nfr.md) lists the non-negotiables.

## Where it lives

Inside the `web/` repo, shared across the client / seh / superadmin entries: design tokens (Tailwind
v4 `@theme` in the shared CSS), the `ui/` primitives, the `common/` composed components, the
`fetch`-based API client, and the i18n string namespaces. Each app composes these into its own
routes/views; product-specific logic stays in the feature folders, not in the shared layer.

## Design tokens (proposed defaults — replace once a visual system is locked)

Semantic CSS variables, themed (light designed first; dark is a designed pass, not an inversion):

| Token | Purpose | Default (light) |
|---|---|---|
| `--color-bg` | page background | neutral-50 |
| `--color-surface` | cards, table rows | white |
| `--color-border` | dividers | neutral-200 |
| `--color-text` | body text | neutral-900 |
| `--color-muted` | secondary text | neutral-500 |
| `--color-primary` / `--color-primary-fg` | brand action / text on it | indigo-600 / white |
| `--color-success` | confirmed / completed | emerald-600 |
| `--color-warning` | pending / SLA | amber-500 |
| `--color-danger` | cancelled / refund / destructive | rose-600 |
| `--color-info` | awaiting payment / info | sky-600 |
| `--radius-md` / `--radius-lg` | inputs & buttons / cards | 8px / 12px |
| `--shadow-card` | card elevation | subtle |
| type | UI sans, body ≥ 16px, line-height ~1.5, line length ~50–75ch | Inter |
| spacing | one 4px-based scale (4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96) | — |

**Order status colors** (for badges, the board, filters) — color paired with text/icon, never color
alone: `new` neutral · `pending_payment` info · `confirmed` primary · `in_production` indigo-tint ·
`ready` warning · `in_delivery` violet · `completed` success · `cancelled` danger.

## UI primitives (`ui/`)

Thin wrappers over a headless primitive library, each carrying the tokens and the non-negotiables
(visible `:focus-visible` ring, ≥ 44×44 hit area, proper roles/labels): `button`, `input`,
`textarea`, `select`, `combobox`, `checkbox`, `radio-group`, `toggle`, `badge`, `card`, `dialog`
(focus trapped, returns focus on close), `dropdown-menu`, `tabs` (ARIA tabs), `tooltip`, `skeleton`,
`table`, `progress`, `date-picker`, `toast`.

## Composed components (`common/`)

Each follows the interaction-spec shape (purpose · anatomy · variants · states · keyboard · feedback ·
accessibility · tokens):

- **`AppShell`** — top bar (brand, app-specific context control, notification bell, language switcher,
  user menu) + side nav (sectioned; items shown by permission in the seh app; drawer on mobile;
  bottom tab bar on mobile in the client app) + main slot + minimal footer (build version, trace-id
  copy). The three SPAs configure it per app.
- **`PageHeader`** — title, breadcrumb, a primary-action slot. Exactly one primary action per screen.
- **`StatusBadge`** — status enum + namespace (order / branch / refund / job / …) → label + token
  color + an icon; color is never the only signal.
- **`MoneyDisplay`** — renders integer **tiyin** as UZS with thousand separators; never parses float.
  Money *inputs* accept UZS and convert to tiyin on submit (the server is the source of truth).
- **`DateDisplay`** — relative (e.g. "2 days ago") with an absolute timestamp on hover/focus.
- **`EmptyState`** — icon + headline + body + a primary action. Every list/table/data region has a
  designed empty (first-run) and empty (no-results) state.
- **`DataTable`** — wraps `ui/table`: column sort, pagination (`page_number` / `page_size` / `count`
  from the API envelope) or cursor pagination, row click → detail, skeleton rows while loading,
  designed empty/error states; falls back to a card list under the `md` breakpoint.
- **`FilterBar`** — chip-style status/category filters + a search input + a date range; what each
  list page composes for its filters.
- **`Stepper`** — wizard step indicator + a sticky back/continue/save footer; used by the cutting
  wizard, the order create wizard, and the modify wizard.
- **`FormField`** — visible persistent label + control slot + help text + an inline error wired to
  `error.fields`; placeholders are hint-only, never the label. On a failed submit, focus lands on the
  first invalid field; errors state the cause *and* the fix in plain language.
- **`ConfirmDialog`** / **confirm-with-reason** — a destructive-action confirmation; the
  reason-required variant has a mandatory textarea (cancellations, blocks, force-cancels, refund
  notes, adjustment reasons). Danger-colored; the button names the consequence ("Cancel order",
  "Block workshop"), not "OK". Prefer an undo over a nag where feasible.
- **one-time-secret field** — shows a generated login + temp password once, with a copy button and a
  "shown only here — share it now" note (used by every "create user / reset password" flow).
- **masked-secret field** — for payment-channel merchant credentials: masked, reveal-on-click,
  keyboard-operable; owner-visible only.
- **`FileUploader`** — drag-drop + click, a progress bar, a preview for images, error/retry; talks to
  the `files` module; used for material images, the workshop logo, refund/delivery receipt scans,
  delivery docs.
- **`CuttingLayoutSVG`** — renders a cutting result's `sheet_layouts`: one panel per sheet (sheet
  tabs to switch), pan/zoom, hover-a-placement-highlights-the-legend-row, a grain arrow; remains
  scrollable/zoomable on a small phone; has a text-equivalent legend (the per-sheet placement list)
  for non-pointer / screen-reader users.
- **`KanbanBoard`** — column-per-status (orders queue); lazy-loaded paginated cards per column;
  **no drag-and-drop** (status transitions are restricted — they go through a card action menu);
  keyboard-navigable (focus a card, Enter to open).
- **order timeline** — a vertical step list of an order's status events (who / when; system vs.
  workshop user vs. client; stale waits highlighted), built from `order_status_event`s.
- **grants matrix** — permission rows × branch columns, toggling adds/removes `permission_grant`
  rows; explicit Save + unsaved-changes guard; keyboard-navigable with labelled cells.
- **notification bell + dropdown** — a badge with the unread count (polled), a dropdown of the last
  ~10 items linking to the relevant entity, "mark all as read", "see all"; degrades to no badge if
  the endpoint is down. See [`docs/ref/features/notifications-inbox.md`](../features/notifications-inbox.md).
- **error boundary** — surfaces `error.code` → a localized message (falling back to the server's
  `error.message`), the `trace_id` in monospace, and a retry. Every async region that can hang has a
  timeout → error path; no infinite spinners.
- **working-hours grid** — per-weekday open/close, with a "closed this day" toggle; used by the branch
  form.
- **small editable grid** — add/remove-row mini-table; used by branch pricing's edge-banding rates,
  workshop settings' delivery zones, and the cutting wizard's parts editor.

## i18n

Uzbek (`uz`) only in v1. Namespaces: `common` (nav, actions, generic states), `app` (landing/marketing
copy that the apps echo), `auth`, `order`, `cutting`, `org` (workshop / branch / material / inventory /
worker / pricing), `errors` (backend `error.code` → user message; falls back to the server's
`error.message` for an unknown code). Keys are kept generic so `ru` / `en` are mechanical to add.
No literal strings in components.

## API boundary patterns (UI side)

- Every authenticated request carries `Authorization: Bearer <access_token>`; on `401`, the client
  refreshes once and replays, then logs out on a second `401`.
- Lists read `content`; paginated lists read `page_number` / `page_size` / `count`; single resources
  read the root; errors read `error.code` (drives the UI) and show `error.message` (already localized
  by the server) as a fallback, plus `error.fields` → `FormField` inline errors; `X-Trace-ID` is
  surfaced on errors (small, copyable).
- All amounts arrive as integer tiyin; render via `MoneyDisplay`; money inputs convert UZS → tiyin
  before sending.
- Mutations show a busy state that blocks double-submits and end in an explicit success (toast +
  route or cache invalidation) or a recoverable error — never a silent reset.

## Accessibility & responsive baseline

Mobile-first; the `md` breakpoint switches side nav → drawer and tables → card lists; no horizontal
page scroll on any viewport; usable at 200% text/zoom; keyboard reaches and operates everything in
visual order with a visible focus ring; AA contrast; color never the only signal; reserved space for
async content (no layout shift); `prefers-reduced-motion` respected; modals trap and restore focus;
the cutting SVG stays usable on a small phone. (The full checklist is the ui-ux-mastery review list;
the must-haves are in [`docs/spec/nfr.md`](../../spec/nfr.md).)
