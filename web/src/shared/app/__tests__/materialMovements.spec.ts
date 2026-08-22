import { describe, expect, it } from 'vitest'

import { groupMaterialMovements, movementTotal } from '@/shared/app/materialMovements'
import type { StockTransaction, StockTransactionType } from '@/shared/stores/workshop'

function movement(
  type: StockTransactionType,
  quantity: number,
  overrides: Partial<StockTransaction> = {},
): StockTransaction {
  return {
    id: `tx-${type}-${quantity}`,
    stock_item_id: 'si-1',
    branch_material_id: 'bm-1',
    invoice_id: null,
    invoice_no: null,
    material_name: 'LDSP Egger H1145',
    type,
    quantity,
    balance_after: 0,
    unit_price_tiyin: null,
    total_price_tiyin: null,
    order_id: null,
    order_number: null,
    supplier_id: null,
    supplier_name: null,
    actor_user_id: null,
    actor_name: null,
    note: null,
    created_at: '2026-08-20T10:00:00Z',
    ...overrides,
  }
}

describe('groupMaterialMovements', () => {
  it('answers the three questions separately', () => {
    const groups = groupMaterialMovements([
      movement('stock_in', 10),
      movement('consume', -4),
      movement('adjust', -1),
      movement('restore', 4),
    ])

    expect(groups.arrivals.map((row) => row.type)).toEqual(['stock_in'])
    expect(groups.adjustments.map((row) => row.type)).toEqual(['adjust'])
    // A revert belongs with what it reverted: both are the order's story.
    expect(groups.consumption.map((row) => row.type)).toEqual(['consume', 'restore'])
  })

  it('files a void reversal with the arrival it undoes', () => {
    // The reversal carries the same `K-…`; splitting it into its own section
    // would show an arrival that still looks delivered next to nothing.
    const groups = groupMaterialMovements([
      movement('stock_in', 10, { invoice_no: 'K-0007' }),
      movement('stock_in_void', -10, { invoice_no: 'K-0007' }),
    ])

    expect(groups.arrivals).toHaveLength(2)
    expect(groups.adjustments).toHaveLength(0)
    expect(groups.consumption).toHaveLength(0)
  })

  it('keeps a type it does not know rather than dropping it', () => {
    // Stock that moved must never be invisible on the page that explains the
    // balance — an unlabelled row is a bug, a missing row is a wrong number.
    const groups = groupMaterialMovements([
      movement('write_off' as StockTransactionType, -2),
      movement('stock_in', 5),
    ])

    expect(groups.arrivals).toHaveLength(1)
    expect(groups.adjustments).toHaveLength(1)
  })

  it('preserves the order it was given', () => {
    const groups = groupMaterialMovements([
      movement('stock_in', 10, { id: 'first' }),
      movement('stock_in', 3, { id: 'second' }),
    ])

    expect(groups.arrivals.map((row) => row.id)).toEqual(['first', 'second'])
  })
})

describe('movementTotal', () => {
  it('nets the signed quantities', () => {
    expect(movementTotal([movement('consume', -4), movement('restore', 4)])).toBe(0)
    expect(movementTotal([movement('stock_in', 10), movement('stock_in_void', -10)])).toBe(0)
    expect(movementTotal([])).toBe(0)
  })
})
