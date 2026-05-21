<script setup lang="ts">
// Login + password card shared by the workshop and admin apps (.auth-card).
// The parent passes a `submit` action (the store login) and copy; this
// component owns the form, the inline error, and a simple client-side lockout
// after 5 bad attempts (15 min), mirroring the prototype.
import { computed, ref } from 'vue'
import { ApiError } from '@/shared/api/client'
import { t } from '@/shared/i18n'
import type { Credentials } from '@/shared/api/auth'
import FormField from '../FormField.vue'
import AppButton from '../AppButton.vue'

const props = defineProps<{
  subtitle: string
  brandLabel: string
  submit: (creds: Credentials) => Promise<void>
  footer?: string
}>()

const login = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)
const attempts = ref(0)
const lockedUntil = ref<Date | null>(null)

const locked = computed(() => lockedUntil.value !== null && lockedUntil.value > new Date())
const lockoutText = computed(() => {
  if (!lockedUntil.value) return ''
  const hh = String(lockedUntil.value.getHours()).padStart(2, '0')
  const mm = String(lockedUntil.value.getMinutes()).padStart(2, '0')
  return t('auth.lockout', { time: `${hh}:${mm}` })
})

async function onSubmit() {
  if (locked.value || busy.value) return
  error.value = ''
  busy.value = true
  try {
    await props.submit({ login: login.value, password: password.value })
  } catch (e) {
    attempts.value += 1
    if (attempts.value >= 5) {
      lockedUntil.value = new Date(Date.now() + 15 * 60 * 1000)
    }
    error.value = e instanceof ApiError ? e.detail : t('auth.wrongCredentials')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="auth-wrap">
    <div class="auth-card">
      <span class="brand">
        <span class="mk">M</span>
        <span style="font-family: var(--f-display); font-size: 19px; font-weight: 600">
          {{ t('common.appName')
          }}<small
            style="
              display: block;
              font-family: var(--f-ui);
              font-size: 11px;
              color: var(--ink-6);
              font-weight: 500;
              letter-spacing: 0.04em;
              text-transform: uppercase;
            "
            >{{ brandLabel }}</small
          >
        </span>
      </span>
      <h1>{{ subtitle }}</h1>
      <p class="sub">{{ t('auth.forgotPassword') }}</p>

      <div v-if="locked" class="lockout">{{ lockoutText }}</div>
      <div v-else-if="error" class="err-msg">{{ error }}</div>

      <form novalidate @submit.prevent="onSubmit">
        <FormField v-model="login" :label="t('auth.login')" autocomplete="username" required />
        <FormField
          v-model="password"
          type="password"
          :label="t('auth.password')"
          autocomplete="current-password"
          required
        />
        <AppButton
          variant="primary"
          size="lg"
          block
          type="submit"
          :loading="busy"
          :disabled="locked"
        >
          {{ t('auth.signIn') }}
        </AppButton>
      </form>

      <div v-if="footer" class="meta">{{ footer }}</div>
    </div>
  </div>
</template>
