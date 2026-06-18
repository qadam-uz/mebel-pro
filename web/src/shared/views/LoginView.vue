<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { isUzPhone, normalizeUzPhone } from '@/shared/app/clientUi'
import { safeRedirectPath } from '@/shared/app/redirect'
import { useRoleConfig } from '@/shared/app/roleConfig'
import { useAuthStore } from '@/shared/stores/auth'

const config = useRoleConfig()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const isDev = import.meta.env.DEV

const login = ref('')
const password = ref('')
const workshopCode = ref('')
const phone = ref('+998')
const otpCode = ref('')
const clientName = ref('')
const clientStep = ref<'phone' | 'code' | 'name'>('phone')
const resendAfter = ref<number | null>(null)
const resendLeft = ref(0)
const isSubmitting = ref(false)
const error = ref<string | null>(null)
let resendTimer: number | undefined

const redirectTo = computed(() => safeRedirectPath(route.query.redirect, config.homePath))

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
const clientErrorText = computed(() => {
  const code = error.value
  if (!code) return null
  if (code === 'invalid_code') {
    const remaining = Number(auth.lastErrorDetails?.attempts_remaining)
    return Number.isFinite(remaining) && remaining > 0
      ? `Kod noto'g'ri. Qolgan urinishlar: ${remaining}.`
      : "Kod noto'g'ri."
  }
  return (
    {
      account_blocked: 'Hisobingiz bloklangan.',
      // non-breaking spaces keep the example number from splitting across lines
      invalid_phone: "Telefon raqami noto'g'ri. Masalan: +998\u00a090\u00a0123\u00a045\u00a067",
      phone_unreachable_on_telegram:
        "Bu raqam Telegram'da topilmadi — kirish uchun ushbu raqamda Telegram bo'lishi kerak.",
      code_send_rate_limited: "Kod yuborish vaqtincha to'xtatilgan. Birozdan so'ng urinib ko'ring.",
      invalid_code: "Kod noto'g'ri.",
      code_expired: 'Kod muddati tugadi. Yangi kod oling.',
      too_many_attempts: "Juda ko'p noto'g'ri urinish. Yangi kod oling.",
      name_required: 'Ismingizni kiriting.',
      network_error: "Serverga ulanib bo'lmadi — qayta urinib ko'ring.",
    }[code] ?? 'Kirish amalga oshmadi.'
  )
})
const maskedPhone = computed(() =>
  normalizeUzPhone(phone.value).replace(/^(\+998)(\d{2})(\d{3})(\d{2})(\d{2})$/, '$1 $2 ••• •• $5'),
)
// Connection / rate-limit problems are not the user's fault → calmer amber tone;
// validation mistakes stay red.
const errorTone = computed(() =>
  error.value === 'network_error' || error.value === 'code_send_rate_limited' ? 'warn' : 'danger',
)

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

function sanitizePhone() {
  // Live-format as +998 XX XXX XX XX and cap at 9 national digits (type="tel" enforces nothing).
  let digits = phone.value.replace(/\D/g, '')
  if (digits.startsWith('8998')) digits = digits.slice(1)
  if (digits.startsWith('998')) {
    digits = digits.slice(3)
  } else {
    digits = digits.replace(/^0+/, '')
  }
  digits = digits.slice(0, 9)
  const groups = [digits.slice(0, 2), digits.slice(2, 5), digits.slice(5, 7), digits.slice(7, 9)]
  phone.value = digits ? `+998 ${groups.filter(Boolean).join(' ')}` : '+998'
}

function sanitizeOtp() {
  otpCode.value = otpCode.value.replace(/\D/g, '')
}

async function sendOtp() {
  error.value = null
  const normalized = normalizeUzPhone(phone.value)
  if (!isUzPhone(normalized)) {
    error.value = 'invalid_phone'
    return
  }
  phone.value = normalized
  isSubmitting.value = true
  try {
    const response = await auth.requestClientOtp(normalized)
    resendAfter.value = response.resend_after_seconds
    clientStep.value = 'code'
    startCooldown(response.resend_after_seconds)
  } catch {
    error.value = auth.lastError
    if (error.value === 'code_send_rate_limited') {
      const retry = Number(auth.lastErrorDetails?.retry_after_seconds)
      if (Number.isFinite(retry) && retry > 0) startCooldown(retry)
    }
  } finally {
    isSubmitting.value = false
  }
}

