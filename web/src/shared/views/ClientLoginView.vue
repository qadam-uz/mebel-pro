<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { sanitizeWholeNumberInput } from '@/shared/app/inputSanitizers'
import { safeRedirectPath } from '@/shared/app/redirect'
import { useRoleConfig } from '@/shared/app/roleConfig'
import BrandMark from '@/shared/components/BrandMark.vue'
import Icon from '@/shared/components/AppIcon.vue'
import LocaleSwitcher from '@/shared/components/LocaleSwitcher.vue'
import QrCode from '@/shared/components/QrCode.vue'
import { useCountdown } from '@/shared/composables/useCountdown'
import { useAuthStore, type ClientLoginPoll } from '@/shared/stores/auth'
import { useClientEntryStore } from '@/shared/stores/clientEntry'

const { t } = useI18n()
const config = useRoleConfig()
const auth = useAuthStore()
const entry = useClientEntryStore()
const route = useRoute()
const router = useRouter()

// Two seconds: the handshake lives five minutes, so this costs ~150 requests at
// the very worst and still reads as instant when the client presses Tasdiqlash.
const POLL_INTERVAL_MS = 2_000
// The primary affordance follows the device, not the window: a phone gets the
// button that opens Telegram, everything else gets the QR another device scans.
const MOBILE_QUERY = '(max-width: 768px), (pointer: coarse)'
const CODE_LENGTH = 6

/** What the card is showing. `loading` covers minting the first token. */
type Phase = 'loading' | 'waiting' | 'started' | 'expired' | 'error'

const phase = ref<Phase>('loading')
const deepLink = ref('')
const tokenError = ref<string | null>(null)
const declined = ref(false)
const isMobile = ref(false)
const qrShown = ref(false)
const codeOpen = ref(false)
const code = ref('')
const codeError = ref<string | null>(null)
const isRedeeming = ref(false)
const { left: retryLeft, start: startRetry, stop: stopRetry } = useCountdown()
const { left: codeRetryLeft, start: startCodeRetry, stop: stopCodeRetry } = useCountdown()

// The poll secret is the credential a session is released against, so it stays
// out of reactive state — nothing renders it and nothing can leak it into a
// devtools snapshot or a template.
let pollSecret: string | null = null
let pollTimer: number | undefined
let pollInFlight = false
let unmounted = false
let viewportQuery: MediaQueryList | undefined

const redirectTo = computed(() => safeRedirectPath(route.query.redirect, config.homePath))
// Set by the API client's 401 interceptor when a silent refresh fails (CB-08).
const sessionExpired = computed(() => route.query.reason === 'session_expired')

// The QR is on screen whenever it is the primary affordance (desktop) or the
// client asked for it (mobile, Telegram on another device).
const showQr = computed(() => !isMobile.value || qrShown.value)
const isLive = computed(() => phase.value === 'waiting' || phase.value === 'started')

// The token budget is measured in hours, so its `retry_after_seconds` arrives as
// a four-digit number — "3061 soniyadan keyin" is a figure nobody converts. Under
// a minute the seconds are the useful unit; above it, minutes are.
const MINUTE_SECONDS = 60

const tokenErrorText = computed(() => {
  const errorCode = tokenError.value
  if (!errorCode) return null
  if (errorCode === 'login_token_rate_limited') {
    return retryLeft.value >= MINUTE_SECONDS
      ? t('client.error.login_token_rate_limited_minutes', {
          minutes: Math.ceil(retryLeft.value / MINUTE_SECONDS),
        })
      : t('client.error.login_token_rate_limited', { seconds: retryLeft.value })
  }
  return errorCode === 'network_error'
    ? t('client.error.network_error')
    : t('client.error.loginFallback')
})
// A throttle or a dropped connection is not the client's mistake — amber, not red.
const tokenErrorTone = computed(() =>
  tokenError.value === 'login_token_rate_limited' || tokenError.value === 'network_error'
    ? 'warn'
    : 'danger',
)
const canRetryToken = computed(() => retryLeft.value === 0)

