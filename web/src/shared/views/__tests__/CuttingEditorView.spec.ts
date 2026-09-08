import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref, type Ref } from 'vue'

import { ApiError } from '@/shared/api/client'
import type { CuttingEditorAdapter } from '@/shared/app/cuttingEditorAdapter'
import { clientConfig, roleConfigKey, workshopConfig } from '@/shared/app/roleConfig'
import CuttingBranchPicker from '@/shared/components/CuttingBranchPicker.vue'
import CuttingEditorView from '@/shared/views/CuttingEditorView.vue'
import { useAuthStore, type MeResponse } from '@/shared/stores/auth'
import {
  useCuttingStore,
  type ClientBranchOption,
  type ClientCatalogMaterialOption,
  type CuttingDraft,
  type CuttingPart,
} from '@/shared/stores/cutting'

/**
 * The editor keeps a per-draft recovery snapshot in `localStorage` (the
 * last-mile layer behind server autosave), and jsdom keeps that storage for the
 * whole file. Every test here mounts `draft-1`, so without this one test's
 * parts reappear in the next — which is the editor working as designed, and a
 * shared browser these tests never meant to share.
 */
beforeEach(() => {
  window.localStorage.clear()
})

const editorRoutes = [
  { path: '/c/cutting/new', name: 'client-cutting-new', component: { template: '<div />' } },
  { path: '/c/cutting/:id', name: 'client-cutting-editor', component: { template: '<div />' } },
  {
    path: '/c/cutting/:id/result',
    name: 'client-cutting-result',
    component: { template: '<div />' },
  },
  { path: '/c/cutting/drafts', name: 'client-cutting-drafts', component: { template: '<div />' } },
  { path: '/c/orders/:id', name: 'client-order-detail', component: { template: '<div />' } },
  { path: '/c/branches', name: 'client-branches', component: { template: '<div />' } },
]

function draft(overrides: Partial<CuttingDraft> = {}): CuttingDraft {
  return {
    id: 'draft-1',
    client_id: 'client-1',
    name: 'Oshxona',
    preferred_branch_id: null,
    kerf_mm: 4,
    edge_trim_mm: 5,
    own_material_allowed: false,
    parts_snapshot: [],
    own_panel_counts: {},
    own_edge_material_ids: [],
    chosen_result_id: null,
    revision_of_order_id: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    results: [],
    ...overrides,
  }
}

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

function importedResult(parts: CuttingPart[]) {
  return {
    id: 'imported-result-1',
    source: 'imported_map',
    status: 'candidate',
    parts_snapshot: parts,
    panels: [],
  } as unknown as CuttingDraft['results'][number]
}

async function mountEditor(
  path = '/c/cutting/draft-1',
  currentDraft: CuttingDraft | null = draft(),
  // Per-test stub overrides. `AppModal: true` renders no slot, so a test that
  // needs to reach a component *inside* a modal replaces that one stub.
  stubOverrides: Record<string, unknown> = {},
  // The store scope decides which editor this is (SPEC_CLIENT_UX_MVP §7): the
  // client's phone sheets, group tape and decor-first pickers, or the
  // workshop's registry, tape picker and file import. Default 'client', the
  // store's own default.
  scope: 'client' | 'workshop' = 'client',
) {
  const router = createRouter({ history: createMemoryHistory(), routes: editorRoutes })
  await router.push(path)
  await router.isReady()

  const cutting = useCuttingStore()
  cutting.configureScope(scope)
  cutting.currentDraft = currentDraft
  vi.spyOn(cutting, 'loadBranchOptions').mockResolvedValue()
  vi.spyOn(cutting, 'loadMaterials').mockResolvedValue([])

  const wrapper = mount(CuttingEditorView, {
    global: {
      plugins: [router],
      provide: { [roleConfigKey as symbol]: clientConfig },
      stubs: {
        Icon: true,
        AppModal: true,
        CuttingBranchPicker: true,
        // The docked kromka card is where a side is banded in both editors
        // now (§13 W2), so it is the seam these specs write an edge through.
        CuttingKromkaPanel: {
          props: ['part', 'partNumber', 'groupTapeDecor', 'selectedThicknessMm'],
          emits: ['set-side', 'close'],
          template: `
            <button data-test="edge-only-edit" @click="$emit('set-side', 'edge_top', 'edge-2')" />
          `,
        },
        CuttingImportWizard: {
          props: ['open'],
          emits: ['committed'],
          template: `<button v-if="open" data-test="map-committed" @click="$emit('committed', 'draft-map')" />`,
        },
        CuttingPartRow: {
          props: [
            'part',
            'index',
            'displayIndex',
            'hasError',
            'sizeError',
            'materialMissing',
            'optimizeError',
            'edgeRegistry',
          ],
          emits: ['open-edge-picker', 'update:length'],
          template: `
            <div>
              <button data-test="open-edge-picker" @click="$emit('open-edge-picker')" />
              <button data-test="edit-length" @click="$emit('update:length', 301)" />
            </div>
          `,
        },
        CuttingResultsSection: true,
        SearchCombobox: true,
        ConfirmDialog: {
          props: ['open', 'title', 'message', 'busy'],
          emits: ['cancel', 'confirm'],
          template: `
            <section v-if="open" role="dialog">
              <h2>{{ title }}</h2><p>{{ message }}</p><slot />
              <button type="button" :disabled="busy" @click="$emit('confirm')">confirm</button>
              <button type="button" @click="$emit('cancel')">cancel</button>
            </section>
          `,
        },
        ...stubOverrides,
      },
    },
  })
  await flushPromises()
  return { wrapper, router, cutting }
}

