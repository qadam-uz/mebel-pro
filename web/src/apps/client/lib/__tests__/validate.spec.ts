import { describe, expect, it } from 'vitest'
import { partMaxFor, validateDraft, validatePart } from '../validate'
import type { EditablePart } from '../cutting'
import type { Material } from '../../api/types'

const sheet = (over: Partial<Material> = {}): Material => ({
  id: 'm1',
  kind: 'sheet',
  type: null,
  name: 'DSP 18mm Bel · 2800×2070',
  thickness_mm: 18,
  color: 'Bel',
  decor_code: null,
  sheet_length_mm: 2800,
  sheet_width_mm: 2070,
  grain_direction: false,
  image_file_id: null,
  status: 'active',
  created_at: '',
  updated_at: '',
  ...over,
})

const part = (over: Partial<EditablePart> = {}): EditablePart => ({
  ref: 'p1',
  materialId: 'm1',
  source: 'shop',
  l: 600,
  w: 400,
  qty: 2,
  edges: { t: null, b: null, l: null, r: null },
  ...over,
})

describe('partMaxFor', () => {
  it('subtracts 2x edge trim from the sheet dims', () => {
    expect(partMaxFor([sheet()], 'm1')).toEqual({ l: 2780, w: 2050 })
  })
  it('returns null for an unknown material', () => {
    expect(partMaxFor([sheet()], 'nope')).toBeNull()
  })
})

describe('validatePart', () => {
  const mats = [sheet()]

  it('passes a valid part', () => {
    expect(validatePart(part(), mats).ok).toBe(true)
  })

  it('flags a missing material', () => {
    expect(validatePart(part({ materialId: null }), mats).code).toBe('no_material')
  })

  it('flags a removed/missing catalog material', () => {
    expect(validatePart(part({ materialId: 'gone' }), mats).code).toBe('material_not_found')
  })

  it('flags incomplete dims', () => {
    expect(validatePart(part({ l: null }), mats).code).toBe('incomplete')
  })

  it('flags parts below the 50×50 minimum (inclusive bound passes)', () => {
    expect(validatePart(part({ l: 49, w: 600 }), mats).code).toBe('part_too_small')
    expect(validatePart(part({ l: 50, w: 50 }), mats).ok).toBe(true)
  })

  it('flags parts over the sheet-minus-trim maximum', () => {
    expect(validatePart(part({ l: 2800, w: 400 }), mats).code).toBe('part_too_large')
    expect(validatePart(part({ l: 2780, w: 2050 }), mats).ok).toBe(true)
  })

  it('flags impossible grain — a part that would fit rotated but not as-is', () => {
    const grained = [sheet({ grain_direction: true })]
    // max = { l: 2780, w: 2050 }. l=400,w=2700 fits rotated but not as-is.
    expect(validatePart(part({ l: 400, w: 2700 }), grained).code).toBe('impossible_grain')
    // the same part on a non-grained material is fine (rotation allowed).
    expect(validatePart(part({ l: 400, w: 2700 }), [sheet()]).ok).toBe(true)
  })
})

describe('validateDraft', () => {
  const mats = [sheet()]

  it('rejects an over-100 total quantity', () => {
    const v = validateDraft([part({ qty: 101 })], mats)
    expect(v.code).toBe('too_many_parts')
  })

  it('rejects an entirely empty draft', () => {
    const v = validateDraft([part({ materialId: null, l: null, w: null })], mats)
    expect(v.code).toBe('empty')
  })

  it('wraps a per-part failure with the row index + inner message', () => {
    const v = validateDraft([part(), part({ l: 49 })], mats)
    expect(v.ok).toBe(false)
    expect(v.code).toBe('part_too_small')
    expect(v.params?.n).toBe(2)
    expect(v.inner?.key).toBe('client.valTooSmall')
  })

  it('passes when at least one part is valid and none blocks', () => {
    expect(validateDraft([part()], mats).ok).toBe(true)
  })
})
