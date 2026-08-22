import { describe, expect, it } from 'vitest'

import {
  isMovedScope,
  stockEmptyKind,
  stockListFilters,
  type StockScope,
} from '@/shared/app/stockScope'

function scope(overrides: Partial<StockScope> = {}): StockScope {
  return { search: '', lowOnly: false, wholeCatalog: false, types: [], ...overrides }
}

describe('stock scope → query', () => {
  it('defaults the table to rows that have actually moved', () => {
    expect(stockListFilters(scope())).toEqual({
      search: '',
      low_stock: null,
      moved_only: true,
      types: null,
    })
  })

  it('drops the moved scope when «Butun katalog» is pressed', () => {
    expect(isMovedScope(scope({ wholeCatalog: true }))).toBe(false)
  })

  it('searches the whole catalog even inside the moved scope', () => {
    // The point of the scope is less browse noise, not fewer results: a
    // material you searched for is usually one you are about to book an
    // arrival for, and it has never moved by definition.
    expect(stockListFilters(scope({ search: 'sonoma' }))).toEqual({
      search: 'sonoma',
      low_stock: null,
      moved_only: false,
      types: null,
    })
  })

  it('treats whitespace as no search at all', () => {
    expect(stockListFilters(scope({ search: '   ' }))).toEqual({
      search: '',
      low_stock: null,
      moved_only: true,
      types: null,
    })
  })

  it('widens for the low filter, which is already narrow by definition', () => {
    expect(stockListFilters(scope({ lowOnly: true }))).toEqual({
      search: '',
      low_stock: true,
      moved_only: false,
      types: null,
    })
  })

  it('keeps both filters when search and the low chip are combined', () => {
    expect(stockListFilters(scope({ search: 'egger', lowOnly: true }))).toEqual({
      search: 'egger',
      low_stock: true,
      moved_only: false,
      types: null,
    })
  })

  it('narrows by tur without leaving the moved scope', () => {
    // «Faqat kromka» is browsing, not a lookup: it asks a narrower question
    // about the warehouse, so it must not drag the catalog's dead rows in.
    expect(stockListFilters(scope({ types: ['kromka'] }))).toEqual({
      search: '',
      low_stock: null,
      moved_only: true,
      types: ['kromka'],
    })
    expect(isMovedScope(scope({ types: ['kromka'] }))).toBe(true)
  })

  it('sends type alongside a search that widened the scope', () => {
    expect(stockListFilters(scope({ search: 'egger', types: ['ldsp', 'dsp'] }))).toEqual({
      search: 'egger',
      low_stock: null,
      moved_only: false,
      types: ['ldsp', 'dsp'],
    })
  })
})

describe('stock empty state', () => {
  it('names the filter when one is active', () => {
    expect(stockEmptyKind(scope({ search: 'nothing' }), true)).toBe('filtered')
    expect(stockEmptyKind(scope({ lowOnly: true }), true)).toBe('filtered')
    // Even with nothing in the branch at all: "change the filter" is still the
    // actionable sentence, and first-run copy under an active filter lies.
    expect(stockEmptyKind(scope({ search: 'nothing' }), false)).toBe('filtered')
  })

  it('counts a type filter as filtering, though it never widened the scope', () => {
    // Empty under «Faqat kromka» is a filter's emptiness, not the warehouse's:
    // the moved-scope copy ("record an arrival") would be advice for the wrong
    // problem when the branch is full of panels that have moved.
    expect(stockEmptyKind(scope({ types: ['kromka'] }), true)).toBe('filtered')
    expect(stockEmptyKind(scope({ types: ['kromka'] }), false)).toBe('filtered')
  })

  it('separates an unmoved warehouse from a branch with no materials', () => {
    expect(stockEmptyKind(scope(), true)).toBe('moved')
    expect(stockEmptyKind(scope(), false)).toBe('first-run')
  })

  it('calls the whole-catalog view empty only when the catalog is empty', () => {
    expect(stockEmptyKind(scope({ wholeCatalog: true }), false)).toBe('first-run')
    // Pressed «Butun katalog» with rows in the catalog cannot render empty —
    // but if it ever did, first-run is the honest copy: no scope hid anything.
    expect(stockEmptyKind(scope({ wholeCatalog: true }), true)).toBe('first-run')
  })
})
