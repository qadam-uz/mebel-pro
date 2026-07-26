import { describe, expect, it } from 'vitest'

import { workshopDashboardAccess } from '@/shared/app/workshopDashboard'
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

  it('gives production staff the queue section without any KPI tile', () => {
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
