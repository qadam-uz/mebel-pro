import { computed, ref } from 'vue'
import { defineStore, getActivePinia, type StoreGeneric } from 'pinia'

import { ApiError, api } from '@/shared/api/client'
import type { RoleKey } from '@/shared/app/roleConfig'

export type PrincipalType = 'platform_user' | 'workshop_user' | 'client'
export type AuthStatus = 'idle' | 'loading' | 'authenticated' | 'anonymous'

export interface PermissionGrant {
  permission: string
  branch_id: string
}

export interface MeResponse {
  principal_type: PrincipalType
  principal_id: string
  session_id: string
  password_reset_required: boolean
  workshop_id: string | null
  is_owner: boolean
  grants: PermissionGrant[]
  login: string | null
  full_name: string | null
  phone: string | null
  name: string | null
  preferred_branch_id: string | null
  status: 'active' | 'blocked' | null
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  access_token_expires_at: string
  me: MeResponse
}

export interface SessionResponse {
  id: string
  created_at: string
  last_used_at: string
  access_token_expires_at: string
  refresh_token_expires_at: string
  device_info: Record<string, unknown>
  is_current: boolean
}

interface ResettableStore extends StoreGeneric {
  reset?: () => void
}

const rolePrincipal: Record<RoleKey, PrincipalType> = {
  admin: 'platform_user',
  workshop: 'workshop_user',
  client: 'client',
}

function errorCode(error: unknown): string {
  if (error instanceof ApiError && typeof error.body === 'object' && error.body) {
    return String((error.body as { code?: unknown }).code ?? 'api_error')
  }
  return 'network_error'
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(null)
  const me = ref<MeResponse | null>(null)
  const status = ref<AuthStatus>('idle')
  const restored = ref(false)
  const lastError = ref<string | null>(null)
  const lastErrorDetails = ref<Record<string, unknown> | null>(null)

  const displayName = computed(
    () => me.value?.full_name ?? me.value?.name ?? me.value?.login ?? me.value?.phone ?? 'Account',
  )
  const isAuthenticated = computed(() => accessToken.value !== null && me.value !== null)

  function applyToken(response: TokenResponse) {
    accessToken.value = response.access_token
    me.value = response.me
    status.value = 'authenticated'
    lastError.value = null
  }

  function clear() {
    accessToken.value = null
    me.value = null
    status.value = 'anonymous'
    resetSessionStores()
  }

  function resetSessionStores() {
    const pinia = getActivePinia()
    if (!pinia) return
    const stores = (pinia as unknown as { _s: Map<string, ResettableStore> })._s
    for (const store of stores.values()) {
      if (store.$id === 'auth') continue
      store.reset?.()
    }
  }

  async function restore() {
    if (restored.value) return
    restored.value = true
    status.value = 'loading'
    try {
      applyToken(await api.post<TokenResponse>('/auth/refresh'))
    } catch {
      clear()
    }
  }

  // On-demand silent refresh used by the API client's 401 interceptor (CB-08).
  // Returns the new access token, or null when the session can't be renewed.
  async function refreshSession(): Promise<string | null> {
    try {
      const response = await api.post<TokenResponse>('/auth/refresh')
      applyToken(response)
      return response.access_token
    } catch {
      clear()
      return null
    }
  }

  // Re-read the principal without rotating the session. Grants can be revoked
  // while a tab is open, and the shell is built from the `me` captured at
  // sign-in — so a refused request is the app's cue to re-read it (QAD-172).
  // Concurrent callers (a screen firing several requests at once) share one
  // round-trip; a failed re-read leaves the last known principal in place
  // rather than logging a working session out.
  let meInFlight: Promise<void> | null = null
  async function refreshMe(): Promise<void> {
    if (!accessToken.value) return
    if (!meInFlight) {
      meInFlight = api
        .get<MeResponse>('/auth/me', authInit())
        .then((response) => {
          me.value = response
        })
        .catch(() => undefined)
        .finally(() => {
          meInFlight = null
        })
    }
    return meInFlight
  }

  function isAllowedFor(role: RoleKey) {
    return me.value?.principal_type === rolePrincipal[role]
  }

  async function platformLogin(login: string, password: string) {
    status.value = 'loading'
    try {
      applyToken(await api.post<TokenResponse>('/auth/platform/login', { login, password }))
    } catch (error) {
      clear()
      lastError.value = errorCode(error)
      throw error
    }
  }

  async function workshopLogin(login: string, password: string) {
    status.value = 'loading'
    try {
      applyToken(
        await api.post<TokenResponse>('/auth/workshop/login', {
          login,
          password,
        }),
      )
    } catch (error) {
      clear()
      lastError.value = errorCode(error)
      throw error
    }
  }

  async function requestClientOtp(phone: string) {
    lastError.value = null
    try {
      return await api.post<{ phone: string; expires_at: string; resend_after_seconds: number }>(
        '/auth/client/otp/request',
        { phone },
      )
    } catch (error) {
      lastError.value = errorCode(error)
      lastErrorDetails.value =
        error instanceof ApiError && typeof error.body === 'object' && error.body
          ? ((error.body as { details?: Record<string, unknown> }).details ?? null)
          : null
      throw error
    }
  }

  async function verifyClientOtp(phone: string, code: string, name?: string) {
    status.value = 'loading'
    try {
      const response = await api.post<TokenResponse | { is_new: true }>('/auth/client/otp/verify', {
        phone,
        code,
        name,
      })
      if ('is_new' in response) {
        status.value = 'anonymous'
        return response
      }
      applyToken(response)
      return response
    } catch (error) {
      status.value = accessToken.value ? 'authenticated' : 'anonymous'
      lastError.value = errorCode(error)
      lastErrorDetails.value =
        error instanceof ApiError && typeof error.body === 'object' && error.body
          ? ((error.body as { details?: Record<string, unknown> }).details ?? null)
          : null
      throw error
    }
  }

  async function changePassword(currentPassword: string, newPassword: string) {
    try {
      await api.post(
        '/auth/password/change',
        {
          current_password: currentPassword,
          new_password: newPassword,
        },
        authInit(),
      )
      if (me.value) me.value = { ...me.value, password_reset_required: false }
      lastError.value = null
    } catch (error) {
      lastError.value = errorCode(error)
      throw error
    }
  }

  async function fetchSessions() {
    return await api.get<SessionResponse[]>('/auth/sessions', authInit())
  }

  async function logoutCurrent() {
    if (accessToken.value) {
      await api.del('/auth/sessions/current', authInit()).catch(() => undefined)
    }
    clear()
  }

  async function logoutEverywhere() {
    if (accessToken.value) {
      await api.del('/auth/sessions', authInit()).catch(() => undefined)
    }
    clear()
  }

  // Revoke ONE other session by id (CB-114). Throws on failure so the caller can
  // roll back its optimistic UI removal; never touches the current session here.
  async function revokeSession(sessionId: string) {
    await api.del(`/auth/sessions/${sessionId}`, authInit())
  }

  function authInit() {
    return { accessToken: accessToken.value }
  }

  return {
    accessToken,
    me,
    status,
    restored,
    lastError,
    lastErrorDetails,
    displayName,
    isAuthenticated,
    restore,
    refreshSession,
    refreshMe,
    isAllowedFor,
    platformLogin,
    workshopLogin,
    requestClientOtp,
    verifyClientOtp,
    changePassword,
    fetchSessions,
    logoutCurrent,
    logoutEverywhere,
    revokeSession,
  }
})
