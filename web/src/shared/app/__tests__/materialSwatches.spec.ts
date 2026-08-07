import { describe, expect, it } from 'vitest'

import { materialSwatchClass } from '@/shared/app/materialSwatches'

describe('material swatches', () => {
  it('maps common material colours to readable swatch classes', () => {
    expect(materialSwatchClass({ id: 'dekor-white', nomi: 'Alpine White', kod: null })).toBe('sw-7')
    expect(materialSwatchClass({ id: 'dekor-black', nomi: 'Black graphite', kod: null })).toBe(
      'sw-8',
    )
  })

  it('matches a colour word that lives in the kod', () => {
    expect(materialSwatchClass({ id: 'dekor-oak', nomi: 'Sahara', kod: 'OAK-12' })).toBe('sw-2')
  })

  it('uses a stable non-default fallback for other materials', () => {
    const dekor = { id: 'dekor-green', nomi: 'Forest', kod: 'F-220' }

    expect(materialSwatchClass(dekor)).toBe(materialSwatchClass(dekor))
    expect(materialSwatchClass(dekor)).toMatch(/^sw-/)
  })

  // The hash is seeded with the id, so the SAME dekor must resolve to the same
  // swatch at every branch and across its 16 mm / 18 mm rows. Callers therefore
  // pass `dekor.id`, never a branch-material id — this pins that contract.
  it('is per-dekor, not per-format', () => {
    const dekor = { id: 'dekor-green', nomi: 'Forest', kod: 'F-220' }
    const otherDekor = { ...dekor, id: 'dekor-green-2' }

    expect(materialSwatchClass({ ...dekor })).toBe(materialSwatchClass(dekor))
    expect(materialSwatchClass(otherDekor)).not.toBe('')
  })
})
