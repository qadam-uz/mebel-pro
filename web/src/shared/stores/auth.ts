// Shared auth store, parameterised by app key. Each app calls
// createAuthStore({ app, loginRoute, changePasswordRoute }) once and re-uses
// the returned useAuth() composable. Holds the principal (/auth/me), token
// state, the workshop grant set + can() helper, and the branch-picker context.

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { AppKey } from '@/shared/api/storage'
import {
  clearTokens,
  getSelectedBranch,
  getTokens,
  setSelectedBranch,
  setTokens,
} from '@/shared/api/storage'
import * as authApi from '@/shared/api/auth'
import type { Credentials } from '@/shared/api/auth'
import type { Me, Permission } from '@/shared/types'

export interface AuthStoreConfig {
  app: AppKey
}

// 'all' is the branch-picker sentinel meaning "every branch I can scope to".
export type BranchSelection = string | 'all'

export function createAuthStore(config: AuthStoreConfig) {
  return defineStore(`auth:${config.app}`, () => {
    const me = ref<Me | null>(null)
    const loading = ref(false)
    const initialized = ref(false)
    const selectedBranch = ref<BranchSelection>(
      (getSelectedBranch(config.app) as BranchSelection | null) ?? 'all',
    )

    // NB: read the reactive `me` first. If `getTokens()` (non-reactive
    // localStorage) is evaluated first and returns null, the && short-circuits
    // before `me.value` is ever read, so the computed tracks no reactive dep and
    // caches `false` forever — login then can't flip it without a full reload.
    const isAuthenticated = computed(() => me.value !== null && getTokens(config.app) !== null)
    const isOwner = computed(() => me.value?.is_owner === true)
    const forcePasswordChange = computed(() => me.value?.force_password_change === true)
    const grants = computed(() => me.value?.grants ?? [])

    // can(permission, branchId?) — owner allowed everywhere; otherwise the
    // (permission, branch) pair must be granted. branchId omitted → holds the
    // permission on at least one branch.
    function can(permission: Permission, branchId?: string): boolean {
      if (!me.value) return false
      if (me.value.is_owner) return true
      const branches = grants.value
        .filter((g) => g.permission === permission)
        .map((g) => g.branch_id)
      if (branches.length === 0) return false
      return branchId == null ? true : branches.includes(branchId)
    }

    // Branch ids the principal can scope to (derived from grants; owner = all
    // is represented by the 'all' sentinel — branch list comes from the API).
    const grantedBranchIds = computed(() => {
      const ids = new Set<string>()
      for (const g of grants.value) ids.add(g.branch_id)
      if (me.value?.home_branch_id) ids.add(me.value.home_branch_id)
      return [...ids]
    })

    function selectBranch(selection: BranchSelection): void {
      selectedBranch.value = selection
      setSelectedBranch(config.app, selection === 'all' ? null : selection)
    }

    // The effective branch id to scope an API call to, or null for "all".
    const branchScope = computed<string | null>(() =>
      selectedBranch.value === 'all' ? null : selectedBranch.value,
    )

    async function fetchMe(): Promise<void> {
      me.value = await authApi.fetchMe()
    }

    // Loads the principal if a token is present; safe to call repeatedly. Used
    // by route guards before the first navigation.
    async function ensureLoaded(): Promise<void> {
      if (initialized.value) return
      initialized.value = true
      if (getTokens(config.app) === null) return
      loading.value = true
      try {
        await fetchMe()
      } catch {
        clearTokens(config.app)
        me.value = null
      } finally {
        loading.value = false
      }
    }

    async function loginPlatform(creds: Credentials): Promise<void> {
      const tokens = await authApi.loginPlatform(creds)
      setTokens(config.app, { access: tokens.access_token, refresh: tokens.refresh_token })
      await fetchMe()
    }

    async function loginWorkshop(creds: Credentials): Promise<void> {
      const tokens = await authApi.loginWorkshop(creds)
      setTokens(config.app, { access: tokens.access_token, refresh: tokens.refresh_token })
      await fetchMe()
    }

    async function loginClientTelegram(payload: Record<string, unknown>): Promise<void> {
      const tokens = await authApi.loginClientTelegram(payload)
      setTokens(config.app, { access: tokens.access_token, refresh: tokens.refresh_token })
      await fetchMe()
    }

    async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
      await authApi.changePassword(currentPassword, newPassword)
      // A successful change clears the force-change flag — refresh the principal.
      await fetchMe()
    }

    async function logout(): Promise<void> {
      try {
        await authApi.logout()
      } catch {
        /* even if the call fails, drop local state */
      }
      clearTokens(config.app)
      me.value = null
      initialized.value = false
    }

    return {
      me,
      loading,
      initialized,
      selectedBranch,
      isAuthenticated,
      isOwner,
      forcePasswordChange,
      grants,
      grantedBranchIds,
      branchScope,
      can,
      selectBranch,
      fetchMe,
      ensureLoaded,
      loginPlatform,
      loginWorkshop,
      loginClientTelegram,
      changePassword,
      logout,
    }
  })
}