describe('CuttingEditorView draft deletion', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('hides deletion for a new or read-only drawing', async () => {
    const fresh = await mountEditor('/c/cutting/new', null)
    expect(fresh.wrapper.find('[aria-label="Chizmani o\'chirish"]').exists()).toBe(false)

    const readOnly = await mountEditor(
      '/c/cutting/draft-1',
      draft({
        results: [{ order_id: 'order-1', panels: [] }] as unknown as CuttingDraft['results'],
      }),
    )
    expect(readOnly.wrapper.find('[aria-label="Chizmani o\'chirish"]').exists()).toBe(false)
  })

  it('deletes the drawing after confirmation and returns to the drafts list', async () => {
    const { wrapper, router, cutting } = await mountEditor()
    const remove = vi.spyOn(cutting, 'deleteDraft').mockResolvedValue()

    await wrapper.get('[aria-label="Chizmani o\'chirish"]').trigger('click')
    expect(wrapper.get('[role="dialog"]').text()).toContain('«Oshxona» — 0 detalli chizma')

    await wrapper.get('[role="dialog"] button').trigger('click')
    await flushPromises()

    expect(remove).toHaveBeenCalledWith('draft-1')
    expect(router.currentRoute.value.path).toBe('/c/cutting/drafts')
  })

  it('keeps the confirmation open and shows its trace when deletion fails', async () => {
    const { wrapper, cutting } = await mountEditor()
    vi.spyOn(cutting, 'deleteDraft').mockRejectedValue(
      new ApiError(409, { code: 'cutting_draft_delete_failed', trace_id: 'trace-delete-1' }),
    )

    await wrapper.get('[aria-label="Chizmani o\'chirish"]').trigger('click')
    await wrapper.get('[role="dialog"] button').trigger('click')
    await flushPromises()

    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    expect(wrapper.get('[role="dialog"]').text()).toContain('trace_id: trace-delete-1')
  })

  it('opens a current result but never optimizes a read-only drawing', async () => {
    const initialPart = part()
    const currentResult = {
      ...importedResult([initialPart]),
      order_id: 'order-1',
    }
    const saved = await mountEditor(
      '/c/cutting/draft-read-only-result',
      draft({
        id: 'draft-read-only-result',
        preferred_branch_id: 'branch-1',
        parts_snapshot: [initialPart],
        chosen_result_id: 'imported-result-1',
        results: [currentResult],
      }),
    )
    // §7.0 fixes the client's CTA copy: the button says what the tap does.
    const viewResult = saved.wrapper
      .findAll('button')
      .filter((button) => button.text() === "Natijani ko'rish")

    expect(viewResult).toHaveLength(1)
    expect(viewResult[0]?.attributes('disabled')).toBeUndefined()
    await viewResult[0]?.trigger('click')
    await flushPromises()
    expect(saved.router.currentRoute.value.path).toBe('/c/cutting/draft-read-only-result/result')

    const withoutResult = await mountEditor(
      '/c/cutting/draft-read-only-empty',
      draft({
        id: 'draft-read-only-empty',
        preferred_branch_id: 'branch-1',
        parts_snapshot: [initialPart],
        results: [{ order_id: 'order-1', panels: [] }] as unknown as CuttingDraft['results'],
      }),
    )
    const optimise = withoutResult.wrapper
      .findAll('button')
      .filter((button) => button.text() === 'Hisoblash')

    expect(optimise).toHaveLength(1)
    expect(optimise[0]?.attributes('disabled')).toBeDefined()
  })
})

/**
 * The MAP-import layout guard, in **workshop** scope.
 *
 * These used to mount the client editor, because the client had the import too.
 * Decision 18 / §7.6 removed it from the client entirely — no mode switch, no
 * wizard mount, no flag — so the guard's only remaining home is the workshop
 * editor, and that is where it is now exercised. The subject is unchanged: an
 * edit that moves a part must not silently discard an imported layout, and an
 * edge-only edit must not warn at all.
 *
 * A revision draft is the shape that puts the workshop editor outside its order
 * wizard (`inOrderWizard` is false for a revision), which is the standalone
 * editor these assertions describe — the mode switch, the sticky CTA and the
 * edge-picker modal rather than the docked panel.
 */
