import { describe, expect, it } from 'vitest'

import {
  buildBillRows,
  buildPartRows,
  billRowsTotal,
  canPlaceBlocker,
  canPlaceBlockerLabel,
  fieldDiffersFromProfile,
} from '@/shared/app/clientOrderReview'
import type { CuttingPart } from '@/shared/stores/cutting'
import type { OrderQuote } from '@/shared/stores/orders'

function part(overrides: Partial<CuttingPart> = {}): CuttingPart {
  return {
    part_ref: 'part-a',
    name: null,
    material_id: 'panel-a',
    material_source: 'shop',
    follow_grain: true,
    length_mm: 600,
    width_mm: 400,
    quantity: 2,
    edge_top: null,
    edge_bottom: null,
    edge_left: null,
    edge_right: null,
    ...overrides,
  }
}

// A realistic quote fixture: two panel materials, one edge material — the
// shape the backend actually returns (sales/service.py:_price_result), where
// subtotal_cutting = panels_used × cutting_rate and every line total sums
// exactly to total_tiyin (no rounding remainder).
function quote(overrides: Partial<OrderQuote> = {}): OrderQuote {
  return {
    draft_id: 'draft-a',
    branch_id: 'branch-a',
    branch_name: 'Chilonzor filiali',
    branch_address: 'Bunyodkor 12',
    branch_phone: '+998901112233',
    subtotal_cutting_tiyin: 5 * 45_000_00,
    subtotal_materials_tiyin: 3 * 250_000_00 + 2 * 180_000_00,
    subtotal_edge_banding_tiyin: 12_500_00,
    total_tiyin: 5 * 45_000_00 + (3 * 250_000_00 + 2 * 180_000_00) + 12_500_00,
    panels_used: 5,
    cutting_rate_tiyin: 45_000_00,
    material_lines: [
      {
        material_id: 'panel-a',
        material_name: 'LDSP Egger 18mm oq',
        panels_used: 3,
        unit_price_tiyin: 250_000_00,
        line_total_tiyin: 3 * 250_000_00,
      },
      {
        material_id: 'panel-b',
        material_name: "LDSP Egger 18mm yong'oq",
        panels_used: 2,
        unit_price_tiyin: 180_000_00,
        line_total_tiyin: 2 * 180_000_00,
      },
    ],
    edge_lines: [
      {
        material_id: 'edge-a',
        material_name: 'ABS kromka 2mm oq',
        consumed_mm: 5150,
        material_cost_tiyin: 8_000_00,
        service_cost_tiyin: 4_500_00,
        line_total_tiyin: 12_500_00,
      },
    ],
    ...overrides,
  }
}

describe('canPlaceBlocker', () => {
  it('blocks on a missing quote first, regardless of contact fields', () => {
    expect(canPlaceBlocker({ hasQuote: false, name: '', phone: '' })).toBe('quote')
    expect(canPlaceBlocker({ hasQuote: false, name: 'Dilshod', phone: '+998901112233' })).toBe(
      'quote',
    )
  })

  it('blocks on an empty name once the quote is ready', () => {
    expect(canPlaceBlocker({ hasQuote: true, name: '   ', phone: '+998901112233' })).toBe('name')
  })

  it('blocks on an invalid phone once name and quote are ready', () => {
    expect(canPlaceBlocker({ hasQuote: true, name: 'Dilshod', phone: '12345' })).toBe('phone')
    expect(canPlaceBlocker({ hasQuote: true, name: 'Dilshod', phone: '' })).toBe('phone')
  })

  it('is unblocked once a quote, name, and valid phone are all present', () => {
    expect(canPlaceBlocker({ hasQuote: true, name: 'Dilshod', phone: '+998901112233' })).toBeNull()
  })

  it('maps each blocker to distinct, non-empty Uzbek copy', () => {
    const labels = new Set(
      (['quote', 'name', 'phone'] as const).map((blocker) => canPlaceBlockerLabel(blocker)),
    )
    expect(labels.size).toBe(3)
    for (const label of labels) expect(label?.length).toBeGreaterThan(0)
    expect(canPlaceBlockerLabel(null)).toBeNull()
  })
})

