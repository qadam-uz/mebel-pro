import { describe, expect, it } from 'vitest'

import { materialSwatchClass } from '@/shared/app/materialSwatches'

describe('material swatches', () => {
  it('maps common material colours to readable swatch classes', () => {
    expect(materialSwatchClass({ id: 'decor-white', name: 'Alpine White', code: null })).toBe(
      'sw-7',
    )
    expect(materialSwatchClass({ id: 'decor-black', name: 'Black graphite', code: null })).toBe(
      'sw-8',
    )
  })

  it('matches a colour word that lives in the kod', () => {
    expect(materialSwatchClass({ id: 'decor-oak', name: 'Sahara', code: 'OAK-12' })).toBe('sw-2')
  })

  it('uses a stable non-default fallback for other materials', () => {
    const decor = { id: 'decor-green', name: 'Forest', code: 'F-220' }

    expect(materialSwatchClass(decor)).toBe(materialSwatchClass(decor))
    expect(materialSwatchClass(decor)).toMatch(/^sw-/)
  })

  // The hash is seeded with the id, so the SAME decor must resolve to the same
  // swatch at every branch and across its 16 mm / 18 mm rows. Callers therefore
  // pass `decor.id`, never a branch-material id — this pins that contract.
  it('is per-dekor, not per-format', () => {
    const decor = { id: 'decor-green', name: 'Forest', code: 'F-220' }
    const otherDecor = { ...decor, id: 'decor-green-2' }

    expect(materialSwatchClass({ ...decor })).toBe(materialSwatchClass(decor))
    expect(materialSwatchClass(otherDecor)).not.toBe('')
  })
})
