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
      'Tushum va xarajat',
      'Xodimlar mehnati',
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

  it('does not expose the orders board to dashboard-only staff', () => {
    expect(
      workshopNavItems({
        isOwner: false,
        branches: [{ id: 'branch-1', permissions: ['view_dashboard'] }],
        selectedBranchId: 'branch-1',
        path: identity,
      }).map((item) => item.label),
    ).toEqual(['Asosiy'])
  })

  it('exposes the orders board to staff with order-management grants', () => {
    expect(
      workshopNavItems({
        isOwner: false,
        branches: [{ id: 'branch-1', permissions: ['manage_orders'] }],
        selectedBranchId: 'branch-1',
        path: identity,
      }).map((item) => item.label),
    ).toEqual(['Asosiy', 'Buyurtmalar'])
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

  it('shows only worker production to reports-only finance staff', () => {
    expect(
      workshopNavItems({
        isOwner: false,
        branches: [{ id: 'branch-1', permissions: ['view_finance_reports'] }],
        selectedBranchId: 'branch-1',
        path: identity,
      }).map((item) => item.label),
    ).toEqual(['Asosiy', 'Xodimlar mehnati'])
  })

  it('shows income/expenses and worker production to finance managers', () => {
    expect(
      workshopNavItems({
        isOwner: false,
        branches: [{ id: 'branch-1', permissions: ['manage_finance'] }],
        selectedBranchId: 'branch-1',
        path: identity,
      }).map((item) => item.label),
    ).toEqual(['Asosiy', 'Tushum va xarajat', 'Xodimlar mehnati'])
  })
})
