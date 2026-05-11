---
title: Client
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/spec/domain-model.md
  - docs/spec/access.md
  - docs/ref/entities/identity/session.md
  - docs/ref/entities/sales/order.md
  - docs/ref/features/client-onboarding.md
---

# Client

## What it is

The customer — a person or small business that orders panels cut to size. A **separate entity** from
workshop/platform users ([`docs/spec/access.md`](../../../spec/access.md)). Authenticates via **Telegram OAuth only** — no login, no password; self-registers on the first OAuth handshake. Global to the platform: bound to no workshop or branch; picks a branch per order. Uses the **client app**.

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `telegram_id` | bigint | Telegram account id | unique; required |
| `telegram_username` | text? | `@username` from Telegram | may be null (not all accounts have one) |
| `phone` | text | `+998XXXXXXXXX` — primary human identifier | required (Telegram must share it) |
| `first_name` | text | from Telegram | required |
| `last_name` | text? | from Telegram | |
| `photo_url` | text? | Telegram avatar url | |
| `status` | enum | `active` / `blocked` | default `active` |
| `created_at` / `updated_at` | timestamp | | |
| `last_login_at` | timestamp? | | refreshed on each OAuth login |

The Telegram profile fields are **refreshed from the OAuth payload on every login** — Telegram is the
source of truth for them.

## States / lifecycle

`active` ↔ `blocked` (soft delete only — orders and history are preserved). No password, so no
forced-change / lockout machinery — auth integrity is the Telegram HMAC check ([`docs/spec/access.md`](../../../spec/access.md)).

## Invariants

- `telegram_id` unique — DB constraint.
- A client cannot exist without a verified Telegram identity and a shared phone number — service rule (registration is rejected otherwise: `missing_phone_number`).
- A blocked client cannot log in; blocking deletes its sessions; its open orders are handled by workshop staff per the order rules — service rule.
- A client is never tied to a workshop or branch in the data model — invariant.

## Relationships

- has many → [`docs/ref/entities/identity/session.md`](session.md)
- places → [`docs/ref/entities/sales/order.md`](../sales/order.md) (one-to-many; the client owns its orders)
- creates → [`docs/ref/entities/cutting/cutting-result.md`](../cutting/cutting-result.md) (drafts; one-to-many)
- receives → [`docs/ref/entities/support/notification.md`](../support/notification.md)

## Owner

[`docs/ref/features/client-onboarding.md`](../../features/client-onboarding.md) owns registration & profile; [`docs/spec/access.md`](../../../spec/access.md) the auth posture; [`docs/spec/access.md`](../../../spec/access.md) the (no-)tenancy rules.
