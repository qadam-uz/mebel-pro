---
title: File
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/spec/architecture.md
  - docs/ref/entities/catalog/material.md
  - docs/ref/entities/workshop/workshop.md
  - docs/ref/entities/sales/order-payment.md
---

# File

## What it is

A stored blob in object storage (MinIO/S3) with its metadata, optionally attached to another entity:
a material's sample image, a workshop's logo, a payment/refund/delivery receipt scan, a generated
cutting-map PDF. The `files` module owns the blob + metadata; other modules attach/detach by id and
never touch object storage directly.

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `storage_key` | text | the object-storage key | unique |
| `original_name` | text | the uploaded filename | |
| `content_type` | text | MIME type | validated against the allowed set for the attach context |
| `size_bytes` | bigint | | ≤ the configured max (default 10 MB) |
| `storage_status` | enum | `pending` / `stored` / `deleted` | `stored` once the upload to object storage completed |
| `entity_type` | text? | what it's attached to (`material` / `workshop` / `order_payment` / `order_refund` / `cutting_result` / …) | null if unattached |
| `entity_id` | UUID? | the attached entity's id | null if unattached |
| `sort_order` | int? | ordering when an entity has several files | |
| `uploaded_by_type` / `uploaded_by_id` | enum / UUID | the principal who uploaded it | |
| `created_at` / `updated_at` | timestamp | | |

## States / lifecycle

`pending` (record created, upload in progress) → `stored` (upload done) → `deleted` (soft — the
metadata row is kept; the blob may be garbage-collected later). Detaching from an entity clears
`entity_type`/`entity_id`; replacing an entity's file (e.g. a material image) is an atomic
detach-old + attach-new.

## Invariants

- `size_bytes ≤ max_file_size`; `content_type ∈` the allowed set for the attach context — service rules.
- A mutating attach/replace borrows the caller's DB transaction so the file and the referencing
  entity commit together (or both roll back) — service rule.
- Other modules reference files only by `id` — invariant.
- Download access is scope-checked the same way as the referencing entity (a refund receipt is
  visible to the staff/owner who can see the refund) — service rule.

## Relationships

- attached to (logical, by `entity_type`+`entity_id`) → [`docs/ref/entities/catalog/material.md`](../catalog/material.md), [`docs/ref/entities/workshop/workshop.md`](../workshop/workshop.md), [`docs/ref/entities/sales/order-payment.md`](../sales/order-payment.md), [`docs/ref/entities/sales/order-refund.md`](../sales/order-refund.md), [`docs/ref/entities/cutting/cutting-result.md`](../cutting/cutting-result.md)

## Owner

The `files` module; topology in [`docs/spec/architecture.md`](../../../spec/architecture.md). Presigned-URL delivery is [`docs/spec/open-questions.md`](../../../spec/open-questions.md) Q10.
