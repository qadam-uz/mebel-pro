import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref, type Ref } from 'vue'

import { ApiError } from '@/shared/api/client'
import type { CuttingEditorAdapter } from '@/shared/app/cuttingEditorAdapter'
import { clientConfig, roleConfigKey, workshopConfig } from '@/shared/app/roleConfig'
import CuttingEditorView from '@/shared/views/CuttingEditorView.vue'
import {
  useCuttingStore,
  type ClientCatalogMaterialOption,
  type CuttingDraft,
  type CuttingPart,
} from '@/shared/stores/cutting'

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
) {
  const router = createRouter({ history: createMemoryHistory(), routes: editorRoutes })
  await router.push(path)
  await router.isReady()

  const cutting = useCuttingStore()
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
        CuttingEdgePickerModal: {
          emits: ['edges-change'],
          template: `
            <button
              data-test="edge-only-edit"
              @click="$emit('edges-change', {
                edges: {
                  edge_top: { material_id: 'edge-2', source: 'shop' },
                  edge_bottom: null,
                  edge_left: null,
                  edge_right: null,
                },
                rememberedMaterialId: 'edge-2',
              })"
            />
          `,
        },
        CuttingEdgeTapeRegistry: true,
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
    const viewResult = saved.wrapper
      .findAll('button')
      .filter((button) => button.text() === 'Davom etish')

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
      .filter((button) => button.text() === 'Davom etish')

    expect(optimise).toHaveLength(1)
    expect(optimise[0]?.attributes('disabled')).toBeDefined()
  })
})

describe('CuttingEditorView imported layout guard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('opens a committed MAP import on the standalone result stage', async () => {
    const { wrapper, router } = await mountEditor(
      '/c/cutting/draft-1',
      draft({ preferred_branch_id: 'branch-1' }),
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
      draft({
        id: 'draft-map',
        preferred_branch_id: 'branch-1',
        parts_snapshot: [initialPart],
        chosen_result_id: 'imported-result-1',
        results: [importedResult([initialPart])],
      }),
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
      draft({
        id: 'draft-map-stale',
        preferred_branch_id: 'branch-1',
        parts_snapshot: [part({ length_mm: 301 })],
        chosen_result_id: 'imported-result-1',
        results: [importedResult([part({ length_mm: 300 })])],
      }),
    )

    expect(
      wrapper.findAll('button').filter((button) => button.text() === 'Davom etish'),
    ).toHaveLength(1)
  })

  it('does not warn for an edge-only edit and keeps the returned layout', async () => {
    const initialPart = part()
    const current = draft({
      id: 'draft-edge',
      preferred_branch_id: 'branch-1',
      parts_snapshot: [initialPart],
      chosen_result_id: 'imported-result-1',
      results: [importedResult([initialPart])],
    })
    const { wrapper, cutting } = await mountEditor('/c/cutting/draft-edge', current)
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
      draft({
        id: 'draft-dimension',
        preferred_branch_id: 'branch-1',
        parts_snapshot: [initialPart],
        results: [importedResult([initialPart])],
      }),
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

// The picker reads like the catalog table: one photo + identity line per dekor,
// its formats listed beneath. Selection is unchanged — one format, one click, no
// extra step — and there is no "this branch does not carry it" state left, because
// the catalog endpoint is branch-scoped.
describe('CuttingEditorView material picker', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  function option(overrides: Partial<ClientCatalogMaterialOption> = {}) {
    return {
      id: 'm-1',
      tur: 'ldsp',
      manufacturer_id: 'mfr-1',
      manufacturer_name: 'Egger',
      kod: 'H1334',
      nomi: 'Dub Sonoma',
      tolali: true,
      image_file_id: null,
      qalinlik_mm: '18',
      uzunlik_mm: 2800,
      eni_mm: 2070,
      kromka_eni_mm: null,
      price_tiyin: 120_000,
      price_unset: false,
      display_unit: 'sheet',
      ...overrides,
    } as ClientCatalogMaterialOption
  }

  it('groups formats under one dekor heading and picks a format in one click', async () => {
    const { wrapper, cutting } = await mountEditor(
      '/c/cutting/draft-1',
      draft({ preferred_branch_id: 'branch-1' }),
    )
    cutting.panelOptions = [
      option({ id: 'm-18' }),
      option({ id: 'm-16', qalinlik_mm: '16', uzunlik_mm: 2750, eni_mm: 1830 }),
      option({
        id: 'm-other',
        kod: 'W980',
        nomi: 'Oq',
        qalinlik_mm: '18',
        price_tiyin: 0,
        price_unset: true,
      }),
    ]
    await flushPromises()

    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('Material tanlash'))!
      .trigger('click')

    const groups = wrapper.findAll('[role="dialog"] section')
    expect(groups).toHaveLength(2)
    // Identity once per dekor — the label without its format tail — then the
    // formats as the rows underneath.
    expect(groups[0].text()).toContain('LDSP Egger H1334 · Dub Sonoma')
    expect(groups[0].findAll('button').map((button) => button.text())).toEqual([
      '2800×2070×18 mm',
      '2750×1830×16 mm',
    ])
    // A workshop-facing row with no price is flagged rather than silently quoted at 0.
    expect(groups[1].text()).toContain("Narx yo'q")

    // One click on a format row picks it and closes — no second step.
    await groups[0].findAll('button')[1].trigger('click')

    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(wrapper.findAll('[data-test="edit-length"]')).toHaveLength(1)
  })
})
