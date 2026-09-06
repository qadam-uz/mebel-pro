<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { isAbortError } from '@/shared/api/client'
import { sanitizeWholeNumberInput } from '@/shared/app/inputSanitizers'
import { safeRedirectPath } from '@/shared/app/redirect'
import { useRoleConfig } from '@/shared/app/roleConfig'
import AppTabs from '@/shared/components/AppTabs.vue'
import BrandMark from '@/shared/components/BrandMark.vue'
import Icon from '@/shared/components/AppIcon.vue'
import LocaleSwitcher from '@/shared/components/LocaleSwitcher.vue'
import QrCode from '@/shared/components/QrCode.vue'
import { useCountdown } from '@/shared/composables/useCountdown'
import { useAuthStore, type ClientLoginPoll, type ClientLoginToken } from '@/shared/stores/auth'
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
// A ceiling on one poll. `fetch` has none of its own, and a phone that freezes
// this page while the client is in Telegram routinely leaves the in-flight
// request never settling — which is exactly the request that must not be allowed
// to own the loop. Generous against the 2s cadence, short enough that a request
// stuck behind a dead connection is replaced within one screen's worth of waiting.
const POLL_TIMEOUT_MS = 8_000
// Coming back to a phone's browser fires `visibilitychange`, `focus` and
// sometimes `pageshow` within the same few milliseconds. They are one event as
// far as this card is concerned: whichever lands first asks, the rest are
// swallowed. Wide enough to cover the burst, far below the poll interval.
const RESUME_WINDOW_MS = 400
// Both ways into the bot are on the card at once; only the tab that *opens*
// first follows the device — a phone leads with the button that opens Telegram,
// everything else with the QR another device scans.
const MOBILE_QUERY = '(max-width: 768px), (pointer: coarse)'
const CODE_LENGTH = 6
// The bot's handle, read back off the deep link so the code fallback's `t.me`
// link and the deep link can never name two different bots.
const BOT_LINK_PATTERN = /^https:\/\/t\.me\/([A-Za-z0-9_]+)/
// Where the in-flight handshake is parked so this card can be re-created without
// abandoning it. `sessionStorage`, never `localStorage`: the poll secret is the
// credential a session is released against, so it belongs to exactly the tab
// that minted it and must die with that tab — not sit in a store every other tab
// and every later visit can read.
const HANDSHAKE_KEY = 'mp-client-login-handshake'

/** What the card is showing. `loading` covers minting the first token. */
type Phase = 'loading' | 'waiting' | 'started' | 'expired' | 'error'
/** The two ways into the bot, each its own tab on the card. */
type LoginTab = 'qr' | 'telegram'

const phase = ref<Phase>('loading')
const deepLink = ref('')
const botUsername = ref('')
const tokenError = ref<string | null>(null)
const declined = ref(false)
const isMobile = ref(false)
// `null` means "nobody has picked yet", so the card keeps following the device
// until the reader chooses a tab — and then stops, because a rotated phone or a
// dragged window must not yank them off the tab they are reading. Latching the
// device answer at mount instead would freeze whatever the very first
// `matchMedia` read said, which is not reliably the final viewport.
const chosenTab = ref<LoginTab | null>(null)
// The client has been handed to Telegram and this page is now the thing they
// must come back to. Set on the tap rather than waited for, because the bot's
// `/start` can land seconds later — or never, if they tap and hesitate — and the
// instruction "come back here" is what they need in either case.
const linkOpened = ref(false)
// A poll is out. Only the manual check reads it: the automatic loop supersedes
// its own requests, so it never has to ask.
const pollBusy = ref(false)
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
// Every poll gets a number. The newest one owns the card: an answer arriving
// under an older number is dropped rather than applied, which is what lets a
// request be abandoned instead of waited on. A boolean latch cannot do this — a
// poll that never settles never clears it, and the loop stays wedged until the
// page is reloaded (the reported "I confirmed in Telegram and had to refresh").
let pollSeq = 0
let pollAbort: AbortController | null = null
let lastResumeAt = 0
let unmounted = false
let viewportQuery: MediaQueryList | undefined

/** The half of a minted handshake this card needs to keep polling it. */
interface SavedHandshake {
  deep_link: string
  poll_secret: string
  expires_at: string
}

/**
 * Per-tab storage, or `null`. Reaching `sessionStorage` throws outright in a few
 * real configurations (Safari private mode, storage blocked by policy), and a
 * store this card cannot reach only costs it the resume — never the login.
 */
