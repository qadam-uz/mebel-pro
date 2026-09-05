import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DRAFT_RECOVERY_DEBOUNCE_MS } from '@/shared/app/constants'
import { clientConfig, roleConfigKey } from '@/shared/app/roleConfig'
import CuttingEditorView from '@/shared/views/CuttingEditorView.vue'
import { useCuttingStore, type CuttingDraft, type CuttingPart } from '@/shared/stores/cutting'

/**
 * The `localStorage` draft-recovery snapshot used to be written synchronously on
 * every edit — a full re-serialisation of the drawing (~60 kB at 300 rows) per
 * character. It is debounced now, which only holds if every exit still flushes
 * it: the layer exists for the tab closing inside the 700ms autosave window and
 * for a save that never reaches the server from a phone.
 *
 * These tests hold both halves — that keystrokes coalesce, and that each exit
 * (unload/pagehide, tab hidden, route leave) still leaves the *latest* state
 * behind — plus the two cases where the snapshot must NOT survive: a successful
 * server save, and a deleted drawing.
 */
const RECOVERY_KEY = 'mebel-pro:cutting-draft:draft-1'

// The editor is mounted *through* the router, not standalone: `onBeforeRouteLeave`
// only registers for a component rendered by a `<router-view>`, and that guard is
// one of the flush points under test.
const editorRoutes = [
  { path: '/c/cutting/:id', name: 'client-cutting-editor', component: CuttingEditorView },
  {
    path: '/c/cutting/:id/result',
    name: 'client-cutting-result',
    component: { template: '<div />' },
  },
  { path: '/c/cutting/drafts', name: 'client-cutting-drafts', component: { template: '<div />' } },
  { path: '/c/orders/:id', name: 'client-order-detail', component: { template: '<div />' } },
]

function part(overrides: Partial<CuttingPart> = {}): CuttingPart {
  return {
    part_ref: 'part-1',
    name: null,
    material_id: 'panel-1',
    material_source: 'shop',
    follow_grain: true,
    thickened: false,
    length_mm: 300,
    width_mm: 200,
    quantity: 1,
    edge_top: null,
    edge_bottom: null,
    edge_left: null,
    edge_right: null,
    ...overrides,
  }
}

function draft(): CuttingDraft {
  return {
    id: 'draft-1',
    client_id: 'client-1',
    name: 'Oshxona',
    preferred_branch_id: 'branch-1',
    kerf_mm: 4,
    edge_trim_mm: 5,
    own_material_allowed: false,
    parts_snapshot: [part()],
    own_panel_counts: {},
    own_edge_material_ids: [],
    chosen_result_id: null,
    revision_of_order_id: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    results: [],
  }
}

function storedParts(): CuttingPart[] | null {
  const raw = window.localStorage.getItem(RECOVERY_KEY)
  return raw ? (JSON.parse(raw).parts as CuttingPart[]) : null
}

async function mountEditor() {
  const router = createRouter({ history: createMemoryHistory(), routes: editorRoutes })
  await router.push('/c/cutting/draft-1')
  await router.isReady()

  const cutting = useCuttingStore()
  cutting.configureScope('client')
  cutting.currentDraft = draft()
  vi.spyOn(cutting, 'loadBranchOptions').mockResolvedValue()
  vi.spyOn(cutting, 'loadMaterials').mockResolvedValue([])
  const updateDraft = vi.spyOn(cutting, 'updateDraft').mockResolvedValue(draft())

  const wrapper = mount(
    { template: '<router-view />' },
    {
      global: {
        plugins: [router],
        provide: { [roleConfigKey as symbol]: clientConfig },
        stubs: {
          Icon: true,
          AppModal: true,
          CuttingBranchPicker: true,
          CuttingEdgePickerModal: true,
          CuttingEdgeTapeRegistry: true,
          CuttingImportWizard: true,
          CuttingResultsSection: true,
          SearchCombobox: true,
          ConfirmDialog: {
            props: ['open', 'busy'],
            emits: ['cancel', 'confirm'],
            template: `<section v-if="open" role="dialog">
              <button data-test="confirm" :disabled="busy" @click="$emit('confirm')" />
            </section>`,
          },
          CuttingPartRow: {
            props: ['part', 'index', 'edgeRegistry'],
            emits: ['update:length'],
            template: `<button data-test="edit-length" @click="$emit('update:length', part.length_mm + 1)" />`,
          },
        },
      },
    },
  )
  await flushPromises()
  return { wrapper, router, cutting, updateDraft }
}

