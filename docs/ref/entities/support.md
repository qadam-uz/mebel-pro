---
title: Support
status: draft
owner: shape
updated: 2026-05-17
order: 60
---

# Support

The cross-cutting entities: file blobs (MinIO/S3), in-app notifications, and the two halves of
the audit log (action log + status change log). Wired into every other module by id.

## File

A stored blob in object storage with its metadata, optionally attached to another entity: a
material's sample image, a workshop's logo, a payment/refund/delivery receipt scan, a generated
cutting-map PDF. The `files` module owns the blob + metadata; other modules attach/detach by id
and never touch object storage directly.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `storage_key` | text | the object-storage key; unique |
| `original_name` | text | uploaded filename |
| `content_type` | text | MIME type; validated against the allowed set for the attach context |
| `size_bytes` | bigint | ≤ configured max (default 10 MB) |
| `storage_status` | enum | `pending` / `stored` / `deleted` |
| `entity_type` | text? | what it's attached to (`material` / `workshop` / `income` / `cutting_result` / `expense` / …) |
| `entity_id` | UUID? | the attached entity's id |
| `sort_order` | int? | ordering when an entity has several files |
| `uploaded_by_type` / `uploaded_by_id` | enum / UUID | the principal who uploaded it |
| `created_at` / `updated_at` | timestamp | |

Lifecycle: `pending` (record created, upload in progress) → `stored` → `deleted` (soft — the
metadata row is kept; the blob may be garbage-collected later). Detaching from an entity clears
`entity_type`/`entity_id`; replacing an entity's file is an atomic detach-old + attach-new.

Invariants: size and content-type bounds enforced per attach context; a mutating attach/replace
borrows the caller's DB transaction; other modules reference files only by `id`; download access
is scope-checked the same way as the referencing entity.

## Notification

One in-app inbox item for one principal. Produced by the module where the event happened
(`orders` / `inventory` / `identity` / `workshop` / `platform`), fanned out to the right
recipients, polled by the front-end apps. v1's only notification channel.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `recipient_type` | enum | `platform_user` / `workshop_user` / `client` |
| `recipient_id` | UUID | the principal |
| `event_code` | text | e.g. `order.status_changed`, `warehouse.low_stock`, `workshop.blocked` |
| `entity_type` | text? | the subject entity type (`order` / `stock_item` / `branch` / …) |
| `entity_id` | UUID? | the subject entity's id (for the deep link) |
| `payload` | json | small denormalized fields needed to render without extra lookups |
| `created_at` | timestamp | |
| `read_at` | timestamp? | when the recipient marked it read; null = unread |

Lifecycle: `unread` (`read_at` null) → `read` (set via `mark-read` / `read-all`). Not deleted in
v1 (no purge job). Invariants: one row per recipient per event; a recipient sees only their own
notifications, with the producing module's scope rules applied; the unread count (badge) is the
count of `read_at IS NULL` rows for the principal; `payload` stays small (full data lives on
the linked entity).

## Action log

One row per mutating action anyone took anywhere in the system — who did what, when, to which
entity, with the relevant context (and before/after values where they matter). The "who did
what" half of the audit log. Append-only.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `actor_type` | enum | `platform_user` / `workshop_user` / `client` / `system` |
| `actor_user_id` / `actor_client_id` | UUID? / UUID? | mutually exclusive (or both null if `system`) |
| `workshop_id` / `branch_id` | UUID? / UUID? | for scoping the viewer; null for client-only / platform-only actions |
| `action` | text | a stable action code, e.g. `material.created`, `order.discount_applied`, `workshop.blocked`, `user.password_reset` |
| `entity_type` / `entity_id` | text? / UUID? | the affected entity |
| `summary` | text? | short human description |
| `details` | json? | context / before-after (sensitive fields masked) |
| `trace_id` | text | the request trace id |
| `created_at` | timestamp | |

Invariants: every mutating use case writes exactly one row, in the same atomic operation as the
change; never updated or deleted; sensitive values (passwords, full payment credentials) masked
in `details`; scoping — a workshop owner/staff sees only rows for their workshop (and granted
branches); a platform operator sees all.

## Status change log

One row per state transition of any entity that has a status — primarily orders (mirroring each
[order status event](sales.md#order-status-event)), but also branches, materials, workers,
workshops, users, refunds going `active`/`blocked`/`inactive`/`completed`/etc. The "what changed
state" half of the audit log. Append-only.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `entity_type` | text | `order` / `branch` / `material` / `workshop` / `workshop_user` / `client` / `income` / `expense` / … |
| `entity_id` | UUID | the entity's id |
| `workshop_id` / `branch_id` | UUID? / UUID? | for scoping the viewer |
| `from_status` | text? | null for the first |
| `to_status` | text | required |
| `actor_type` | enum | `platform_user` / `workshop_user` / `client` / `system` |
| `actor_user_id` / `actor_client_id` | UUID? / UUID? | mutually exclusive |
| `reason` | text? | when the transition requires one |
| `action_log_id` | UUID? | the action-log row this transition belongs to (when part of a user action) |
| `changed_at` | timestamp | |

Invariants: every status transition of an audited entity writes exactly one row in the same
atomic operation; for orders, this row corresponds 1:1 with an `order_status_event`; never
updated or deleted; same scoping as the action log.
