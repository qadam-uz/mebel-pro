import { normalizeRolePath, resolveHistoryBase } from '@/shared/app/createRoleApp'
import { useRoleConfig, type RoleKey } from '@/shared/app/roleConfig'

const localBaseByRole: Record<RoleKey, string> = {
  admin: '/admin',
  workshop: '/workshop',
  client: '/client',
}

export function rolePath(
  path: string,
  role: RoleKey,
  pathname = typeof window === 'undefined' ? '/' : window.location.pathname,
  isDev = import.meta.env.DEV,
): string {
  const localBase = localBaseByRole[role]
  return normalizeRolePath(path, localBase, resolveHistoryBase(localBase, pathname, isDev))
}

export function useRolePath(): (path: string) => string {
  const config = useRoleConfig()
  return (path: string) => rolePath(path, config.role)
}
