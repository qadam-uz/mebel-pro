import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { useRoleConfig } from '@/shared/app/roleConfig'
import { useToast } from '@/shared/composables/useToast'
import { useAuthStore, type SessionResponse } from '@/shared/stores/auth'

/**
 * Active-sessions list + revoke/logout, shared by the client and workshop profile
 * views (CB-95). `revokeRow` removes one session optimistically and rolls back on
 * failure (CB-114); `logoutCurrent`/`logoutEverywhere` clear and bounce to login.
 */
export function useSessions() {
  const auth = useAuthStore()
  const toast = useToast()
  const router = useRouter()
  const config = useRoleConfig()

  const sessions = ref<SessionResponse[]>([])
  const logoutCurrentOpen = ref(false)
  const logoutEverywhereOpen = ref(false)
  const loggingOut = ref(false)

  async function loadSessions() {
    sessions.value = await auth.fetchSessions()
  }

  function deviceLabel(session: SessionResponse) {
    const browser =
      typeof session.device_info.browser === 'string' && session.device_info.browser.trim()
        ? session.device_info.browser
        : 'Brauzer'
    const os =
      typeof session.device_info.os === 'string' && session.device_info.os.trim()
        ? session.device_info.os
        : 'Qurilma'
    return `${browser} · ${os}`
  }

  async function revokeRow(id: string) {
    const index = sessions.value.findIndex((session) => session.id === id)
    if (index === -1) return
    const [removed] = sessions.value.splice(index, 1)
    try {
      await auth.revokeSession(id)
      toast.success('Sessiya yopildi.')
    } catch {
      sessions.value.splice(index, 0, removed)
      toast.danger("Sessiyani yopib bo'lmadi. Qayta urinib ko'ring.")
    }
  }

  // `loggingOut` feeds the confirm dialogs' :busy so the confirm can't double-fire,
  // and an API failure resurfaces as a toast instead of an unhandled rejection.
  async function logoutCurrent() {
    loggingOut.value = true
    try {
      await auth.logoutCurrent()
      await router.replace(config.loginPath)
    } catch {
      toast.danger("Chiqib bo'lmadi. Qayta urinib ko'ring.")
    } finally {
      loggingOut.value = false
    }
  }

  async function logoutEverywhere() {
    loggingOut.value = true
    try {
      await auth.logoutEverywhere()
      await router.replace(config.loginPath)
    } catch {
      toast.danger("Chiqib bo'lmadi. Qayta urinib ko'ring.")
    } finally {
      loggingOut.value = false
    }
  }

  return {
    sessions,
    logoutCurrentOpen,
    logoutEverywhereOpen,
    loggingOut,
    loadSessions,
    deviceLabel,
    revokeRow,
    logoutCurrent,
    logoutEverywhere,
  }
}
