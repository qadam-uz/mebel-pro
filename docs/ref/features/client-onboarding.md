---
title: Client onboarding
status: stable
owner: shape
updated: 2026-05-11
order: 32
related:
  - docs/spec/access.md
  - docs/ref/entities/identity/client.md
  - docs/ref/entities/identity/session.md
  - docs/ref/features/order-placement.md
---

# Client onboarding

## Problem

Customers should be able to start using the platform with zero friction — no account-creation form,
no password to invent and forget. They overwhelmingly already use Telegram. Let them sign in with
Telegram, auto-registering on the first try, and keep their profile in sync from Telegram. They also
need a place to manage their own sessions and see their Telegram-synced details.

## User stories

- As a **prospective client**, I want to sign in with Telegram and have an account created for me
  automatically so I can go straight to picking a branch and cutting.
- As a **returning client**, I want to sign in with Telegram and land where I left off.
- As a **client**, I want my name, phone, and photo to reflect what's in Telegram.
- As a **client**, I want to see and end my sessions, and log out everywhere.
- As a **client**, I want a clear message if my account is blocked, or if Telegram didn't share my
  phone number, or if the sign-in failed.

## Requirements

1. `telegram-login` (public): accepts the Telegram Login Widget payload (`telegram_id`, `first_name`,
   `last_name`, `username`, `photo_url`, `phone_number`, `auth_date`, `hash`); **HMAC-verifies** it
   against the bot token and checks `auth_date` freshness ([`docs/spec/access.md`](../../spec/access.md)).
   Looks up the client by `telegram_id`: not found → create one (`status = active`) with the Telegram
   profile (auto-registration); found → use it; either way refresh the stored profile from the
   payload. Checks `status` (blocked → `account_blocked`). Creates a session (access 24 h + refresh
   7 d), returns the tokens + the client summary, with `is_new = true` on first registration. Phone
   number is required — if Telegram didn't share it, returns `missing_phone_number`.
2. `refresh-session` / `logout` / `logout-all` (client): standard session ops — refresh re-issues the
   access token and re-checks the client is still active; logout removes the current session; logout-all
   removes all the client's sessions.
3. `get-me` (client): the client's profile (from [`docs/ref/entities/identity/client.md`](../entities/identity/client.md)).
4. `list-my-sessions` / `revoke-my-session` / `revoke-my-sessions` (client): see/end own sessions
   (device, IP, last used, current marker).
5. A client is a **separate entity** from workshop/platform users, with no password, no permissions,
   no workshop binding — [`docs/spec/access.md`](../../spec/access.md).
6. Auth events (login, logout, block) are audited.

## UX

In the **client app**:

- **Sign-in** (`/auth/telegram`) — a centered card: brand mark, short copy ("Sign in to Mebel Pro
  with Telegram"), the embedded Telegram Login Widget (script-injected, bound to the bot username),
  small footer links (privacy / help — placeholders v1). Any unauthenticated visit to a `/c/*` route
  redirects here.
- **Flow:** widget mounts → user authorizes in Telegram → payload posted to `telegram-login` → on
  200, store the tokens, route to the branch picker; on first registration, a one-time "Welcome"
  toast. On `account_blocked` → a blocking card with a support-contact placeholder. On
  `missing_phone_number` → "Allow Telegram to share your phone number, then try again" + a retry
  button. On `invalid_oauth_signature` / `oauth_expired` → a generic error card + retry.
- **Profile** (`/c/profile`) — the Telegram-synced fields read-only (photo, first/last name, phone,
  `@username`, telegram id); a "Refresh from Telegram" button (re-runs sign-in, since the profile
  syncs on each login); a sessions list (device, IP, last used, current marker) with per-row "log
  out" + a global "log out everywhere"; a "log out" button for this device.
- States: widget loading, signing-in (disabled), the error/blocked cards, the welcome toast, sessions
  list loading/empty.
- Accessibility: the sign-in card and error cards are keyboard-operable; the sessions list rows have
  clear labels; the "log out everywhere" action confirms.

Shared patterns (auth card, sessions list, toast): [`docs/ref/ux/components.md`](../ux/components.md).

## Entities touched

- [`docs/ref/entities/identity/client.md`](../entities/identity/client.md) — created on first sign-in; profile refreshed each login.
- [`docs/ref/entities/identity/session.md`](../entities/identity/session.md) — created/refreshed/revoked.
- [`docs/ref/entities/support/action-log.md`](../entities/support/action-log.md) — auth events.

## Edge cases

- **Telegram didn't share the phone** → `missing_phone_number`; re-prompt with phone-sharing on.
- **Stale or forged Telegram payload** → `invalid_oauth_signature` / `oauth_expired`; generic retry.
- **Account blocked** (by a platform operator or — there's no other path for clients in v1)
  → `account_blocked`; the client can't sign in; their open orders are handled by workshop staff.
- **Telegram OAuth unavailable** → the client can't sign in; there is no fallback in v1 ([`docs/spec/access.md`](../../spec/access.md)).
- **Profile changed in Telegram** → reflected on the client's next sign-in (no live sync).
- **6th concurrent session** → the oldest is evicted (5-session cap).

## Out of scope

- A password fallback for clients — not in v1 ([`docs/spec/access.md`](../../spec/access.md)).
- Other OAuth providers / email signup — out.
- Client deletion of their own account — out (a platform operator can block; data is kept).
- A Telegram notification bot — v1.1 ([`docs/spec/open-questions.md`](../../spec/open-questions.md) Q5); Telegram is sign-in only in v1.

## Open questions

- Adding a non-Telegram client auth method — owner: shape — [`docs/spec/open-questions.md`](../../spec/open-questions.md) (revisit trigger: Telegram OAuth unreliability).
