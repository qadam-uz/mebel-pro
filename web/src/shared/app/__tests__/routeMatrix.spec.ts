import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import process from 'node:process'

import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it } from 'vitest'

import { i18n } from '@/shared/i18n'
import type {
  NavigationGuardNext,
  RouteLocationNormalized,
  RouteLocationNormalizedLoaded,
  RouteRecordRaw,
} from 'vue-router'

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
    workshop_name: 'Mebel Master',
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

function adminViewFiles(): string[] {
  return sourceFiles(join(process.cwd(), 'src', 'shared', 'views')).filter((file) =>
    file.includes('/Admin'),
  )
}

function nonAdminViewFiles(): string[] {
  return sourceFiles(join(process.cwd(), 'src', 'shared', 'views')).filter(
    (file) => !file.includes('/Admin'),
  )
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
      'Buyurtmalar — Mebel Pro · Ustaxona',
    )
    expect(roleDocumentTitle(undefined, adminConfig)).toBe('Asosiy — Mebel Pro · Superadmin')
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
      roleRoutePermissionAllowed(
        'workshop',
        inventoryOnly,
        { workshopAccess: { ownerOnly: true } },
        {},
      ),
    ).toBe(false)
    expect(
      roleRoutePermissionAllowed('client', null, {
        workshopAccess: { ownerOnly: true },
      }),
    ).toBe(true)
  })

  it('keeps read-only order staff out of the orders board route', () => {
    const ordersRoute = workshopRoutes.find((route) => route.path === '/workshop/orders')
    const readOnlyOrderStaff = workshopPrincipal({
      grants: [{ branch_id: 'branch-1', permission: workshopPermissions.viewOrders }],
    })
    const orderManager = workshopPrincipal({
      grants: [{ branch_id: 'branch-1', permission: workshopPermissions.manageOrders }],
    })

    expect(ordersRoute?.meta).toBeDefined()
    expect(
      roleRoutePermissionAllowed('workshop', readOnlyOrderStaff, ordersRoute?.meta ?? {}),
    ).toBe(false)
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
      '/catalog/dekorlar',
      '/catalog/dekorlar/:dekor_id',
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
      '/catalog/dekorlar',
      '/platform/jobs',
      '/platform/errors',
      '/audit',
      '/platform/users',
    ])
    expect(normalizeRoleConfig(workshopConfig, '/workshop', '/workshop/').homePath).toBe('/')
  })

  it('keeps the client header nav to four items (Profil lives in the user pill, CB-37)', () => {
    expect(
      normalizeRoleConfig(clientConfig, '/client', '/client/').nav.map((item) =>
        i18n.global.t(item.labelKey),
      ),
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
      '/c/cutting/new',
      '/c/cutting/:id',
      '/c/cutting/:id/result',
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
      '/workshop/orders/new',
      '/workshop/orders/new/cutting',
      '/workshop/orders/cutting/:id',
      '/workshop/orders/cutting/:id/result',
      '/workshop/orders/new/:draft_id/checkout',
      '/workshop/orders/drafts',
      '/workshop/orders/edit/:draft_id/review',
      '/workshop/orders/:order_id',
      '/workshop/production',
      '/workshop/production/:order_id',
      '/workshop/cutting',
      '/workshop/banding',
      '/workshop/inventory',
      '/workshop/catalog',
      '/workshop/settings/users',
      '/workshop/settings',
      '/workshop/branches',
      '/workshop/branches/:branch_id',
      '/workshop/finance/income',
      '/workshop/finance/expenses',
      '/workshop/finance/debts',
      '/workshop/finance/production',
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
      '/admin/catalog/dekorlar',
      '/admin/catalog/dekorlar/:dekor_id',
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

  it('does not expose standalone admin refresh controls', () => {
    const files = sourceFiles(join(process.cwd(), 'src'))
    const refreshComponent = 'Admin' + 'RefreshButton'
    const refreshClass = 'admin-' + 'refresh-button'
    const offenders = files.filter((file) => {
      const source = readFileSync(file, 'utf8')
      return source.includes(refreshComponent) || source.includes(refreshClass)
    })

    expect(offenders).toEqual([])
  })

  it('keeps admin load error states retryable', () => {
    const offenders = adminViewFiles().flatMap((file) => {
      const source = readFileSync(file, 'utf8')
      return Array.from(source.matchAll(/<AdminErrorState[\s\S]*?(?:\/>|><\/AdminErrorState>)/g))
        .filter(([match]) => !match.includes('@retry='))
        .map((_, index) => `${file}#AdminErrorState-${index + 1}`)
    })

    expect(offenders).toEqual([])
  })

  it('keeps admin filter rows on labeled filter controls', () => {
    const offenders = adminViewFiles().flatMap((file) => {
      const source = readFileSync(file, 'utf8')
      return Array.from(source.matchAll(/<div class="admin-filters">[\s\S]*?<\/div>/g)).flatMap(
        ([match], index) => {
          const issues: string[] = []
          if (match.includes('ProjectDropdown')) issues.push('ProjectDropdown')
          if (/<FormSelect(?![\s\S]*?class="admin-filter-select")/.test(match)) {
            issues.push('FormSelect without admin-filter-select')
          }
          return issues.map((issue) => `${file}#admin-filters-${index + 1}:${issue}`)
        },
      )
    })

    expect(offenders).toEqual([])
  })

  it('keeps admin classes out of non-admin views', () => {
    const offenders = nonAdminViewFiles().filter((file) => {
      const source = readFileSync(file, 'utf8')
      return /\bclass="[^"]*\badmin-/.test(source) || /\bclass='[^']*\badmin-/.test(source)
    })

    expect(offenders).toEqual([])
  })

  it('keeps admin components out of non-admin views', () => {
    const offenders = nonAdminViewFiles().filter((file) => {
      const source = readFileSync(file, 'utf8')
      return /<Admin[A-Z]/.test(source) || /from ['"]@\/shared\/components\/Admin/.test(source)
    })

    expect(offenders).toEqual([])
  })

  it('keeps admin required fields covered by visible required markers', () => {
    const nativeOffenders = adminViewFiles().flatMap((file) => {
      const source = readFileSync(file, 'utf8')
      return Array.from(source.matchAll(/<(input|textarea)\b(?=[^>]*\brequired\b)[^>]*>/g))
        .filter((match) => {
          const start = match.index ?? 0
          const labelStart = source.lastIndexOf('<label', start)
          const labelEndBeforeField = source.lastIndexOf('</label>', start)
          const labelOpen =
            labelStart >= 0 ? source.slice(labelStart, source.indexOf('>', labelStart)) : ''
          return labelStart < labelEndBeforeField || !labelOpen.includes('admin-field')
        })
        .map((match) => `${file}:${match[0]}`)
    })
    const dekorlar = readFileSync(
      join(process.cwd(), 'src', 'shared', 'views', 'AdminDekorlarView.vue'),
      'utf8',
    )
    const requiredFormSelectIds = ['dek-manufacturer']
    const customOffenders = requiredFormSelectIds.filter((id) => {
      const field = dekorlar.match(new RegExp(`<FormSelect[\\s\\S]*?id="${id}"[\\s\\S]*?/>`))?.[0]
      return !field?.includes('required')
    })

    expect(nativeOffenders).toEqual([])
    expect(customOffenders).toEqual([])
  })

  // `tur` is required but renders as a chip group, so it carries no `required`
  // attribute for the check above to find. Its required-ness moved to form-level
  // validation — assert that, or the reshape leaves the field guarded by nothing.
  it('keeps the dekor tur chip group required at form level', () => {
    const dekorlar = readFileSync(
      join(process.cwd(), 'src', 'shared', 'views', 'AdminDekorlarView.vue'),
      'utf8',
    )

    expect(dekorlar).toContain("set('tur', requiredText(form.tur")
    expect(dekorlar).toContain('dekorFieldErrors.tur')
    expect(dekorlar).toContain('dek-tur')
  })

  // The workshop order flow REUSES the client cutting editor — there must be
  // exactly one editor module, not a fork. Resolving both apps' lazy editor
  // routes must return the identical module (AC3).
  it('serves one shared cutting editor module to both the client and workshop apps', async () => {
    function lazyComponent(routes: typeof clientRoutes, name: string) {
      const record = routes.find((route) => route.name === name)
      if (!record || typeof record.component !== 'function') {
        throw new Error(`route ${name} is not a lazy component`)
      }
      return record.component as () => Promise<{ default: unknown }>
    }

    const clientEditor = await lazyComponent(clientRoutes, 'client-cutting-editor')()
    const workshopEditor = await lazyComponent(workshopRoutes, 'workshop-order-cutting-editor')()
    expect(clientEditor.default).toBe(workshopEditor.default)
  })

  it('serves one shared cutting result module to both client and workshop apps', async () => {
    function lazyComponent(routes: typeof clientRoutes, name: string) {
      const record = routes.find((route) => route.name === name)
      if (!record || typeof record.component !== 'function') {
        throw new Error(`route ${name} is not a lazy component`)
      }
      return record.component as () => Promise<{ default: unknown }>
    }

    const clientResult = await lazyComponent(clientRoutes, 'client-cutting-result')()
    const workshopResult = await lazyComponent(workshopRoutes, 'workshop-order-cutting-result')()
    expect(clientResult.default).toBe(workshopResult.default)
  })

  it('keeps the workshop editor routes out of the production namespace', () => {
    // /workshop/cutting and /workshop/banding are the process_production
    // station pages; the manage_orders editor lives under /workshop/orders/*
    // so the two never collide. The retired tabbed workspace URL stays alive
    // as a redirect into the station pages.
    const editorPaths = workshopRoutes
      .map((route) => route.path)
      .filter((path) => path.includes('cutting') && path.includes('orders'))
    expect(editorPaths).toContain('/workshop/orders/new/cutting')
    expect(editorPaths).toContain('/workshop/orders/cutting/:id')
    expect(workshopRoutes.find((r) => r.path === '/workshop/cutting')?.name).toBe(
      'workshop-cutting',
    )
    expect(workshopRoutes.find((r) => r.path === '/workshop/banding')?.name).toBe(
      'workshop-banding',
    )
    const legacy = workshopRoutes.find((r) => r.path === '/workshop/production')?.redirect
    if (typeof legacy !== 'function') throw new Error('production URL must redirect')
    const redirect = legacy as (to: { query: Record<string, unknown> }) => unknown
    expect(redirect({ query: {} })).toEqual({ path: '/workshop/cutting' })
    expect(redirect({ query: { station: 'cutting' } })).toEqual({ path: '/workshop/cutting' })
    expect(redirect({ query: { station: 'banding' } })).toEqual({ path: '/workshop/banding' })

    // Dev-mode base stripping must reach function redirects too — a raw
    // '/workshop/...' target would double the base under createWebHistory.
    const normalized = normalizeRoleRoutes(workshopRoutes, '/workshop', '/workshop/')
    const devRedirect = normalized.find((r) => r.path === '/production')?.redirect
    if (typeof devRedirect !== 'function') throw new Error('normalized redirect missing')
    const devResolve = devRedirect as (to: { query: Record<string, unknown> }) => unknown
    expect(devResolve({ query: {} })).toEqual({ path: '/cutting' })
    expect(devResolve({ query: { station: 'banding' } })).toEqual({ path: '/banding' })
  })

  // QAD-178: a `beforeEnter` guard bounces to a route path just like a
  // `redirect` does, and is written with the same absolute role-prefixed
  // literals — so it needs the same dev-base stripping. Without it, entering
  // /workshop/orders/new/cutting directly in dev redirected to a path that no
  // longer existed under the stripped base and rendered nothing.
  describe('beforeEnter guard targets', () => {
    async function runGuard(
      guard: RouteRecordRaw['beforeEnter'],
      to: Partial<RouteLocationNormalized> = {},
    ) {
      if (typeof guard !== 'function') throw new Error('expected a single guard function')
      return await guard.call(
        undefined,
        { query: {}, ...to } as RouteLocationNormalized,
        {} as RouteLocationNormalizedLoaded,
        (() => {}) as NavigationGuardNext,
      )
    }

    it('strips the dev base from the walk-in guard redirect', async () => {
      setActivePinia(createPinia())
      const normalized = normalizeRoleRoutes(workshopRoutes, '/workshop', '/workshop/')
      const guard = normalized.find((r) => r.path === '/orders/new/cutting')?.beforeEnter
      expect(await runGuard(guard)).toEqual({ path: '/orders/new' })

      // The route it lands on must exist under the same stripped base.
      expect(routePaths(normalized)).toContain('/orders/new')
    })

    it('leaves the production target untouched', async () => {
      setActivePinia(createPinia())
      const normalized = normalizeRoleRoutes(workshopRoutes, '/workshop', '/')
      const guard = normalized.find((r) => r.path === '/workshop/orders/new/cutting')?.beforeEnter
      expect(await runGuard(guard)).toEqual({ path: '/workshop/orders/new' })
    })

    it('normalizes every guard in an array and passes non-redirect verdicts through', async () => {
      const routes = [
        {
          path: '/workshop/gated',
          component: {},
          beforeEnter: [
            () => ({ path: '/workshop/elsewhere' }),
            () => true,
            () => undefined,
            () => ({ name: 'workshop-home' }),
          ],
        },
      ] as unknown as RouteRecordRaw[]
      const guards = normalizeRoleRoutes(routes, '/workshop', '/workshop/')[0]?.beforeEnter
      if (!Array.isArray(guards)) throw new Error('expected an array of guards')

      expect(await runGuard(guards[0])).toEqual({ path: '/elsewhere' })
      expect(await runGuard(guards[1])).toBe(true)
      expect(await runGuard(guards[2])).toBeUndefined()
      // Named targets are base-independent and must survive unchanged.
      expect(await runGuard(guards[3])).toEqual({ name: 'workshop-home' })
    })

    it('leaves a next()-style guard alone', () => {
      const nextStyle = (
        _to: RouteLocationNormalized,
        _from: RouteLocationNormalizedLoaded,
        next: NavigationGuardNext,
      ) => next()
      const routes = [
        { path: '/workshop/gated', component: {}, beforeEnter: nextStyle },
      ] as unknown as RouteRecordRaw[]

      // Re-wrapping would change the arity vue-router reads to decide whether
      // the guard reports through `next` or through its return value.
      expect(normalizeRoleRoutes(routes, '/workshop', '/workshop/')[0]?.beforeEnter).toBe(nextStyle)
    })
  })
})
