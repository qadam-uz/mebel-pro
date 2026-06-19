import { describe, expect, it } from 'vitest'

import { partFitError, partNotCarried, type CuttingPart } from '@/shared/stores/cutting'

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

describe('partNotCarried (branch-carry recovery detection, CB-124)', () => {
  const makePart = (overrides: Partial<CuttingPart> = {}): CuttingPart => ({
    part_ref: 'p1',
    material_id: 'panel-ok',
    material_source: 'shop',
    length_mm: 100,
    width_mm: 100,
    quantity: 1,
    edge_top: null,
    edge_bottom: null,
    edge_left: null,
    edge_right: null,
    ...overrides,
  })
  const resolvePanel = (id: string | null | undefined) =>
    id === 'panel-ok'
      ? { branch_carried: true }
      : id === 'panel-no'
        ? { branch_carried: false }
        : null
  const resolveEdge = (id: string | null | undefined) =>
    id === 'edge-ok'
      ? { branch_carried: true }
      : id === 'edge-no'
        ? { branch_carried: false }
        : null

  it('returns [] when no branch is chosen', () => {
    expect(
      partNotCarried(makePart({ material_id: 'panel-no' }), null, resolvePanel, resolveEdge),
    ).toEqual([])
  })

  it('flags a shop panel the branch does not carry', () => {
    expect(
      partNotCarried(makePart({ material_id: 'panel-no' }), 'b1', resolvePanel, resolveEdge),
    ).toEqual(['panel'])
  })

  it('does not flag an own-sourced panel even if not carried', () => {
    expect(
      partNotCarried(
        makePart({ material_id: 'panel-no', material_source: 'own' }),
        'b1',
        resolvePanel,
        resolveEdge,
      ),
    ).toEqual([])
  })

  it('flags an uncarried shop edge on a carried panel, by side', () => {
    expect(
      partNotCarried(
        makePart({ edge_top: { material_id: 'edge-no', source: 'shop' } }),
        'b1',
        resolvePanel,
        resolveEdge,
      ),
    ).toEqual(['edge_top'])
  })

  it('does not flag an own-sourced edge', () => {
    expect(
      partNotCarried(
        makePart({ edge_left: { material_id: 'edge-no', source: 'own' } }),
        'b1',
        resolvePanel,
        resolveEdge,
      ),
    ).toEqual([])
  })

  it('returns [] when panel and all edges are carried', () => {
    expect(
      partNotCarried(
        makePart({ edge_top: { material_id: 'edge-ok', source: 'shop' } }),
        'b1',
        resolvePanel,
        resolveEdge,
      ),
    ).toEqual([])
  })
})
