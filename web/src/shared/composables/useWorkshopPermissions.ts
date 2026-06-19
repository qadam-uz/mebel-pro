import { computed } from 'vue'

import {
  branchesWithAnyPermission,
  canAccessWorkshopRoute,
  hasAnyPermission,
  hasAnyPermissionOnBranch,
  hasPermissionOnBranch,
  isWorkshopOwner,
  type PermissionBranch,
  type WorkshopPermission,
  type WorkshopRouteRequirement,
} from '@/shared/app/workshopPermissions'
import { useAuthStore } from '@/shared/stores/auth'

export function useWorkshopPermissions() {
  const auth = useAuthStore()
  const principal = computed(() => auth.me)
  const isOwner = computed(() => isWorkshopOwner(principal.value))
  const hasAnyGrant = computed(() => isOwner.value || (principal.value?.grants.length ?? 0) > 0)

  function can(permission: WorkshopPermission): boolean {
    return hasAnyPermission(principal.value, [permission])
  }

  function canAny(permissions: readonly WorkshopPermission[]): boolean {
    return hasAnyPermission(principal.value, permissions)
  }

  function canOnBranch(permission: WorkshopPermission, branchId: string | null | undefined) {
    return hasPermissionOnBranch(principal.value, permission, branchId)
  }

  function canAnyOnBranch(
    permissions: readonly WorkshopPermission[],
    branchId: string | null | undefined,
  ): boolean {
    return hasAnyPermissionOnBranch(principal.value, permissions, branchId)
  }

  function accessibleBranches<TBranch extends PermissionBranch>(
    branches: TBranch[],
    permissions: readonly WorkshopPermission[],
  ): TBranch[] {
    return branchesWithAnyPermission(principal.value, branches, permissions)
  }

  function canAccessRoute(
    requirement: WorkshopRouteRequirement | null | undefined,
    params?: Record<string, unknown>,
  ): boolean {
    return canAccessWorkshopRoute(principal.value, requirement, params)
  }

  return {
    isOwner,
    hasAnyGrant,
    can,
    canAny,
    canOnBranch,
    canAnyOnBranch,
    accessibleBranches,
    canAccessRoute,
  }
}
