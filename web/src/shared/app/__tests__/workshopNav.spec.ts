import { describe, expect, it } from 'vitest'

import { i18n } from '@/shared/i18n'
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
      }).map((item) => i18n.global.t(item.labelKey)),
    ).toEqual([
      'Asosiy',
      'Buyurtmalar',
      'Kesish',
      'Krom',
      'Ombor',
      'Material katalogi',
      'Tushum va xarajat',
      'Qarzdorlik',
      'Xodimlar mehnati',
      'Filiallar',
      "Xodimlar ro'yxati",
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
      }).map((item) => i18n.global.t(item.labelKey)),
    ).toEqual(['Asosiy'])
  })

  it('shows only the granted branch workspace for inventory-only staff', () => {
    expect(
      workshopNavItems({
        isOwner: false,
        branches: [{ id: 'branch-1', permissions: ['manage_inventory'] }],
        selectedBranchId: 'branch-1',
        path: identity,
      }).map((item) => i18n.global.t(item.labelKey)),
    ).toEqual(['Asosiy', 'Ombor'])
  })

  it('does not expose the orders board to read-only order staff', () => {
    expect(
      workshopNavItems({
        isOwner: false,
        branches: [{ id: 'branch-1', permissions: ['view_orders'] }],
        selectedBranchId: 'branch-1',
        path: identity,
      }).map((item) => i18n.global.t(item.labelKey)),
    ).toEqual(['Asosiy'])
  })

  it('exposes the orders board to staff with order-management grants', () => {
    expect(
      workshopNavItems({
        isOwner: false,
        branches: [{ id: 'branch-1', permissions: ['manage_orders'] }],
        selectedBranchId: 'branch-1',
        path: identity,
      }).map((item) => i18n.global.t(item.labelKey)),
    ).toEqual(['Asosiy', 'Buyurtmalar'])
  })

  it('shows the production stations only to staff with production grants', () => {
    expect(
      workshopNavItems({
        isOwner: false,
        branches: [{ id: 'branch-1', permissions: ['process_production'] }],
        selectedBranchId: 'branch-1',
        path: identity,
      }).map((item) => i18n.global.t(item.labelKey)),
    ).toEqual(['Asosiy', 'Kesish', 'Krom'])
  })

  // orders.md — simple mode: the station queues are assignment-fed and a simple
  // branch never writes an assignment, so the two entries (and the counters the
  // shell derives from this list) come off the sidebar entirely.
  it('hides the station pages while the selected branch runs simple mode', () => {
    expect(
      workshopNavItems({
        isOwner: false,
        branches: [
          { id: 'branch-1', permissions: ['process_production'], production_mode: 'simple' },
        ],
        selectedBranchId: 'branch-1',
        path: identity,
      }).map((item) => i18n.global.t(item.labelKey)),
    ).toEqual(['Asosiy'])
  })

  it('hides the station pages for the owner too when the selected branch is simple', () => {
    const labels = workshopNavItems({
      isOwner: true,
      branches: [
        { id: 'branch-1', permissions: [], production_mode: 'full' },
        { id: 'branch-2', permissions: [], production_mode: 'simple' },
      ],
      selectedBranchId: 'branch-2',
      path: identity,
    }).map((item) => i18n.global.t(item.labelKey))
    expect(labels).not.toContain('Kesish')
    expect(labels).not.toContain('Krom')
    // everything else the owner has stays put — this hides two entries, not a group
    expect(labels).toContain('Buyurtmalar')
    expect(labels).toContain('Ombor')
  })

  it('keeps the station pages on a full-mode branch', () => {
    expect(
      workshopNavItems({
        isOwner: false,
        branches: [
          { id: 'branch-1', permissions: ['process_production'], production_mode: 'full' },
        ],
        selectedBranchId: 'branch-1',
        path: identity,
      }).map((item) => i18n.global.t(item.labelKey)),
    ).toEqual(['Asosiy', 'Kesish', 'Krom'])
  })

  it('shows only worker production to reports-only finance staff', () => {
    expect(
      workshopNavItems({
        isOwner: false,
        branches: [{ id: 'branch-1', permissions: ['view_finance_reports'] }],
        selectedBranchId: 'branch-1',
        path: identity,
      }).map((item) => i18n.global.t(item.labelKey)),
    ).toEqual(['Asosiy', 'Xodimlar mehnati'])
  })

  it('shows income/expenses and worker production to finance managers', () => {
    expect(
      workshopNavItems({
        isOwner: false,
        branches: [{ id: 'branch-1', permissions: ['manage_finance'] }],
        selectedBranchId: 'branch-1',
        path: identity,
      }).map((item) => i18n.global.t(item.labelKey)),
    ).toEqual(['Asosiy', 'Tushum va xarajat', 'Qarzdorlik', 'Xodimlar mehnati'])
  })
})