async function verifyOtp() {
  error.value = null
  if (clientStep.value === 'code' && otpCode.value.length !== 6) {
    error.value = 'invalid_code'
    return
  }
  if (clientStep.value === 'name' && clientName.value.trim().length === 0) {
    error.value = 'name_required'
    return
  }
  isSubmitting.value = true
  try {
    const response = await auth.verifyClientOtp(
      phone.value,
      otpCode.value,
      clientStep.value === 'name' ? clientName.value.trim() : undefined,
    )
    if ('is_new' in response) {
      clientStep.value = 'name'
      return
    }
    await finish()
  } catch {
    error.value = auth.lastError
    if (error.value === 'code_expired' || error.value === 'too_many_attempts') {
      // The code is dead — return to the phone step so the user can request a fresh one
      // instead of being stranded on an error with no way forward.
      clientStep.value = 'phone'
      otpCode.value = ''
      window.clearInterval(resendTimer)
      resendLeft.value = 0
    }
  } finally {
    isSubmitting.value = false
  }
}

function editPhone() {
  clientStep.value = 'phone'
  otpCode.value = ''
  error.value = null
  window.clearInterval(resendTimer)
  resendLeft.value = 0
}

async function resendOtp() {
  if (resendLeft.value > 0) return
  await sendOtp()
}

function startCooldown(seconds: number) {
  window.clearInterval(resendTimer)
  resendLeft.value = Math.max(0, seconds)
  resendTimer = window.setInterval(() => {
    resendLeft.value = Math.max(0, resendLeft.value - 1)
    if (resendLeft.value === 0) window.clearInterval(resendTimer)
  }, 1000)
}

onBeforeUnmount(() => {
  window.clearInterval(resendTimer)
})
</script>

