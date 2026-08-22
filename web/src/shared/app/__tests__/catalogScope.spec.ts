import { describe, expect, it } from 'vitest'

import {
  CATALOG_DEFAULT_STATUS,
  activeCatalogFilterCount,
  catalogListFilters,
  defaultCatalogScope,
  isCatalogFiltered,
  type CatalogScope,
} from '@/shared/app/catalogScope'

function scope(overrides: Partial<CatalogScope> = {}): CatalogScope {
  return { ...defaultCatalogScope(), ...overrides }
}

describe('catalog scope → query', () => {
  it('opens on what the branch actually sells', () => {
    expect(catalogListFilters(scope())).toEqual({
      status: CATALOG_DEFAULT_STATUS,
      type: null,
      manufacturer_id: null,
      low_stock: false,
      search: '',
      offset: 0,
    })
  })

  it('sends the picked manufacturer, and nothing for «Barcha»', () => {
    expect(catalogListFilters(scope({ manufacturerId: 'egger-id' })).manufacturer_id).toBe(
      'egger-id',
    )
    expect(catalogListFilters(scope()).manufacturer_id).toBeNull()
  })

  it('sends no status at all once «Hammasi» is picked', () => {
    expect(catalogListFilters(scope({ status: 'all' })).status).toBeNull()
  })

  it('carries the offset a load-more asks for', () => {
    expect(catalogListFilters(scope(), 50).offset).toBe(50)
  })
})

describe('catalog scope → is anything narrowed', () => {
  // The whole risk of defaulting the status to «Faol»: measured against 'all',
  // every one of these would read as filtered on a page nobody has touched.
  it('a freshly opened page is not filtered', () => {
    expect(isCatalogFiltered(scope())).toBe(false)
    expect(activeCatalogFilterCount(scope())).toBe(0)
  })

  it('«Hammasi» is itself a filter — it is not the default', () => {
    expect(isCatalogFiltered(scope({ status: 'all' }))).toBe(true)
    expect(activeCatalogFilterCount(scope({ status: 'all' }))).toBe(1)
  })

  it('«Faol emas» is a filter', () => {
    expect(activeCatalogFilterCount(scope({ status: 'inactive' }))).toBe(1)
  })

  it('treats whitespace as no search at all', () => {
    expect(isCatalogFiltered(scope({ search: '   ' }))).toBe(false)
  })

  it('a picked manufacturer is a filter', () => {
    expect(isCatalogFiltered(scope({ manufacturerId: 'egger-id' }))).toBe(true)
  })

  it('«Kam qolganlar» is a filter, and it reaches the query', () => {
    expect(isCatalogFiltered(scope({ lowOnly: true }))).toBe(true)
    expect(catalogListFilters(scope({ lowOnly: true })).low_stock).toBe(true)
  })

  it('counts each narrowed axis once, so the reset-all knows when to appear', () => {
    expect(activeCatalogFilterCount(scope({ search: 'sonoma', tur: 'kromka' }))).toBe(2)
    expect(
      activeCatalogFilterCount(
        scope({ search: 'sonoma', tur: 'kromka', manufacturerId: 'egger-id' }),
      ),
    ).toBe(3)
    expect(
      activeCatalogFilterCount(
        scope({ search: 'sonoma', tur: 'kromka', manufacturerId: 'egger-id', status: 'all' }),
      ),
    ).toBe(4)
    expect(
      activeCatalogFilterCount(
        scope({
          search: 'sonoma',
          tur: 'kromka',
          manufacturerId: 'egger-id',
          status: 'all',
          lowOnly: true,
        }),
      ),
    ).toBe(5)
  })

  it('a reset returns to the default status, not to «Hammasi»', () => {
    expect(defaultCatalogScope().status).toBe(CATALOG_DEFAULT_STATUS)
    expect(isCatalogFiltered(defaultCatalogScope())).toBe(false)
  })
})
