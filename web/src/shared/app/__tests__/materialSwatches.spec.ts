import { describe, expect, it } from 'vitest'

import { materialSwatchClass } from '@/shared/app/materialSwatches'

describe('material swatches', () => {
  it('maps common material colors to readable swatch classes', () => {
    expect(
      materialSwatchClass({
        id: 'mat-white',
        name: 'Alpine White',
        color: 'White',
        decor_code: null,
      }),
    ).toBe('sw-7')
    expect(
      materialSwatchClass({
        id: 'mat-black',
        name: 'Graphite panel',
        color: 'Black',
        decor_code: null,
      }),
    ).toBe('sw-8')
  })

  it('uses a stable non-default fallback for other materials', () => {
    const material = {
      id: 'mat-green',
      name: 'Forest decor',
      color: 'Green',
      decor_code: 'F-220',
    }

    expect(materialSwatchClass(material)).toBe(materialSwatchClass(material))
    expect(materialSwatchClass(material)).toMatch(/^sw-/)
  })
})
