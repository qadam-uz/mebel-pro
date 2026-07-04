<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { isUzPhone, normalizeUzPhone } from '@/shared/app/clientUi'
import { safeRedirectPath } from '@/shared/app/redirect'
import PhoneInput from '@/shared/components/PhoneInput.vue'
import { useRoleConfig } from '@/shared/app/roleConfig'
import { useResendCooldown } from '@/shared/composables/useResendCooldown'
import { useAuthStore } from '@/shared/stores/auth'

const config = useRoleConfig()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const isDev = import.meta.env.DEV

const phone = ref('')
const otpCode = ref('')
const clientName = ref('')
const clientStep = ref<'phone' | 'code' | 'name'>('phone')
const resendAfter = ref<number | null>(null)
const isSubmitting = ref(false)
const error = ref<string | null>(null)
const { left: resendLeft, start: startCooldown, stop: stopCooldown } = useResendCooldown()

const redirectTo = computed(() => safeRedirectPath(route.query.redirect, config.homePath))
// Set by the API client's 401 interceptor when a silent refresh fails (CB-08).
const sessionExpired = computed(() => route.query.reason === 'session_expired')

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
      invalid_phone: "Telefon raqami noto'g'ri. Masalan: +998 90 123 45 67",
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
      stopCooldown()
    }
  } finally {
    isSubmitting.value = false
  }
}

function editPhone() {
  clientStep.value = 'phone'
  otpCode.value = ''
  error.value = null
  stopCooldown()
}

async function resendOtp() {
  if (resendLeft.value > 0) return
  await sendOtp()
}
</script>

<template>
  <main class="grid min-h-screen place-items-center bg-bg px-4 py-8">
    <section
      class="client-card w-[min(100%,420px)] p-8 shadow-[0_18px_44px_-16px_rgb(15_27_45_/_35%)]"
    >
      <RouterLink :to="config.homePath" class="client-brand mb-7 inline-flex">
        <img src="/favicon.svg" alt="" class="size-8" />
        <span class="client-brand-name">Mebel Pro</span>
      </RouterLink>

      <div v-if="sessionExpired" class="client-banner warn mb-4" role="status">
        <span aria-hidden="true">!</span>
        <span>Sessiya tugadi. Davom etish uchun qaytadan kiring.</span>
      </div>

      <form v-if="clientStep === 'phone'" class="space-y-4" novalidate @submit.prevent="sendOtp">
        <div>
          <h1 class="font-serif text-3xl font-semibold leading-tight text-ink">
            Mijoz kabinetiga kirish
          </h1>
          <p class="mt-2 text-sm text-ink-muted">
            Telefon raqamingizni kiriting — Telegram orqali tasdiqlash kodi yuboramiz.
          </p>
        </div>

        <label class="block" for="client-phone">
          <span class="mb-1 block text-sm font-bold text-ink">Telefon raqami</span>
          <PhoneInput id="client-phone" v-model="phone" required />
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
</template>