async function type(wrapper: Awaited<ReturnType<typeof mountEditor>>['wrapper'], strokes: number) {
  for (let stroke = 0; stroke < strokes; stroke += 1) {
    await wrapper.get('[data-test="edit-length"]').trigger('click')
  }
}

describe('CuttingEditorView draft recovery', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('coalesces a burst of keystrokes into a single storage write', async () => {
    const { wrapper } = await mountEditor()
    const setItem = vi.spyOn(window.localStorage, 'setItem')

    await type(wrapper, 10)
    expect(setItem).not.toHaveBeenCalled()

    vi.advanceTimersByTime(DRAFT_RECOVERY_DEBOUNCE_MS)
    expect(setItem).toHaveBeenCalledTimes(1)
    expect(setItem.mock.calls[0]?.[0]).toBe(RECOVERY_KEY)
    // The one write carries the last keystroke, not the first.
    expect(storedParts()?.[0]?.length_mm).toBe(310)
  })

  it('flushes synchronously on pagehide', async () => {
    const { wrapper } = await mountEditor()

    await type(wrapper, 3)
    expect(storedParts()).toBeNull()

    window.dispatchEvent(new Event('pagehide'))

    expect(storedParts()?.[0]?.length_mm).toBe(303)
  })

  it('flushes synchronously when the tab is hidden', async () => {
    const { wrapper } = await mountEditor()

    await type(wrapper, 2)
    expect(storedParts()).toBeNull()

    // A phone backgrounds the tab before the OS kills it; `hidden` is the last
    // moment the editor is guaranteed to run.
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
    document.dispatchEvent(new Event('visibilitychange'))

    expect(storedParts()?.[0]?.length_mm).toBe(302)
  })

  it('leaves the latest snapshot behind when a route leave hits a failing save', async () => {
    const { wrapper, router, updateDraft } = await mountEditor()
    updateDraft.mockRejectedValue(new Error('offline'))

    await type(wrapper, 4)
    // Leaving inside the 300ms window — nothing has been written yet.
    expect(storedParts()).toBeNull()

    await router.push('/c/cutting/drafts')
    await flushPromises()

    expect(updateDraft).toHaveBeenCalled()
    expect(storedParts()?.[0]?.length_mm).toBe(304)
  })

  it('clears the snapshot once the server save succeeds', async () => {
    const { wrapper, updateDraft } = await mountEditor()

    await type(wrapper, 2)
    vi.advanceTimersByTime(DRAFT_RECOVERY_DEBOUNCE_MS)
    expect(storedParts()?.[0]?.length_mm).toBe(302)

    vi.advanceTimersByTime(1000)
    await flushPromises()

    expect(updateDraft).toHaveBeenCalled()
    expect(window.localStorage.getItem(RECOVERY_KEY)).toBeNull()
  })

  it('leaves no snapshot behind when the drawing is deleted', async () => {
    const { wrapper, router, cutting } = await mountEditor()
    vi.spyOn(cutting, 'deleteDraft').mockResolvedValue()

    // A queued write from the last keystroke must not resurrect the drawing.
    await type(wrapper, 2)
    await wrapper.get('[aria-label="Chizmani o\'chirish"]').trigger('click')
    await wrapper.get('[data-test="confirm"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/c/cutting/drafts')
    vi.advanceTimersByTime(2000)
    await flushPromises()
    expect(window.localStorage.getItem(RECOVERY_KEY)).toBeNull()
  })

  it('does not save a deleted drawing on the way out', async () => {
    const { wrapper, router, cutting, updateDraft } = await mountEditor()
    vi.spyOn(cutting, 'deleteDraft').mockResolvedValue()
    // The draft no longer exists server-side, so a PATCH against it 404s — and
    // the route-leave guard refuses to navigate on a failed save, which would
    // strand the user on the drawing they just deleted.
    updateDraft.mockRejectedValue(new Error('draft not found'))

    // Delete inside the 700ms autosave window: the edit is still queued.
    await type(wrapper, 2)
    await wrapper.get('[aria-label="Chizmani o\'chirish"]').trigger('click')
    await wrapper.get('[data-test="confirm"]').trigger('click')
    await flushPromises()

    expect(updateDraft).not.toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/c/cutting/drafts')

    // Nor does the queued save resurface after the debounce would have elapsed.
    vi.advanceTimersByTime(2000)
    await flushPromises()
    expect(updateDraft).not.toHaveBeenCalled()
  })
})
