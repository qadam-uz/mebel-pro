import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api } from '@/shared/api/client'
import { useAuthStore, type SessionResponse } from '@/shared/stores/auth'

export interface BranchContextItem {
  id: string
  name: string
  address: string
  phone: string
  status: 'active' | 'temporarily_closed'
  closed_reason: string | null
  permissions: string[]
}

export interface WorkshopUser {
  id: string
  workshop_id: string
  login: string
  full_name: string
  phone: string
  is_owner: boolean
  home_branch_id: string | null
  status: 'active' | 'blocked'
  password_reset_required: boolean
  grants: Array<{ permission: string; branch_id: string }>
}

export const permissionCatalog = [
  'view_dashboard',
  'manage_orders',
  'process_production',
  'manage_catalog',
  'manage_inventory',
  'manage_finance',
  'view_finance_reports',
] as const

export const useWorkshopStore = defineStore('workshop', () => {
  const branches = ref<BranchContextItem[]>([])
  const users = ref<WorkshopUser[]>([])
  const selectedUser = ref<WorkshopUser | null>(null)
  const sessions = ref<SessionResponse[]>([])
  const lastTempPassword = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const auth = useAuthStore()

  function authInit() {
    return { accessToken: auth.accessToken }
  }

  async function loadBranchContext() {
    try {
      const response = await api.get<{ branches: BranchContextItem[] }>(
        '/workshop/branch-context',
        authInit(),
      )
      branches.value = response.branches
    } catch {
      error.value = 'branch_context_load_failed'
      throw error.value
    }
  }

  async function loadUsers() {
    loading.value = true
    error.value = null
    try {
      users.value = await api.get<WorkshopUser[]>('/workshop/users', authInit())
    } catch {
      error.value = 'users_load_failed'
    } finally {
      loading.value = false
    }
  }

  async function createUser(payload: unknown) {
    error.value = null
    const response = await api.post<{ user: WorkshopUser; temp_password: string }>(
      '/workshop/users',
      payload,
      authInit(),
    )
    users.value = [...users.value, response.user]
    lastTempPassword.value = response.temp_password
    return response
  }

  async function loadUser(id: string) {
    loading.value = true
    error.value = null
    try {
      selectedUser.value = await api.get<WorkshopUser>(`/workshop/users/${id}`, authInit())
      sessions.value = (
        await api.get<{ sessions: SessionResponse[] }>(`/workshop/users/${id}/sessions`, authInit())
      ).sessions
    } catch {
      error.value = 'user_load_failed'
    } finally {
      loading.value = false
    }
  }

  async function replaceGrants(
    id: string,
    grants: Array<{ permission: string; branch_id: string }>,
  ) {
    error.value = null
    selectedUser.value = await api.put<WorkshopUser>(
      `/workshop/users/${id}/grants`,
      { grants },
      authInit(),
    )
  }

  async function resetPassword(id: string) {
    error.value = null
    const response = await api.post<{ user: WorkshopUser; temp_password: string }>(
      `/workshop/users/${id}/reset-password`,
      undefined,
      authInit(),
    )
    selectedUser.value = response.user
    lastTempPassword.value = response.temp_password
  }

  async function blockUser(id: string, reason: string) {
    error.value = null
    selectedUser.value = await api.post<WorkshopUser>(
      `/workshop/users/${id}/block`,
      { reason },
      authInit(),
    )
  }

  async function unblockUser(id: string) {
    error.value = null
    selectedUser.value = await api.post<WorkshopUser>(
      `/workshop/users/${id}/unblock`,
      undefined,
      authInit(),
    )
  }

  async function revokeUserSessions(id: string) {
    error.value = null
    await api.del(`/workshop/users/${id}/sessions`, authInit())
    sessions.value = []
  }

  async function revokeUserSession(id: string, sessionId: string) {
    error.value = null
    await api.del(`/workshop/users/${id}/sessions/${sessionId}`, authInit())
    sessions.value = sessions.value.filter((session) => session.id !== sessionId)
  }

  return {
    branches,
    users,
    selectedUser,
    sessions,
    lastTempPassword,
    loading,
    error,
    loadBranchContext,
    loadUsers,
    createUser,
    loadUser,
    replaceGrants,
    resetPassword,
    blockUser,
    unblockUser,
    revokeUserSessions,
    revokeUserSession,
  }
})