function tabStorage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage
  } catch {
    return null
  }
}

function saveHandshake(issued: ClientLoginToken) {
  const entry: SavedHandshake = {
    deep_link: issued.deep_link,
    poll_secret: issued.poll_secret,
    expires_at: issued.expires_at,
  }
  try {
    tabStorage()?.setItem(HANDSHAKE_KEY, JSON.stringify(entry))
  } catch {
    // A full or refusing store is not a login failure — the card just loses its
    // ability to survive a reload.
  }
}

function clearHandshake() {
  try {
    tabStorage()?.removeItem(HANDSHAKE_KEY)
  } catch {
    // Nothing to do: an unreachable store holds nothing worth resuming either.
  }
}

/**
 * The handshake this tab left in flight, if there still is one. Anything that
 * cannot be resumed — unparseable, incomplete, or past its `expires_at` — is
 * dropped here rather than carried into a poll the server would refuse.
 */
function readHandshake(): SavedHandshake | null {
  let raw: string | null = null
  try {
    raw = tabStorage()?.getItem(HANDSHAKE_KEY) ?? null
  } catch {
    return null
  }
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Partial<SavedHandshake>
    const expiresAt = Date.parse(String(parsed.expires_at))
    if (
      typeof parsed.deep_link === 'string' &&
      typeof parsed.poll_secret === 'string' &&
      parsed.deep_link &&
      parsed.poll_secret &&
      Number.isFinite(expiresAt) &&
      expiresAt > Date.now()
    ) {
      return parsed as SavedHandshake
    }
  } catch {
    // Fall through: garbage in the store reads exactly like no store at all.
  }
  clearHandshake()
  return null
}

const redirectTo = computed(() => safeRedirectPath(route.query.redirect, config.homePath))
// Set by the API client's 401 interceptor when a silent refresh fails (CB-08).
const sessionExpired = computed(() => route.query.reason === 'session_expired')

const isLive = computed(() => phase.value === 'waiting' || phase.value === 'started')
// The tab that opens follows the device — a phone leads with the button that
// opens Telegram, everything else with the QR another device scans.
const activeTab = computed<LoginTab>({
  get: () => chosenTab.value ?? (isMobile.value ? 'telegram' : 'qr'),
  set: (value) => {
    chosenTab.value = value
  },
})
// Expired and un-mintable both replace the handshake affordance with a named
// cause and one retry — in the QR tab and the Telegram tab alike, because both
// render the same dead token. The code disclosure is unaffected: its code comes
// from the chat, not from this browser's handshake.
const handshakeStopped = computed(() => phase.value === 'expired' || phase.value === 'error')

const tabs = computed(() => [
  { value: 'qr', label: t('client.login.tabQr') },
  { value: 'telegram', label: t('client.login.tabTelegram') },
])

const botLink = computed(() => (botUsername.value ? `https://t.me/${botUsername.value}` : ''))
const botHandle = computed(() => `@${botUsername.value}`)

