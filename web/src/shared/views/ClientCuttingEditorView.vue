<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import {
  materialLabel,
  metres,
  useCuttingStore,
  type CuttingEdgeBand,
  type CuttingPanel,
  type CuttingPart,
  type CuttingPlacement,
  type CuttingResult,
  type MaterialSource,
} from '@/shared/stores/cutting'

const route = useRoute()
const cutting = useCuttingStore()
const draftId = computed(() => String(route.params.id))
const parts = ref<CuttingPart[]>([])
const saveState = ref<'saved' | 'saving' | 'error' | 'editing'>('saved')
const saveError = ref<string | null>(null)
const branchPickerOpen = ref(false)
const selectedBranchId = ref<string | null>(null)
const showAllCatalog = ref(false)
const activeResultId = ref<string | null>(null)
const activePanelId = ref<string | null>(null)
const activePlacementId = ref<string | null>(null)
const preferredEdgeByPart = ref<Record<string, string>>({})
let saveTimer: number | undefined
let hydrating = false

const draft = computed(() => cutting.currentDraft)
const preferredBranch = computed(() =>
  cutting.branchOptions.find((branch) => branch.branch_id === draft.value?.preferred_branch_id),
)
const branchOptions = computed<ChoiceOption[]>(() =>
  cutting.branchOptions.map((branch) => ({
    value: branch.branch_id,
    label: `${branch.workshop_name} · ${branch.branch_name}`,
    meta:
      branch.status === 'temporarily_closed'
        ? (branch.closed_reason ?? 'temporarily closed')
        : 'active branch',
  })),
)
const panelOptions = computed(() =>
  cutting.panelOptions.filter((material) =>
    draft.value?.preferred_branch_id && !showAllCatalog.value ? material.branch_carried : true,
  ),
)
const panelChoices = computed<ChoiceOption[]>(() =>
  panelOptions.value.map((material) => ({
    value: material.id,
    label: materialLabel(material),
    meta: `${material.color}${material.decor_code ? ` · ${material.decor_code}` : ''}${
      material.branch_carried ? '' : ' · not at branch'
    }`,
  })),
)
const edgeChoices = computed<ChoiceOption[]>(() =>
  cutting.edgeOptions.map((material) => ({
    value: material.id,
    label: materialLabel(material),
    meta: `${material.color}${material.decor_code ? ` · ${material.decor_code}` : ''}${
      material.branch_carried ? '' : ' · not at branch'
    }`,
  })),
)
const hasPersistableParts = computed(() =>
  parts.value.every(
    (part) => part.material_id && part.length_mm >= 50 && part.width_mm >= 50 && part.quantity >= 1,
  ),
)
const notCarriedRows = computed(() =>
  parts.value.filter((part) => rowNotCarried(part).length > 0 && part.material_source === 'shop'),
)
const chosenResult = computed(() => {
  if (!draft.value) return null
  return (
    draft.value.results.find((result) => result.id === activeResultId.value) ??
    draft.value.results.find((result) => result.id === draft.value?.chosen_result_id) ??
    draft.value.results[0] ??
    null
  )
})
const activePanel = computed(() => {
  const result = chosenResult.value
  if (!result) return null
  return result.panels.find((panel) => panel.id === activePanelId.value) ?? result.panels[0] ?? null
})
const totalPanels = computed(() =>
  chosenResult.value
    ? Object.values(chosenResult.value.panels_used_by_material).reduce(
        (sum, count) => sum + count,
        0,
      )
    : 0,
)
const consumedShop = computed(() => sumRecord(chosenResult.value?.edge_consumed_shop_by_material))
const consumedOwn = computed(() => sumRecord(chosenResult.value?.edge_consumed_own_by_material))
const resultWaste = computed(() =>
  chosenResult.value ? `${(Number(chosenResult.value.waste_percentage) * 100).toFixed(2)}%` : '-',
)

function blankPart(): CuttingPart {
  return {
    part_ref: crypto.randomUUID?.() ?? `part-${Date.now()}`,
    material_id: panelOptions.value[0]?.id ?? '',
    material_source: 'shop',
    length_mm: 100,
    width_mm: 100,
    quantity: 1,
    edge_top: null,
    edge_bottom: null,
    edge_left: null,
    edge_right: null,
  }
}

