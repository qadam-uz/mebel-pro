---
title: Support
status: draft
owner: shape
updated: 2026-05-17
order: 60
---

# Support

Cross-cutting entity'lar: file blob'lar (MinIO/S3), in-app notification'lar va audit log'ning
ikki yarmi (action log + status change log). Har bir boshqa module'ga id orqali ulangan.

## File

Object storage'dagi saqlangan blob va uning metadata'si, ixtiyoriy ravishda boshqa
entity'ga attach qilinadi: material'ning sample image'i, workshop'ning logo'si,
payment/refund/delivery receipt scan'i, generate qilingan cutting-map PDF. `files` module
blob + metadata'ni egallaydi; boshqa module'lar id orqali attach/detach qiladi va hech
qachon object storage'ga toʻgʻridan-toʻgʻri tegmaydi.

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

Lifecycle: `pending` (record yaratilgan, upload jarayonda) → `stored` → `deleted` (soft —
metadata row saqlanadi; blob keyinroq garbage-collect qilinishi mumkin). Entity'dan detach
qilish `entity_type`/`entity_id`'ni clear qiladi; entity'ning file'ini almashtirish atomic
detach-old + attach-new.

Invariant'lar: size va content-type bound'lar har bir attach context boʻyicha enforce
qilinadi; mutating attach/replace caller'ning DB transaction'ini qarz oladi; boshqa
module'lar file'larga faqat `id` orqali reference qiladi; download access referencing
entity bilan bir xil tarzda scope-check qilinadi.

## Notification

Bitta principal uchun bitta in-app inbox item. Event sodir boʻlgan module
(`orders` / `inventory` / `identity` / `workshop` / `platform`) tomonidan produce
qilinadi, toʻgʻri recipient'larga fan-out qilinadi, front-end app'lar tomonidan poll
qilinadi. v1'ning yagona notification channel'i.

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

Lifecycle: `unread` (`read_at` null) → `read` (`mark-read` / `read-all` orqali set
qilinadi). v1'da delete qilinmaydi (purge job yoʻq). Invariant'lar: har bir recipient
uchun har bir event boʻyicha bitta row; recipient faqat oʻzining notification'larini
koʻradi, produce qilayotgan module'ning scope rule'lari qoʻllanilgan holda; unread count
(badge) principal uchun `read_at IS NULL` row'lar soni; `payload` kichik qoladi (full data
linked entity'da yotadi).

## Action log

System'da har qanday joyda kimdir qilgan har bir mutating action uchun bitta row — kim nima
qildi, qachon, qaysi entity'ga, tegishli context bilan (va muhim boʻlganda before/after
qiymatlar). Audit log'ning "kim nima qildi" yarmi. Append-only.

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

Invariant'lar: har bir mutating use case oʻzgarish bilan bir xil atomic operation'da aniq
bitta row yozadi; hech qachon update yoki delete qilinmaydi; sensitive qiymatlar (password,
full payment credential) `details`'da mask qilinadi; scoping — workshop owner/staff faqat
oʻz workshop'i (va granted branch'lar) uchun row'larni koʻradi; platform operator hammasini
koʻradi.

## Status change log

Status'i boʻlgan har qanday entity'ning har bir state transition'i uchun bitta row —
asosan order'lar (har bir [order status event](sales.md#order-status-event)'ni mirror
qiladi), shuningdek branch'lar, material'lar, worker'lar, workshop'lar, user'lar, refund'lar
`active`/`blocked`/`inactive`/`completed`/va h.k.'ga ketishi. Audit log'ning "nima state
oʻzgardi" yarmi. Append-only.

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

Invariant'lar: audited entity'ning har bir status transition'i bir xil atomic
operation'da aniq bitta row yozadi; order'lar uchun bu row `order_status_event` bilan 1:1
mos keladi; hech qachon update yoki delete qilinmaydi; action log bilan bir xil scoping.
