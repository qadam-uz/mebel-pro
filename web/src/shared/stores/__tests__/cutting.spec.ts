import { describe, expect, it } from 'vitest'

import { partFitError } from '@/shared/stores/cutting'

// usable area with the default 10mm edge trim on a 2750×1830 panel = 2730 × 1810
const panel = (grain: boolean | null) => ({
  panel_length_mm: 2750,
  panel_width_mm: 1830,
  grain_direction: grain,
})

describe('partFitError (part vs panel usable area)', () => {
  it('accepts parts within the usable area', () => {
    expect(partFitError(2000, 1000, panel(false))).toBeNull()
    expect(partFitError(2730, 1810, panel(false))).toBeNull()
  })

  it('flags oversized parts on a non-grained panel (neither orientation fits)', () => {
    expect(partFitError(3000, 1000, panel(false))).toBe('part_too_large')
    expect(partFitError(2731, 1811, panel(false))).toBe('part_too_large')
  })

  it('allows rotation on non-grained panels', () => {
    // 1810×2730 fits only when rotated — allowed without grain
    expect(partFitError(1810, 2730, panel(false))).toBeNull()
  })

  it('forbids rotation on grained panels', () => {
    // fits the panel only when rotated, but the grain direction is fixed
    expect(partFitError(1000, 2000, panel(true))).toBe('impossible_grain')
    expect(partFitError(2000, 1000, panel(true))).toBeNull()
  })

  it('skips the check when panel size is unknown or values are non-finite', () => {
    expect(
      partFitError(5000, 5000, {
        panel_length_mm: null,
        panel_width_mm: null,
        grain_direction: false,
      }),
    ).toBeNull()
    expect(partFitError(Number.NaN, 1000, panel(false))).toBeNull()
  })
})