function materialById(id: string | null | undefined) {
  return cutting.panelOptions.find((material) => material.id === id) ?? null
}

function edgeById(id: string | null | undefined) {
  return cutting.edgeOptions.find((material) => material.id === id) ?? null
}

function rowNotCarried(part: CuttingPart) {
  if (!draft.value?.preferred_branch_id) return []
  const issues: string[] = []
  const panel = materialById(part.material_id)
  if (part.material_source === 'shop' && panel && !panel.branch_carried) issues.push('panel')
  for (const side of edgeFields) {
    const edge = part[side]
    const material = edgeById(edge?.material_id)
    if (edge?.source === 'shop' && material && !material.branch_carried) issues.push(side)
  }
  return issues
}

function addRow() {
  parts.value = [...parts.value, blankPart()]
}

function duplicateRow(part: CuttingPart) {
  const nextPart = { ...part, part_ref: crypto.randomUUID?.() ?? `part-${Date.now()}` }
  parts.value = [...parts.value, nextPart]
  const preferredEdge = preferredEdgeId(part)
  if (preferredEdge) {
    preferredEdgeByPart.value = {
      ...preferredEdgeByPart.value,
      [nextPart.part_ref]: preferredEdge,
    }
  }
}

function deleteRow(index: number) {
  const removed = parts.value[index]
  parts.value = parts.value.filter((_, current) => current !== index)
  if (removed) {
    const next = { ...preferredEdgeByPart.value }
    delete next[removed.part_ref]
    preferredEdgeByPart.value = next
  }
}

function clearParts() {
  if (!window.confirm(`Remove all ${parts.value.length} parts? This cannot be undone.`)) return
  parts.value = []
  preferredEdgeByPart.value = {}
}

function setPanelSource(part: CuttingPart, source: MaterialSource) {
  part.material_source = source
}

function setPanel(part: CuttingPart, value: string | null) {
  part.material_id = value ?? ''
}

function firstEdgeId(part: CuttingPart) {
  return (
    part.edge_top?.material_id ??
    part.edge_bottom?.material_id ??
    part.edge_left?.material_id ??
    part.edge_right?.material_id ??
    null
  )
}

function preferredEdgeId(part: CuttingPart) {
  return preferredEdgeByPart.value[part.part_ref] ?? null
}

function rememberEdgeMaterial(part: CuttingPart, materialId: string | null) {
  const next = { ...preferredEdgeByPart.value }
  if (materialId) next[part.part_ref] = materialId
  else delete next[part.part_ref]
  preferredEdgeByPart.value = next
}

function commonEdgeSource(part: CuttingPart): MaterialSource {
  return (
    part.edge_top?.source ??
    part.edge_bottom?.source ??
    part.edge_left?.source ??
    part.edge_right?.source ??
    'shop'
  )
}

function setAllEdgeSources(part: CuttingPart, source: MaterialSource) {
  for (const side of edgeFields) {
    if (part[side]) part[side] = { ...part[side], source } as CuttingEdgeBand
  }
}

function setEdgeMaterial(part: CuttingPart, materialId: string | null) {
  rememberEdgeMaterial(part, materialId)
  const currentSource = commonEdgeSource(part)
  const nextId = materialId ?? ''
  for (const side of edgeFields) {
    if (part[side]) part[side] = nextId ? { material_id: nextId, source: currentSource } : null
  }
}

function toggleEdge(part: CuttingPart, side: EdgeField) {
  if (part[side]) {
    part[side] = null
    return
  }
  const materialId = firstEdgeId(part) ?? preferredEdgeId(part) ?? cutting.edgeOptions[0]?.id
  if (!materialId) return
  part[side] = { material_id: materialId, source: commonEdgeSource(part) }
}

function bringOwn(part: CuttingPart) {
  part.material_source = 'own'
  for (const side of edgeFields) {
    if (part[side]) part[side] = { ...part[side], source: 'own' } as CuttingEdgeBand
  }
}

function scheduleSave() {
  if (hydrating) return
  window.clearTimeout(saveTimer)
  saveState.value = 'editing'
  saveTimer = window.setTimeout(() => void saveParts(), 700)
}

