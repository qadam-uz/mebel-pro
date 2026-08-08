<script setup lang="ts">
import BrandMark from '@/shared/components/BrandMark.vue'
import { reactive } from 'vue'
import { RouterLink } from 'vue-router'

import {
  clearFieldErrors,
  focusFirstFieldError,
  requiredText,
  type FieldErrors,
} from '@/shared/app/adminValidation'
import { useStaffLogin } from '@/shared/composables/useStaffLogin'

const {
  config,
  login,
  password,
  isSubmitting,
  error,
  errorText,
  submit: submitLogin,
} = useStaffLogin()
type LoginField = 'login' | 'password'
const fieldErrors = reactive<FieldErrors<LoginField>>({})
const fieldIds: Record<LoginField, string> = {
  login: 'admin-login',
  password: 'admin-password',
}
const fieldOrder: LoginField[] = ['login', 'password']

// AB-13 kept a local Uzbek map here because the shared composable's own map was
// English. QAD-163 moved the Uzbek copy into the composable, so both sign-in
// screens now read from one source and this duplicate is gone.

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
        <BrandMark :size="32" />
        <span class="client-brand-name">Mebel Pro</span>
      </RouterLink>

      <form class="space-y-4" novalidate @submit.prevent="submit">
        <h1 id="admin-login-title" class="font-display text-3xl font-semibold leading-tight">
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
