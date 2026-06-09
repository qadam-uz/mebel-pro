import { describe, expect, it } from 'vitest'

import { workshopNavItems } from '@/shared/app/workshopNav'

const identity = (path: string) => path

describe('workshop navigation permissions', () => {
  it('shows all workshop operations for owners', () => {
    expect(
      workshopNavItems({
        isOwner: true,
        branches: [],
        selectedBranchId: '',
        path: identity,
      }).map((item) => item.label),
    ).toEqual([
      'Asosiy',
      'Buyurtmalar',
      'Kesish navbati',
      'Krom navbati',
      'Ombor',
      'Material katalogi',
      'Hisobotlar',
      'Tushum va xarajat',
      'Filiallar',
      'Xodimlar',
      'Sozlamalar',
    ])
  })

  it('keeps zero-grant staff out of branch-scoped work navigation', () => {
    expect(
      workshopNavItems({
        isOwner: false,
        branches: [],
        selectedBranchId: '',
        path: identity,
      }).map((item) => item.label),
    ).toEqual(['Asosiy'])
  })

  it('shows only the granted branch workspace for inventory-only staff', () => {
    expect(
      workshopNavItems({
        isOwner: false,
        branches: [{ id: 'branch-1', permissions: ['manage_inventory'] }],
        selectedBranchId: 'branch-1',
        path: identity,
      }).map((item) => item.label),
    ).toEqual(['Asosiy', 'Ombor'])
  })

  it('shows production queues only to staff with production grants', () => {
    expect(
      workshopNavItems({
        isOwner: false,
        branches: [{ id: 'branch-1', permissions: ['process_production'] }],
        selectedBranchId: 'branch-1',
        path: identity,
      }).map((item) => item.label),
    ).toEqual(['Asosiy', 'Kesish navbati', 'Krom navbati'])
  })

  it('shows finance only to staff with finance grants', () => {
    expect(
      workshopNavItems({
        isOwner: false,
        branches: [{ id: 'branch-1', permissions: ['view_finance_reports'] }],
        selectedBranchId: 'branch-1',
        path: identity,
      }).map((item) => item.label),
    ).toEqual(['Asosiy', 'Hisobotlar', 'Tushum va xarajat'])
  })
})