const codeErrorText = computed(() => {
  const errorCode = codeError.value
  if (!errorCode) return null
  if (errorCode === 'login_code_rate_limited') {
    return codeRetryLeft.value >= MINUTE_SECONDS
      ? t('client.error.login_code_rate_limited_minutes', {
          minutes: Math.ceil(codeRetryLeft.value / MINUTE_SECONDS),
        })
      : t('client.error.login_code_rate_limited', { seconds: codeRetryLeft.value })
  }
  if (errorCode === 'invalid_code') return t('client.error.invalid_code')
  if (errorCode === 'account_blocked') return t('client.error.account_blocked')
  return errorCode === 'network_error'
    ? t('client.error.network_error')
    : t('client.error.loginFallback')
})
const codeBlocked = computed(() => codeRetryLeft.value > 0)

async function finish() {
  stopPolling()
  pollSecret = null
  // A workshop link scanned before signing in parked its entry in
  // `localStorage`; this is the moment there is a session to apply it to. A
  // missing or refused entry is a normal un-pinned login (spec §3.1) — the store
  // swallows both, so the redirect below always happens.
  await entry.applyPendingEntry()
  await router.replace(redirectTo.value)
}

/** Ask for a fresh handshake and start polling it. */
async function mintToken() {
  stopPolling()
  pollSecret = null
  stopRetry()
  tokenError.value = null
  phase.value = 'loading'
  try {
    const issued = await auth.createClientLoginToken()
    if (unmounted) return
    pollSecret = issued.poll_secret
    deepLink.value = issued.deep_link
    phase.value = 'waiting'
    startPolling()
  } catch {
    if (unmounted) return
    phase.value = 'error'
    tokenError.value = auth.lastError
    const retryAfter = Number(auth.lastErrorDetails?.retry_after_seconds)
    if (tokenError.value === 'login_token_rate_limited' && Number.isFinite(retryAfter)) {
      startRetry(retryAfter)
    }
  }
}

function startPolling() {
  stopPolling()
  // A hidden tab is not waiting for anything a client can see; the
  // visibilitychange handler polls once and re-arms the moment it comes back.
  if (typeof document !== 'undefined' && document.hidden) return
  pollTimer = window.setInterval(() => void runPoll(), POLL_INTERVAL_MS)
}

function stopPolling() {
  if (pollTimer !== undefined) window.clearInterval(pollTimer)
  pollTimer = undefined
}

async function runPoll() {
  const secret = pollSecret
  // One request at a time: two in flight could both read `confirmed`, and only
  // one can win the session — the loser would then paint an error over a card
  // that is already signing in.
  if (!secret || pollInFlight) return
  pollInFlight = true
  try {
    const response = await auth.pollClientLogin(secret)
    if (unmounted || secret !== pollSecret) return
    if ('access_token' in response) {
      await finish()
      return
    }
    applyPollState(response)
  } catch {
    if (unmounted || secret !== pollSecret) return
    // The handshake row is gone (pruned, or burned by another tab): a fresh one
    // is the only way forward. Anything else is a transport hiccup — keep
    // polling, the next tick usually lands.
    if (auth.lastError === 'invalid_poll_secret') await mintToken()
  } finally {
    pollInFlight = false
  }
}

function applyPollState(poll: ClientLoginPoll) {
  if (poll.expired || poll.status === 'used') {
    expire()
    return
  }
  if (poll.status === 'declined') {
    // Back to waiting on a fresh QR, with a line saying why — a silently
    // swapped QR reads as "my Bekor qilish did nothing".
    declined.value = true
    void mintToken()
    return
  }
  // `pending` means the chat has not opened yet. Everything past it — the bot
  // asked, or is waiting on a contact — is the client's turn on their phone.
  const next = poll.status === 'pending' ? 'waiting' : 'started'
  // The cancelled-login line stays up for the whole wait on the fresh QR and
  // clears when the client opens the chat again. Clearing it on every `pending`
  // poll would flash it for one two-second tick and take it away unread.
  if (next === 'started') declined.value = false
  phase.value = next
}

function expire() {
  stopPolling()
  pollSecret = null
  declined.value = false
  phase.value = 'expired'
}

function onVisibilityChange() {
  if (document.hidden) {
    stopPolling()
    return
  }
  if (!isLive.value) return
  // Coming back from Telegram is exactly when the answer is ready — ask now
  // rather than up to two seconds from now.
  void runPoll()
  startPolling()
}