<template>
  <main
    v-if="config.role === 'client'"
    class="grid min-h-screen place-items-center bg-bg px-4 py-8"
  >
    <section
      class="client-card w-[min(100%,420px)] p-8 shadow-[0_18px_44px_-16px_rgb(15_27_45_/_35%)]"
    >
      <RouterLink :to="config.homePath" class="client-brand mb-7 inline-flex">
        <img src="/favicon.svg" alt="" class="size-8" />
        <span class="client-brand-name">Mebel Pro</span>
      </RouterLink>

      <form v-if="clientStep === 'phone'" class="space-y-4" novalidate @submit.prevent="sendOtp">
        <div>
          <h1 class="font-serif text-3xl font-semibold leading-tight text-ink">
            Mijoz kabinetiga kirish
          </h1>
          <p class="mt-2 text-sm text-ink-muted">
            Telefon raqamingizni kiriting — Telegram orqali tasdiqlash kodi yuboramiz.
          </p>
        </div>

        <label class="block">
          <span class="mb-1 block text-sm font-bold text-ink">Telefon raqami</span>
          <input
            v-model="phone"
            class="mp-input"
            type="tel"
            inputmode="tel"
            autocomplete="tel"
            required
            @input="sanitizePhone"
          />
          <span class="mt-1 block text-xs text-ink-muted">
            Telegram o'rnatilgan raqamni kiriting — kod o'sha raqamning Telegram'iga keladi.
          </span>
        </label>

        <div v-if="clientErrorText" class="client-banner" :class="errorTone">
          <svg
            class="mt-0.5 size-4 shrink-0"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4M12 16h.01" />
          </svg>
          <span>{{ clientErrorText }}</span>
        </div>

        <button
          type="submit"
          class="mp-button mp-button-primary min-h-[46px] w-full"
          :disabled="isSubmitting"
        >
          {{ isSubmitting ? 'Yuborilmoqda' : 'Kod yuborish' }}
        </button>
      </form>

      <form
        v-else-if="clientStep === 'code'"
        class="space-y-4"
        novalidate
        @submit.prevent="verifyOtp"
      >
        <div>
          <h1 class="font-serif text-3xl font-semibold leading-tight text-ink">Kodni kiriting</h1>
          <p class="mt-2 text-sm text-ink-muted">
            <b>{{ maskedPhone }}</b> raqamiga kod yubordik.
          </p>
        </div>

        <label class="block">
          <span class="sr-only">Tasdiqlash kodi</span>
          <input
            v-model="otpCode"
            class="mp-input font-mono tracking-[0.5em]"
            type="text"
            inputmode="numeric"
            autocomplete="one-time-code"
            maxlength="6"
            pattern="\d{6}"
            placeholder="••••••"
            required
            @input="sanitizeOtp"
          />
          <span v-if="isDev && resendAfter" class="mt-1 block text-xs text-ink-muted">
            Dev rejimda test kodi: <b>000000</b>.
          </span>
        </label>

        <div v-if="clientErrorText" class="client-banner" :class="errorTone">
          <svg
            class="mt-0.5 size-4 shrink-0"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4M12 16h.01" />
          </svg>
          <span>{{ clientErrorText }}</span>
        </div>

        <button
          type="submit"
          class="mp-button mp-button-primary min-h-[46px] w-full"
          :disabled="isSubmitting"
        >
          {{ isSubmitting ? 'Tekshirilmoqda' : 'Tasdiqlash' }}
        </button>

        <div class="flex justify-between gap-3 border-t border-hairline pt-4 text-sm font-bold">
          <button type="button" class="text-accent" @click="editPhone">
            ← Raqamni o'zgartirish
          </button>
          <button
            type="button"
            class="text-accent disabled:opacity-50"
            :disabled="resendLeft > 0 || isSubmitting"
            @click="resendOtp"
          >
            {{ resendLeft > 0 ? `Kodni qayta yuborish (${resendLeft}s)` : 'Kodni qayta yuborish' }}
          </button>
        </div>
      </form>

      <form v-else class="space-y-4" novalidate @submit.prevent="verifyOtp">
        <div>
          <h1 class="font-serif text-3xl font-semibold leading-tight text-ink">Tanishib olaylik</h1>
          <p class="mt-2 text-sm text-ink-muted">
            Ustaxona buyurtmalarda sizga shu ism bilan murojaat qiladi.
          </p>
        </div>

        <label class="block">
          <span class="mb-1 block text-sm font-bold text-ink">Ismingiz</span>
          <input
            v-model="clientName"
            class="mp-input"
            type="text"
            autocomplete="name"
            maxlength="80"
            required
          />
        </label>

        <div v-if="clientErrorText" class="client-banner" :class="errorTone">
          <svg
            class="mt-0.5 size-4 shrink-0"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4M12 16h.01" />
          </svg>
          <span>{{ clientErrorText }}</span>
        </div>

        <button
          type="submit"
          class="mp-button mp-button-primary min-h-[46px] w-full"
          :disabled="isSubmitting"
        >
          {{ isSubmitting ? 'Saqlanmoqda' : 'Davom etish' }}
        </button>

        <div class="flex border-t border-hairline pt-4 text-sm font-bold">
          <button type="button" class="text-accent" @click="editPhone">
            ← Raqamni o'zgartirish
          </button>
        </div>
      </form>
    </section>
  </main>

  <main v-else-if="config.role === 'admin'" class="admin-auth-wrap">
    <section class="admin-auth-card" aria-labelledby="admin-login-title">
      <RouterLink :to="config.homePath" class="client-brand mb-7 inline-flex">
        <img src="/favicon.svg" alt="" class="size-8" />
        <span class="client-brand-name">Mebel Pro</span>
      </RouterLink>

      <form class="space-y-4" @submit.prevent="submitPasswordLogin">
        <div>
          <h1 id="admin-login-title" class="font-serif text-3xl font-semibold leading-tight">
            Operator paneliga kirish
          </h1>
          <p class="mt-2 text-sm text-ink-soft">
            Platforma operatori login va parol bilan kiradi. Hujjatlar va API havolalari alohida
            HTTP-Basic himoyasida ochiladi.
          </p>
        </div>

        <label class="admin-field" for="admin-login">
          <span class="admin-field-label">Login</span>
          <input id="admin-login" v-model="login" type="text" autocomplete="username" required />
        </label>

        <label class="admin-field" for="admin-password">
          <span class="admin-field-label">Parol</span>
          <input
            id="admin-password"
            v-model="password"
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
          {{ isSubmitting ? 'Tekshirilmoqda' : 'Kirish' }}
        </button>
      </form>

      <p class="mt-6 border-t border-hairline pt-5 text-center text-xs text-ink-muted">
        Sessiya serverda saqlanadi va bloklash yoki parol almashtirishda darhol bekor qilinadi.
      </p>
    </section>
  </main>

  <main
    v-else
    class="grid min-h-screen bg-bg px-4 py-8 text-ink md:grid-cols-[1fr_minmax(360px,460px)]"
  >
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
        <p class="mt-4 text-lg text-ink-soft">Enter account credentials to continue.</p>
      </div>
    </section>

    <section class="mp-surface self-center p-5 md:p-6" aria-labelledby="signin-title">
      <h2 id="signin-title" class="font-serif text-2xl font-semibold">Sign in</h2>

      <form class="mt-5 space-y-4" @submit.prevent="submitPasswordLogin">
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
    </section>
  </main>
</template>
