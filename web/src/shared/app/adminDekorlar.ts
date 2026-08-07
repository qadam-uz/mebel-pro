import { dekorTurLabel } from '@/shared/app/materialLabel'
import type { DekorType, DekorWriteRequest } from '@/shared/stores/admin'

/**
 * The admin "Dekorlar" form. Six fields, and no more: a dekor is identity, the
 * format belongs to the branch that carries it. Replaces the old
 * `AdminMaterialFormState`, whose thickness / size / grain fields moved to
 * `BranchMaterial`.
 */
export interface AdminDekorFormState {
  manufacturerId: string
  tur: DekorType
  kod: string
  nomi: string
  tolali: boolean
  imageFileId: string | null
}

export function buildDekorWriteRequest(form: AdminDekorFormState): DekorWriteRequest {
  return {
    manufacturer_id: form.manufacturerId,
    tur: form.tur,
    kod: normalizeText(form.kod) || null,
    nomi: normalizeText(form.nomi),
    tolali: form.tolali,
    image_file_id: form.imageFileId,
  }
}

/**
 * Live preview of the dekor's label, for the create/edit form.
 *
 * This is `material_label()` MINUS the dimension segment — the admin app has no
 * thickness and no size to print, so `… · 2800×2070×18 mm` is unreachable here by
 * construction. What it does reproduce exactly is the identity half: the tur
 * prefix, the manufacturer, `kod || nomi` in the name slot, and the suppression
 * of `nomi` in the detail slot when the base already says it (otherwise a
 * kod-less dekor previews as «Egger Sonoma eman · Sonoma eman»).
 */
export function composeDekorLabel(
  form: AdminDekorFormState,
  manufacturerName: string | null | undefined,
): string {
  const type = dekorTurLabel(form.tur)
  const manufacturer = normalizeText(manufacturerName) || '...'
  const nomi = normalizeText(form.nomi) || '...'
  const kod = normalizeText(form.kod)
  const base = [type, manufacturer, kod || nomi].filter(Boolean).join(' ')
  return nomi && !base.toLowerCase().includes(nomi.toLowerCase()) ? `${base} · ${nomi}` : base
}

function normalizeText(value: string | null | undefined): string {
  return (value ?? '').trim().split(/\s+/).filter(Boolean).join(' ')
}
