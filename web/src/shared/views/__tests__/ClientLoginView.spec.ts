import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/shared/api/client'
import { clientConfig, roleConfigKey } from '@/shared/app/roleConfig'
import ClientLoginView from '@/shared/views/ClientLoginView.vue'
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

function handshake(index = 1) {
  return {
    token: `tok-${index}`,
    poll_secret: `secret-${index}`,
    deep_link: `https://t.me/mebel_pro_uz_bot?start=tok-${index}`,
    expires_at: '2026-01-01T00:05:00Z',
  }
}

function poll(status: ClientLoginPoll['status'], expired = false): ClientLoginPoll {
  return { status, expired }
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

describe('ClientLoginView — mobile', () => {
  it('opens on the Telegram tab and keeps the QR one click away', async () => {
    setViewport(true)
    const auth = useAuthStore()
    const create = vi.spyOn(auth, 'createClientLoginToken').mockResolvedValue(handshake())
    vi.spyOn(auth, 'pollClientLogin').mockResolvedValue(poll('pending'))

    const view = await mountLogin()

    expect(selectedTab(view)).toBe('Telegram orqali')
    const button = view.find('a.mp-button-primary')
    expect(button.attributes('href')).toBe('https://t.me/mebel_pro_uz_bot?start=tok-1')
    expect(button.text()).toBe("Telegram botga o'tish")
    expect(view.find('svg[role="img"]').exists()).toBe(false)

    // The QR is still there for the client whose Telegram lives on another
    // device — one tab away, on the same handshake.
    await selectTab(view, 'qr')

    expect(view.find('svg[role="img"]').exists()).toBe(true)
    expect(create).toHaveBeenCalledTimes(1)
  })
})
