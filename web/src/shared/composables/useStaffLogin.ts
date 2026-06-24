import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { safeRedirectPath } from '@/shared/app/redirect'
import { useRoleConfig } from '@/shared/app/roleConfig'
import { useAuthStore } from '@/shared/stores/auth'

const STAFF_ERROR_TEXT: Record<string, string> = {
  invalid_credentials: 'Credentials do not match an active account.',
  account_locked: 'Account is locked. Try again later.',
  account_blocked: 'Account is blocked.',
  network_error: 'API is not reachable.',
}

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
    error.value ? (STAFF_ERROR_TEXT[error.value] ?? 'Sign-in failed.') : null,
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
