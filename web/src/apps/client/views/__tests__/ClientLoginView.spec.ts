import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/shared/api/client'
import { clientConfig, roleConfigKey } from '@/shared/app/roleConfig'
import ClientLoginView from '@/apps/client/views/ClientLoginView.vue'
import { useAuthStore, type ClientLoginPoll, type MeResponse } from '@/shared/stores/auth'

const loginRoutes = [
  { path: '/auth/login', name: 'client-login', component: { template: '<div />' } },
  { path: '/c', name: 'client-home', component: { template: '<div />' } },
  { path: '/c/orders', name: 'client-orders', component: { template: '<div />' } },
]

const clientMe: MeResponse = {
  principal_type: 'client',
  principal_id: 'client-1',
  session_id: 'session-1',
  password_reset_required: false,
  workshop_id: null,
  workshop_name: null,
  is_owner: false,
  grants: [],
  login: null,
  full_name: null,
  phone: '+998901112233',
  name: 'Dilshod',
  preferred_branch_id: null,
  status: 'active',
}

const session = {
  access_token: 'access-1',
  token_type: 'bearer' as const,
  access_token_expires_at: '2026-01-01T00:05:00Z',
  me: clientMe,
}

/** Where the card parks the handshake it is polling (per tab). */
const HANDSHAKE_KEY = 'mp-client-login-handshake'

/** A minted handshake, alive for the five minutes the server gives it. */
function handshake(index = 1, livesForMs = 5 * 60_000) {
  return {
    token: `tok-${index}`,
    poll_secret: `secret-${index}`,
    deep_link: `https://t.me/mebel_pro_uz_bot?start=tok-${index}`,
    expires_at: new Date(Date.now() + livesForMs).toISOString(),
  }
}

/** What a card that is mid-handshake left behind for the tab that comes back. */
function parkHandshake(index = 1, livesForMs = 5 * 60_000) {
  const issued = handshake(index, livesForMs)
  window.sessionStorage.setItem(
    HANDSHAKE_KEY,
    JSON.stringify({
      deep_link: issued.deep_link,
      poll_secret: issued.poll_secret,
      expires_at: issued.expires_at,
    }),
  )
  return issued
}

function parkedHandshake(): { poll_secret?: string } | null {
  const raw = window.sessionStorage.getItem(HANDSHAKE_KEY)
  return raw ? (JSON.parse(raw) as { poll_secret?: string }) : null
}

function poll(status: ClientLoginPoll['status'], expired = false): ClientLoginPoll {
  return { status, expired }
}

/** The poll secrets a spy was asked with — every call carries its own abort
 *  signal and ceiling alongside, which no assertion here is about. */
function polledSecrets(spy: { mock: { calls: unknown[][] } }) {
  return spy.mock.calls.map((call) => call[0])
}

/** Drive the card's own poll interval forward by one tick. */
async function tick(times = 1) {
  for (let index = 0; index < times; index += 1) {
    await vi.advanceTimersByTimeAsync(2_000)
  }
  await flushPromises()
}

let viewportListeners: ((event: MediaQueryListEvent) => void)[] = []

function setViewport(mobile: boolean) {
  viewportListeners = []
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: (query: string) =>
      ({
        matches: mobile,
        media: query,
        addEventListener: (_: string, listener: (event: MediaQueryListEvent) => void) => {
          viewportListeners.push(listener)
        },
        removeEventListener: () => {},
      }) as unknown as MediaQueryList,
  })
}

/** Send the tab away and bring it back, the way a trip to Telegram does. */
async function hideTab() {
  Object.defineProperty(document, 'hidden', { configurable: true, value: true })
  document.dispatchEvent(new Event('visibilitychange'))
  await flushPromises()
}

async function showTab() {
  Object.defineProperty(document, 'hidden', { configurable: true, value: false })
  document.dispatchEvent(new Event('visibilitychange'))
  await flushPromises()
}

/** A bfcache restore: no mount, no reload, `persisted: true`. */
function pageShowEvent() {
  return Object.assign(new Event('pageshow'), { persisted: true })
}

