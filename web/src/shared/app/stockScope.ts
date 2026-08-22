/**
 * The Zaxira tab's scope rules: what the stock table asks the server for, and
 * which empty state it shows when the answer is nothing.
 *
 * Extracted from the view because both are matrices, and a matrix is exactly
 * what a unit test owns. The server stays dumb — it ANDs whatever it is sent;
 * deciding that a search must never be narrowed is the client's job.
 */

import type { DecorType } from '@/shared/stores/admin'
import type { StockListFilters } from '@/shared/stores/workshop'

export interface StockScope {
  /** The raw search box value; trimmed here so callers can't forget to. */
  search: string
  /** «Kam qolganlar» — the low-stock filter chip. */
  lowOnly: boolean
  /** «Butun katalog» — the operator asked to leave the moved scope. */
  wholeCatalog: boolean
  /**
   * The decor types behind the picked filter option; empty means every type.
   *
   * A list rather than one value because one label can cover several enum
   * members — «LDSP» is both `ldsp` and `dsp`. The view owns that expansion
   * (it is the side that knows the labels); this module only carries it.
   */
  types: DecorType[]
}

/**
 * True when the table shows only rows that have moved.
 *
 * Search and the low filter always query the whole catalog, whatever the chip
 * says: the scope exists to cut browse noise, not to hide results. An operator
 * searching for a material wants to find it — that is usually the prelude to
 * recording its first arrival — and the low set is filtered by definition.
 */
export function isMovedScope(scope: StockScope): boolean {
  return !scope.wholeCatalog && !scope.lowOnly && scope.search.trim() === ''
}

/** True when search or the low chip is overriding the «Butun katalog» toggle. */
export function isScopeWidened(scope: StockScope): boolean {
  return scope.lowOnly || scope.search.trim() !== ''
}

/**
 * True when any filter is narrowing the table.
 *
 * The `type` filter deliberately does **not** widen the scope the way search
 * does: "show me only kromka" narrows a browse, it does not look a specific
 * material up, so it stays inside whichever scope the operator is in. It still
 * counts as filtering, which is what the empty state and the count line read.
 */
export function isStockFiltered(scope: StockScope): boolean {
  return isScopeWidened(scope) || scope.types.length > 0
}

/** The stock list query for one scope. */
export function stockListFilters(scope: StockScope): StockListFilters {
  return {
    search: scope.search.trim(),
    low_stock: scope.lowOnly ? true : null,
    moved_only: isMovedScope(scope),
    types: scope.types.length > 0 ? scope.types : null,
  }
}

/**
 * Which empty state an empty stock table earns.
 *
 * Three facts, three messages (the QAD-182 lesson): a filter that matched
 * nothing · a warehouse nobody has moved anything into yet · a branch with no
 * materials at all. `catalogHasRows` is the picker collection's answer — it is
 * already loaded for the modals, so telling the last two apart costs no
 * request.
 */
export type StockEmptyKind = 'filtered' | 'moved' | 'first-run'

export function stockEmptyKind(scope: StockScope, catalogHasRows: boolean): StockEmptyKind {
  if (isStockFiltered(scope)) return 'filtered'
  if (isMovedScope(scope) && catalogHasRows) return 'moved'
  return 'first-run'
}
