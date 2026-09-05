import { describe, expect, it } from 'vitest'

import {
  autoTapeDecorForPanel,
  decorIdentityKey,
  foreignTapeIds,
  groupBandedTapeIds,
  groupsMissingTape,
  groupTapeDecors,
  nearestVariant,
  preferredVariant,
  reResolveGroupTape,
  resolveGroupTape,
  tapeThicknessList,
  thicknessColorVar,
} from '@/shared/app/cuttingGroupTape'
import type { ClientCatalogMaterialOption, CuttingPart } from '@/shared/stores/cutting'

function material(
  overrides: Partial<ClientCatalogMaterialOption> = {},
): ClientCatalogMaterialOption {
  return {
    id: overrides.id ?? `mat-${Math.random()}`,
    type: 'ldsp',
    manufacturer_id: 'egger',
    manufacturer_name: 'Egger',
    code: 'H1145',
    name: 'Dub Bardolino',
    has_grain: true,
    image_file_id: null,
    thickness_mm: '18',
    length_mm: 2800,
    width_mm: 2070,
    tape_width_mm: null,
    price_tiyin: 100_000,
    price_unset: false,
    display_unit: 'list',
    ...overrides,
  }
}

function tape(overrides: Partial<ClientCatalogMaterialOption> = {}): ClientCatalogMaterialOption {
  return material({
    type: 'kromka',
    length_mm: null,
    width_mm: null,
    tape_width_mm: 22,
    thickness_mm: '2',
    ...overrides,
  })
}

function part(overrides: Partial<CuttingPart> = {}): CuttingPart {
  return {
    part_ref: overrides.part_ref ?? `part-${Math.random()}`,
    name: null,
    material_id: 'panel-1',
    material_source: 'shop',
    follow_grain: true,
    thickened: false,
    length_mm: 700,
    width_mm: 400,
    quantity: 1,
    edge_top: null,
    edge_bottom: null,
    edge_left: null,
    edge_right: null,
    ...overrides,
  }
}

// The fixture branch: one decor in three thicknesses, one in two, one in one.
const eggerThin = tape({ id: 'tape-egger-04', thickness_mm: '0.4', price_tiyin: 130_000 })
const eggerMid = tape({ id: 'tape-egger-1', thickness_mm: '1', price_tiyin: 190_000 })
const eggerThick = tape({ id: 'tape-egger-2', thickness_mm: '2', price_tiyin: 260_000 })
const kronoThin = tape({
  id: 'tape-krono-04',
  manufacturer_id: 'kronospan',
  manufacturer_name: 'Kronospan',
  code: 'U963',
  name: 'Antrasit',
  thickness_mm: '0.4',
})
const kronoThick = tape({
  id: 'tape-krono-2',
  manufacturer_id: 'kronospan',
  manufacturer_name: 'Kronospan',
  code: 'U963',
  name: 'Antrasit',
  thickness_mm: '2',
})
const kashmir = tape({ id: 'tape-kashmir-2', code: 'U702', name: 'Kashmir', thickness_mm: '2' })

const branchTapes = [eggerThick, eggerThin, kronoThick, kronoThin, kashmir, eggerMid]

const eggerBoard = material({ id: 'panel-1', code: 'H1145', name: 'Dub Bardolino' })
const kronoBoard = material({
  id: 'panel-2',
  manufacturer_id: 'kronospan',
  manufacturer_name: 'Kronospan',
  code: 'U963',
  name: 'Antrasit',
})
const orphanBoard = material({ id: 'panel-3', code: 'W980', name: 'Platinum oq' })

describe('groupTapeDecors', () => {
  it('folds the branch tape list into one row per decor, thickness ascending', () => {
    const decors = groupTapeDecors(branchTapes)
    expect(decors.map((decor) => decor.key)).toEqual([
      decorIdentityKey(eggerThick),
      decorIdentityKey(kronoThick),
      decorIdentityKey(kashmir),
    ])
    const egger = decors[0]
    expect(egger.variants.map((variant) => variant.thicknessMm)).toEqual([0.4, 1, 2])
    expect(tapeThicknessList(egger)).toBe('0.4 / 1 / 2')
    expect(tapeThicknessList(decors[2])).toBe('2')
  })

  it('keeps a decor picture found on any one of its thickness rows', () => {
    const decors = groupTapeDecors([
      tape({ id: 'a', thickness_mm: '0.4', image_file_id: null }),
      tape({ id: 'b', thickness_mm: '2', image_file_id: 'file-9' }),
    ])
    expect(decors).toHaveLength(1)
    expect(decors[0].imageFileId).toBe('file-9')
  })
})

