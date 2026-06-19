import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import process from 'node:process'

import { describe, expect, it } from 'vitest'

import { adminRoutes } from '@/apps/admin/routes'
import { clientRoutes } from '@/apps/client/routes'
import { workshopRoutes } from '@/apps/workshop/routes'
import {
  normalizeRoleConfig,
  normalizeRolePath,
  normalizeRoleRoutes,
  resolveHistoryBase,
  roleRoutePermissionAllowed,
  roleDocumentTitle,
} from '@/shared/app/createRoleApp'
import { rolePath } from '@/shared/app/paths'
import { adminConfig, clientConfig, workshopConfig } from '@/shared/app/roleConfig'
import { workshopPermissions } from '@/shared/app/workshopPermissions'
import type { MeResponse } from '@/shared/stores/auth'

function routePaths(routes: { path: string }[]) {
  return routes.map((route) => route.path)
}

function workshopPrincipal(overrides: Partial<MeResponse> = {}): MeResponse {
  return {
    principal_type: 'workshop_user',
    principal_id: 'user-1',
    session_id: 'session-1',
    password_reset_required: false,
    workshop_id: 'workshop-1',
    is_owner: false,
    grants: [],
    login: 'worker',
    full_name: 'Worker',
    phone: '+998901234567',
    name: null,
    preferred_branch_id: null,
    status: 'active',
    ...overrides,
  }
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry)
    if (statSync(path).isDirectory()) return sourceFiles(path)
    return path.endsWith('.vue') || path.endsWith('.ts') ? [path] : []
  })
}

