import { describe, expect, it } from 'vitest'

import {
  branchesWithAnyPermission,
  canAccessWorkshopRoute,
  hasAnyPermission,
  hasAnyPermissionOnBranch,
  hasPermissionOnBranch,
  workshopPermissions,
  type WorkshopPrincipal,
} from '@/shared/app/workshopPermissions'

const owner: WorkshopPrincipal = { is_owner: true, grants: [] }
const noGrantStaff: WorkshopPrincipal = { is_owner: false, grants: [] }
const branchStaff: WorkshopPrincipal = {
  is_owner: false,
  grants: [
    { branch_id: 'branch-a', permission: workshopPermissions.manageFinance },
    { branch_id: 'branch-b', permission: workshopPermissions.manageInventory },
  ],
}

describe('workshop permissions', () => {
  it('treats owners as allowed on every branch and route', () => {
    expect(hasPermissionOnBranch(owner, workshopPermissions.manageOrders, 'branch-x')).toBe(true)
    expect(
      canAccessWorkshopRoute(owner, {
        any: [workshopPermissions.manageInventory],
        branchParam: 'branch_id',
      }),
    ).toBe(true)
    expect(canAccessWorkshopRoute(owner, { ownerOnly: true })).toBe(true)
  })

  it('keeps staff permissions scoped to the granted branch', () => {
    expect(hasPermissionOnBranch(branchStaff, workshopPermissions.manageFinance, 'branch-a')).toBe(
      true,
    )
    expect(hasPermissionOnBranch(branchStaff, workshopPermissions.manageFinance, 'branch-b')).toBe(
      false,
    )
    expect(
      hasAnyPermissionOnBranch(
        branchStaff,
        [workshopPermissions.manageFinance, workshopPermissions.viewFinanceReports],
        'branch-b',
      ),
    ).toBe(false)
  })

  it('supports broad route access without treating it as branch-wide write access', () => {
    expect(hasAnyPermission(branchStaff, [workshopPermissions.manageFinance])).toBe(true)
    expect(canAccessWorkshopRoute(branchStaff, { any: [workshopPermissions.manageFinance] })).toBe(
      true,
    )
    expect(
      canAccessWorkshopRoute(branchStaff, {
        any: [workshopPermissions.manageFinance],
        branchParam: 'branch_id',
      }),
    ).toBe(false)
    expect(
      canAccessWorkshopRoute(
        branchStaff,
        {
          any: [workshopPermissions.manageFinance],
          branchParam: 'branch_id',
        },
        { branch_id: 'branch-a' },
      ),
    ).toBe(true)
  })

  it('keeps no-grant staff out of protected routes', () => {
    expect(canAccessWorkshopRoute(noGrantStaff, undefined)).toBe(true)
    expect(
      canAccessWorkshopRoute(noGrantStaff, { any: [workshopPermissions.manageInventory] }),
    ).toBe(false)
    expect(canAccessWorkshopRoute(noGrantStaff, { ownerOnly: true })).toBe(false)
  })

  it('filters accessible branches by any matching permission', () => {
    expect(
      branchesWithAnyPermission(
        branchStaff,
        [{ id: 'branch-a' }, { id: 'branch-b' }, { id: 'branch-c' }],
        [workshopPermissions.manageFinance],
      ),
    ).toEqual([{ id: 'branch-a' }])

    expect(
      branchesWithAnyPermission(
        owner,
        [{ id: 'branch-a' }, { id: 'branch-b' }],
        [workshopPermissions.manageFinance],
      ),
    ).toEqual([{ id: 'branch-a' }, { id: 'branch-b' }])
  })
})