describe('CuttingEditorView imported layout guard (workshop)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function workshopDraft(overrides: Partial<CuttingDraft> = {}) {
    return draft({ revision_of_order_id: 'order-9', ...overrides })
  }

  it('opens a committed MAP import on the standalone result stage', async () => {
    const { wrapper, router } = await mountEditor(
      '/c/cutting/draft-1',
      workshopDraft({ preferred_branch_id: 'branch-1' }),
      {},
      'workshop',
    )

    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Fayldan import')
      ?.trigger('click')
    await wrapper.get('[data-test="map-committed"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/c/cutting/draft-map/result')
  })

  it('offers one Continue CTA for an unchanged chosen MAP layout', async () => {
    const initialPart = part()
    const { wrapper, router } = await mountEditor(
      '/c/cutting/draft-map',
      workshopDraft({
        id: 'draft-map',
        preferred_branch_id: 'branch-1',
        parts_snapshot: [initialPart],
        chosen_result_id: 'imported-result-1',
        results: [importedResult([initialPart])],
      }),
      {},
      'workshop',
    )

    const viewResult = wrapper.findAll('button').filter((button) => button.text() === 'Davom etish')
    expect(viewResult).toHaveLength(1)

    await viewResult[0]?.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/c/cutting/draft-map/result')
  })

  it('keeps one Continue CTA when the chosen MAP snapshot is stale', async () => {
    const { wrapper } = await mountEditor(
      '/c/cutting/draft-map-stale',
      workshopDraft({
        id: 'draft-map-stale',
        preferred_branch_id: 'branch-1',
        parts_snapshot: [part({ length_mm: 301 })],
        chosen_result_id: 'imported-result-1',
        results: [importedResult([part({ length_mm: 300 })])],
      }),
      {},
      'workshop',
    )

    expect(
      wrapper.findAll('button').filter((button) => button.text() === 'Davom etish'),
    ).toHaveLength(1)
  })

  it('does not warn for an edge-only edit and keeps the returned layout', async () => {
    const initialPart = part()
    const current = workshopDraft({
      id: 'draft-edge',
      preferred_branch_id: 'branch-1',
      parts_snapshot: [initialPart],
      chosen_result_id: 'imported-result-1',
      results: [importedResult([initialPart])],
    })
    const { wrapper, cutting } = await mountEditor('/c/cutting/draft-edge', current, {}, 'workshop')
    const update = vi.spyOn(cutting, 'updateDraft').mockImplementation(async (_id, payload) => {
      const updated = draft({
        ...current,
        parts_snapshot: payload.parts_snapshot ?? current.parts_snapshot,
        results: [importedResult(payload.parts_snapshot ?? current.parts_snapshot)],
      })
      cutting.currentDraft = updated
      return updated
    })

    await wrapper.get('[data-test="open-edge-picker"]').trigger('click')
    await wrapper.get('[data-test="edge-only-edit"]').trigger('click')
    await vi.advanceTimersByTimeAsync(700)
    await flushPromises()

    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(update).toHaveBeenCalled()
    expect(cutting.currentDraft?.results.map((result) => result.id)).toEqual(['imported-result-1'])
  })

  it('warns before a dimension edit can replace an imported layout', async () => {
    const initialPart = part()
    const { wrapper, cutting } = await mountEditor(
      '/c/cutting/draft-dimension',
      workshopDraft({
        id: 'draft-dimension',
        preferred_branch_id: 'branch-1',
        parts_snapshot: [initialPart],
        results: [importedResult([initialPart])],
      }),
      {},
      'workshop',
    )
    const update = vi.spyOn(cutting, 'updateDraft').mockResolvedValue(draft())

    await wrapper.get('[data-test="edit-length"]').trigger('click')
    await vi.advanceTimersByTimeAsync(700)
    await flushPromises()

    expect(wrapper.get('[role="dialog"]').text()).toContain('Import qilingan joylashuv')
    expect(update).not.toHaveBeenCalled()
  })
})

