import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { clientConfig, roleConfigKey } from '@/shared/app/roleConfig'
import CuttingEditorView from '@/shared/views/CuttingEditorView.vue'
import { useCuttingStore, type CuttingDraft, type CuttingPart } from '@/shared/stores/cutting'

/**
 * The editor's tape registry used to be re-derived by a `deep: true` watch on
 * `parts`, so every character typed into a length / width / soni / name field
 * re-ran `syncEdgeAssignments` over the whole drawing and allocated a new Map —
 * up to 300 rows of work per keystroke, for a result that cannot change. It now
 * watches `edgeAssignmentSignature`, which reads only the banded sides.
 *
 * These tests are the guard on that: the counter proves the work is *skipped*
 * for a geometry edit (a numbering assertion alone cannot — the sync is
 * idempotent, so it produces identical numbers whether it ran or not), and the
 * cases below it prove every edit that does move the registry still fires.
 *
 * Edit-for-edit equivalence with the old unconditional watch is proved on the
 * pure function in `app/__tests__/cuttingEditorDerived.spec.ts`.
 */
const syncCalls = { count: 0 }

vi.mock('@/shared/app/cuttingEditorDerived', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/app/cuttingEditorDerived')>()
  return {
    ...actual,
    syncEdgeAssignments(...args: Parameters<typeof actual.syncEdgeAssignments>) {
      syncCalls.count += 1
      return actual.syncEdgeAssignments(...args)
    },
  }
})

const editorRoutes = [
  { path: '/c/cutting/:id', name: 'client-cutting-editor', component: { template: '<div />' } },
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

function draft(parts: CuttingPart[]): CuttingDraft {
  return {
    id: 'draft-1',
    client_id: 'client-1',
    name: 'Oshxona',
    preferred_branch_id: 'branch-1',
    kerf_mm: 4,
    edge_trim_mm: 5,
    own_material_allowed: false,
    parts_snapshot: parts,
    own_panel_counts: {},
    own_edge_material_ids: [],
    chosen_result_id: null,
    // A revision draft, so kromka is edited in the modal rather than docked in
    // the side panel — the modal is the seam these tests band a side through.
    revision_of_order_id: 'order-9',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    results: [],
  }
}

// The registry as the rows see it — the prop the tape chips are painted from.
function rowRegistryNumbers(wrapper: VueWrapper) {
  return wrapper
    .findAllComponents({ name: 'CuttingPartRowStub' })
    .flatMap((row) =>
      ((row.props('edgeRegistry') ?? []) as Array<{ materialId: string; number: number }>).map(
        (entry) => `${entry.materialId}#${entry.number}`,
      ),
    )
}

async function mountEditor(parts: CuttingPart[]) {
  const router = createRouter({ history: createMemoryHistory(), routes: editorRoutes })
  await router.push('/c/cutting/draft-1')
  await router.isReady()

  const cutting = useCuttingStore()
  cutting.configureScope('workshop')
  cutting.currentDraft = draft(parts)
  vi.spyOn(cutting, 'loadBranchOptions').mockResolvedValue()
  vi.spyOn(cutting, 'loadMaterials').mockResolvedValue([])
  vi.spyOn(cutting, 'updateDraft').mockResolvedValue(draft(parts))

  const wrapper = mount(CuttingEditorView, {
    global: {
      plugins: [router],
      provide: { [roleConfigKey as symbol]: clientConfig },
      stubs: {
        Icon: true,
        AppModal: true,
        CuttingBranchPicker: true,
        CuttingEdgeTapeRegistry: true,
        CuttingResultsSection: true,
        SearchCombobox: true,
        CuttingImportWizard: true,
        CuttingEdgePickerModal: {
          name: 'CuttingEdgePickerModalStub',
          emits: ['edges-change'],
          template: `
            <button
              data-test="band-top"
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
        CuttingPartRow: {
          name: 'CuttingPartRowStub',
          props: ['part', 'index', 'edgeRegistry'],
          emits: ['open-edge-picker', 'update:length', 'update:name', 'delete', 'duplicate'],
          template: `
            <div>
              <button data-test="open-edge-picker" @click="$emit('open-edge-picker')" />
              <button data-test="edit-length" @click="$emit('update:length', part.length_mm + 1)" />
              <button data-test="edit-name" @click="$emit('update:name', 'Eshik')" />
              <button data-test="duplicate" @click="$emit('duplicate')" />
              <button data-test="delete" @click="$emit('delete')" />
            </div>
          `,
        },
      },
    },
  })
  await flushPromises()
  syncCalls.count = 0
  return { wrapper, cutting }
}

describe('CuttingEditorView tape registry watch', () => {
  beforeEach(() => {
    // Every test here mounts `draft-1`, and the editor's localStorage recovery
    // snapshot outlives a mount — without this, test two opens on test one's
    // parts. (Same reason the sibling editor spec clears it.)
    window.localStorage.clear()
    setActivePinia(createPinia())
    syncCalls.count = 0
  })

  it('does not re-derive the registry while a geometry or name field is typed', async () => {
    const { wrapper } = await mountEditor([
      part({ part_ref: 'p1', edge_top: { material_id: 'edge-1', source: 'shop' } }),
    ])
    const before = rowRegistryNumbers(wrapper)

    for (let stroke = 0; stroke < 5; stroke += 1) {
      await wrapper.get('[data-test="edit-length"]').trigger('click')
      await wrapper.get('[data-test="edit-name"]').trigger('click')
    }

    expect(syncCalls.count).toBe(0)
    expect(rowRegistryNumbers(wrapper)).toEqual(before)
    expect(before).toEqual(['edge-1#1'])
  })

  it('re-derives when a side is banded, and keeps first-use numbering', async () => {
    const { wrapper } = await mountEditor([
      part({ part_ref: 'p1', edge_left: { material_id: 'edge-1', source: 'shop' } }),
    ])

    await wrapper.get('[data-test="open-edge-picker"]').trigger('click')
    await wrapper.get('[data-test="band-top"]').trigger('click')
    await flushPromises()

    expect(syncCalls.count).toBeGreaterThan(0)
    // edge-1 left the drawing (the picker replaced every side), so the new tape
    // takes #1 rather than inheriting the removed one's number.
    expect(rowRegistryNumbers(wrapper)).toEqual(['edge-2#1'])
  })

  it('re-derives when a row is added or removed', async () => {
    const { wrapper } = await mountEditor([
      part({ part_ref: 'p1', edge_top: { material_id: 'edge-1', source: 'shop' } }),
      part({ part_ref: 'p2', edge_top: { material_id: 'edge-2', source: 'shop' } }),
    ])
    expect(rowRegistryNumbers(wrapper)).toEqual(['edge-1#1', 'edge-2#2', 'edge-1#1', 'edge-2#2'])

    await wrapper.findAll('[data-test="delete"]')[1].trigger('click')
    await flushPromises()

    expect(syncCalls.count).toBeGreaterThan(0)
    expect(rowRegistryNumbers(wrapper)).toEqual(['edge-1#1'])

    syncCalls.count = 0
    await wrapper.get('[data-test="duplicate"]').trigger('click')
    await flushPromises()

    // The duplicate brings no new tape, so the registry's input is unchanged and
    // the sync is skipped — and the numbering the second row paints is still the
    // right one, which is the whole claim behind watching the signature.
    expect(syncCalls.count).toBe(0)
    expect(rowRegistryNumbers(wrapper)).toEqual(['edge-1#1', 'edge-1#1'])
  })
})
