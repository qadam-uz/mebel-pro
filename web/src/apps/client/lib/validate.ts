// Per-part + whole-draft validation, mirroring backend cutting limits so the
// wizard surfaces the same failure codes inline before the optimiser runs.
// Pure functions — unit-tested.

import type { Material } from '../api/types'
import { LIMITS, materialById, type EditablePart } from './cutting'

export type ValidationCode =
  | 'ok'
  | 'no_material'
  | 'material_not_found'
  | 'incomplete'
  | 'part_too_small'
  | 'part_too_large'
  | 'impossible_grain'
  | 'too_many_parts'
  | 'empty'

export interface Validation {
  ok: boolean
  code: ValidationCode
  // i18n key + params, so the component renders Uzbek without baking strings here.
  key?: string
  params?: Record<string, string | number>
  // when a per-part failure is wrapped by the draft gate, the inner message.
  inner?: { key?: string; params?: Record<string, string | number> }
}

const OK: Validation = { ok: true, code: 'ok' }

export function partMaxFor(materials: Material[], materialId: string | null) {
  const m = materialById(materials, materialId)
  if (!m || !m.sheet_length_mm || !m.sheet_width_mm) return null
  return { l: m.sheet_length_mm - 2 * LIMITS.EDGE_TRIM, w: m.sheet_width_mm - 2 * LIMITS.EDGE_TRIM }
}

export function validatePart(p: EditablePart, materials: Material[]): Validation {
  if (!p.materialId) return { ok: false, code: 'no_material', key: 'client.valNoMaterial' }
  const mat = materialById(materials, p.materialId)
  if (!mat || mat.status !== 'active') {
    return { ok: false, code: 'material_not_found', key: 'client.valMaterialNotFound' }
  }
  if (p.l == null || p.w == null || !p.qty) {
    return { ok: false, code: 'incomplete', key: 'client.valIncomplete' }
  }
  if (p.l < LIMITS.PART_MIN || p.w < LIMITS.PART_MIN) {
    return {
      ok: false,
      code: 'part_too_small',
      key: 'client.valTooSmall',
      params: { min: LIMITS.PART_MIN },
    }
  }
  const max = partMaxFor(materials, p.materialId)
  if (!max) return OK
  const fitsAsIs = p.l <= max.l && p.w <= max.w
  const fitsRotated = p.w <= max.l && p.l <= max.w
  if (mat.grain_direction) {
    // grained material can't rotate: the part must fit in its forced orientation.
    if (!fitsAsIs) {
      // if it would have fit rotated, the blocker is the grain lock, not size.
      const code = fitsRotated ? 'impossible_grain' : 'part_too_large'
      return {
        ok: false,
        code,
        key: code === 'impossible_grain' ? 'client.valImpossibleGrain' : 'client.valTooLarge',
        params:
          code === 'impossible_grain'
            ? undefined
            : { l: max.l, w: max.w, mat: mat.name.split('·')[0].trim() },
      }
    }
    return OK
  }
  // non-grained material: free to rotate, so either orientation fitting is fine.
  if (!fitsAsIs && !fitsRotated) {
    return {
      ok: false,
      code: 'part_too_large',
      key: 'client.valTooLarge',
      params: { l: max.l, w: max.w, mat: mat.name.split('·')[0].trim() },
    }
  }
  return OK
}

// Whole-draft gate — first blocking failure or ok.
export function validateDraft(parts: EditablePart[], materials: Material[]): Validation {
  const totalUnits = parts.reduce((a, p) => a + (p.qty || 0), 0)
  if (totalUnits > LIMITS.MAX_PARTS) {
    return {
      ok: false,
      code: 'too_many_parts',
      key: 'client.valTooManyParts',
      params: { max: LIMITS.MAX_PARTS, n: totalUnits },
    }
  }
  const filled = parts.filter((p) => p.materialId || p.l != null || p.w != null)
  if (filled.length === 0) return { ok: false, code: 'empty', key: 'client.valEmpty' }
  for (let i = 0; i < parts.length; i++) {
    const v = validatePart(parts[i], materials)
    if (!v.ok && v.code !== 'incomplete') {
      return {
        ok: false,
        code: v.code,
        key: 'client.valPartPrefix',
        params: { n: i + 1, msg: '' },
        inner: { key: v.key, params: v.params },
      }
    }
  }
  const anyValid = parts.some((p) => validatePart(p, materials).ok)
  if (!anyValid) return { ok: false, code: 'empty', key: 'client.valEmpty' }
  return OK
}

// Map a backend AppError code → a friendly i18n key for the run-failure roll-up.
export const RUN_ERROR_KEYS: Record<string, string> = {
  material_not_found: 'client.valMaterialNotFound',
  part_too_large: 'client.valTooLarge',
  part_too_small: 'client.valTooSmall',
  impossible_grain: 'client.valImpossibleGrain',
  too_many_parts: 'client.valTooManyParts',
  too_many_sheets_needed: 'client.optFailed',
  optimization_timeout: 'client.optFailed',
  validation_error: 'client.valEmpty',
}
