/**
 * A material's movement history, split into the three questions an owner asks.
 *
 * The Tranzaksiyalar tab is the audit journal — one flat, chronological ledger
 * of everything. The material page is not that: standing in front of one
 * material, "qancha keldi", "kim tuzatdi" and "qayoqqa ketdi" are three
 * separate questions with three different context columns (a faktura, a person
 * with a reason, an order), and answering them in one mixed table makes the
 * reader do the sorting the screen should have done.
 *
 * `stock_in_void` sits with the arrivals it reverses rather than in its own
 * section: it is the same document's story, told backwards.
 */

import type { StockTransaction, StockTransactionType } from '@/shared/stores/workshop'

export type MaterialMovementSection = 'arrivals' | 'adjustments' | 'consumption'

const SECTION_BY_TYPE: Record<StockTransactionType, MaterialMovementSection> = {
  stock_in: 'arrivals',
  stock_in_void: 'arrivals',
  adjust: 'adjustments',
  consume: 'consumption',
  restore: 'consumption',
}

export interface MaterialMovementGroups {
  arrivals: StockTransaction[]
  adjustments: StockTransaction[]
  consumption: StockTransaction[]
}

/** Split one material's ledger into its three sections, order preserved. */
export function groupMaterialMovements(rows: StockTransaction[]): MaterialMovementGroups {
  const groups: MaterialMovementGroups = { arrivals: [], adjustments: [], consumption: [] }
  for (const row of rows) {
    const section = SECTION_BY_TYPE[row.type]
    // An unknown type must not vanish from the page: a movement the client has
    // not learned about yet is still stock that moved, and the audit journal
    // would be the only place it existed. Adjustments carry the free-form
    // context column, so it reads there.
    groups[section ?? 'adjustments'].push(row)
  }
  return groups
}

/**
 * Net change a section accounts for, in the material's stock unit.
 *
 * Signed, and summed over the *fetched* window rather than all history — the
 * page says so where it renders, because a total whose scope is unstated is
 * worse than no total.
 */
export function movementTotal(rows: StockTransaction[]): number {
  return rows.reduce((sum, row) => sum + row.quantity, 0)
}
