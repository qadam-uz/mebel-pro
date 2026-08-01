import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { safeRedirectPath } from '@/shared/app/redirect'
import { useRoleConfig } from '@/shared/app/roleConfig'
import { translate } from '@/shared/i18n'
import { useAuthStore } from '@/shared/stores/auth'

/**
 * Sign-in failures, keyed by the backend's error code. This used to be an
 * English map that both consuming views shadowed with byte-identical Uzbek
 * copies of their own; one map, one voice, and a forgotten call site can no
 * longer render English (QAD-163).
 *
 * Built per call rather than held in a module constant: a constant would freeze
 * the copy at whichever locale was active when this module first evaluated.
 */
function staffErrorText(): Record<string, string> {
  return {
    invalid_credentials: translate('shell.error.invalid_credentials'),
    account_locked: translate('shell.error.account_locked'),
    account_blocked: translate('shell.error.account_blocked'),
    login_rate_limited: translate('shell.error.login_rate_limited'),
    network_error: translate('shell.error.network_error'),
  }
}

/** Generic sign-in failure — the message for a code the map does not cover. */
export function staffLoginFallback(): string {
  return translate('shell.login.errorFallback')
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
    error.value ? (staffErrorText()[error.value] ?? staffLoginFallback()) : null,
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