/** The viewport answering later than mount — a settling layout, a rotation. */
async function emitViewportChange(mobile: boolean) {
  for (const listener of viewportListeners) listener({ matches: mobile } as MediaQueryListEvent)
  await flushPromises()
}

/** Click one of the card's two tabs, the way a reader does. */
async function selectTab(view: VueWrapper, tab: 'qr' | 'telegram') {
  await view.find(`#client-login-${tab}-tab`).trigger('click')
  await flushPromises()
}

function selectedTab(view: VueWrapper) {
  return view.find('[role="tab"][aria-selected="true"]').text()
}

/**
 * Tap the deep-link button. On mobile its href is a `tg://` scheme in this same
 * tab, which jsdom tries to follow and then logs as unimplemented navigation —
 * the tap is what these cases are about, not the browser's handling of a scheme.
 */
async function tapDeepLink(view: VueWrapper) {
  const link = view.find('#client-login-telegram')
  link.element.addEventListener('click', (event) => event.preventDefault(), { once: true })
  await link.trigger('click')
}

/** «Tasdiqladim, tekshirish» — the manual poll under the status line. */
function checkButton(view: VueWrapper) {
  return view.find('#client-login-check')
}

let router: Router
let wrapper: VueWrapper | null = null

async function mountLogin() {
  router = createRouter({ history: createMemoryHistory(), routes: loginRoutes })
  await router.push('/auth/login')
  await router.isReady()
  wrapper = mount(ClientLoginView, {
    global: {
      plugins: [router],
      provide: { [roleConfigKey as symbol]: clientConfig },
    },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.useFakeTimers()
  // The parked handshake outlives its card by design, so it also outlives a
  // test — every case states its own starting point.
  window.sessionStorage.clear()
  setViewport(false)
  Object.defineProperty(document, 'hidden', { configurable: true, value: false })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('ClientLoginView — Telegram handshake', () => {
  it('opens on the QR tab on desktop and waits', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending'))

    const view = await mountLogin()

    expect(selectedTab(view)).toBe('QR kod')
    expect(view.find('svg[role="img"]').exists()).toBe(true)
    // The phone's camera scans it — the QR is not something Telegram scans.
    expect(view.text()).toContain('telefoningiz kamerasi bilan skanerlang')
    expect(view.text()).toContain('Telegramdan javob kutilmoqda')
  })

  it('keeps one handshake and one live poll across a tab switch', async () => {
    const auth = useAuthStore()
    const create = vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    const pollSpy = vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending'))

    const view = await mountLogin()
    await tick()
    expect(pollSpy).toHaveBeenCalledTimes(1)

    await selectTab(view, 'telegram')

    // Same token behind the button the QR was encoding, and no second mint.
    const link = view.find('a.mp-button-primary')
    expect(link.attributes('href')).toBe('https://t.me/mebel_pro_uz_bot?start=tok-1')
    expect(link.text()).toBe("Telegram botga o'tish")
    expect(create).toHaveBeenCalledTimes(1)

    // The poll is the card's, not the tab's — it never stopped.
    await tick()
    expect(pollSpy).toHaveBeenCalledTimes(2)
    expect(create).toHaveBeenCalledTimes(1)
  })

  it('follows a late viewport answer, then defers to the reader', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending'))

    const view = await mountLogin()
    expect(selectedTab(view)).toBe('QR kod')

    // A viewport that only answers after mount still moves the default.
    await emitViewportChange(true)
    expect(selectedTab(view)).toBe('Telegram orqali')

    // Once the reader picks, no rotation or resize takes them off that tab.
    await selectTab(view, 'qr')
    await emitViewportChange(false)
    await emitViewportChange(true)
    expect(selectedTab(view)).toBe('QR kod')
  })

  it('offers the code fallback under the QR tab only', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending'))

    const view = await mountLogin()
    expect(view.find('button[aria-controls="client-code-fallback"]').exists()).toBe(true)

    await selectTab(view, 'telegram')
    expect(view.find('button[aria-controls="client-code-fallback"]').exists()).toBe(false)
  })

  it('says to confirm on the phone once the bot chat opens', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('started'))

    const view = await mountLogin()
    await tick()

    expect(view.text()).toContain('Telefoningizda tasdiqlang')
  })

  it('enters the app on the confirming poll and never polls again', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    const pollSpy = vi
      .spyOn(auth, 'pollClientLogin')
      .mockResolvedValueOnce(poll('started'))
      .mockResolvedValueOnce(session)
      .mockResolvedValue(poll('used'))

    await mountLogin()
    const replace = vi.spyOn(router, 'replace')
    await tick(4)

    // Two polls: the `started` one and the one that won the session. The
    // handshake is single-redemption, so a third would either 404 or hand a
    // second session to a card that has already navigated away.
    expect(pollSpy).toHaveBeenCalledTimes(2)
    expect(replace).toHaveBeenCalledTimes(1)
    expect(replace).toHaveBeenCalledWith('/c')
  })

  it('honours ?redirect= on the way in', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(session)

    router = createRouter({ history: createMemoryHistory(), routes: loginRoutes })
    await router.push('/auth/login?redirect=/c/orders')
    await router.isReady()
    const replace = vi.spyOn(router, 'replace')
    wrapper = mount(ClientLoginView, {
      global: { plugins: [router], provide: { [roleConfigKey as symbol]: clientConfig } },
    })
    await flushPromises()
    await tick()

    expect(replace).toHaveBeenCalledWith('/c/orders')
  })

  it('shows the stale-QR state and mints a new handshake on Yangilash', async () => {
    const auth = useAuthStore()
    const create = vi
      .spyOn(auth, 'createClientLoginToken')
      .mockResolvedValueOnce(handshake(1))
      .mockResolvedValueOnce(handshake(2))
    const pollSpy = vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending', true))

    const view = await mountLogin()
    await tick()

    expect(view.text()).toContain('QR eskirdi.')
    // Nothing left to resume: a reload onto a dead handshake must mint, not poll.
    expect(parkedHandshake()).toBeNull()
    const pollsWhileExpired = pollSpy.mock.calls.length
    await tick(2)
    expect(pollSpy.mock.calls.length).toBe(pollsWhileExpired)

    await view.find('button.mp-button-primary').trigger('click')
    await flushPromises()

    expect(create).toHaveBeenCalledTimes(2)
    expect(view.find('svg[role="img"]').exists()).toBe(true)
    await selectTab(view, 'telegram')
    expect(view.find('a[href="https://t.me/mebel_pro_uz_bot?start=tok-2"]').exists()).toBe(true)
  })

  it('returns to waiting on a fresh handshake when the client declines', async () => {
    const auth = useAuthStore()
    const create = vi
      .spyOn(auth, 'createClientLoginToken')
      .mockResolvedValueOnce(handshake(1))
      .mockResolvedValueOnce(handshake(2))
    vi.spyOn(auth, 'pollClientLogin')
      .mockResolvedValueOnce(poll('declined'))
      .mockResolvedValue(poll('pending'))

    const view = await mountLogin()
    await tick()

    expect(create).toHaveBeenCalledTimes(2)
    expect(view.text()).toContain('Kirish bekor qilindi')
    await selectTab(view, 'telegram')
    expect(view.find('a[href="https://t.me/mebel_pro_uz_bot?start=tok-2"]').exists()).toBe(true)
    await selectTab(view, 'qr')

    // The line survives the fresh handshake's own `pending` polls — clearing it
    // per tick would flash it for two seconds and take it away unread.
    await tick(2)
    expect(view.text()).toContain('Kirish bekor qilindi')
  })

  it('drops the cancelled line once the client opens the chat again', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken')
      .mockResolvedValueOnce(handshake(1))
      .mockResolvedValueOnce(handshake(2))
    vi.spyOn(auth, 'pollClientLogin')
      .mockResolvedValueOnce(poll('declined'))
      .mockResolvedValue(poll('started'))

    const view = await mountLogin()
    await tick()
    expect(view.text()).toContain('Kirish bekor qilindi')

    await tick()
    expect(view.text()).not.toContain('Kirish bekor qilindi')
    expect(view.text()).toContain('Telefoningizda tasdiqlang')
  })

  it('names the throttle and holds Yangilash for the retry budget', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockImplementation(async () => {
      auth.lastError = 'login_token_rate_limited'
      auth.lastErrorDetails = { retry_after_seconds: 3 }
      throw new ApiError(429, { code: 'login_token_rate_limited' })
    })

    const view = await mountLogin()

    expect(view.text()).toContain('3 soniyadan keyin')
    expect(view.find('button.mp-button-primary').attributes('disabled')).toBeDefined()

    await vi.advanceTimersByTimeAsync(3_000)
    await flushPromises()
    expect(view.find('button.mp-button-primary').attributes('disabled')).toBeUndefined()
  })

  it('states an hour-long token budget in minutes, not four digits of seconds', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockImplementation(async () => {
      auth.lastError = 'login_token_rate_limited'
      auth.lastErrorDetails = { retry_after_seconds: 3_061 }
      throw new ApiError(429, { code: 'login_token_rate_limited' })
    })

    const view = await mountLogin()

    expect(view.text()).toContain('52 daqiqadan keyin')
    expect(view.text()).not.toContain('3061')
  })

  it('stops polling when the card unmounts', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    const pollSpy = vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending'))

    const view = await mountLogin()
    await tick()
    expect(pollSpy).toHaveBeenCalledTimes(1)

    view.unmount()
    wrapper = null
    await tick(3)

    expect(pollSpy).toHaveBeenCalledTimes(1)
  })

  it('stops polling while the tab is hidden and asks again on return', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    const pollSpy = vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending'))

    await mountLogin()
    await tick()
    expect(pollSpy).toHaveBeenCalledTimes(1)

    Object.defineProperty(document, 'hidden', { configurable: true, value: true })
    document.dispatchEvent(new Event('visibilitychange'))
    await tick(3)
    expect(pollSpy).toHaveBeenCalledTimes(1)

    Object.defineProperty(document, 'hidden', { configurable: true, value: false })
    document.dispatchEvent(new Event('visibilitychange'))
    await flushPromises()
    expect(pollSpy).toHaveBeenCalledTimes(2)
  })
})