function onViewportChange(event: MediaQueryList | MediaQueryListEvent) {
  isMobile.value = event.matches
}

function sanitizeCode() {
  code.value = sanitizeWholeNumberInput(code.value).slice(0, CODE_LENGTH)
}

async function submitCode() {
  if (codeBlocked.value || isRedeeming.value) return
  codeError.value = null
  if (code.value.length !== CODE_LENGTH) {
    codeError.value = 'invalid_code'
    return
  }
  isRedeeming.value = true
  try {
    await auth.redeemClientLoginCode(code.value)
    await finish()
  } catch {
    if (unmounted) return
    codeError.value = auth.lastError
    const retryAfter = Number(auth.lastErrorDetails?.retry_after_seconds)
    if (codeError.value === 'login_code_rate_limited' && Number.isFinite(retryAfter)) {
      startCodeRetry(retryAfter)
    }
  } finally {
    isRedeeming.value = false
  }
}

onMounted(() => {
  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    viewportQuery = window.matchMedia(MOBILE_QUERY)
    onViewportChange(viewportQuery)
    viewportQuery.addEventListener('change', onViewportChange)
  }
  document.addEventListener('visibilitychange', onVisibilityChange)
  void mintToken()
})

onBeforeUnmount(() => {
  unmounted = true
  stopPolling()
  stopRetry()
  stopCodeRetry()
  pollSecret = null
  viewportQuery?.removeEventListener('change', onViewportChange)
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>

<template>
  <main class="grid min-h-[var(--app-vh)] place-items-center bg-bg px-4 py-8">
    <section
      class="client-card w-[min(100%,420px)] p-8 shadow-[0_18px_44px_-16px_color-mix(in_srgb,var(--color-ink)_35%,transparent)]"
    >
      <RouterLink :to="config.homePath" class="client-brand mb-7 inline-flex">
        <BrandMark :size="32" />
        <span class="client-brand-name">Mebel Pro</span>
      </RouterLink>

      <div v-if="sessionExpired" class="client-banner warn" role="status">
        <span aria-hidden="true">!</span>
        <span>{{ $t('client.login.expired') }}</span>
      </div>

      <h1 class="font-display text-3xl font-semibold leading-tight text-ink">
        {{ $t('client.login.title') }}
      </h1>
      <!-- The subtitle explains the affordance below it, so it goes away in the
           states that have none — "scan the QR" over a dead handshake with no QR
           on screen is an instruction the reader cannot carry out. -->
      <p v-if="isLive || phase === 'loading'" class="mt-2 text-sm text-ink-muted">
        {{ isMobile ? $t('client.login.subtitleMobile') : $t('client.login.subtitleDesktop') }}
      </p>

      <!-- Expired: the one thing to do is mint a new handshake. -->
      <div v-if="phase === 'expired'" class="mt-5">
        <div class="client-banner warn">
          <Icon name="alert" class="mt-0.5 size-4 shrink-0" />
          <span>{{
            isMobile ? $t('client.login.expiredLink') : $t('client.login.expiredQr')
          }}</span>
        </div>
        <button
          type="button"
          class="mp-button mp-button-primary min-h-[46px] w-full"
          @click="mintToken"
        >
          {{ $t('client.login.refresh') }}
        </button>
      </div>

      <!-- The handshake could not be minted at all: named cause + retry. -->
      <div v-else-if="phase === 'error'" class="mt-5">
        <div class="client-banner" :class="tokenErrorTone">
          <Icon name="alert" class="mt-0.5 size-4 shrink-0" />
          <span>{{ tokenErrorText }}</span>
        </div>
        <button
          type="button"
          class="mp-button mp-button-primary min-h-[46px] w-full"
          :disabled="!canRetryToken"
          @click="mintToken"
        >
          {{ $t('client.login.refresh') }}
        </button>
      </div>

      <div v-else class="mt-5">
        <div v-if="declined" class="client-banner info" role="status">
          <Icon name="alert" class="mt-0.5 size-4 shrink-0" />
          <span>{{ $t('client.login.declined') }}</span>
        </div>

        <!-- Mobile: Telegram is on this device, so the deep link is the action. -->
        <a
          v-if="isMobile"
          class="mp-button mp-button-primary min-h-[46px] w-full"
          :class="phase === 'loading' ? 'pointer-events-none opacity-50' : ''"
          :href="deepLink || undefined"
          :aria-disabled="phase === 'loading' ? 'true' : undefined"
          rel="noopener"
        >
          {{ $t('client.login.telegramButton') }}
        </a>

        <!-- The QR frame keeps its size while the token is minting, so the card
             does not jump when it arrives. -->
        <div
          v-if="showQr"
          class="mx-auto w-[210px] rounded-xl border border-hairline p-3"
          :class="isMobile ? 'mt-4' : ''"
        >
          <div v-if="phase === 'loading'" class="client-skeleton aspect-square w-full"></div>
          <QrCode v-else :value="deepLink" :label="$t('client.login.qrLabel')" />
        </div>

        <div class="mt-4 text-center">
          <button
            v-if="isMobile"
            type="button"
            class="text-sm font-bold text-accent-deep"
            :aria-expanded="qrShown"
            @click="qrShown = !qrShown"
          >
            {{ qrShown ? $t('client.login.hideQr') : $t('client.login.showQr') }}
          </button>
          <a
            v-else-if="deepLink"
            class="text-sm font-bold text-accent-deep"
            :href="deepLink"
            rel="noopener"
          >
            {{ $t('client.login.openInTelegram') }}
          </a>
        </div>

        <p class="mt-4 text-center text-sm text-ink-soft" role="status">
          {{ phase === 'started' ? $t('client.login.confirmOnPhone') : $t('client.login.waiting') }}
        </p>
      </div>

      <!-- Fallback: the client who reached the bot without the deep link and got
           a 6-digit code there. Collapsed — it is the exception, not the path. -->
      <div class="mt-6 border-t border-hairline pt-5">
        <button
          type="button"
          class="flex w-full items-center justify-between text-sm font-bold text-accent-deep"
          :aria-expanded="codeOpen"
          aria-controls="client-code-form"
          @click="codeOpen = !codeOpen"
        >
          <span>{{ $t('client.login.codeToggle') }}</span>
          <Icon
            name="chevron-down"
            class="size-4 transition-transform"
            :class="codeOpen ? 'rotate-180' : ''"
          />
        </button>

        <form
          v-if="codeOpen"
          id="client-code-form"
          class="mt-4 space-y-3"
          novalidate
          @submit.prevent="submitCode"
        >
          <p class="text-sm text-ink-muted">{{ $t('client.login.codeHint') }}</p>
          <label class="block" for="client-login-code">
            <span class="mb-1 block text-sm font-bold text-ink">
              {{ $t('client.login.codeLabel') }}
            </span>
            <input
              id="client-login-code"
              v-model="code"
              class="mp-input tracking-[0.5em]"
              type="text"
              inputmode="numeric"
              autocomplete="one-time-code"
              :maxlength="CODE_LENGTH"
              placeholder="123456"
              :aria-invalid="codeError ? 'true' : undefined"
              :aria-describedby="codeError ? 'client-login-code-error' : undefined"
              @input="sanitizeCode"
            />
          </label>

          <p
            v-if="codeErrorText"
            id="client-login-code-error"
            class="text-sm font-bold"
            :class="codeError === 'login_code_rate_limited' ? 'text-warning' : 'text-danger'"
          >
            {{ codeErrorText }}
          </p>

          <button
            type="submit"
            class="mp-button mp-button-outline w-full"
            :disabled="isRedeeming || codeBlocked"
          >
            {{ isRedeeming ? $t('client.login.codeSubmitting') : $t('client.login.codeSubmit') }}
          </button>
        </form>
      </div>

      <!-- Below the actions, not above them: the card has one primary action and a
           three-way radiogroup over the heading would compete with it. Still on
           the first screen, spelled out in each language's own script, because
           the one person who needs it cannot read the rest of this card. -->
      <div class="mt-6 border-t border-hairline pt-5">
        <LocaleSwitcher variant="segmented" />
      </div>
    </section>
  </main>
</template>