describe('fieldDiffersFromProfile', () => {
  it('is false when the field still matches the profile value', () => {
    expect(fieldDiffersFromProfile('Dilshod', 'Dilshod')).toBe(false)
    expect(fieldDiffersFromProfile('', null)).toBe(false)
    expect(fieldDiffersFromProfile('', undefined)).toBe(false)
  })

  it('is true once the client edits away from the profile value', () => {
    expect(fieldDiffersFromProfile('Boshqa ism', 'Dilshod')).toBe(true)
    expect(fieldDiffersFromProfile('+998907654321', '+998901112233')).toBe(true)
  })
})

describe('buildBillRows', () => {
  it('reconciles exactly to total_tiyin against a realistic multi-material quote', () => {
    const q = quote()
    const rows = buildBillRows(q)
    expect(billRowsTotal(rows)).toBe(q.total_tiyin)
  })

  it('emits one row for cutting, one per material line, one per edge line', () => {
    const q = quote()
    const rows = buildBillRows(q)
    expect(rows).toHaveLength(1 + q.material_lines.length + q.edge_lines.length)
  })

  it('shows the cutting row basis as panels_used × cutting_rate, not just the sum', () => {
    const q = quote()
    const [cuttingRow] = buildBillRows(q)
    expect(cuttingRow.amount_tiyin).toBe(q.panels_used * q.cutting_rate_tiyin)
    expect(cuttingRow.detail).toContain(String(q.panels_used))
  })

  it('reconciles on a quote with no edge banding at all', () => {
    const q = quote({
      edge_lines: [],
      subtotal_edge_banding_tiyin: 0,
      total_tiyin: 5 * 45_000_00 + (3 * 250_000_00 + 2 * 180_000_00),
    })
    const rows = buildBillRows(q)
    expect(billRowsTotal(rows)).toBe(q.total_tiyin)
  })

  it('labels edge rows so the money figure never reads as bare "Kromka" (CB collision fix)', () => {
    const rows = buildBillRows(quote())
    const edgeRow = rows.find((row) => row.key.startsWith('edge:'))
    expect(edgeRow?.label).not.toBe('Kromka')
    expect(edgeRow?.label).toContain('Kromka')
  })
})

describe('buildPartRows', () => {
  const resolveMaterialName = (materialId: string) =>
    materialId === 'panel-a' ? 'LDSP oq' : materialId

  it('renders one row per part with its display name, size, and quantity', () => {
    const parts = [
      part({ part_ref: 'p1', name: 'Yon devor', length_mm: 600, width_mm: 400, quantity: 2 }),
      part({ part_ref: 'p2', name: null, length_mm: 300, width_mm: 250, quantity: 1 }),
    ]
    const rows = buildPartRows(parts, resolveMaterialName)
    expect(rows).toHaveLength(2)
    expect(rows[0]).toMatchObject({
      name: 'Yon devor',
      sizeLabel: '600×400 mm',
      quantity: 2,
    })
    // Falls back to the D-number convention when the part has no custom name.
    expect(rows[1].name).toBe('D2')
    expect(rows[1].sizeLabel).toBe('300×250 mm')
  })

  it('marks a client-supplied material with the "own material" note', () => {
    const rows = buildPartRows([part({ material_source: 'own' })], resolveMaterialName)
    expect(rows[0].materialLabel).toContain("o'z materiali")
  })

  it('lists only the sides that are actually banded', () => {
    const banded = part({
      edge_top: { material_id: 'edge-a', source: 'shop' },
      edge_left: { material_id: 'edge-a', source: 'shop' },
    })
    const rows = buildPartRows([banded], resolveMaterialName)
    expect(rows[0].edgeLabel).toContain('Yuqori')
    expect(rows[0].edgeLabel).toContain('Chap')
    expect(rows[0].edgeLabel).not.toContain('Pastki')
  })

  it('reports no banding distinctly from a banded part', () => {
    const rows = buildPartRows([part()], resolveMaterialName)
    expect(rows[0].edgeLabel).toBe("yo'q")
  })

  it('surfaces follow_grain so a grain-locked part is flagged to the client', () => {
    const rows = buildPartRows(
      [part({ follow_grain: true }), part({ part_ref: 'p2', follow_grain: false })],
      resolveMaterialName,
    )
    expect(rows[0].followGrain).toBe(true)
    expect(rows[1].followGrain).toBe(false)
  })
})