describe('ClientLoginView — surviving the trip to Telegram', () => {
  it('sends the deep link to a new tab so the card is never torn down', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending'))

    const view = await mountLogin()
    await selectTab(view, 'telegram')

    // Navigating *this* tab to t.me unmounts the card mid-handshake: the poll
    // stops and nothing is left to redeem the token the client just confirmed.
    const link = view.find('a.mp-button-primary')
    expect(link.attributes('target')).toBe('_blank')
    expect(link.attributes('rel')).toBe('noopener')
  })

  it('resumes a parked handshake instead of minting a second one', async () => {
    parkHandshake(7)
    const auth = useAuthStore()
    const create = vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake(1))
    const pollSpy = vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('started'))

    const view = await mountLogin()

    // Straight away, not two seconds from now: the page is usually back
    // precisely because the client has finished answering in the bot.
    expect(create).not.toHaveBeenCalled()
    expect(polledSecrets(pollSpy)).toContain('secret-7')
    expect(view.text()).toContain('Telefoningizda tasdiqlang')

    // Same handshake behind both affordances — the QR and the button the
    // resumed card renders are the token the client is already holding. The bot
    // chat is already open, so that button is already the way back.
    await selectTab(view, 'telegram')
    const back = view.find('#client-login-telegram')
    expect(back.attributes('href')).toBe('https://t.me/mebel_pro_uz_bot?start=tok-7')
    expect(back.text()).toBe('Telegramga qaytish')
    await tick()
    expect(polledSecrets(pollSpy).at(-1)).toBe('secret-7')
    expect(create).not.toHaveBeenCalled()
  })

  it('parks the live handshake, so a reload finds it', async () => {
    const auth = useAuthStore()
    const create = vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake(1))
    const pollSpy = vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending'))

    const view = await mountLogin()
    await tick()
    expect(parkedHandshake()).toMatchObject({ poll_secret: 'secret-1' })

    // The tab is re-created around the same login — a reload, or a browser that
    // evicted it while the client was in Telegram.
    view.unmount()
    wrapper = null
    await mountLogin()

    expect(create).toHaveBeenCalledTimes(1)
    expect(polledSecrets(pollSpy).at(-1)).toBe('secret-1')
  })

  it('mints afresh when the parked handshake has already expired', async () => {
    parkHandshake(7, -1_000)
    const auth = useAuthStore()
    const create = vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake(2))
    const pollSpy = vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending'))

    const view = await mountLogin()
    await tick()

    expect(create).toHaveBeenCalledTimes(1)
    expect(polledSecrets(pollSpy)).toContain('secret-2')
    expect(polledSecrets(pollSpy)).not.toContain('secret-7')
    await selectTab(view, 'telegram')
    expect(view.find('a.mp-button-primary').attributes('href')).toBe(
      'https://t.me/mebel_pro_uz_bot?start=tok-2',
    )
    // The dead entry is replaced, not left for the next reload to trip over.
    expect(parkedHandshake()).toMatchObject({ poll_secret: 'secret-2' })
  })

  it('drops the parked handshake once the session is won', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    vi.spyOn(auth, 'pollClientLogin')
      .mockResolvedValueOnce(poll('started'))
      .mockResolvedValue(session)

    await mountLogin()
    await tick()
    expect(parkedHandshake()).toMatchObject({ poll_secret: 'secret-1' })

    await tick()

    expect(parkedHandshake()).toBeNull()
  })
})

