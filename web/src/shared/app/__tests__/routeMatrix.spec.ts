import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import process from 'node:process'

import { describe, expect, it } from 'vitest'

import { adminRoutes } from '@/apps/admin/routes'
import { clientRoutes } from '@/apps/client/routes'
import { workshopRoutes } from '@/apps/workshop/routes'
import { resolveHistoryBase } from '@/shared/app/createRoleApp'

function routePaths(routes: { path: string }[]) {
  return routes.map((route) => route.path)
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
    expect(resolveHistoryBase('/client', '/client/c')).toBe('/client/')
    expect(resolveHistoryBase('/workshop', '/workshop/profile')).toBe('/workshop/')
    expect(resolveHistoryBase('/admin', '/admin')).toBe('/admin/')
    expect(resolveHistoryBase('/client', '/c')).toBe('/')
  })

  it('keeps the documented initial route inventories', () => {
    expect(routePaths(clientRoutes)).toEqual([
      '/',
      '/auth/login',
      '/c',
      '/c/profile',
      '/c/cutting/drafts',
      '/:pathMatch(.*)*',
    ])
    expect(routePaths(workshopRoutes)).toEqual([
      '/',
      '/auth/login',
      '/workshop',
      '/workshop/profile',
      '/:pathMatch(.*)*',
    ])
    expect(routePaths(adminRoutes)).toEqual([
      '/',
      '/auth/login',
      '/admin',
      '/admin/profile',
      '/:pathMatch(.*)*',
    ])
  })

  it('does not use native visible select controls in app source', () => {
    const files = sourceFiles(join(process.cwd(), 'src'))
    const nativeSelectTag = '<sel' + 'ect'
    const offenders = files.filter((file) => readFileSync(file, 'utf8').includes(nativeSelectTag))

    expect(offenders).toEqual([])
  })
})
