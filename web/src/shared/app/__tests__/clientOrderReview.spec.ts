import { describe, expect, it } from 'vitest'

import {
  buildBillRows,
  billRowsTotal,
  canPlaceBlocker,
  canPlaceBlockerLabel,
  fieldDiffersFromProfile,
} from '@/shared/app/clientOrderReview'
import type { OrderQuote } from '@/shared/stores/orders'

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
    workshop_name: 'Mebel Master',
    branch_additional_phones: [],
    branch_latitude: null,
    branch_longitude: null,
    subtotal_cutting_tiyin: 5 * 45_000_00,
    subtotal_materials_tiyin: 3 * 250_000_00 + 2 * 180_000_00,
    subtotal_edge_banding_tiyin: 12_500_00,
    total_tiyin: 5 * 45_000_00 + (3 * 250_000_00 + 2 * 180_000_00) + 12_500_00,
    panels_used: 5,
    edge_banding_rate_tiyin: 100_000,
    cutting_rate_tiyin: 45_000_00,
    material_lines: [
      {
        material_id: 'panel-a',
        material_name: 'LDSP Egger 18mm oq',
        own_panels: 0,
        panels_used: 3,
        unit_price_tiyin: 250_000_00,
        line_total_tiyin: 3 * 250_000_00,
      },
      {
        material_id: 'panel-b',
        material_name: "LDSP Egger 18mm yong'oq",
        own_panels: 0,
        panels_used: 2,
        unit_price_tiyin: 180_000_00,
        line_total_tiyin: 2 * 180_000_00,
      },
    ],
    edge_lines: [
      {
        material_id: 'edge-a',
        material_name: 'ABS kromka 2mm oq',
        own: false,
        metre_price_tiyin: 500_000,
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
