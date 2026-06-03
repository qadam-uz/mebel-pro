<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { useRoleConfig } from '@/shared/app/roleConfig'
import { useAuthStore } from '@/shared/stores/auth'

const config = useRoleConfig()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const login = ref('')
const password = ref('')
const workshopCode = ref('')
const phone = ref('+998')
const otpCode = ref('')
const clientName = ref('')
const clientStep = ref<'phone' | 'code' | 'name'>('phone')
const resendAfter = ref<number | null>(null)
const isSubmitting = ref(false)
const error = ref<string | null>(null)

const redirectTo = computed(() => {
  const redirect = route.query.redirect
  return typeof redirect === 'string' && redirect.startsWith('/') ? redirect : config.homePath
})

const errorText = computed(() => {
  const code = error.value
  if (!code) return null
  return (
    {
      invalid_credentials: 'Credentials do not match an active account.',
      account_locked: 'Account is locked. Try again later.',
      account_blocked: 'Account is blocked.',
      invalid_phone: 'Enter a valid +998 phone number.',
      phone_unreachable_on_telegram: 'Telegram could not reach this phone number.',
      code_send_rate_limited: 'Code sending is paused. Try again later.',
      invalid_code: 'The code is not valid.',
      code_expired: 'The code expired. Request a new one.',
      too_many_attempts: 'Too many attempts. Request a new code.',
      name_required: 'Enter your name to finish registration.',
      network_error: 'API is not reachable.',
    }[code] ?? 'Sign-in failed.'
  )
})

async function finish() {
  await router.replace(redirectTo.value)
}

async function submitPasswordLogin() {
  error.value = null
  isSubmitting.value = true
  try {
    if (config.role === 'admin') {
      await auth.platformLogin(login.value, password.value)
    } else if (config.role === 'workshop') {
      await auth.workshopLogin(workshopCode.value, login.value, password.value)
    }
    await finish()
  } catch {
    error.value = auth.lastError
  } finally {
    isSubmitting.value = false
  }
}

async function sendOtp() {
  error.value = null
  isSubmitting.value = true
  try {
    const response = await auth.requestClientOtp(phone.value)
    resendAfter.value = response.resend_after_seconds
    clientStep.value = 'code'
  } catch {
    error.value = auth.lastError
  } finally {
    isSubmitting.value = false
  }
}

async function verifyOtp() {
  error.value = null
  isSubmitting.value = true
  try {
    const response = await auth.verifyClientOtp(
      phone.value,
      otpCode.value,
      clientStep.value === 'name' ? clientName.value : undefined,
    )
    if ('is_new' in response) {
      clientStep.value = 'name'
      return
    }
    await finish()
  } catch {
    error.value = auth.lastError
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <main class="grid min-h-screen bg-bg px-4 py-8 text-ink md:grid-cols-[1fr_minmax(360px,460px)]">
    <section class="flex min-h-[320px] flex-col justify-between py-6 md:px-8">
      <RouterLink :to="config.homePath" class="flex items-center gap-3">
        <img src="/favicon.svg" alt="" class="size-9" />
        <span class="font-serif text-2xl font-semibold">{{ config.productLabel }}</span>
      </RouterLink>

      <div class="max-w-xl">
        <p class="mp-chip mb-5">
          <span class="mp-dot" aria-hidden="true"></span>
          {{ config.roleLabel }}
        </p>
        <h1 class="font-serif text-4xl font-semibold leading-tight tracking-normal md:text-5xl">
          {{ config.roleLabel }} sign-in
        </h1>
        <p class="mt-4 text-lg text-ink-soft">
          {{
            config.role === 'client'
              ? 'Use your Telegram-verified phone number.'
              : 'Enter account credentials to continue.'
          }}
        </p>
      </div>
    </section>

    <section class="mp-surface self-center p-5 md:p-6" aria-labelledby="signin-title">
      <h2 id="signin-title" class="font-serif text-2xl font-semibold">Sign in</h2>

      <form
        v-if="config.role !== 'client'"
        class="mt-5 space-y-4"
        @submit.prevent="submitPasswordLogin"
      >
        <label v-if="config.role === 'workshop'" class="block">
          <span class="mb-2 block text-sm font-bold text-ink">Workshop code</span>
          <input
            v-model="workshopCode"
            class="min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 text-base text-ink"
            type="text"
            autocomplete="organization"
            required
          />
        </label>
        <label class="block">
          <span class="mb-2 block text-sm font-bold text-ink">Login</span>
          <input
            v-model="login"
            class="min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 text-base text-ink"
            type="text"
            autocomplete="username"
            required
          />
        </label>
        <label class="block">
          <span class="mb-2 block text-sm font-bold text-ink">Password</span>
          <input
            v-model="password"
            class="min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 text-base text-ink"
            type="password"
            autocomplete="current-password"
            required
          />
        </label>
        <p
          v-if="errorText"
          class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
        >
          {{ errorText }}
        </p>
        <button type="submit" class="mp-button mp-button-primary w-full" :disabled="isSubmitting">
          {{ isSubmitting ? 'Signing in' : 'Continue' }}
        </button>
      </form>

      <form
        v-else
        class="mt-5 space-y-4"
        @submit.prevent="clientStep === 'phone' ? sendOtp() : verifyOtp()"
      >
        <label class="block">
          <span class="mb-2 block text-sm font-bold text-ink">Phone</span>
          <input
            v-model="phone"
            class="min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 text-base text-ink"
            type="tel"
            autocomplete="tel"
            :disabled="clientStep !== 'phone'"
            required
          />
        </label>
        <label v-if="clientStep !== 'phone'" class="block">
          <span class="mb-2 block text-sm font-bold text-ink">Code</span>
          <input
            v-model="otpCode"
            class="min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 text-base text-ink"
            type="text"
            inputmode="numeric"
            autocomplete="one-time-code"
            maxlength="6"
            required
          />
        </label>
        <label v-if="clientStep === 'name'" class="block">
          <span class="mb-2 block text-sm font-bold text-ink">Name</span>
          <input
            v-model="clientName"
            class="min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 text-base text-ink"
            type="text"
            autocomplete="name"
            required
          />
        </label>
        <p v-if="resendAfter && clientStep !== 'phone'" class="text-sm text-ink-soft">
          Resend available in {{ resendAfter }} seconds.
        </p>
        <p
          v-if="errorText"
          class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
        >
          {{ errorText }}
        </p>
        <div class="flex gap-2">
          <button
            v-if="clientStep !== 'phone'"
            type="button"
            class="mp-button mp-button-outline"
            @click="clientStep = 'phone'"
          >
            Edit
          </button>
          <button type="submit" class="mp-button mp-button-primary flex-1" :disabled="isSubmitting">
            {{ clientStep === 'phone' ? 'Send code' : isSubmitting ? 'Checking' : 'Continue' }}
          </button>
        </div>
      </form>
    </section>
  </main>
</template>
