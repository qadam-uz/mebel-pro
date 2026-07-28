import type { PermissionGrant } from '@/shared/stores/auth'

export const workshopPermissions = {
  // Read-only order access, named for what the server actually enforces
  // (QAD-166). It grants no dashboard section of its own.
  viewOrders: 'view_orders',
  manageOrders: 'manage_orders',
  processProduction: 'process_production',
  manageCatalog: 'manage_catalog',
  manageInventory: 'manage_inventory',
  manageFinance: 'manage_finance',
  viewFinanceReports: 'view_finance_reports',
} as const

export type WorkshopPermission = (typeof workshopPermissions)[keyof typeof workshopPermissions]

export interface WorkshopPrincipal {
  is_owner?: boolean
  grants?: PermissionGrant[]
}

export interface WorkshopRouteRequirement {
  ownerOnly?: boolean
  any?: readonly WorkshopPermission[]
  branchParam?: string
}

export interface PermissionBranch {
  id: string
}

function routeParamValue(value: unknown): string | null {
  if (typeof value === 'string' && value.trim()) return value
  if (Array.isArray(value) && typeof value[0] === 'string' && value[0].trim()) return value[0]
  return null
}

function grants(principal: WorkshopPrincipal | null | undefined): PermissionGrant[] {
  return principal?.grants ?? []
}

function includesPermission(
  permissions: readonly WorkshopPermission[],
  permission: string,
): boolean {
  return (permissions as readonly string[]).includes(permission)
}

export function isWorkshopOwner(principal: WorkshopPrincipal | null | undefined): boolean {
  return principal?.is_owner === true
}

export function hasPermissionOnBranch(
  principal: WorkshopPrincipal | null | undefined,
  permission: WorkshopPermission,
  branchId: string | null | undefined,
): boolean {
  if (isWorkshopOwner(principal)) return true
  if (!branchId) return false
  return grants(principal).some(
    (grant) => grant.branch_id === branchId && grant.permission === permission,
  )
}

export function hasAnyPermissionOnBranch(
  principal: WorkshopPrincipal | null | undefined,
  permissions: readonly WorkshopPermission[],
  branchId: string | null | undefined,
): boolean {
  if (isWorkshopOwner(principal)) return true
  if (!branchId || permissions.length === 0) return false
  return grants(principal).some(
    (grant) => grant.branch_id === branchId && includesPermission(permissions, grant.permission),
  )
}

export function hasAnyPermission(
  principal: WorkshopPrincipal | null | undefined,
  permissions: readonly WorkshopPermission[],
): boolean {
  if (isWorkshopOwner(principal)) return true
  if (permissions.length === 0) return false
  return grants(principal).some((grant) => includesPermission(permissions, grant.permission))
}

export function branchesWithAnyPermission<TBranch extends PermissionBranch>(
  principal: WorkshopPrincipal | null | undefined,
  branches: TBranch[],
  permissions: readonly WorkshopPermission[],
): TBranch[] {
  if (isWorkshopOwner(principal)) return branches
  return branches.filter((branch) => hasAnyPermissionOnBranch(principal, permissions, branch.id))
}

export function canAccessWorkshopRoute(
  principal: WorkshopPrincipal | null | undefined,
  requirement: WorkshopRouteRequirement | null | undefined,
  params: Record<string, unknown> = {},
): boolean {
  if (!requirement) return true
  if (isWorkshopOwner(principal)) return true
  if (requirement.ownerOnly) return false

  const permissions = requirement.any ?? []
  if (permissions.length === 0) return true

  if (requirement.branchParam) {
    return hasAnyPermissionOnBranch(
      principal,
      permissions,
      routeParamValue(params[requirement.branchParam]),
    )
  }

  return hasAnyPermission(principal, permissions)
}