async function saveParts() {
  window.clearTimeout(saveTimer)
  if (!hasPersistableParts.value) {
    saveState.value = 'error'
    saveError.value = 'Complete material, length, width, and quantity before saving.'
    return
  }
  saveState.value = 'saving'
  saveError.value = null
  try {
    await cutting.updateDraft(draftId.value, { parts_snapshot: parts.value })
    saveState.value = 'saved'
  } catch {
    saveState.value = 'error'
    saveError.value = 'Draft could not be saved.'
  }
}

async function setPreferredBranch(branchId: string | null) {
  await cutting.updateDraft(draftId.value, { preferred_branch_id: branchId })
  branchPickerOpen.value = false
  selectedBranchId.value = branchId
  await loadMaterials()
}

async function optimize() {
  await saveParts()
  if (saveState.value === 'error') return
  const updated = await cutting.optimizeDraft(draftId.value)
  activeResultId.value = updated.chosen_result_id
  activePanelId.value = updated.results[0]?.panels[0]?.id ?? null
  await nextTick()
  document.getElementById('cutting-results')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function choose(result: CuttingResult) {
  await cutting.chooseResult(draftId.value, result.id)
  activeResultId.value = result.id
  activePanelId.value = result.panels[0]?.id ?? null
}

async function loadMaterials() {
  await Promise.all([
    cutting.loadMaterials({
      kind: 'panel',
      branchId: draft.value?.preferred_branch_id,
      carriedOnly: false,
    }),
    cutting.loadMaterials({
      kind: 'edge',
      branchId: draft.value?.preferred_branch_id,
      carriedOnly: false,
    }),
  ])
}

function sumRecord(record: Record<string, number> | undefined) {
  return Object.values(record ?? {}).reduce((sum, value) => sum + value, 0)
}

function panelTitle(result: CuttingResult, panel: CuttingPanel) {
  const snapshot = result.material_snapshots[panel.material_id]
  return `${String(snapshot?.name ?? 'Panel')} · ${panel.panel_index}`
}

function selectPlacement(placement: CuttingPlacement) {
  activePlacementId.value = placement.id
}

watch(
  () => cutting.currentDraft,
  (value) => {
    if (!value) return
    hydrating = true
    parts.value = value.parts_snapshot.map((part) => ({ ...part }))
    activeResultId.value = value.chosen_result_id ?? value.results[0]?.id ?? null
    activePanelId.value =
      value.results.find((result) => result.id === activeResultId.value)?.panels[0]?.id ??
      value.results[0]?.panels[0]?.id ??
      null
    selectedBranchId.value = value.preferred_branch_id
    saveState.value = 'saved'
    nextTick(() => {
      hydrating = false
    })
  },
  { immediate: true },
)

watch(parts, scheduleSave, { deep: true })

onMounted(async () => {
  await cutting.loadDraft(draftId.value)
  await cutting.loadBranchOptions()
  selectedBranchId.value = draft.value?.preferred_branch_id ?? null
  await loadMaterials()
})

const edgeFields = ['edge_top', 'edge_bottom', 'edge_left', 'edge_right'] as const
type EdgeField = (typeof edgeFields)[number]
const sideLabels: Record<EdgeField, string> = {
  edge_top: 'Top',
  edge_bottom: 'Bottom',
  edge_left: 'Left',
  edge_right: 'Right',
}
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <RouterLink to="/c/cutting/drafts" class="text-sm font-bold text-accent">
          Cutting drafts
        </RouterLink>
        <h1 class="mt-2 font-serif text-3xl font-semibold text-ink">Cutting editor</h1>
        <p class="mt-2 max-w-2xl text-base text-ink-soft">
          Enter parts, run deterministic layouts, and download the cutting plan.
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <span
          class="mp-chip"
          :class="{
            'bg-success-soft text-success': saveState === 'saved',
            'bg-info-soft text-info': saveState === 'saving' || saveState === 'editing',
            'bg-danger-soft text-danger': saveState === 'error',
          }"
          aria-live="polite"
        >
          <span class="mp-dot" aria-hidden="true"></span>
          {{
            saveState === 'saved'
              ? 'Saved'
              : saveState === 'saving'
                ? 'Saving'
                : saveState === 'editing'
                  ? 'Editing'
                  : 'Save error'
          }}
        </span>
        <button type="button" class="mp-button mp-button-outline text-danger" @click="clearParts">
          Clear parts list
        </button>
      </div>
    </div>

    <div v-if="cutting.loading" class="mp-surface p-5" aria-live="polite">
      Loading cutting draft
    </div>
    <div v-else-if="cutting.error" class="mp-surface p-5 text-danger">
      Draft could not be loaded. trace {{ cutting.traceId ?? 'unavailable' }}
    </div>

    <template v-else-if="draft">
      <section class="mp-surface p-5">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div class="text-sm font-bold text-ink">Catalog pre-filter</div>
            <p class="mt-1 text-sm text-ink-soft">
              {{
                preferredBranch
                  ? `${preferredBranch.branch_name} · ${preferredBranch.workshop_name}`
                  : 'Catalog: all branches'
              }}
            </p>
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              type="button"
              class="mp-button mp-button-outline"
              @click="branchPickerOpen = true"
            >
              {{ preferredBranch ? 'Change' : 'Pick a branch' }}
            </button>
            <button
              v-if="preferredBranch"
              type="button"
              class="mp-button mp-button-outline"
              @click="setPreferredBranch(null)"
            >
              Clear
            </button>
          </div>
        </div>

        <div v-if="branchPickerOpen" class="mt-4 grid gap-3 md:grid-cols-[1fr_auto]">
          <FormSelect
            v-model="selectedBranchId"
            label="Preferred branch"
            :options="branchOptions"
          />
          <button
            type="button"
            class="mp-button mp-button-primary self-end"
            @click="setPreferredBranch(selectedBranchId)"
          >
            Apply
          </button>
        </div>

        <label class="mt-4 inline-flex min-h-11 items-center gap-2 text-sm font-bold text-ink">
          <input v-model="showAllCatalog" type="checkbox" class="size-4" />
          Show all catalog
        </label>
      </section>

      <section v-if="notCarriedRows.length > 0" class="rounded-lg bg-warning-soft p-4 text-warning">
        <div class="font-extrabold">
          {{ notCarriedRows.length }} parts use materials not carried at the preferred branch.
        </div>
        <button
          type="button"
          class="mp-button mp-button-outline mt-3"
          @click="setPreferredBranch(null)"
        >
          Clear preferred branch
        </button>
      </section>

      <section class="mp-surface overflow-hidden">
        <div class="flex flex-wrap items-center justify-between gap-3 border-b border-hairline p-5">
          <div>
            <h2 class="font-serif text-xl font-semibold text-ink">Manual entry</h2>
            <p class="mt-1 text-sm text-ink-soft">Part rows for this draft.</p>
          </div>
          <button type="button" class="mp-button mp-button-outline" @click="addRow">
            Add part
          </button>
        </div>

        <div v-if="parts.length === 0" class="p-5">
          <div class="rounded-lg border border-dashed border-hairline-strong bg-sunk p-5">
            <h3 class="text-base font-extrabold text-ink">No parts in this draft</h3>
            <p class="mt-1 text-sm text-ink-soft">Add a row to start the cutting list.</p>
          </div>
        </div>

        <div v-else class="overflow-x-auto">
          <table class="min-w-[1120px] w-full border-collapse text-sm">
            <thead class="bg-sunk text-left text-xs uppercase text-ink-muted">
              <tr>
                <th class="px-4 py-3">#</th>
                <th class="px-4 py-3">Panel</th>
                <th class="px-4 py-3">L mm</th>
                <th class="px-4 py-3">W mm</th>
                <th class="px-4 py-3">Qty</th>
                <th class="px-4 py-3">Edges</th>
                <th class="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-hairline">
              <tr v-for="(part, index) in parts" :key="part.part_ref" class="align-top">
                <td class="px-4 py-4 font-mono text-xs text-ink-muted">{{ index + 1 }}</td>
                <td class="w-[360px] px-4 py-4">
                  <SearchCombobox
                    label="Panel material"
                    :model-value="part.material_id"
                    :options="panelChoices"
                    placeholder="Pick panel"
                    @update:model-value="setPanel(part, $event)"
                  />
                  <div class="mt-2 flex flex-wrap gap-2">
                    <button
                      type="button"
                      class="mp-chip"
                      :class="part.material_source === 'shop' ? 'bg-accent-soft text-accent' : ''"
                      @click="setPanelSource(part, 'shop')"
                    >
                      From shop
                    </button>
                    <button
                      type="button"
                      class="mp-chip"
                      :class="part.material_source === 'own' ? 'bg-accent-soft text-accent' : ''"
                      @click="setPanelSource(part, 'own')"
                    >
                      I'll bring it
                    </button>
                  </div>
                  <div
                    v-if="rowNotCarried(part).length"
                    class="mt-2 text-xs font-bold text-warning"
                  >
                    Not at branch
                    <button type="button" class="underline" @click="bringOwn(part)">
                      I'll bring my own
                    </button>
                  </div>
                </td>
                <td class="px-4 py-4">
                  <input
                    v-model.number="part.length_mm"
                    type="number"
                    min="50"
                    class="min-h-11 w-24 rounded-md border border-hairline-strong px-3"
                    aria-label="Length millimetres"
                  />
                </td>
                <td class="px-4 py-4">
                  <input
                    v-model.number="part.width_mm"
                    type="number"
                    min="50"
                    class="min-h-11 w-24 rounded-md border border-hairline-strong px-3"
                    aria-label="Width millimetres"
                  />
                </td>
                <td class="px-4 py-4">
                  <input
                    v-model.number="part.quantity"
                    type="number"
                    min="1"
                    class="min-h-11 w-20 rounded-md border border-hairline-strong px-3"
                    aria-label="Quantity"
                  />
                </td>
                <td class="w-[340px] px-4 py-4">
                  <SearchCombobox
                    label="Edge tape"
                    :model-value="firstEdgeId(part)"
                    :options="edgeChoices"
                    placeholder="Pick edge"
                    @update:model-value="setEdgeMaterial(part, $event)"
                  />
                  <div class="mt-2 flex flex-wrap gap-2">
                    <button
                      v-for="side in edgeFields"
                      :key="side"
                      type="button"
                      class="mp-chip"
                      :class="part[side] ? 'bg-info-soft text-info' : ''"
                      @click="toggleEdge(part, side)"
                    >
                      {{ sideLabels[side] }}
                    </button>
                  </div>
                  <div class="mt-2 flex flex-wrap gap-2">
                    <button
                      type="button"
                      class="mp-chip"
                      :class="commonEdgeSource(part) === 'shop' ? 'bg-accent-soft text-accent' : ''"
                      @click="setAllEdgeSources(part, 'shop')"
                    >
                      Workshop supplies
                    </button>
                    <button
                      type="button"
                      class="mp-chip"
                      :class="commonEdgeSource(part) === 'own' ? 'bg-accent-soft text-accent' : ''"
                      @click="setAllEdgeSources(part, 'own')"
                    >
                      I'll bring it
                    </button>
                  </div>
                </td>
                <td class="px-4 py-4">
                  <div class="flex flex-col gap-2">
                    <button
                      type="button"
                      class="mp-button mp-button-outline"
                      @click="duplicateRow(part)"
                    >
                      Duplicate
                    </button>
                    <button
                      type="button"
                      class="mp-button mp-button-outline text-danger"
                      @click="deleteRow(index)"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="flex flex-wrap items-center justify-between gap-3 border-t border-hairline p-5">
          <p v-if="saveError" class="text-sm font-bold text-danger">{{ saveError }}</p>
          <p v-else class="text-sm text-ink-soft">{{ parts.length }} rows</p>
          <button
            type="button"
            class="mp-button mp-button-primary"
            :disabled="cutting.optimizing || parts.length === 0"
            @click="optimize"
          >
            {{ cutting.optimizing ? 'Optimising' : 'Optimise' }}
          </button>
        </div>
      </section>

      <section id="cutting-results" class="mp-surface overflow-hidden">
        <div class="border-b border-hairline p-5">
          <h2 class="font-serif text-xl font-semibold text-ink">Result</h2>
          <p class="mt-1 text-sm text-ink-soft">Compare algorithms and download the chosen plan.</p>
        </div>

        <div v-if="!chosenResult" class="p-5">
          <div class="rounded-lg border border-dashed border-hairline-strong bg-sunk p-5">
            <h3 class="text-base font-extrabold text-ink">No optimizer result</h3>
            <p class="mt-1 text-sm text-ink-soft">
              Run the optimiser after the parts list is saved.
            </p>
          </div>
        </div>

        <div v-else class="grid gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div class="min-w-0 space-y-4">
            <div class="grid gap-3 sm:grid-cols-4">
              <div class="rounded-md bg-sunk p-3">
                <div class="text-xs font-bold uppercase text-ink-muted">Waste</div>
                <div class="mt-1 text-xl font-extrabold text-ink">{{ resultWaste }}</div>
              </div>
              <div class="rounded-md bg-sunk p-3">
                <div class="text-xs font-bold uppercase text-ink-muted">Panels</div>
                <div class="mt-1 text-xl font-extrabold text-ink">{{ totalPanels }}</div>
              </div>
              <div class="rounded-md bg-sunk p-3">
                <div class="text-xs font-bold uppercase text-ink-muted">Edge tape</div>
                <div class="mt-1 text-xl font-extrabold text-ink">
                  {{ metres(consumedShop + consumedOwn) }}
                </div>
              </div>
              <div class="rounded-md bg-sunk p-3">
                <div class="text-xs font-bold uppercase text-ink-muted">Cut length</div>
                <div class="mt-1 text-xl font-extrabold text-ink">
                  {{ metres(chosenResult.total_cut_length_mm) }}
                </div>
              </div>
            </div>

            <div class="overflow-x-auto rounded-lg border border-hairline">
              <table class="w-full min-w-[520px] text-sm">
                <thead class="bg-sunk text-left text-xs uppercase text-ink-muted">
                  <tr>
                    <th class="px-3 py-2">Algorithm</th>
                    <th class="px-3 py-2">Waste</th>
                    <th class="px-3 py-2">Panels</th>
                    <th class="px-3 py-2">Action</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-hairline">
                  <tr v-for="result in draft.results" :key="result.id">
                    <td class="px-3 py-3 font-bold">{{ result.algorithm_name }}</td>
                    <td class="px-3 py-3">
                      {{ (Number(result.waste_percentage) * 100).toFixed(2) }}%
                    </td>
                    <td class="px-3 py-3">
                      {{
                        Object.values(result.panels_used_by_material).reduce(
                          (sum, count) => sum + count,
                          0,
                        )
                      }}
                    </td>
                    <td class="px-3 py-3">
                      <button
                        type="button"
                        class="mp-button mp-button-outline"
                        @click="choose(result)"
                      >
                        {{ result.id === draft.chosen_result_id ? 'Chosen' : 'Use this one' }}
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="flex flex-wrap gap-2">
              <button
                v-for="panel in chosenResult.panels"
                :key="panel.id"
                type="button"
                class="mp-chip"
                :class="panel.id === activePanel?.id ? 'bg-accent-soft text-accent' : ''"
                @click="activePanelId = panel.id"
              >
                {{ panelTitle(chosenResult, panel) }}
              </button>
            </div>

            <CuttingPanelSvg
              v-if="activePanel"
              :result="chosenResult"
              :panel="activePanel"
              :active-placement-id="activePlacementId"
              @select-placement="selectPlacement"
            />
          </div>

          <aside class="space-y-4">
            <RouterLink
              v-if="draft.chosen_result_id"
              :to="`/c/orders/new/${draft.id}`"
              class="mp-button mp-button-primary w-full"
            >
              Place order
            </RouterLink>
            <button
              type="button"
              class="mp-button mp-button-outline w-full"
              @click="cutting.downloadClientPdf(chosenResult.id)"
            >
              Download PDF
            </button>
            <div class="rounded-lg border border-hairline bg-sunk p-4">
              <h3 class="text-sm font-extrabold text-ink">Edge split</h3>
              <p class="mt-2 text-sm text-ink-soft">
                Shop {{ metres(consumedShop) }} · Own {{ metres(consumedOwn) }}
              </p>
            </div>
            <div v-if="activePanel" class="rounded-lg border border-hairline bg-sunk p-4">
              <h3 class="text-sm font-extrabold text-ink">Placements</h3>
              <div class="mt-3 grid gap-2">
                <button
                  v-for="placement in activePanel.placements"
                  :key="placement.id"
                  type="button"
                  class="rounded-md border border-hairline bg-elevated px-3 py-2 text-left text-sm"
                  :class="
                    placement.id === activePlacementId ? 'border-accent text-accent' : 'text-ink'
                  "
                  @click="selectPlacement(placement)"
                >
                  {{ placement.part_ref }} #{{ placement.part_quantity_index }}
                  <span v-if="placement.rotated" class="font-bold">R</span>
                </button>
              </div>
            </div>
          </aside>
        </div>
      </section>
    </template>
  </section>
</template>