describe('autoTapeDecorForPanel', () => {
  const decors = groupTapeDecors(branchTapes)

  it('attaches the branch tape carrying the board decor', () => {
    expect(autoTapeDecorForPanel(eggerBoard, decors)?.key).toBe(decorIdentityKey(eggerThick))
    expect(autoTapeDecorForPanel(kronoBoard, decors)?.key).toBe(decorIdentityKey(kronoThick))
  })

  it('falls back to a decor-name match across manufacturers', () => {
    const board = material({ manufacturer_id: 'other', code: 'ZZ1', name: 'Kashmir' })
    expect(autoTapeDecorForPanel(board, decors)?.key).toBe(decorIdentityKey(kashmir))
  })

  it('attaches nothing when the branch stocks no matching colour', () => {
    expect(autoTapeDecorForPanel(orphanBoard, decors)).toBeNull()
    expect(autoTapeDecorForPanel(null, decors)).toBeNull()
  })
})

describe('resolveGroupTape', () => {
  const decors = groupTapeDecors(branchTapes)

  it('prefers the pick made in the editor', () => {
    const resolved = resolveGroupTape({
      panel: eggerBoard,
      groupParts: [part()],
      decors,
      pickedKey: decorIdentityKey(kashmir),
    })
    expect(resolved.source).toBe('picked')
    expect(resolved.decor?.key).toBe(decorIdentityKey(kashmir))
  })

  it('keeps what a resumed draft is already banded with over the auto-match', () => {
    const resolved = resolveGroupTape({
      panel: eggerBoard,
      groupParts: [part({ edge_top: { material_id: kronoThick.id, source: 'shop' } })],
      decors,
    })
    expect(resolved.source).toBe('sides')
    expect(resolved.decor?.key).toBe(decorIdentityKey(kronoThick))
  })

  it('auto-attaches the board decor when nothing is banded yet', () => {
    const resolved = resolveGroupTape({ panel: eggerBoard, groupParts: [part()], decors })
    expect(resolved.source).toBe('auto')
    expect(resolved.decor?.key).toBe(decorIdentityKey(eggerThick))
  })

  it('resolves to nothing for a decor the branch has no tape for', () => {
    expect(resolveGroupTape({ panel: orphanBoard, groupParts: [part()], decors })).toEqual({
      decor: null,
      source: null,
    })
  })

  it('ignores a banded tape that has left the catalog and falls through', () => {
    const resolved = resolveGroupTape({
      panel: eggerBoard,
      groupParts: [part({ edge_top: { material_id: 'tape-retired', source: 'shop' } })],
      decors,
    })
    expect(resolved.source).toBe('auto')
  })
})

describe('thickness chips', () => {
  const decors = groupTapeDecors(branchTapes)
  const egger = decors[0]
  const krono = decors[1]

  it('offers exactly the thicknesses the decor is carried in', () => {
    expect(egger.variants.map((variant) => variant.thicknessMm)).toEqual([0.4, 1, 2])
    expect(krono.variants.map((variant) => variant.thicknessMm)).toEqual([0.4, 2])
  })

  it('pre-selects the last thickness used, else the thickest', () => {
    expect(preferredVariant(egger, 1)?.material.id).toBe(eggerMid.id)
    expect(preferredVariant(egger, null)?.material.id).toBe(eggerThick.id)
    // 1 mm is not stocked in this decor, so the thickest stands in.
    expect(preferredVariant(krono, 1)?.material.id).toBe(kronoThick.id)
  })

  it('picks the nearest thickness, thinner on a tie', () => {
    expect(nearestVariant(krono, 1)?.material.id).toBe(kronoThin.id)
    expect(nearestVariant(krono, 0.4)?.material.id).toBe(kronoThin.id)
    expect(nearestVariant(krono, 5)?.material.id).toBe(kronoThick.id)
  })

  it('colours 0.4 / 1 / 2 mm apart with the tur ramp', () => {
    expect(thicknessColorVar(0.4)).toBe('var(--color-tur-board)')
    expect(thicknessColorVar(1)).toBe('var(--color-tur-mdf)')
    expect(thicknessColorVar(2)).toBe('var(--color-tur-tape)')
  })
})

