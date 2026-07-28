import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { safeRedirectPath } from '@/shared/app/redirect'
import { useRoleConfig } from '@/shared/app/roleConfig'
import { useAuthStore } from '@/shared/stores/auth'

/**
 * Sign-in failures, in Uzbek — the only shipped locale. This used to be an
 * English map that both consuming views shadowed with byte-identical Uzbek
 * copies of their own; one map, one voice, and a forgotten call site can no
 * longer render English (QAD-163).
 */
const STAFF_ERROR_TEXT: Record<string, string> = {
  invalid_credentials: "Login yoki parol noto'g'ri.",
  account_locked: "Hisob vaqtincha bloklangan. Birozdan so'ng urinib ko'ring.",
  account_blocked: 'Hisob bloklangan — ustaxona rahbariga murojaat qiling.',
  login_rate_limited: "Juda ko'p urinish. Birozdan so'ng urinib ko'ring.",
  network_error: "Server bilan bog'lanib bo'lmadi. Internet aloqasini tekshiring.",
}

export const STAFF_LOGIN_FALLBACK = "Kirib bo'lmadi. Qayta urinib ko'ring."

/**
 * Password-login logic shared by the admin + workshop sign-in views (CB-94). The
 * role (from the injected role config) selects which auth call runs, so each SPA
 * ships only its own login markup.
 */
export function useStaffLogin() {
  const config = useRoleConfig()
  const auth = useAuthStore()
  const route = useRoute()
  const router = useRouter()

  const login = ref('')
  const password = ref('')
  const isSubmitting = ref(false)
  const error = ref<string | null>(null)

  const redirectTo = computed(() => safeRedirectPath(route.query.redirect, config.homePath))
  const errorText = computed(() =>
    error.value ? (STAFF_ERROR_TEXT[error.value] ?? STAFF_LOGIN_FALLBACK) : null,
  )

  async function submit() {
    error.value = null
    isSubmitting.value = true
    try {
      if (config.role === 'admin') {
        await auth.platformLogin(login.value, password.value)
      } else if (config.role === 'workshop') {
        await auth.workshopLogin(login.value, password.value)
      }
      await router.replace(redirectTo.value)
    } catch {
      error.value = auth.lastError
    } finally {
      isSubmitting.value = false
    }
  }

  return { config, login, password, isSubmitting, error, errorText, submit }
}
