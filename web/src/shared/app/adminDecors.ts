import type { DecorWriteRequest } from '@/shared/stores/admin'

/**
 * The admin "Decors" form. Five fields, and no more: a decor is a PATTERN —
 * who makes it, what it is called, what it looks like.
 *
 * `type` left this form with the format reshape. What a decor physically is
 * belongs to `decor_formats`, because one decor is sold as both a board and a
 * matching kromka; asking for a substrate here is what forced the duplicate
 * twin rows the reshape merged away. The substrate is chosen per format, on the
 * decor's own page.
 */
export interface AdminDecorFormState {
  manufacturerId: string
  code: string
  name: string
  has_grain: boolean
  imageFileId: string | null
}

export function buildDecorWriteRequest(form: AdminDecorFormState): DecorWriteRequest {
  return {
    manufacturer_id: form.manufacturerId,
    code: normalizeText(form.code) || null,
    name: normalizeText(form.name),
    has_grain: form.has_grain,
    image_file_id: form.imageFileId,
  }
}

/**
 * Live preview of the decor's label, for the create/edit form.
 *
 * This mirrors `decor_label()` on the server: the manufacturer, `code || name`
 * in the name slot, and the suppression of `name` in the detail slot when the
 * base already says it (otherwise a code-less decor previews as «Egger Sonoma
 * eman · Sonoma eman»). No substrate prefix and no dimensions — a decor has
 * neither; those appear on its formats.
 */
export function composeDecorLabel(
  form: AdminDecorFormState,
  manufacturerName: string | null | undefined,
): string {
  const manufacturer = normalizeText(manufacturerName) || '...'
  const name = normalizeText(form.name) || '...'
  const code = normalizeText(form.code)
  const base = [manufacturer, code || name].filter(Boolean).join(' ')
  return name && !base.toLowerCase().includes(name.toLowerCase()) ? `${base} · ${name}` : base
}

function normalizeText(value: string | null | undefined): string {
  return (value ?? '').trim().split(/\s+/).filter(Boolean).join(' ')
}