describe('reResolveGroupTape', () => {
  const decors = groupTapeDecors(branchTapes)
  const egger = decors[0]
  const krono = decors[1]
  const thicknessById = (id: string) =>
    branchTapes.find((item) => item.id === id)
      ? Number(branchTapes.find((item) => item.id === id)!.thickness_mm)
      : null

  it('re-points every banded side of the group and leaves other groups alone', () => {
    const parts = [
      part({
        part_ref: 'a',
        edge_top: { material_id: kronoThick.id, source: 'shop' },
        edge_bottom: { material_id: kronoThin.id, source: 'shop' },
      }),
      part({ part_ref: 'b', material_id: 'panel-2', edge_top: { material_id: kronoThick.id, source: 'shop' } }),
    ]
    const outcome = reResolveGroupTape({
      parts,
      groupMaterialId: 'panel-1',
      decor: egger,
      thicknessById,
    })
    expect(outcome.changed).toBe(true)
    expect(outcome.fellBack).toBe(false)
    expect(outcome.parts[0].edge_top?.material_id).toBe(eggerThick.id)
    expect(outcome.parts[0].edge_bottom?.material_id).toBe(eggerThin.id)
    // Untouched group keeps its band — and its object identity.
    expect(outcome.parts[1]).toBe(parts[1])
  })

  it('falls back to the nearest thickness the new decor carries and says so', () => {
    const parts = [part({ edge_left: { material_id: eggerMid.id, source: 'shop' } })]
    const outcome = reResolveGroupTape({
      parts,
      groupMaterialId: 'panel-1',
      decor: krono,
      thicknessById,
    })
    expect(outcome.fellBack).toBe(true)
    expect(outcome.parts[0].edge_left?.material_id).toBe(kronoThin.id)
  })

  it('leaves bare sides bare', () => {
    const parts = [part()]
    const outcome = reResolveGroupTape({
      parts,
      groupMaterialId: 'panel-1',
      decor: egger,
      thicknessById,
    })
    expect(outcome.changed).toBe(false)
    expect(outcome.parts[0].edge_top).toBeNull()
  })
})

describe('the gate', () => {
  const decors = groupTapeDecors(branchTapes)

  it('names a group that bands a side with no tape decor, and only that group', () => {
    const banded = part({ material_id: 'panel-3', edge_top: { material_id: 'x', source: 'shop' } })
    const bare = part({ material_id: 'panel-4' })
    const groups = [
      { key: 'g-orphan', materialId: 'panel-3', parts: [banded] },
      { key: 'g-bare', materialId: 'panel-4', parts: [bare] },
      { key: 'g-ok', materialId: 'panel-1', parts: [part()] },
    ]
    const missing = groupsMissingTape(
      groups,
      (group) => group.parts,
      (group) =>
        resolveGroupTape({
          panel: group.materialId === 'panel-1' ? eggerBoard : orphanBoard,
          groupParts: group.parts,
          decors,
        }).decor,
    )
    expect(missing.map((group) => group.key)).toEqual(['g-orphan'])
  })
})

describe('legacy bands', () => {
  const decors = groupTapeDecors(branchTapes)

  it('lists the tapes on the group that are outside its decor', () => {
    const parts = [
      part({
        edge_top: { material_id: eggerThick.id, source: 'shop' },
        edge_bottom: { material_id: kronoThin.id, source: 'shop' },
      }),
    ]
    expect(groupBandedTapeIds(parts)).toEqual([eggerThick.id, kronoThin.id])
    expect(foreignTapeIds(parts, decors[0])).toEqual([kronoThin.id])
    expect(foreignTapeIds(parts, null)).toEqual([eggerThick.id, kronoThin.id])
  })
})