// QAD-148: in the workshop app the branch comes from the app, not from an
// in-editor pick. On a cold load the app's context resolves *after* this view
// mounts, so a branch frozen at mount is null and the editor used to fall back
// to the client path — an empty "Filialni tanlang" modal with nothing to pick.
describe('CuttingEditorView app-supplied branch', () => {
  const branchNames: Record<string, string> = {
    'branch-1': 'Chilonzor filiali',
    'branch-2': 'Yunusobod filiali',
  }

  async function mountWorkshopEditor(options: {
    preferredBranchId: string | null
    context: Ref<string | null>
  }) {
    const adapter: CuttingEditorAdapter = {
      newRouteName: 'workshop-cutting-new',
      paths: {
        drafts: '/workshop/orders/drafts',
        editor: (id) => `/workshop/orders/cutting/${id}`,
        result: (id) => `/workshop/orders/cutting/${id}/result`,
        checkout: (id) => `/workshop/orders/new/${id}/checkout`,
        orderDetail: (id) => `/workshop/orders/${id}`,
      },
      // No `fixed`: exactly the cold-load shape, where the app context has not
      // landed by the time the adapter factory runs.
      branch: { context: () => options.context.value },
      branchNameById: (id) => branchNames[id] ?? null,
      quoteForDraft: () => Promise.reject(new Error('unused')),
    }
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/workshop/orders/cutting/:id',
          name: 'workshop-cutting-editor',
          component: { template: '<div />' },
          meta: { cuttingEditorAdapter: () => adapter },
        },
      ],
    })
    await router.push('/workshop/orders/cutting/draft-1')
    await router.isReady()

    const cutting = useCuttingStore()
    cutting.currentDraft = draft({ preferred_branch_id: options.preferredBranchId })
    const loadBranchOptions = vi.spyOn(cutting, 'loadBranchOptions').mockResolvedValue()
    vi.spyOn(cutting, 'loadMaterials').mockResolvedValue([])

    const wrapper = mount(CuttingEditorView, {
      global: {
        plugins: [router],
        provide: { [roleConfigKey as symbol]: workshopConfig },
        stubs: { AppModal: true, CuttingBranchPicker: true, CuttingPartRow: true },
      },
    })
    await flushPromises()
    return { wrapper, loadBranchOptions }
  }

  function branchPickerOpen(wrapper: VueWrapper) {
    return wrapper
      .findAllComponents({ name: 'AppModal' })
      .some((modal) => modal.props('title') === 'Filialni tanlang' && modal.props('open') === true)
  }

  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('seeds an unbound draft from the app context that lands after mount', async () => {
    const context = ref<string | null>(null)
    const { wrapper, loadBranchOptions } = await mountWorkshopEditor({
      preferredBranchId: null,
      context,
    })
    // Nothing bound and no context yet — but never the client's dead-end modal,
    // and never the client-only branch-options endpoint.
    expect(branchPickerOpen(wrapper)).toBe(false)
    expect(loadBranchOptions).not.toHaveBeenCalled()

    context.value = 'branch-1'
    await flushPromises()

    expect(wrapper.text()).toContain('Chilonzor filiali')
    expect(branchPickerOpen(wrapper)).toBe(false)
  })

  it('keeps a bound draft on its own branch when the app context differs', async () => {
    const context = ref<string | null>('branch-2')
    const { wrapper } = await mountWorkshopEditor({ preferredBranchId: 'branch-1', context })

    expect(wrapper.text()).toContain('Chilonzor filiali')
    expect(wrapper.text()).not.toContain('Yunusobod filiali')
  })
})

// One picker, two option payloads. Both editors open the same decor-first panel
// on «+ Material»; what differs is the list the server hands it and, in the
// workshop, the customer-board entry under it. Selection is one format, one
// click on both, and there is no "this branch does not carry it" state left,
// because the catalog endpoint is branch-scoped.
describe('CuttingEditorView material picker', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // The picker lives in a teleported sheet; a transparent stub keeps it
  // reachable through the wrapper and lets us read what it is handed — the
  // list, the caption's branch, the subtitle, and whatever the editor puts in
  // its foot.
  const pickerStub = {
    props: ['open', 'materials', 'currentId', 'branch', 'subtitle'],
    emits: ['pick'],
    template: `<section v-if="open" data-test="material-picker">
      <span data-test="picker-branch">{{ branch }}</span>
      <span data-test="picker-subtitle">{{ subtitle }}</span>
      <button
        v-for="material in materials"
        :key="material.id"
        :data-test="'pick-' + material.id"
        @click="$emit('pick', material.id)"
      />
      <div data-test="picker-foot"><slot name="foot" /></div>
    </section>`,
  }

  function option(overrides: Partial<ClientCatalogMaterialOption> = {}) {
    return {
      id: 'm-1',
      type: 'ldsp',
      manufacturer_id: 'mfr-1',
      manufacturer_name: 'Egger',
      code: 'H1334',
      name: 'Dub Sonoma',
      has_grain: true,
      image_file_id: null,
      thickness_mm: '18',
      length_mm: 2800,
      width_mm: 2070,
      tape_width_mm: null,
      price_tiyin: 120_000,
      price_unset: false,
      display_unit: 'sheet',
      ...overrides,
    } as ClientCatalogMaterialOption
  }

  it('opens the decor-first client picker and adds a part on the format picked', async () => {
    const { wrapper, cutting } = await mountEditor(
      '/c/cutting/draft-1',
      draft({ preferred_branch_id: 'branch-1' }),
      { CuttingMaterialPicker: pickerStub },
    )
    cutting.panelOptions = [
      option({ id: 'm-18' }),
      option({ id: 'm-16', thickness_mm: '16', length_mm: 2750, width_mm: 1830 }),
    ]
    await flushPromises()

    // §7.0: the client's add-material control is «+ Material» on both breakpoints.
    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('+ Material'))!
      .trigger('click')

    expect(wrapper.find('[data-test="material-picker"]').exists()).toBe(true)
    // The whole branch list reaches the picker; the decor grouping and the
    // per-format prices are the picker's own job (see its component spec).
    expect(wrapper.findAll('[data-test^="pick-"]')).toHaveLength(2)

    // One click on a format picks it, closes the sheet and starts a row on it.
    await wrapper.get('[data-test="pick-m-16"]').trigger('click')

    expect(wrapper.find('[data-test="material-picker"]').exists()).toBe(false)
    expect(wrapper.findAll('[data-test="edit-length"]')).toHaveLength(1)
  })

  /**
   * The workshop opens the same panel — including the unpriced formats only its
   * listing carries, which staff must be able to pick (they are the ones who
   * still have to price them). It also gets the one control the client's picker
   * has no use for: the entry to the customer-board form.
   */
  it('opens the same picker in the workshop, with the staff list and the customer-board entry', async () => {
    const { wrapper, cutting } = await mountEditor(
      '/c/cutting/draft-1',
      draft({ preferred_branch_id: 'branch-1' }),
      { CuttingMaterialPicker: pickerStub },
      'workshop',
    )
    cutting.panelOptions = [
      option({ id: 'm-18' }),
      // The staff payload's own row: registered, not yet priced.
      option({ id: 'm-16', thickness_mm: '16', price_tiyin: 0, price_unset: true }),
    ]
    await flushPromises()

    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('+ Material'))!
      .trigger('click')

    const picker = wrapper.get('[data-test="material-picker"]')
    expect(wrapper.findAll('[data-test^="pick-"]')).toHaveLength(2)
    // «Mijoz materiali» is still one click from «+ Material».
    expect(picker.get('[data-test="picker-foot"]').text()).toContain('Mijoz materiali')

    // The unpriced format is pickable, not merely visible.
    await wrapper.get('[data-test="pick-m-16"]').trigger('click')

    expect(wrapper.find('[data-test="material-picker"]').exists()).toBe(false)
    expect(wrapper.findAll('[data-test="edit-length"]')).toHaveLength(1)

    // Changing that group's material names the parts it lands on — the client
    // picker has one trigger per group head and needs no such line.
    // The group head's material name is the trigger. It sits inside the collapse
    // button that also carries the name, so the innermost match is the one — the
    // outer one only folds the group.
    const nameButtons = wrapper.findAll('button').filter((b) => b.text().includes('Dub Sonoma'))
    await nameButtons[nameButtons.length - 1].trigger('click')

    expect(wrapper.get('[data-test="picker-subtitle"]').text()).toBe(
      'Ushbu guruhdagi 1 detal uchun',
    )
  })
})

