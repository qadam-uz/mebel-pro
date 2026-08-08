import { describe, expect, it } from 'vitest'

import { dailyIncomeDelta, workshopDashboardAccess } from '@/shared/app/workshopDashboard'
import { workshopPermissions as p, type WorkshopPrincipal } from '@/shared/app/workshopPermissions'

const branches = [{ id: 'branch-1' }, { id: 'branch-2' }]

function staff(...permissions: string[]): WorkshopPrincipal {
  return {
    is_owner: false,
    grants: permissions.map((permission) => ({ branch_id: 'branch-1', permission })),
  }
}

const owner: WorkshopPrincipal = { is_owner: true, grants: [] }

describe('workshop dashboard access', () => {
  it('shows the owner every section on every branch', () => {
    const access = workshopDashboardAccess(owner, branches)

    expect(access.hasVisibleSection).toBe(true)
    expect(access.canOrders && access.canFinance && access.canInventory).toBe(true)
    expect(access.canManageOrders && access.canManageFinance).toBe(true)
    expect(access.orderBranches).toEqual(branches)
  })

  it('keeps the owner sections up while the branch context is still loading', () => {
    expect(workshopDashboardAccess(owner, []).hasVisibleSection).toBe(true)
  })

  it('reports no visible section for a grant that lights up no card (QAD-167)', () => {
    const access = workshopDashboardAccess(staff(p.manageCatalog), branches)

    expect(access.hasVisibleSection).toBe(false)
    expect(access.hasKpis).toBe(false)
    // The catalog is still reachable — the empty state can offer it.
    expect(access.canCatalog).toBe(true)
  })

  it('reports no visible section for a principal with no grants at all', () => {
    expect(workshopDashboardAccess(staff(), branches).hasVisibleSection).toBe(false)
  })

  it('gives production staff the station section without any KPI tile', () => {
    const access = workshopDashboardAccess(staff(p.processProduction), branches)

    expect(access.hasKpis).toBe(false)
    expect(access.hasVisibleSection).toBe(true)
  })

  it('renders the order cards for view_orders but refuses to link at the board (QAD-170)', () => {
    const access = workshopDashboardAccess(staff(p.viewOrders), branches)

    expect(access.canOrders).toBe(true)
    expect(access.canManageOrders).toBe(false)
  })

  it('renders the money tiles for view_finance_reports but refuses to link at the ledgers', () => {
    const access = workshopDashboardAccess(staff(p.viewFinanceReports), branches)

    expect(access.canFinance).toBe(true)
    expect(access.canManageFinance).toBe(false)
  })

  it('opens the boards for the grants that own them', () => {
    expect(workshopDashboardAccess(staff(p.manageOrders), branches).canManageOrders).toBe(true)
    expect(workshopDashboardAccess(staff(p.manageFinance), branches).canManageFinance).toBe(true)
  })

  it('scopes each section to the branches the grant covers', () => {
    const access = workshopDashboardAccess(staff(p.manageInventory), branches)

    expect(access.inventoryBranches.map((branch) => branch.id)).toEqual(['branch-1'])
    expect(access.orderBranches).toEqual([])
    expect(access.canInventory).toBe(true)
    expect(access.canOrders).toBe(false)
  })
})

describe('today vs. yesterday income', () => {
  const day = (income_tiyin: number) => ({ income_tiyin })

  it('reads today off the end of the dense daily series', () => {
    const delta = dailyIncomeDelta([day(100_000), day(200_000), day(236_000)])

    expect(delta.todayTiyin).toBe(236_000)
    expect(delta.yesterdayTiyin).toBe(200_000)
    expect(delta.kind).toBe('percent')
    expect(delta.percent).toBe(18)
    expect(delta.up).toBe(true)
  })

  it('reports a fall as a negative percent and a bad tone', () => {
    const delta = dailyIncomeDelta([day(200_000), day(150_000)])

    expect(delta.percent).toBe(-25)
    expect(delta.up).toBe(false)
  })

  it('calls an equal day flat rather than a fall', () => {
    const delta = dailyIncomeDelta([day(200_000), day(200_000)])

    expect(delta.percent).toBe(0)
    expect(delta.up).toBe(true)
  })

  it('refuses a percentage when yesterday was zero — it is undefined, not infinite', () => {
    const first = dailyIncomeDelta([day(0), day(412_000)])
    expect(first.kind).toBe('noYesterday')
    expect(first.todayTiyin).toBe(412_000)

    // Both days empty: still no ratio to state, and the caption must not read
    // "+0%" as though nothing had changed from a real number.
    const idle = dailyIncomeDelta([day(0), day(0)])
    expect(idle.kind).toBe('noYesterday')
    expect(idle.up).toBe(false)
  })

  it('has nothing to compare with a one-day or empty series', () => {
    expect(dailyIncomeDelta([day(500_000)])).toMatchObject({
      kind: 'noCompare',
      todayTiyin: 500_000,
      yesterdayTiyin: null,
    })
    expect(dailyIncomeDelta([])).toMatchObject({ kind: 'noCompare', todayTiyin: 0 })
    expect(dailyIncomeDelta(null)).toMatchObject({ kind: 'noCompare', todayTiyin: 0 })
    expect(dailyIncomeDelta(undefined)).toMatchObject({ kind: 'noCompare', todayTiyin: 0 })
  })
})