// The same handshake as a native scheme. `https://t.me/…` on a phone lands on
// Telegram's own "Open in Telegram" interstitial *page* first, and the client
// comes back to that tab rather than to this one — which is where they tapped
// the bot a second time instead of finding themselves signed in. `tg://` hands
// the OS the app directly, with no page in between. Empty when the deep link
// does not parse, which leaves the https form as the only affordance.
const appLink = computed(() => {
  if (!deepLink.value) return ''
  try {
    const url = new URL(deepLink.value)
    const domain = url.pathname.replace(/^\//, '')
    const start = url.searchParams.get('start')
    if (!domain || !start) return ''
    return `tg://resolve?domain=${encodeURIComponent(domain)}&start=${encodeURIComponent(start)}`
  } catch {
    return ''
  }
})
// Desktop keeps the https link in a new tab: there is no guaranteed `tg://`
// handler on a laptop, and a same-tab scheme that does nothing would look
// broken. On a phone the scheme either opens the app or is ignored outright —
// neither navigates this page away, so the card and its poll survive the tap.
const opensAway = computed(() => !(isMobile.value && appLink.value))
const telegramHref = computed(() => (opensAway.value ? deepLink.value : appLink.value))
// The client is in Telegram (or has been sent there) and this page is what they
// must come back to. Scoped to the Telegram tab because that is the only tab
// anyone leaves the page from: the QR reader never went anywhere, so "return to
// this page" and a "check now" button would both be noise under a QR.
const awaitingReturn = computed(
  () =>
    activeTab.value === 'telegram' &&
    isLive.value &&
    (linkOpened.value || phase.value === 'started'),
)
const statusLine = computed(() => {
  if (awaitingReturn.value) return t('client.login.confirmInTelegram')
  return phase.value === 'started' ? t('client.login.confirmOnPhone') : t('client.login.waiting')
})

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
// One line for the dead handshake, named per tab: the QR reader lost a QR, the
// Telegram reader lost a link, and a mint that failed outright names its cause.
const handshakeStoppedText = computed(() => {
  if (phase.value !== 'expired') return tokenErrorText.value
  return activeTab.value === 'qr' ? t('client.login.expiredQr') : t('client.login.expiredLink')
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
  clearHandshake()
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
  // The handshake being replaced is dead the moment this call is made — declined,
  // burned, or simply unwanted — so it goes before the new one arrives rather
  // than after, and a mint that fails leaves nothing stale behind to resume.
  clearHandshake()
  stopRetry()
  tokenError.value = null
  // A fresh handshake is a fresh trip: whatever the client did with the previous
  // link, this one has not been opened.
  linkOpened.value = false
  phase.value = 'loading'
  try {
    const issued = await auth.createClientLoginToken()
    if (unmounted) return
    pollSecret = issued.poll_secret
    deepLink.value = issued.deep_link
    readBotUsername(issued.deep_link)
    // Park it before the first poll: a reload one tick later — or the browser
    // evicting this tab while the client is in Telegram — then finds a handshake
    // to resume instead of minting a second one against the same client.
    saveHandshake(issued)
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

/**
 * Pull the bot's handle out of the freshly minted deep link. The server builds
 * that link from `TELEGRAM_BOT_USERNAME`, so reading it back keeps the code
 * tab's `t.me` link on the same bot with no second config channel. A link that
 * does not parse leaves the last known handle alone — the tab then simply shows
 * its instructions without the shortcut.
 */
function readBotUsername(link: string) {
  const match = BOT_LINK_PATTERN.exec(link)
  if (match) botUsername.value = match[1]
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

/**
 * Drop the request that is out, if any. Called when this card stops caring about
 * the answer — the tab is going away to Telegram, a newer poll has taken over,
 * or the card is unmounting. Aborting is what frees a request a frozen page
 * would otherwise leave hanging for the life of the tab.
 */
function abortPoll() {
  pollAbort?.abort()
  pollAbort = null
}

async function runPoll() {
  const secret = pollSecret
  if (!secret) return
  // A poll already out is superseded, never waited on. Two answers cannot both
  // paint — only the newest sequence number is allowed to — so the old request
  // is free to be abandoned, which is the whole point: on a phone it may never
  // settle at all.
  abortPoll()
  pollSeq += 1
  const seq = pollSeq
  const controller = new AbortController()
  pollAbort = controller
  pollBusy.value = true
  const stale = () => unmounted || seq !== pollSeq || secret !== pollSecret
  try {
    const response = await auth.pollClientLogin(secret, {
      signal: controller.signal,
      timeoutMs: POLL_TIMEOUT_MS,
    })
    if (stale()) return
    if ('access_token' in response) {
      await finish()
      return
    }
    applyPollState(response)
  } catch (error) {
    if (stale() || isAbortError(error)) return
    // The handshake row is gone (pruned, or burned by another tab): a fresh one
    // is the only way forward. Anything else — a timeout, a dropped connection —
    // is a transport hiccup; keep polling, the next tick usually lands.
    if (auth.lastError === 'invalid_poll_secret') await mintToken()
  } finally {
    // Only the poll that still owns the card clears the flag; a superseded one
    // would otherwise hand the manual check button back mid-request.
    if (seq === pollSeq) {
      pollBusy.value = false
      pollAbort = null
    }
  }
}

/** «Tasdiqladim, tekshirish» — one poll now, for the client who cannot wait. */
function checkNow() {
  if (pollBusy.value) return
  void runPoll()
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
  abortPoll()
  pollSecret = null
  linkOpened.value = false
  clearHandshake()
  declined.value = false
  phase.value = 'expired'
}

/**
 * Pick up the handshake this tab left in flight. A reload, a browser that
 * evicted the tab while the client was in Telegram, or a back-navigation to this
 * route all land here — and every one of them used to mint a second token and
 * abandon the first, which is what left the client confirming a handshake
 * nothing was polling. Returns `false` when there is nothing to resume.
 */
function resumeHandshake(): boolean {
  const saved = readHandshake()
  if (!saved) return false
  pollSecret = saved.poll_secret
  deepLink.value = saved.deep_link
  readBotUsername(saved.deep_link)
  phase.value = 'waiting'
  // The page is usually back precisely because the client finished in the bot,
  // so ask now rather than up to two seconds from now. `startPolling` is the
  // hidden-tab guard for both — a hidden tab arms nothing and this poll is the
  // one the return to the tab will fire.
  if (typeof document === 'undefined' || !document.hidden) void runPoll()
  startPolling()
  return true
}

/**
 * The tab is in front again — ask now rather than up to two seconds from now,
 * because it is usually in front precisely because the client just finished in
 * the bot. Three browser events say this (`visibilitychange`, `focus`,
 * `pageshow`) and a phone fires them together, so the first one through wins the
 * window and the rest are swallowed: one return, one request.
 */
function resumePolling() {
  if (!isLive.value) return
  if (typeof document !== 'undefined' && document.hidden) return
  const now = Date.now()
  if (now - lastResumeAt < RESUME_WINDOW_MS) return
  lastResumeAt = now
  void runPoll()
  startPolling()
}

function onVisibilityChange() {
  if (document.hidden) {
    stopPolling()
    // The request that is out belongs to a page the browser is about to freeze;
    // on a phone it can simply never settle. Drop it here so the poll that runs
    // on the way back is a fresh one and not a queue behind a dead socket.
    abortPoll()
    pollBusy.value = false
    return
  }
  resumePolling()
}

/** A bfcache restore — no mount, no `visibilitychange` on some browsers. */
function onPageShow(event: PageTransitionEvent) {
  if (event.persisted) resumePolling()
}

function onDeepLinkOpen() {
  if (phase.value !== 'loading') linkOpened.value = true
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
  window.addEventListener('focus', resumePolling)
  window.addEventListener('pageshow', onPageShow)
  // Resume before minting: a token this tab is already holding is the one the
  // client is answering in the bot.
  if (!resumeHandshake()) void mintToken()
})

onBeforeUnmount(() => {
  unmounted = true
  stopPolling()
  stopRetry()
  stopCodeRetry()
  abortPoll()
  pollSecret = null
  // The stored handshake deliberately outlives the card: unmounting is not the
  // handshake ending, it is this tab being re-created around a login the client
  // is still completing in the bot. Only a terminal answer clears it.
  viewportQuery?.removeEventListener('change', onViewportChange)
  document.removeEventListener('visibilitychange', onVisibilityChange)
  window.removeEventListener('focus', resumePolling)
  window.removeEventListener('pageshow', onPageShow)
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

      <!-- Two ways into the same bot, both available on every device. Switching
           tabs is a change of instructions, not a restart: the handshake token
           and its background poll belong to the card, not to a tab. -->
      <AppTabs
        v-model="activeTab"
        class="mt-5"
        id-prefix="client-login"
        :label="$t('client.login.tabsLabel')"
        :tabs="tabs"
      />

      <!-- The QR and the deep link are two renderings of one token, so they
           share a panel body and differ only in the affordance and its
           instruction. One element, so the tab switch patches in place instead
           of tearing the card down. -->
      <section
        :id="`client-login-${activeTab}-panel`"
        role="tabpanel"
        :aria-labelledby="`client-login-${activeTab}-tab`"
        tabindex="0"
      >
        <div v-if="declined" class="client-banner info" role="status">
          <Icon name="alert" class="mt-0.5 size-4 shrink-0" />
          <span>{{ $t('client.login.declined') }}</span>
        </div>

        <!-- Dead handshake — expired, or never minted: named cause + one retry.
             The instruction and the affordance both go away, because "scan the
             QR" over a QR that is not there cannot be carried out. -->
        <template v-if="handshakeStopped">
          <div class="client-banner" :class="phase === 'expired' ? 'warn' : tokenErrorTone">
            <Icon name="alert" class="mt-0.5 size-4 shrink-0" />
            <span>{{ handshakeStoppedText }}</span>
          </div>
          <button
            type="button"
            class="mp-button mp-button-primary min-h-[46px] w-full"
            :disabled="phase === 'error' && !canRetryToken"
            @click="mintToken"
          >
            {{ $t('client.login.refresh') }}
          </button>
        </template>

        <template v-else>
          <!-- "Go to the bot and confirm" is the instruction until they have
               gone. After that the status line carries the one that matters
               ("come back here"), and leaving both up would have the card asking
               for something already done. -->
          <p v-if="!awaitingReturn" class="text-sm text-ink-muted">
            {{ activeTab === 'qr' ? $t('client.login.qrHint') : $t('client.login.telegramHint') }}
          </p>

          <!-- The QR frame keeps its size while the token is minting, so the card
               does not jump when it arrives. -->
          <div
            v-if="activeTab === 'qr'"
            class="mx-auto mt-4 w-[210px] rounded-xl border border-hairline p-3"
          >
            <div v-if="phase === 'loading'" class="client-skeleton aspect-square w-full"></div>
            <QrCode v-else :value="deepLink" :label="$t('client.login.qrLabel')" />
          </div>

          <!-- On a laptop: a new tab, never this one. Navigating this tab to
               `t.me` tears the card down mid-handshake — the poll stops, nothing
               redeems the token the client is about to confirm, and coming back
               mints a second one. On a phone the href is the `tg://` scheme
               instead, which hands the OS the app without loading a page, so the
               same tab is safe and the client comes back to *this* card rather
               than to Telegram's interstitial. Once they have gone, the button
               is their way back and steps down to secondary — the action that
               matters now is happening in Telegram. -->
          <template v-else>
            <a
              id="client-login-telegram"
              class="mp-button mt-4 min-h-[46px] w-full"
              :class="[
                awaitingReturn ? 'mp-button-outline' : 'mp-button-primary',
                phase === 'loading' ? 'pointer-events-none opacity-50' : '',
              ]"
              :href="telegramHref || undefined"
              :aria-disabled="phase === 'loading' ? 'true' : undefined"
              :target="opensAway ? '_blank' : undefined"
              :rel="opensAway ? 'noopener' : undefined"
              @click="onDeepLinkOpen"
            >
              {{
                awaitingReturn
                  ? $t('client.login.telegramReturn')
                  : $t('client.login.telegramButton')
              }}
            </a>

            <!-- The phone with no Telegram app installed: the scheme above did
                 nothing at all and left no error behind, so the way out has to
                 be visible before it is needed. -->
            <a
              v-if="!opensAway"
              class="mx-auto mt-2 block w-fit py-2 text-center text-sm text-accent-deep underline underline-offset-2"
              :href="deepLink"
              target="_blank"
              rel="noopener"
            >
              {{ $t('client.login.appFallback') }}
            </a>
          </template>

          <p class="mt-4 text-center text-sm text-ink-soft" role="status">
            {{ statusLine }}
          </p>

          <!-- The poll answers on its own within two seconds; this is for the
               client who is back, sees a waiting line, and would otherwise tap
               through to the bot a second time. -->
          <button
            v-if="awaitingReturn"
            id="client-login-check"
            type="button"
            class="mx-auto mt-3 block text-sm font-bold text-accent-deep disabled:opacity-50"
            :disabled="pollBusy"
            @click="checkNow"
          >
            {{ $t('client.login.checkNow') }}
          </button>
        </template>

        <!-- The camera-less way in: the client opens the bot by hand, presses
             «Kirish kodi» there and types the 6 digits back here. It belongs to
             the QR tab because that is the tab whose affordance can fail, and it
             stays collapsed — the reader who scanned the QR never meets it. It
             needs no handshake of its own, so it also works while this browser's
             token is expired or throttled. -->
        <div v-if="activeTab === 'qr'" class="mt-6 border-t border-hairline pt-5">
          <button
            type="button"
            class="flex w-full items-center justify-between text-sm font-bold text-accent-deep"
            :aria-expanded="codeOpen"
            aria-controls="client-code-fallback"
            @click="codeOpen = !codeOpen"
          >
            <span>{{ $t('client.login.codeToggle') }}</span>
            <Icon
              name="chevron-down"
              class="size-4 shrink-0 transition-transform"
              :class="codeOpen ? 'rotate-180' : ''"
            />
          </button>

          <div v-if="codeOpen" id="client-code-fallback" class="mt-4">
            <p class="text-sm text-ink-muted">{{ $t('client.login.codeHint') }}</p>
            <a
              v-if="botLink"
              class="mt-2 inline-flex text-sm font-bold text-accent-deep"
              :href="botLink"
              target="_blank"
              rel="noopener"
            >
              {{ botHandle }}
            </a>

            <form
              id="client-code-form"
              class="mt-4 space-y-3"
              novalidate
              @submit.prevent="submitCode"
            >
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
                {{
                  isRedeeming ? $t('client.login.codeSubmitting') : $t('client.login.codeSubmit')
                }}
              </button>
            </form>
          </div>
        </div>
      </section>

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