describe('CuttingEditorView client branch (spec §2.2, decision 17)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  function branchOption(overrides: Partial<ClientBranchOption> = {}): ClientBranchOption {
    return {
      branch_id: 'branch-1',
      workshop_id: 'workshop-1',
      workshop_name: 'Mebel Master',
      branch_name: 'Chilonzor',
      address: 'Chilonzor 12',
      status: 'active',
      closed_reason: null,
      kerf_mm: 4,
      edge_trim_mm: 5,
      ...overrides,
    }
  }

  const crossWorkshopOptions = [
    branchOption(),
    branchOption({ branch_id: 'branch-2', branch_name: 'Yunusobod' }),
    branchOption({
      branch_id: 'branch-9',
      workshop_id: 'workshop-2',
      workshop_name: 'Yog’och Pro',
      branch_name: 'Sergeli',
    }),
  ]

  function signIn(overrides: Partial<MeResponse> = {}) {
    const auth = useAuthStore()
    auth.accessToken = 'access-1'
    auth.me = {
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
      pinned_workshop_name: null,
      pinned_branch_name: null,
      status: 'active',
      ...overrides,
    }
    auth.status = 'authenticated'
  }

  /** Seed the options the mocked `loadBranchOptions` would have fetched. */
  function seedOptions() {
    useCuttingStore().branchOptions = crossWorkshopOptions
  }

  it('opens a new drawing on the pinned branch, without asking', async () => {
    signIn({ preferred_branch_id: 'branch-2', pinned_workshop_name: 'Mebel Master' })
    seedOptions()

    const { wrapper, cutting } = await mountEditor('/c/cutting/new', null)
    await flushPromises()

    // The pin is the drawing's branch — the editor reads it and names it by the
    // naming rule (decision 16: two visible branches, so workshop first).
    expect(wrapper.text()).toContain('Mebel Master · Yunusobod')
    // And the materials load for it rather than waiting on a pick.
    expect(cutting.loadMaterials).toHaveBeenCalled()
    // No picker, no «Filial tanlash» prompt anywhere on the client path.
    expect(wrapper.findComponent(CuttingBranchPicker).exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Filial tanlash')
  })

  // Decision 25: a branch row's «Yangi chizma» pins nothing, so the branch it
  // was tapped on rides the URL and outranks the pin for this drawing only.
  it('opens a new drawing on the branch named in the URL, over the pin', async () => {
    signIn({ preferred_branch_id: 'branch-1', pinned_workshop_name: 'Mebel Master' })
    seedOptions()

    const { wrapper, cutting } = await mountEditor('/c/cutting/new?branch=branch-9', null)
    await flushPromises()

    expect(wrapper.text()).toContain('Yog’och Pro')
    expect(cutting.loadMaterials).toHaveBeenCalledWith(
      expect.objectContaining({ branchId: 'branch-9' }),
    )
  })

  // The client never got a pin (a multi-branch link, an organic signup); the
  // route guard let them in on the query alone, and the editor must agree.
  it('opens a new drawing from the URL for a client with no pin at all', async () => {
    signIn({ preferred_branch_id: null, pinned_workshop_name: null })
    seedOptions()

    const { wrapper, router } = await mountEditor('/c/cutting/new?branch=branch-2', null)
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/c/cutting/new')
    expect(wrapper.text()).toContain('Mebel Master · Yunusobod')
  })

  // The URL is user-editable, so a branch outside the client's own options is
  // ignored rather than obeyed — the pin answers instead.
  it('falls back to the pin when the URL names a branch it cannot see', async () => {
    signIn({ preferred_branch_id: 'branch-2', pinned_workshop_name: 'Mebel Master' })
    seedOptions()

    const { wrapper, cutting } = await mountEditor('/c/cutting/new?branch=branch-404', null)
    await flushPromises()

    expect(wrapper.text()).toContain('Mebel Master · Yunusobod')
    expect(cutting.loadMaterials).toHaveBeenCalledWith(
      expect.objectContaining({ branchId: 'branch-2' }),
    )
  })

  // Neither a usable query nor a pin: the same answer the route guard gives.
  it('sends an un-pinned client with an unusable branch query to Ustaxonalarim', async () => {
    signIn({ preferred_branch_id: null, pinned_workshop_name: null })
    seedOptions()

    const { router } = await mountEditor('/c/cutting/new?branch=branch-404', null)
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/c/branches')
  })

  it('sends a client whose pin no longer resolves to Ustaxonalarim', async () => {
    // The route guard catches the pin-less client; this is the other hole —
    // a pin whose branch is gone (blocked workshop, retired counter).
    signIn({ preferred_branch_id: 'retired-branch', pinned_workshop_name: 'Mebel Master' })
    seedOptions()

    const { router } = await mountEditor('/c/cutting/new', null)
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/c/branches')
  })

  it('never rebranches a draft that lives on a foreign branch, and never offers to', async () => {
    signIn({ preferred_branch_id: 'branch-1', pinned_workshop_name: 'Mebel Master' })

    // The draft was drawn at another workshop's branch before the pin moved.
    const { wrapper, cutting } = await mountEditor(
      '/c/cutting/draft-1',
      draft({ preferred_branch_id: 'branch-9' }),
    )
    cutting.branchOptions = crossWorkshopOptions
    await flushPromises()

    // The draft keeps its own branch — the pin never touches data.
    expect(cutting.currentDraft?.preferred_branch_id).toBe('branch-9')
    // And the editor still names it, by the naming rule (decision 16): this
    // workshop has one visible branch, so the workshop name stands alone and
    // «Sergeli» never appears — a branch name is never shown on its own.
    expect(wrapper.text()).toContain('Yog’och Pro')
    expect(wrapper.text()).not.toContain('Sergeli')

    // Decision 17: the branch is fixed at creation, so the editor carries no
    // way to change it — no «O'zgartirish», and no picker raised on mount.
    expect(wrapper.findAll('button').some((button) => button.text() === "O'zgartirish")).toBe(false)
    expect(wrapper.findComponent(CuttingBranchPicker).exists()).toBe(false)
  })
})