describe('ClientLoginView — code fallback', () => {
  async function openFallback() {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending'))
    const view = await mountLogin()
    await view.find('button[aria-controls="client-code-fallback"]').trigger('click')
    return { auth, view }
  }

  it('is collapsed until asked for', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending'))

    const view = await mountLogin()
    const toggle = view.find('button[aria-controls="client-code-fallback"]')
    expect(toggle.text()).toBe('Kamera ishlamayaptimi? Kod bilan kirish')
    expect(view.find('#client-code-form').exists()).toBe(false)

    await toggle.trigger('click')

    expect(view.find('#client-code-form').exists()).toBe(true)
    expect(view.find('#client-login-code').exists()).toBe(true)
  })

  it('links the bot the deep link names, so the two can never disagree', async () => {
    const { view } = await openFallback()

    const link = view.find('a[href="https://t.me/mebel_pro_uz_bot"]')
    expect(link.exists()).toBe(true)
    expect(link.text()).toBe('@mebel_pro_uz_bot')
    expect(view.text()).toContain('«Kirish kodi» tugmasini bosing')
  })

  it('keeps a rejected code on screen behind one generic message', async () => {
    const { auth, view } = await openFallback()
    vi.spyOn(auth, 'redeemClientLoginCode').mockImplementation(async () => {
      auth.lastError = 'invalid_code'
      throw new ApiError(400, { code: 'invalid_code' })
    })

    const input = view.find('#client-login-code')
    await input.setValue('123456')
    await view.find('#client-code-form').trigger('submit')
    await flushPromises()

    expect(view.text()).toContain("Kod noto'g'ri yoki muddati tugagan.")
    expect((input.element as HTMLInputElement).value).toBe('123456')
    expect(input.attributes('aria-invalid')).toBe('true')
  })

  it('counts the redeem throttle down and blocks submit meanwhile', async () => {
    const { auth, view } = await openFallback()
    vi.spyOn(auth, 'redeemClientLoginCode').mockImplementation(async () => {
      auth.lastError = 'login_code_rate_limited'
      auth.lastErrorDetails = { retry_after_seconds: 2 }
      throw new ApiError(429, { code: 'login_code_rate_limited' })
    })

    await view.find('#client-login-code').setValue('123456')
    await view.find('#client-code-form').trigger('submit')
    await flushPromises()

    expect(view.text()).toContain('2 soniyadan keyin')
    expect(view.find('button[type="submit"]').attributes('disabled')).toBeDefined()

    await vi.advanceTimersByTimeAsync(2_000)
    await flushPromises()
    expect(view.find('button[type="submit"]').attributes('disabled')).toBeUndefined()
  })

  it('enters the app on a redeemed code', async () => {
    const { auth, view } = await openFallback()
    vi.spyOn(auth, 'redeemClientLoginCode').mockResolvedValue(session)
    const replace = vi.spyOn(router, 'replace')

    await view.find('#client-login-code').setValue('123456')
    await view.find('#client-code-form').trigger('submit')
    await flushPromises()

    expect(replace).toHaveBeenCalledWith('/c')
  })

  it('drops non-digits as they are typed', async () => {
    const { view } = await openFallback()
    const input = view.find('#client-login-code')

    await input.setValue('12a34b5678')

    expect((input.element as HTMLInputElement).value).toBe('123456')
  })
})

