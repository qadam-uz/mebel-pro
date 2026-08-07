import { describe, expect, it } from 'vitest'

import { hasOwnMaterial, ownMaterialRows } from '@/shared/app/ownMaterial'
import type { OrderPriceLine } from '@/shared/stores/orders'

function panel(overrides: Partial<OrderPriceLine> = {}): OrderPriceLine {
  return {
    material_id: 'panel-a',
    material_name: 'LDSP Egger H1334 · 2750×1830×18 mm',
    kind: 'panel',
    panels_used: 3,
    consumed_mm: null,
    unit_price_tiyin: 30_000_000,
    own_panels: 0,
    own_mm: 0,
    line_total_tiyin: 90_000_000,
    ...overrides,
  }
}

function edge(overrides: Partial<OrderPriceLine> = {}): OrderPriceLine {
  return {
    material_id: 'edge-a',
    material_name: 'ABS H1334 · 0.4×19',
    kind: 'edge',
    panels_used: null,
    consumed_mm: 8000,
    unit_price_tiyin: 500_000,
    own_panels: 0,
    own_mm: 0,
    line_total_tiyin: 4_000_000,
    ...overrides,
  }
}

describe('ownMaterialRows', () => {
  it('lists nothing for an order the workshop supplies entirely', () => {
    expect(ownMaterialRows([panel(), edge()])).toEqual([])
    expect(hasOwnMaterial([panel(), edge()])).toBe(false)
  })

  it('names each material and the amount in its own unit', () => {
    const rows = ownMaterialRows([panel({ own_panels: 2 }), edge({ own_mm: 13_500 })])

    expect(rows).toHaveLength(2)
    expect(rows[0]).toMatchObject({ materialId: 'panel-a', amount: '2 list' })
    // Tape is metres, not sheets — the client brings a roll, not a stack.
    expect(rows[1]).toMatchObject({ materialId: 'edge-a', amount: '13.50 m' })
  })

  it('still lists a material the client supplies every sheet of', () => {
    // The charged count is 0 and the line total is 0, which is exactly the case
    // that reads as "free" unless the own count is surfaced separately.
    const rows = ownMaterialRows([panel({ panels_used: 0, own_panels: 4, line_total_tiyin: 0 })])

    expect(rows).toHaveLength(1)
    expect(rows[0]?.amount).toBe('4 list')
  })

  it('skips a line whose own share is zero even when the order has others', () => {
    const rows = ownMaterialRows([
      panel({ material_id: 'panel-a', own_panels: 0 }),
      panel({ material_id: 'panel-b', own_panels: 1 }),
    ])

    expect(rows.map((row) => row.materialId)).toEqual(['panel-b'])
  })

  it('treats a missing or negative own share as nothing owed', () => {
    // Defensive: the field is required on the wire, but a stale cached order
    // from before it existed must not render "undefined list".
    const stale = { ...panel(), own_panels: undefined } as unknown as OrderPriceLine
    expect(ownMaterialRows([stale])).toEqual([])
    expect(ownMaterialRows([panel({ own_panels: -1 })])).toEqual([])
  })
})
