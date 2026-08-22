/**
 * Material katalogi's filter state: what the table asks the server for, which
 * filters count as "on", and what a reset returns to.
 *
 * Extracted from the view for the same reason `stockScope.ts` was — the rules
 * are a matrix, and a matrix is what a unit test owns. The one that matters is
 * the **baseline**: the page opens on «Faol» rather than «Hammasi», so "is a
 * filter on?" is a comparison against the defaults, not against `'all'`. Get
 * that wrong and the page still compiles, still renders, and still lies: the
 * result-count line burns on every load, and a branch with no materials yet
 * gets «Filtrga mos material topilmadi» instead of the first-run empty state
 * that carries the «+ Material» button.
 */

import type { DecorType, MaterialStatus } from '@/shared/stores/admin'
import type { BranchMaterialFilters } from '@/shared/stores/workshop'

/**
 * The status the page opens on.
 *
 * A deactivated o'lcham is hidden from clients, so it is not what the operator
 * came to read. It stays one click away on the Holat segmented control — which
 * is also why that control is segmented: a dropdown would have buried the way
 * back to a material the operator had just switched off.
 */
export const CATALOG_DEFAULT_STATUS: MaterialStatus = 'active'

export interface CatalogScope {
  /** The raw search box value; trimmed here so callers can't forget to. */
  search: string
  /** The picked substrate, or `'all'`. */
  tur: DecorType | 'all'
  /** The picked manufacturer's id, or `'all'`. */
  manufacturerId: string | 'all'
  /** The picked status, or `'all'`. Starts at `CATALOG_DEFAULT_STATUS`. */
  status: MaterialStatus | 'all'
  /**
   * «Kam qolganlar» — only materials at or under their threshold.
   *
   * A stock question asked from the catalog, so the server takes
   * `manage_inventory` for it, and the page only offers the chip to someone who
   * already sees the Qoldiq column.
   */
  lowOnly: boolean
}

export function defaultCatalogScope(): CatalogScope {
  return {
    search: '',
    tur: 'all',
    manufacturerId: 'all',
    status: CATALOG_DEFAULT_STATUS,
    lowOnly: false,
  }
}

/** What the table sends. `null` means "don't narrow on this". */
export function catalogListFilters(scope: CatalogScope, offset = 0): BranchMaterialFilters {
  return {
    status: scope.status === 'all' ? null : scope.status,
    type: scope.tur === 'all' ? null : scope.tur,
    manufacturer_id: scope.manufacturerId === 'all' ? null : scope.manufacturerId,
    low_stock: scope.lowOnly,
    search: scope.search.trim(),
    offset,
  }
}

/**
 * Whether the operator has narrowed anything — drives the result-count line and
 * picks the filtered empty state over the first-run one.
 */
export function isCatalogFiltered(scope: CatalogScope): boolean {
  return activeCatalogFilterCount(scope) > 0
}

/**
 * How many filters are on. The bar-level «Hammasini tozalash» appears from the
 * second one, because with one active it would sit next to that filter's own
 * clear and do the same thing.
 */
export function activeCatalogFilterCount(scope: CatalogScope): number {
  const defaults = defaultCatalogScope()
  return (
    (scope.search.trim() ? 1 : 0) +
    (scope.tur === defaults.tur ? 0 : 1) +
    (scope.manufacturerId === defaults.manufacturerId ? 0 : 1) +
    (scope.lowOnly === defaults.lowOnly ? 0 : 1) +
    (scope.status === defaults.status ? 0 : 1)
  )
}
