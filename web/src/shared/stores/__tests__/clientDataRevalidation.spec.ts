import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { api, type ApiRequestInit } from '@/shared/api/client'
import { useAuthStore } from '@/shared/stores/auth'
import { useCuttingStore, type CuttingDraft } from '@/shared/stores/cutting'
import { useNotificationsStore, type NotificationItem } from '@/shared/stores/notifications'
import { useOrdersStore, type OrderDetail } from '@/shared/stores/orders'

/**
 * Stale-while-revalidate + abort across the client's shared reads (client
 * audit 2026-09-03). Everything below is store logic — the flag ownership, what
 * survives an in-flight refresh, and which rejection is a failure — with only
 * the API client faked, and `isAbortError` / `captureApiError` left real so the
 * abort really is told apart from a failure rather than by a test double.
 */
vi.mock('@/shared/app/authInit', () => ({
  authInit: () => ({ accessToken: 'access-token' }),
}))

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return { ...actual, api: { ...actual.api, get: vi.fn() } }
})

/** One in-flight request: the signal the store handed us, plus its settlers. */
interface Pending {
  path: string
  signal: AbortSignal | undefined
  resolve: (value: unknown) => void
  reject: (reason: unknown) => void
}

let pending: Pending[] = []

/**
 * `api.get` that never settles on its own — the test decides when (and whether)
 * each call answers, and an abort rejects it exactly as `fetch` does.
 */
function captureRequests() {
  pending = []
  vi.mocked(api.get).mockImplementation((path: string, init?: ApiRequestInit) => {
    return new Promise((resolve, reject) => {
      const entry: Pending = { path, signal: init?.signal ?? undefined, resolve, reject }
      pending.push(entry)
      init?.signal?.addEventListener('abort', () =>
        reject(new DOMException('The operation was aborted.', 'AbortError')),
      )
    })
  })
}

/** Let the microtask queue drain so a settled request reaches the store. */
const settle = () => new Promise((resolve) => setTimeout(resolve, 0))

function draft(id: string): CuttingDraft {
  return {
    id,
    client_id: 'client-1',
    name: null,
    preferred_branch_id: null,
    kerf_mm: 4,
    edge_trim_mm: 5,
    own_material_allowed: false,
    parts_snapshot: [],
    own_panel_counts: {},
    own_edge_material_ids: [],
    chosen_result_id: null,
    revision_of_order_id: null,
    created_at: '2026-09-01T00:00:00Z',
    updated_at: '2026-09-01T00:00:00Z',
    results: [],
  }
}

function notification(id: string): NotificationItem {
  return {
    id,
    recipient_type: 'client',
    recipient_id: 'client-1',
    event_code: 'order_ready',
    entity_type: 'order',
    entity_id: 'order-1',
    payload: {},
    created_at: '2026-09-01T00:00:00Z',
    read_at: null,
  }
}

function order(id: string): OrderDetail {
  return { id, order_number: 123456, status: 'new', events: [] } as unknown as OrderDetail
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(api.get).mockReset()
  captureRequests()
})

describe('cutting drafts — stale while revalidating', () => {
  it('keeps the drafts in hand on screen while the next read is in flight', async () => {
    const cutting = useCuttingStore()
    void cutting.loadDrafts()
    pending[0].resolve([draft('draft-1')])
    await settle()

    void cutting.loadDrafts()

    expect(cutting.drafts).toHaveLength(1)
    expect(cutting.draftsLoading).toBe(true)
  })

  it('aborts the older list read and keeps the newer answer', async () => {
    const cutting = useCuttingStore()
    void cutting.loadDrafts()
    void cutting.loadDrafts()
    await settle()

    expect(pending[0].signal?.aborted).toBe(true)
    expect(pending[1].signal?.aborted).toBe(false)
    // The loser's rejection is a cancellation, not a failure — no error line,
    // and its `finally` must not switch the skeleton off under the winner.
    expect(cutting.error).toBeNull()
    expect(cutting.draftsLoading).toBe(true)

    pending[1].resolve([draft('draft-2')])
    await settle()

    expect(cutting.drafts.map((item) => item.id)).toEqual(['draft-2'])
    expect(cutting.draftsLoading).toBe(false)
    expect(cutting.error).toBeNull()
  })

  it('does not blank the list on the client while the workshop drafts flag moves', async () => {
    // The two lists had one shared flag: home's refresh landing mid-editor
    // switched the editor's skeleton off, and vice versa.
    const cutting = useCuttingStore()
    void cutting.loadDrafts()
    void cutting.loadDraft('draft-9')

    expect(cutting.draftsLoading).toBe(true)
    expect(cutting.loading).toBe(true)

    pending[0].resolve([draft('draft-1')])
    await settle()

    expect(cutting.draftsLoading).toBe(false)
    expect(cutting.loading).toBe(true)
  })
})