describe('role route matrix', () => {
  it('resolves local bases and prod root bases', () => {
    expect(resolveHistoryBase('/client', '/client/c', true)).toBe('/client/')
    expect(resolveHistoryBase('/workshop', '/workshop/profile', true)).toBe('/workshop/')
    expect(resolveHistoryBase('/admin', '/admin', true)).toBe('/admin/')
    expect(resolveHistoryBase('/client', '/c', true)).toBe('/')
    expect(resolveHistoryBase('/admin', '/admin/profile', false)).toBe('/')
    expect(resolveHistoryBase('/workshop', '/workshop/settings/users', false)).toBe('/')
  })

  it('normalizes role-prefixed paths when a dev app is mounted under a role base', () => {
    expect(normalizeRolePath('/admin', '/admin', '/admin/')).toBe('/')
    expect(normalizeRolePath('/admin/workshops', '/admin', '/admin/')).toBe('/workshops')
    expect(normalizeRolePath('/auth/login', '/admin', '/admin/')).toBe('/auth/login')
    expect(normalizeRolePath('/admin/workshops', '/admin', '/')).toBe('/admin/workshops')
  })

  it('normalizes role links for local dev without changing production host-root paths', () => {
    expect(rolePath('/admin/workshops/123', 'admin', '/admin/workshops', true)).toBe(
      '/workshops/123',
    )
    expect(rolePath('/workshop/orders/123', 'workshop', '/workshop/orders', true)).toBe(
      '/orders/123',
    )
    expect(rolePath('/c/orders/123', 'client', '/client/c/orders', true)).toBe('/c/orders/123')
    expect(rolePath('/admin/workshops/123', 'admin', '/workshops', false)).toBe(
      '/admin/workshops/123',
    )
  })

  it('formats page titles with role identity', () => {
    expect(roleDocumentTitle('Buyurtmalar', workshopConfig)).toBe(
      'Buyurtmalar — Mebel Pro · Boshqaruv',
    )
    expect(roleDocumentTitle(undefined, adminConfig)).toBe(
      'Platforma asosiy — Mebel Pro · Superadmin',
    )
  })

  it('enforces workshop route permission metadata without affecting other roles', () => {
    const inventoryOnly = workshopPrincipal({
      grants: [{ branch_id: 'branch-1', permission: workshopPermissions.manageInventory }],
    })

    expect(
      roleRoutePermissionAllowed(
        'workshop',
        inventoryOnly,
        { workshopAccess: { any: [workshopPermissions.manageInventory] } },
        {},
      ),
    ).toBe(true)
    expect(
      roleRoutePermissionAllowed(
        'workshop',
        inventoryOnly,
        { workshopAccess: { any: [workshopPermissions.manageFinance] } },
        {},
      ),
    ).toBe(false)
    expect(
      roleRoutePermissionAllowed(
        'workshop',
        inventoryOnly,
        {
          workshopAccess: {
            any: [workshopPermissions.manageInventory],
            branchParam: 'branch_id',
          },
        },
        { branch_id: 'branch-2' },
      ),
    ).toBe(false)
    expect(
      roleRoutePermissionAllowed('workshop', workshopPrincipal({ is_owner: true }), {
        workshopAccess: { ownerOnly: true },
      }),
    ).toBe(true)
    expect(
      roleRoutePermissionAllowed('client', null, {
        workshopAccess: { ownerOnly: true },
      }),
    ).toBe(true)
  })

  it('keeps dashboard-only staff out of the orders board route', () => {
    const ordersRoute = workshopRoutes.find((route) => route.path === '/workshop/orders')
    const dashboardOnly = workshopPrincipal({
      grants: [{ branch_id: 'branch-1', permission: workshopPermissions.viewDashboard }],
    })
    const orderManager = workshopPrincipal({
      grants: [{ branch_id: 'branch-1', permission: workshopPermissions.manageOrders }],
    })

    expect(ordersRoute?.meta).toBeDefined()
    expect(roleRoutePermissionAllowed('workshop', dashboardOnly, ordersRoute?.meta ?? {})).toBe(
      false,
    )
    expect(roleRoutePermissionAllowed('workshop', orderManager, ordersRoute?.meta ?? {})).toBe(true)
  })

  it('keeps direct dev URLs aligned with production route inventories', () => {
    expect(routePaths(normalizeRoleRoutes(adminRoutes, '/admin', '/admin/'))).toEqual([
      '/auth/login',
      '/',
      '/profile',
      '/workshops',
      '/catalog',
      '/catalog/manufacturers',
      '/catalog/materials',
      '/notifications',
      '/platform/jobs',
      '/platform/errors',
      '/platform/users',
      '/audit',
      '/workshops/:workshop_id',
      '/:pathMatch(.*)*',
    ])
    expect(
      normalizeRoleConfig(adminConfig, '/admin', '/admin/').nav.map((item) => item.to),
    ).toEqual([
      '/',
      '/workshops',
      '/catalog/manufacturers',
      '/catalog/materials',
      '/platform/jobs',
      '/platform/errors',
      '/audit',
      '/platform/users',
    ])
    expect(normalizeRoleConfig(workshopConfig, '/workshop', '/workshop/').homePath).toBe('/')
  })

  it('keeps the client header nav to four items (Profil lives in the user pill, CB-37)', () => {
    expect(
      normalizeRoleConfig(clientConfig, '/client', '/client/').nav.map((item) => item.label),
    ).toEqual(['Bosh sahifa', 'Chizmalar', 'Buyurtmalar', 'Ustaxonalar'])
    // Profile stays reachable via the user pill (config.profilePath), not the nav.
    expect(clientConfig.profilePath).toBe('/c/profile')
  })

  it('keeps the documented initial route inventories', () => {
    expect(routePaths(clientRoutes)).toEqual([
      '/',
      '/auth/login',
      '/c',
      '/c/profile',
      '/c/orders',
      '/c/orders/new/:draft_id',
      '/c/orders/:order_id',
      '/c/cutting/drafts',
      '/c/cutting/:id',
      '/c/branches',
      '/c/notifications',
      '/:pathMatch(.*)*',
    ])
    expect(routePaths(workshopRoutes)).toEqual([
      '/',
      '/auth/login',
      '/workshop',
      '/workshop/profile',
      '/workshop/orders',
      '/workshop/orders/:order_id',
      '/workshop/cutting',
      '/workshop/banding',
      '/workshop/inventory',
      '/workshop/catalog',
      '/workshop/settings/users',
      '/workshop/settings',
      '/workshop/branches',
      '/workshop/branches/:branch_id',
      '/workshop/cutting-plans',
      '/workshop/finance',
      '/workshop/finance/income',
      '/workshop/finance/expenses',
      '/workshop/finance/production',
      '/workshop/cutting-plans/:result_id',
      '/workshop/settings/users/:user_id',
      '/workshop/notifications',
      '/:pathMatch(.*)*',
    ])
    expect(routePaths(adminRoutes)).toEqual([
      '/',
      '/auth/login',
      '/admin',
      '/admin/profile',
      '/admin/workshops',
      '/admin/catalog',
      '/admin/catalog/manufacturers',
      '/admin/catalog/materials',
      '/admin/notifications',
      '/admin/platform/jobs',
      '/admin/platform/errors',
      '/admin/platform/users',
      '/admin/audit',
      '/admin/workshops/:workshop_id',
      '/:pathMatch(.*)*',
    ])
  })

  it('does not use native visible select controls in app source', () => {
    const files = sourceFiles(join(process.cwd(), 'src'))
    const nativeSelectTag = '<sel' + 'ect'
    const offenders = files.filter((file) => readFileSync(file, 'utf8').includes(nativeSelectTag))

    expect(offenders).toEqual([])
  })

  it('does not use native browser dialogs in app source', () => {
    const files = sourceFiles(join(process.cwd(), 'src'))
    const nativeDialogCalls = ['window.' + 'alert', 'window.' + 'confirm', 'window.' + 'prompt']
    const offenders = files.filter((file) => {
      const source = readFileSync(file, 'utf8')
      return nativeDialogCalls.some((call) => source.includes(`${call}(`))
    })

    expect(offenders).toEqual([])
  })
})