describe('ClientLoginView — the trip back', () => {
  /** A poll that never answers — a phone freezing the page mid-request. */
  function hangingPoll() {
    const signals: (AbortSignal | undefined)[] = []
    const impl = (_secret: string, init?: { signal?: AbortSignal }) => {
      signals.push(init?.signal)
      return new Promise<never>((_, reject) => {
        init?.signal?.addEventListener('abort', () =>
          reject(new DOMException('aborted', 'AbortError')),
        )
      })
    }
    return { signals, impl }
  }

  it('aborts the poll the tab froze and asks again on return', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    const hanging = hangingPoll()
    const pollSpy = vi
      .spyOn(auth, 'pollClientLogin')
      .mockImplementation(hanging.impl as typeof auth.pollClientLogin)

    await mountLogin()
    await tick()
    expect(pollSpy).toHaveBeenCalledTimes(1)
    expect(hanging.signals[0]?.aborted).toBe(false)

    // The client is in Telegram. The request that was out belongs to a page the
    // browser is freezing and may never settle — it goes now.
    await hideTab()
    expect(hanging.signals[0]?.aborted).toBe(true)

    // Back on the page. The wedge this fixes: a boolean latch left set by that
    // never-settling request swallowed every poll from here on, and only a
    // reload got the client in.
    await showTab()
    expect(pollSpy).toHaveBeenCalledTimes(2)

    // And the loop is armed again, not just poked once.
    await tick()
    expect(pollSpy).toHaveBeenCalledTimes(3)
  })

  it('signs in on the poll that follows the return', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    const hanging = hangingPoll()
    const pollSpy = vi
      .spyOn(auth, 'pollClientLogin')
      .mockImplementation(hanging.impl as typeof auth.pollClientLogin)

    await mountLogin()
    const replace = vi.spyOn(router, 'replace')
    await tick()
    await hideTab()

    // The bot confirmed while the page was frozen.
    pollSpy.mockResolvedValue(session)
    await showTab()

    expect(replace).toHaveBeenCalledWith('/c')
  })

  it('answers a burst of return events with one request', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    const pollSpy = vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending'))

    await mountLogin()
    await tick()
    const polls = pollSpy.mock.calls.length

    await hideTab()
    // A phone fires all three on the way back; they are one return.
    Object.defineProperty(document, 'hidden', { configurable: true, value: false })
    document.dispatchEvent(new Event('visibilitychange'))
    window.dispatchEvent(new Event('focus'))
    window.dispatchEvent(pageShowEvent())
    await flushPromises()

    expect(pollSpy.mock.calls.length).toBe(polls + 1)
  })

  it('takes focus alone as a return', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    const pollSpy = vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending'))

    await mountLogin()
    await tick()
    const polls = pollSpy.mock.calls.length

    window.dispatchEvent(new Event('focus'))
    await flushPromises()

    expect(pollSpy.mock.calls.length).toBe(polls + 1)
  })

  it('takes a bfcache restore alone as a return', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    const pollSpy = vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending'))

    await mountLogin()
    await tick()
    const polls = pollSpy.mock.calls.length

    window.dispatchEvent(pageShowEvent())
    await flushPromises()

    expect(pollSpy.mock.calls.length).toBe(polls + 1)
  })

  it('ignores a return once the handshake is dead', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    const pollSpy = vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending', true))

    const view = await mountLogin()
    await tick()
    expect(view.text()).toContain('QR eskirdi.')
    const polls = pollSpy.mock.calls.length

    window.dispatchEvent(new Event('focus'))
    window.dispatchEvent(pageShowEvent())
    await flushPromises()

    expect(pollSpy.mock.calls.length).toBe(polls)
  })
})