describe('cutting draft detail — revalidate in place', () => {
  it('keeps the draft on screen while the same id revalidates', async () => {
    const cutting = useCuttingStore()
    void cutting.loadDraft('draft-1')
    pending[0].resolve(draft('draft-1'))
    await settle()

    void cutting.loadDraft('draft-1')

    expect(cutting.currentDraft?.id).toBe('draft-1')
  })

  it('clears first when a different draft is opened', async () => {
    const cutting = useCuttingStore()
    void cutting.loadDraft('draft-1')
    pending[0].resolve(draft('draft-1'))
    await settle()

    void cutting.loadDraft('draft-2')

    expect(cutting.currentDraft).toBeNull()
  })

  it('drops the draft and names the failure when the read fails', async () => {
    const cutting = useCuttingStore()
    void cutting.loadDraft('draft-1')
    pending[0].resolve(draft('draft-1'))
    await settle()

    void cutting.loadDraft('draft-1')
    pending[1].reject(new Error('offline'))
    await settle()

    expect(cutting.currentDraft).toBeNull()
    expect(cutting.error).toBe('cutting_draft_load_failed')
  })
})

describe('notifications — stale while revalidating', () => {
  // The feed is authed: without a token the store declines to read at all.
  beforeEach(() => {
    useAuthStore().accessToken = 'access-token'
  })

  it('keeps the feed in hand while the next page is in flight', async () => {
    const notifications = useNotificationsStore()
    void notifications.loadList(20, 0, false)
    pending[0].resolve([notification('n-1')])
    await settle()

    void notifications.loadList(20, 0, true)

    expect(notifications.items).toHaveLength(1)
    expect(notifications.loading).toBe(true)
  })

  it('aborts the older read, and an abort is never an error', async () => {
    const notifications = useNotificationsStore()
    void notifications.loadList(20, 0, false)
    void notifications.loadList(20, 0, true)
    await settle()

    expect(pending[0].signal?.aborted).toBe(true)
    expect(notifications.error).toBeNull()
    expect(notifications.loading).toBe(true)

    pending[1].resolve([notification('n-2')])
    await settle()

    expect(notifications.items.map((item) => item.id)).toEqual(['n-2'])
    expect(notifications.loading).toBe(false)
  })
})

describe('order detail — revalidate in place', () => {
  it('keeps the order on screen while the same id revalidates', async () => {
    const orders = useOrdersStore()
    void orders.loadClientOrder('order-1')
    pending[0].resolve(order('order-1'))
    await settle()

    void orders.loadClientOrder('order-1')

    expect(orders.currentOrder?.id).toBe('order-1')
    expect(orders.detailLoading).toBe(true)
  })

  it('clears first when a different order is opened', async () => {
    const orders = useOrdersStore()
    void orders.loadClientOrder('order-1')
    pending[0].resolve(order('order-1'))
    await settle()

    void orders.loadClientOrder('order-2')

    expect(orders.currentOrder).toBeNull()
  })

  it('leaves the detail flag alone when the list read lands mid-navigation', async () => {
    // `loading` is shared with the list, so the detail page reads
    // `detailLoading`: a list page arriving while the order is still in flight
    // used to switch the skeleton off and flash the not-found state.
    const orders = useOrdersStore()
    void orders.loadClientOrders()
    void orders.loadClientOrder('order-1')

    pending[0].resolve([])
    await settle()

    expect(orders.detailLoading).toBe(true)
    expect(orders.currentOrder).toBeNull()
  })

  it('does not paint an error when its read is aborted', async () => {
    const orders = useOrdersStore()
    void orders.loadClientOrder('order-1')
    void orders.loadClientOrder('order-2')
    await settle()

    expect(pending[0].signal?.aborted).toBe(true)
    expect(orders.error).toBeNull()

    pending[1].resolve(order('order-2'))
    await settle()

    expect(orders.currentOrder?.id).toBe('order-2')
    expect(orders.detailLoading).toBe(false)
  })
})
