<script setup lang="ts">
import { computed, reactive } from 'vue'
import { RouterLink } from 'vue-router'

import {
  clearFieldErrors,
  focusFirstFieldError,
  requiredText,
  type FieldErrors,
} from '@/shared/app/adminValidation'
import { useStaffLogin } from '@/shared/composables/useStaffLogin'

const { config, login, password, isSubmitting, error, submit: submitLogin } = useStaffLogin()
type LoginField = 'login' | 'password'
const fieldErrors = reactive<FieldErrors<LoginField>>({})
const fieldIds: Record<LoginField, string> = {
  login: 'admin-login',
  password: 'admin-password',
}
const fieldOrder: LoginField[] = ['login', 'password']

// AB-13: useStaffLogin is shared with the workshop login, so map the error CODE
// to Uzbek locally here rather than translating the shared English text map
// (which would change the colleague-owned workshop SPA's copy).
const ADMIN_LOGIN_ERROR_UZ: Record<string, string> = {
  invalid_credentials: "Login yoki parol noto'g'ri.",
  account_locked: "Hisob vaqtincha bloklangan. Birozdan so'ng urinib ko'ring.",
  account_blocked: 'Hisob bloklangan.',
  network_error: "Server bilan bog'lanib bo'lmadi.",
}
const errorText = computed(() =>
  error.value ? (ADMIN_LOGIN_ERROR_UZ[error.value] ?? "Kirib bo'lmadi.") : null,
)

function clearLoginField(field: LoginField) {
  delete fieldErrors[field]
  error.value = null
}

function validateLogin() {
  clearFieldErrors(fieldErrors)
  fieldErrors.login = requiredText(login.value, 'Loginni kiriting.') ?? undefined
  fieldErrors.password = requiredText(password.value, 'Parolni kiriting.') ?? undefined
  const hasErrors = fieldOrder.some((field) => Boolean(fieldErrors[field]))
  if (hasErrors) focusFirstFieldError(fieldErrors, fieldOrder, fieldIds)
  return !hasErrors
}

async function submit() {
  if (!validateLogin()) return
  await submitLogin()
}
</script>

<template>
  <main class="admin-auth-wrap">
    <section class="admin-auth-card" aria-labelledby="admin-login-title">
      <RouterLink :to="config.homePath" class="client-brand mb-7 inline-flex">
        <img src="/favicon.svg" alt="" class="size-8" />
        <span class="client-brand-name">Mebel Pro</span>
      </RouterLink>

      <form class="space-y-4" novalidate @submit.prevent="submit">
        <h1 id="admin-login-title" class="font-serif text-3xl font-semibold leading-tight">
          Admin paneliga kirish
        </h1>

        <label class="admin-field" for="admin-login">
          <span class="admin-field-label">Login</span>
          <input
            id="admin-login"
            v-model="login"
            type="text"
            autocomplete="username"
            required
            :aria-invalid="!!fieldErrors.login"
            :aria-describedby="fieldErrors.login ? 'admin-login-error' : undefined"
            @input="clearLoginField('login')"
          />
          <span
            v-if="fieldErrors.login"
            id="admin-login-error"
            class="admin-field-error"
            role="alert"
          >
            {{ fieldErrors.login }}
          </span>
        </label>

        <label class="admin-field" for="admin-password">
          <span class="admin-field-label">Parol</span>
          <input
            id="admin-password"
            v-model="password"
            type="password"
            autocomplete="current-password"
            required
            :aria-invalid="!!fieldErrors.password"
            :aria-describedby="fieldErrors.password ? 'admin-password-error' : undefined"
            @input="clearLoginField('password')"
          />
          <span
            v-if="fieldErrors.password"
            id="admin-password-error"
            class="admin-field-error"
            role="alert"
          >
            {{ fieldErrors.password }}
          </span>
        </label>

        <p
          v-if="errorText"
          class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          role="alert"
          aria-live="assertive"
        >
          {{ errorText }}
        </p>

        <button type="submit" class="mp-button mp-button-primary w-full" :disabled="isSubmitting">
          {{ isSubmitting ? 'Tekshirilmoqda' : 'Kirish' }}
        </button>
      </form>
    </section>
  </main>
</template>