describe('ClientLoginView — mobile', () => {
  it('opens on the Telegram tab and keeps the QR one click away', async () => {
    setViewport(true)
    const auth = useAuthStore()
    const create = vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending'))

    const view = await mountLogin()

    expect(selectedTab(view)).toBe('Telegram orqali')
    const button = view.find('a.mp-button-primary')
    expect(button.text()).toBe("Telegram botga o'tish")
    expect(view.find('svg[role="img"]').exists()).toBe(false)

    // The QR is still there for the client whose Telegram lives on another
    // device — one tab away, on the same handshake.
    await selectTab(view, 'qr')

    expect(view.find('svg[role="img"]').exists()).toBe(true)
    expect(create).toHaveBeenCalledTimes(1)
  })

  it('hands the phone the app scheme in this tab, with t.me underneath', async () => {
    setViewport(true)
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending'))

    const view = await mountLogin()

    // `https://t.me/…` on a phone loads Telegram's own "Open in Telegram" page
    // first, and the client comes back to *that* tab. The scheme opens the app
    // with no page in between, so this tab — and its poll — stays put.
    const button = view.find('a.mp-button-primary')
    expect(button.attributes('href')).toBe('tg://resolve?domain=mebel_pro_uz_bot&start=tok-1')
    expect(button.attributes('target')).toBeUndefined()

    // No installed Telegram means the scheme did nothing and said nothing, so
    // the way out is on screen before it is needed.
    const fallback = view
      .findAll('a')
      .find((link) => link.text() === 'Telegram ochilmadimi? t.me orqali ochish')
    expect(fallback?.attributes('href')).toBe('https://t.me/mebel_pro_uz_bot?start=tok-1')
    expect(fallback?.attributes('target')).toBe('_blank')
  })

  it('turns the button into the way back and offers a manual check once tapped', async () => {
    setViewport(true)
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    const pollSpy = vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending'))

    const view = await mountLogin()
    expect(checkButton(view).exists()).toBe(false)

    await tapDeepLink(view)

    // The action that matters now is in Telegram; this button is only the way
    // back, so it steps down and says so.
    const back = view.find('a.mp-button-outline')
    expect(back.text()).toBe('Telegramga qaytish')
    expect(view.find('a.mp-button-primary').exists()).toBe(false)
    expect(view.text()).toContain('shu sahifaga qayting — avtomatik kirasiz')
    // …and the card stops asking for the thing that has just been done.
    expect(view.text()).not.toContain("Telegram botga o'ting")

    // The client who is back and impatient gets an answer instead of tapping
    // through to the bot a second time.
    const polls = pollSpy.mock.calls.length
    await checkButton(view).trigger('click')
    await flushPromises()
    expect(pollSpy.mock.calls.length).toBe(polls + 1)
  })

  it('drops the "come back" state when the handshake is replaced', async () => {
    setViewport(true)
    const auth = useAuthStore()
    vi.spyOn(auth, 'createClientLoginToken')
      .mockResolvedValueOnce(handshake(1))
      .mockResolvedValueOnce(handshake(2))
    vi.spyOn(auth, 'pollClientLogin')
      .mockResolvedValueOnce(poll('declined'))
      .mockResolvedValue(poll('pending'))

    const view = await mountLogin()
    await tapDeepLink(view)
    expect(checkButton(view).exists()).toBe(true)

    // A declined token mints a fresh one — a link nobody has opened yet.
    await tick()

    expect(checkButton(view).exists()).toBe(false)
    expect(view.find('a.mp-button-primary').text()).toBe("Telegram botga o'tish")
  })
})