/**
 * The group tape, end to end through the real components (§7.1).
 *
 * Nothing below the view is stubbed here except the part row and the icons: the
 * group line, the docked kromka card and the tape sheet are the shipped ones.
 * That is deliberate — `vue-tsc` cannot see a component used in a template but
 * never imported (web/AGENTS.md, "Verifying UI work"), and neither can a spec
 * that stubs it away. Mounting the real tree is what catches that class of
 * defect without a browser.
 */
describe('CuttingEditorView group tape (spec §7.1, §13 W2)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  const BOARD = 'panel-egger'
  const TAPE_THIN = 'tape-egger-04'
  const TAPE_THICK = 'tape-egger-2'
  const TAPE_OTHER = 'tape-krono-2'

  function catalogOption(overrides: Partial<ClientCatalogMaterialOption>) {
    return {
      id: 'x',
      type: 'ldsp',
      manufacturer_id: 'egger',
      manufacturer_name: 'Egger',
      code: 'H1145',
      name: 'Dub Bardolino',
      has_grain: true,
      image_file_id: null,
      thickness_mm: '18',
      length_mm: 2800,
      width_mm: 2070,
      tape_width_mm: null,
      price_tiyin: 28_500_000,
      price_unset: false,
      display_unit: 'list',
      ...overrides,
    } as ClientCatalogMaterialOption
  }

  function tapeOption(overrides: Partial<ClientCatalogMaterialOption>) {
    return catalogOption({
      type: 'kromka',
      tape_width_mm: 22,
      length_mm: null,
      width_mm: null,
      ...overrides,
    })
  }

  const board = catalogOption({ id: BOARD })
  // One decor in two thicknesses, plus a second decor the board does not match.
  const tapes = [
    tapeOption({ id: TAPE_THIN, thickness_mm: '0.4', price_tiyin: 130_000 }),
    tapeOption({ id: TAPE_THICK, thickness_mm: '2', price_tiyin: 260_000 }),
    tapeOption({
      id: TAPE_OTHER,
      manufacturer_id: 'kronospan',
      manufacturer_name: 'Kronospan',
      code: 'U963',
      name: 'Antrasit',
      thickness_mm: '2',
      price_tiyin: 230_000,
    }),
  ]

  async function mountWithCatalog(
    parts: CuttingPart[],
    // §13 W2 gave the workshop editor the same model, so every case below runs
    // against whichever editor the test names — the client by default.
    scope: 'client' | 'workshop' = 'client',
    draftOverrides: Partial<CuttingDraft> = {},
  ) {
    const mounted = await mountEditor(
      '/c/cutting/draft-1',
      draft({ preferred_branch_id: 'branch-1', parts_snapshot: parts, ...draftOverrides }),
      // `false` un-stubs the row and the card the shared harness stubs by
      // default: the row's kromka cell is how a desktop user reaches the card,
      // and a stub would test a selection nobody can actually make.
      { CuttingPartRow: false, CuttingKromkaPanel: false, Icon: true },
      scope,
    )
    mounted.cutting.panelOptions = [board]
    mounted.cutting.edgeOptions = tapes
    await flushPromises()
    return mounted
  }

  function partOn(overrides: Partial<CuttingPart> = {}): CuttingPart {
    return part({ material_id: BOARD, ...overrides })
  }

  function editorParts(wrapper: VueWrapper) {
    return (wrapper.vm as unknown as { parts: CuttingPart[] }).parts
  }

  /** The row's read-only sides glyph — the client's way into the docked card. */
  async function selectRow(wrapper: VueWrapper) {
    await wrapper.get('[data-cell="edge"]').trigger('click')
  }

  function kromkaPanel(wrapper: VueWrapper) {
    return wrapper.findComponent({ name: 'CuttingKromkaPanel' })
  }

  function panelButton(wrapper: VueWrapper, startsWith: string) {
    return kromkaPanel(wrapper)
      .findAll('button')
      .find((button) => button.text().startsWith(startsWith))!
  }

  it('auto-attaches the branch tape of the board decor, with every thickness', async () => {
    const { wrapper } = await mountWithCatalog([partOn()])

    // «Kromka: Egger H1145 · Dub Bardolino · 0.4 / 2 mm» — one tape, and the
    // thicknesses the branch stocks it in. Not a registry of numbers.
    const line = wrapper.get(`#group-tape-${BOARD}`)
    expect(line.text()).toContain('Dub Bardolino')
    expect(line.text()).toContain('0.4 / 2 mm')
    expect(wrapper.text()).not.toContain('rangi mos lentani tanlang')
  })

  it('asks for a colour when the branch carries no tape in the board decor', async () => {
    const { wrapper, cutting } = await mountWithCatalog([partOn()])
    cutting.edgeOptions = [tapes[2]]
    await flushPromises()

    expect(wrapper.get(`#group-tape-${BOARD}`).text()).toContain('rangi mos lentani tanlang')
  })

  it('bands a side with the armed thickness from the docked card', async () => {
    const { wrapper } = await mountWithCatalog([partOn()])

    // The row's kromka cell selects the row, which is what raises the card
    // (§7.5) — on the client it no longer opens a modal.
    await selectRow(wrapper)
    expect(kromkaPanel(wrapper).exists()).toBe(true)

    // The thickest variant is armed by default — a visible edge is the common
    // case, and 2 mm is what a shop puts on one.
    await panelButton(wrapper, 'Yuqori').trigger('click')

    expect(editorParts(wrapper)[0].edge_top).toEqual({
      material_id: TAPE_THICK,
      source: 'shop',
    })
    // The side names its own thickness, which is what makes two of them on one
    // part readable at a glance.
    expect(panelButton(wrapper, 'Yuqori').text()).toContain('2 mm')
  })

  it('carries two thicknesses on one part', async () => {
    const { wrapper } = await mountWithCatalog([partOn()])
    await selectRow(wrapper)

    await panelButton(wrapper, 'Yuqori').trigger('click')
    // Arm 0.4 mm, then band the bottom with it.
    await panelButton(wrapper, '0.4 mm').trigger('click')
    await panelButton(wrapper, 'Pastki').trigger('click')

    expect(editorParts(wrapper)[0].edge_top?.material_id).toBe(TAPE_THICK)
    expect(editorParts(wrapper)[0].edge_bottom?.material_id).toBe(TAPE_THIN)
  })

  it('re-resolves every banded side when the group tape changes', async () => {
    const { wrapper } = await mountWithCatalog([
      partOn({
        edge_top: { material_id: TAPE_THICK, source: 'shop' },
        edge_bottom: { material_id: TAPE_THIN, source: 'shop' },
      }),
    ])

    await wrapper.get(`#group-tape-${BOARD}`).trigger('click')
    const sheet = wrapper.findComponent({ name: 'CuttingTapePicker' })
    expect(sheet.props('open')).toBe(true)
    sheet.vm.$emit('pick', 'kronospan|u963')
    await flushPromises()

    // 2 mm exists in the new decor and is kept; 0.4 mm does not, so that side
    // falls back to the nearest thickness rather than losing its band.
    expect(editorParts(wrapper)[0].edge_top?.material_id).toBe(TAPE_OTHER)
    expect(editorParts(wrapper)[0].edge_bottom?.material_id).toBe(TAPE_OTHER)
    expect(wrapper.get(`#group-tape-${BOARD}`).text()).toContain('Antrasit')
  })

  it('blocks «Hisoblash» on a banded group with no tape, and says why', async () => {
    const { wrapper, cutting } = await mountWithCatalog([
      partOn({ edge_top: { material_id: TAPE_THICK, source: 'shop' } }),
    ])
    const optimize = vi.spyOn(cutting, 'optimizeDraft')
    // Drop every tape: the group is banded but now has no decor to band with.
    cutting.edgeOptions = []
    await flushPromises()

    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Hisoblash')!
      .trigger('click')
    await flushPromises()

    expect(optimize).not.toHaveBeenCalled()
    expect(wrapper.get(`#group-tape-${BOARD}`).text()).toContain('rangi mos lentani tanlang')
  })

  it('shows no tape registry, no import and no whole-part patterns', async () => {
    const { wrapper } = await mountWithCatalog([
      partOn({ edge_top: { material_id: TAPE_THICK, source: 'shop' } }),
    ])
    await selectRow(wrapper)

    expect(wrapper.findComponent({ name: 'CuttingImportWizard' }).exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Fayldan import')
    // §7.1 dropped the patterns with the per-part tape list: four taps on the
    // diagram, or none, say the same thing.
    expect(wrapper.text()).not.toContain('4 tomon')
    expect(wrapper.text()).not.toContain('Kromsiz')
  })

  // ── The workshop editor, on the same model (§13 W2) ───────────────────────
  // A plain workshop draft IS the order wizard's Detallar step (`inOrderWizard`);
  // a revision draft is the standalone workshop editor. Both are covered, because
  // they lay the docked card out differently and only the wizard levels it with
  // the row.
  const REVISION = { revision_of_order_id: 'order-9' }

  it('attaches the group tape and bands a side in the order wizard', async () => {
    const { wrapper } = await mountWithCatalog([partOn()], 'workshop')

    expect(wrapper.get(`#group-tape-${BOARD}`).text()).toContain('Dub Bardolino')

    await selectRow(wrapper)
    await panelButton(wrapper, 'Yuqori').trigger('click')

    expect(editorParts(wrapper)[0].edge_top).toEqual({ material_id: TAPE_THICK, source: 'shop' })
  })

  it('bands a side from the docked card in the standalone workshop editor', async () => {
    const { wrapper } = await mountWithCatalog([partOn()], 'workshop', REVISION)

    await selectRow(wrapper)
    await panelButton(wrapper, 'Pastki').trigger('click')

    expect(editorParts(wrapper)[0].edge_bottom).toEqual({ material_id: TAPE_THICK, source: 'shop' })
  })

  // The workshop is where mixed groups actually turn up — a drawing banded
  // before W2, or one the import wizard mapped edge by edge.
  it('marks a mixed group and re-points every banded side on a pick', async () => {
    const { wrapper } = await mountWithCatalog(
      [
        partOn({ part_ref: 'p1', edge_top: { material_id: TAPE_THICK, source: 'shop' } }),
        partOn({ part_ref: 'p2', edge_top: { material_id: TAPE_OTHER, source: 'shop' } }),
      ],
      'workshop',
    )

    // The head names the first tape its sides use — and says it is not alone.
    const line = wrapper.get(`#group-tape-${BOARD}`)
    expect(line.text()).toContain('Dub Bardolino')
    expect(line.text()).toContain('aralash')

    await line.trigger('click')
    const picker = wrapper.findComponent({ name: 'CuttingTapePicker' })
    picker.vm.$emit('pick', 'kronospan|u963')
    await flushPromises()

    // One pick is the whole way out of a mixed group: both sides move.
    expect(editorParts(wrapper)[0].edge_top?.material_id).toBe(TAPE_OTHER)
    expect(editorParts(wrapper)[1].edge_top?.material_id).toBe(TAPE_OTHER)
    expect(wrapper.get(`#group-tape-${BOARD}`).text()).not.toContain('aralash')
  })

  it('keeps thickening on the workshop card and off the client one', async () => {
    const workshop = await mountWithCatalog([partOn()], 'workshop')
    await selectRow(workshop.wrapper)
    await kromkaPanel(workshop.wrapper).get('[role="switch"]').trigger('click')
    expect(editorParts(workshop.wrapper)[0].thickened).toBe(true)

    const client = await mountWithCatalog([partOn()])
    await selectRow(client.wrapper)
    expect(kromkaPanel(client.wrapper).find('[role="switch"]').exists()).toBe(false)
  })
})
