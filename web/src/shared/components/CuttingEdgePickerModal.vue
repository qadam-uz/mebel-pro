<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import { edgeTooNarrow, rankedEdges, recommendedEdge } from '@/shared/app/cuttingEdgeDisplay'
import {
  colorForMaterial,
  edgeFields,
  edgeSearchText,
  edgeShortLabel,
  type EdgeField,
} from '@/shared/app/cuttingDisplay'
import {
  edgeRegistryKey,
  previewEdgeAssignments,
  registryColorStyle,
  type EdgeRegistryColorStyle,
  type EdgeRegistryEntry,
} from '@/shared/app/cuttingEditorDerived'
import { lockBodyScroll, unlockBodyScroll } from '@/shared/app/scrollLock'
import { useCuttingStore, type CuttingEdgeBand, type CuttingPart } from '@/shared/stores/cutting'

// CB-93 seam: the edge-banding modal. The editor owns which part is open
// (`part` prop = the part being edited, null = closed) and the preferred-edge memory;
// this dialog owns its own working selection (sides / search / thickness),
// the recommended-edge ranking, the Tab focus-trap, the Escape handler, and the body
// scroll-lock. It EMITS the chosen edges on apply (the editor writes them onto the
// part + remembers the material) and `close` on cancel — it never mutates the part.
// Focus RETURN stays in the editor (it captured the trigger element), so this only
// focuses the dialog on open.
const props = defineProps<{
  part: CuttingPart | null
  initialSide: EdgeField | null
  partNumber: number
  preferredEdgeId: string | null
  preferredBranchId: string | null
  preferredBranchName: string
  // Overrides the "detal #N" part of the title — used for bulk apply ("N detalga").
  titleSuffix?: string
  edgeRegistry: EdgeRegistryEntry[]
  edgeAssignmentEntries: Array<[string, number]>
  groupEdgeIds: string[]
  otherGroupEdgeIds: string[]
}>()
const emit = defineEmits<{
  'edges-change': [
    { edges: Record<EdgeField, CuttingEdgeBand | null>; rememberedMaterialId: string | null },
  ]
  close: []
}>()

const cutting = useCuttingStore()

const edgePickerState = ref<Record<EdgeField, CuttingEdgeBand | null>>(blankEdgeState())
const edgePickerSearch = ref('')
const edgePickerThickness = ref('all')
const edgeDialogRef = ref<HTMLElement | null>(null)
// Panel 2 is the branch catalog. Panel 1 only lists tapes already in this drawing.
const showTapeList = ref(false)
const addedCatalogEdgeIds = ref<string[]>([])
// The tape currently used by side cards and preset chips. Picking a tape never
// auto-bands a side; side cards paint with this active tape.
const lastPickedEdgeId = ref<string | null>(null)
const activeEdgeId = ref<string | null>(null)

const sideNames: Record<EdgeField, string> = {
  edge_top: 'Yuqori',
  edge_bottom: 'Pastki',
  edge_left: 'Chap',
  edge_right: "O'ng",
}

const edgePatterns: Array<{ key: string; label: string; hint: string; sides: EdgeField[] }> = [
  { key: 'all', label: '4 tomon', hint: '— joriy kromka bilan', sides: [...edgeFields] },
  { key: 'none', label: 'Kromkasiz', hint: '— joriy kromka bilan', sides: [] },
]

function blankEdgeState(): Record<EdgeField, CuttingEdgeBand | null> {
  return { edge_top: null, edge_bottom: null, edge_left: null, edge_right: null }
}

function materialById(id: string | null | undefined) {
  return cutting.panelOptions.find((material) => material.id === id) ?? null
}

function edgeById(id: string | null | undefined) {
  return cutting.edgeOptions.find((material) => material.id === id) ?? null
}

function bandedEdgeFields(state: Record<EdgeField, CuttingEdgeBand | null>) {
  return edgeFields.filter((side) => state[side])
}

function cloneEdgeStateFromPart(part: CuttingPart): Record<EdgeField, CuttingEdgeBand | null> {
  return {
    edge_top: part.edge_top ? { ...part.edge_top } : null,
    edge_bottom: part.edge_bottom ? { ...part.edge_bottom } : null,
    edge_left: part.edge_left ? { ...part.edge_left } : null,
    edge_right: part.edge_right ? { ...part.edge_right } : null,
  }
}

function firstEdgeId(edges: Record<EdgeField, CuttingEdgeBand | null>) {
  return (
    edges.edge_top?.material_id ??
    edges.edge_bottom?.material_id ??
    edges.edge_left?.material_id ??
    edges.edge_right?.material_id ??
    null
  )
}

// The picker is branch-scoped like the panel picker (docs/ref/features/cutting.md):
// only tapes the selected branch carries are offered or recommended. A tape already
// on one of this part's sides stays visible (flagged) so the selection can't vanish.
const carriedEdgeOptions = computed(() =>
  cutting.edgeOptions.filter((material) => material.branch_carried),
)

function mostUsedEdgeId(edges: Record<EdgeField, CuttingEdgeBand | null>) {
  const counts = new Map<string, number>()
  for (const side of edgeFields) {
    const id = edges[side]?.material_id
    if (id) counts.set(id, (counts.get(id) ?? 0) + 1)
  }
  return [...counts.entries()].sort((left, right) => right[1] - left[1])[0]?.[0] ?? null
}

function recommendedEdgeForPart() {
  const part = props.part
  if (!part) return null
  return recommendedEdge(
    materialById(part.material_id),
    carriedEdgeOptions.value,
    lastPickedEdgeId.value ?? edgePickerSelectedMaterialId.value,
    props.preferredEdgeId,
    props.groupEdgeIds,
    props.otherGroupEdgeIds,
  )
}

function panelThicknessForPart() {
  if (!props.part) return null
  const panel = materialById(props.part.material_id)
  const thickness = Number(panel?.thickness_mm)
  return Number.isFinite(thickness) ? thickness : null
}

function narrowWarning(material: { edge_width_mm: number | null } | null | undefined) {
  const panelThickness = panelThicknessForPart()
  if (!material || panelThickness == null || !edgeTooNarrow(panelThickness, material)) return null
  return `Lenta eni (${material.edge_width_mm} mm) panel qalinligidan (${panelThickness} mm) tor — qirrani to'liq yopmaydi.`
}

function sideClass(side: EdgeField) {
  const edge = edgePickerState.value[side]
  if (!edge) {
    return 'border border-dashed border-hairline-strong bg-sunk text-ink-muted hover:border-ink-soft'
  }
  return 'border text-ink hover:border-ink-soft'
}

function sideEdgeCounts() {
  const counts = new Map<string, number>()
  for (const side of edgeFields) {
    const materialId = edgePickerState.value[side]?.material_id
    if (!materialId) continue
    counts.set(materialId, (counts.get(materialId) ?? 0) + 1)
  }
  return counts
}

const registryAssignments = computed(() => new Map(props.edgeAssignmentEntries))
const visibleRegistryAssignments = computed(
  () => new Set(props.edgeRegistry.map((entry) => entry.key)),
)

function orderedTapeIds() {
  const ids: string[] = []
  const seen = new Set<string>()
  const required = new Set<string>()
  const add = (id: string | null | undefined, requiredSide = false) => {
    if (!id || !edgeById(id)) return
    if (requiredSide) required.add(id)
    if (seen.has(id)) return
    seen.add(id)
    ids.push(id)
  }
  for (const side of edgeFields) add(edgePickerState.value[side]?.material_id, true)
  for (const materialId of props.groupEdgeIds) add(materialId)
  for (const materialId of props.otherGroupEdgeIds) add(materialId)
  for (const materialId of addedCatalogEdgeIds.value) add(materialId)
  const byRegistryNumber = (left: string, right: string) => {
    const leftNumber = registryAssignments.value.get(edgeRegistryKey(left, 'shop'))
    const rightNumber = registryAssignments.value.get(edgeRegistryKey(right, 'shop'))
    if (leftNumber != null && rightNumber != null) return leftNumber - rightNumber
    if (leftNumber != null) return -1
    if (rightNumber != null) return 1
    return ids.indexOf(left) - ids.indexOf(right)
  }
  ids.sort(byRegistryNumber)
  if (ids.length <= 6) return ids
  const limited: string[] = []
  for (const id of ids) {
    if (limited.length < 6 || required.has(id)) limited.push(id)
  }
  return limited
}

function originMeta(materialId: string, count: number) {
  if (count > 0) return `Shu detalda ${count} tomonga`
  if (props.groupEdgeIds.includes(materialId)) return 'Shu guruhda ishlatilgan'
  if (props.otherGroupEdgeIds.includes(materialId)) return 'Chizmaning boshqa guruhida'
  return 'Yangi'
}

const tapeEntries = computed(() => {
  const ids = orderedTapeIds()
  const keys = ids.map((materialId) => edgeRegistryKey(materialId, 'shop'))
  const preview = previewEdgeAssignments(registryAssignments.value, keys)
  const counts = sideEdgeCounts()
  return ids.map((materialId) => {
    const material = edgeById(materialId)
    const key = edgeRegistryKey(materialId, 'shop')
    const number = preview.get(key) ?? registryAssignments.value.get(key) ?? 1
    const count = counts.get(materialId) ?? 0
    const tentative = !visibleRegistryAssignments.value.has(key)
    const meta = [originMeta(materialId, count)]
    if (tentative && meta[0] !== 'Yangi') meta.push('Yangi')
    return {
      key,
      materialId,
      material,
      count,
      number,
      color: registryColorStyle(number),
      tentative,
      meta,
    }
  })
})

function tapeEntryForMaterial(materialId: string | null | undefined) {
  if (!materialId) return null
  return tapeEntries.value.find((entry) => entry.materialId === materialId) ?? null
}

function sideStyle(side: EdgeField) {
  const entry = tapeEntryForMaterial(edgePickerState.value[side]?.material_id)
  if (!entry) return {}
  return {
    background: entry.color.soft,
    borderColor: entry.color.bg,
    color: entry.color.bg,
  }
}

function badgeStyle(entry: { color: EdgeRegistryColorStyle }) {
  return {
    background: entry.color.bg,
    color: entry.color.fg,
  }
}

function tentativeTitle(entry: { tentative: boolean } | null | undefined) {
  return entry?.tentative
    ? "Bu kromka chizmada hali ishlatilmagan — qo'llangach shu raqam va rangni oladi."
    : undefined
}

function sideAria(side: EdgeField) {
  const edge = edgePickerState.value[side]
  const active = activeEdgeId.value
  if (edge?.material_id && edge.material_id === active)
    return `${sideNames[side]} tomon — joriy kromka bor, bosib olib tashlang`
  if (edge?.material_id)
    return `${sideNames[side]} tomon — boshqa kromka bor, bosib joriy kromkaga almashtiring`
  return `${sideNames[side]} tomon — joriy kromkani qo'shing`
}

const edgeThicknesses = computed(() =>
  [...new Set(carriedEdgeOptions.value.map((material) => material.thickness_mm))]
    .filter((value): value is string => Boolean(value))
    .sort((left, right) => Number(left) - Number(right)),
)
const catalogExcludedIds = computed(() => {
  const ids = new Set(props.edgeRegistry.map((entry) => entry.materialId))
  for (const side of edgeFields) {
    const materialId = edgePickerState.value[side]?.material_id
    if (materialId) ids.add(materialId)
  }
  return ids
})
const catalogFilteredEdges = computed(() => {
  const part = props.part
  if (!part) return []
  const query = edgePickerSearch.value.trim().toLowerCase()
  return rankedEdges(materialById(part.material_id), cutting.edgeOptions)
    .filter(({ material }) => material.branch_carried)
    .filter(({ material }) =>
      edgePickerThickness.value !== 'all'
        ? material.thickness_mm === edgePickerThickness.value
        : true,
    )
    .filter(({ material }) => {
      if (!query) return true
      return edgeSearchText(material).includes(query)
    })
})
const edgePickerMaterials = computed(() =>
  catalogFilteredEdges.value.filter(({ material }) => !catalogExcludedIds.value.has(material.id)),
)
const catalogMatchedEdges = computed(() =>
  edgePickerMaterials.value.filter(({ rank }) => rank <= 1),
)
const catalogOtherEdges = computed(() => edgePickerMaterials.value.filter(({ rank }) => rank > 1))
const catalogOnlyAddedHint = computed(
  () =>
    Boolean(edgePickerSearch.value.trim()) &&
    edgePickerMaterials.value.length === 0 &&
    catalogFilteredEdges.value.length > 0,
)
const catalogPanelName = computed(
  () => materialById(props.part?.material_id)?.name ?? "Material yo'q",
)
const edgePickerActiveSides = computed(() => bandedEdgeFields(edgePickerState.value))
const edgePickerPatternKey = computed(() => {
  const active = edgePickerActiveSides.value
  return (
    edgePatterns.find(
      (pattern) =>
        pattern.sides.length === active.length &&
        pattern.sides.every((side) => active.includes(side)),
    )?.key ?? null
  )
})
const edgePickerSelectedMaterialId = computed(() => {
  const first = edgePickerActiveSides.value
    .map((side) => edgePickerState.value[side]?.material_id)
    .find(Boolean)
  return first ?? null
})
const partDisplayName = computed(() => props.part?.name?.trim() || `D${props.partNumber}`)
const edgePickerBranchNote = computed(() => {
  if (!props.preferredBranchId) return null
  const missing = new Map<string, string>()
  for (const side of edgeFields) {
    const edge = edgePickerState.value[side]
    if (!edge) continue
    const material = edgeById(edge.material_id)
    if (material && !material.branch_carried) {
      missing.set(material.id, edgeShortLabel(material, true))
    }
  }
  if (!missing.size) return null
  return `${props.preferredBranchName} filialida ${[...missing.values()].join(' · ')} hozir mavjud emas. Boshqa kromka tanlang.`
})

function applyEdgePattern(key: string) {
  if (!props.part) return
  const pattern = edgePatterns.find((item) => item.key === key)
  if (!pattern) return
  if (pattern.sides.length === 0) {
    edgePickerState.value = blankEdgeState()
    emitEdgeChange()
    return
  }
  const materialId = activeEdgeId.value
  if (!materialId) return
  activeEdgeId.value = materialId
  lastPickedEdgeId.value = materialId
  const next = blankEdgeState()
  for (const side of pattern.sides) {
    next[side] = { material_id: materialId, source: 'shop' }
  }
  edgePickerState.value = next
  emitEdgeChange()
}

function togglePickerSide(side: EdgeField) {
  if (!props.part) return
  const materialId = activeEdgeId.value
  if (!materialId) return
  activeEdgeId.value = materialId
  lastPickedEdgeId.value = materialId
  const next = { ...edgePickerState.value }
  if (next[side]?.material_id === materialId) {
    next[side] = null
  } else {
    next[side] = { material_id: materialId, source: 'shop' }
  }
  edgePickerState.value = next
  emitEdgeChange()
}

function selectPickerMaterial(materialId: string) {
  if (!addedCatalogEdgeIds.value.includes(materialId)) {
    addedCatalogEdgeIds.value = [...addedCatalogEdgeIds.value, materialId]
  }
  lastPickedEdgeId.value = materialId
  activeEdgeId.value = materialId
  showTapeList.value = false
}

function setActiveTape(materialId: string) {
  activeEdgeId.value = materialId
  lastPickedEdgeId.value = materialId
}

function openCatalogForAdd() {
  edgePickerSearch.value = ''
  edgePickerThickness.value = 'all'
  showTapeList.value = true
}

function edgePayload() {
  const edges: Record<EdgeField, CuttingEdgeBand | null> = {
    edge_top: edgePickerState.value.edge_top ? { ...edgePickerState.value.edge_top } : null,
    edge_bottom: edgePickerState.value.edge_bottom
      ? { ...edgePickerState.value.edge_bottom }
      : null,
    edge_left: edgePickerState.value.edge_left ? { ...edgePickerState.value.edge_left } : null,
    edge_right: edgePickerState.value.edge_right ? { ...edgePickerState.value.edge_right } : null,
  }
  return { edges, rememberedMaterialId: activeEdgeId.value ?? firstEdgeId(edges) }
}

function emitEdgeChange() {
  emit('edges-change', edgePayload())
}

const EDGE_FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

// Trap Tab/Shift-Tab inside the modal so keyboard/SR users can't reach the obscured
// part rows behind the scrim (CB-06; mirrors ConfirmDialog).
function trapEdgeFocus(event: KeyboardEvent) {
  const root = edgeDialogRef.value
  if (!root) return
  const focusable = Array.from(root.querySelectorAll<HTMLElement>(EDGE_FOCUSABLE)).filter(
    (element) => element.getClientRects().length > 0,
  )
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (!first || !last) {
    event.preventDefault()
    root.focus()
    return
  }
  const active = document.activeElement
  if (event.shiftKey) {
    if (active === first || active === root) {
      event.preventDefault()
      last.focus()
    }
  } else if (active === last) {
    event.preventDefault()
    first.focus()
  }
}

function onDocumentKeydown(event: KeyboardEvent) {
  if (!props.part) return
  if (event.key === 'Escape') {
    emit('close')
    return
  }
  if (event.key === 'Tab') trapEdgeFocus(event)
}

// Open/close are driven by the `part` prop. On open: seed the working selection
// from the part, lock the body, listen for Escape/Tab, and focus the dialog. On
// close: undo those. Focus RETURN to the trigger is the editor's job.
watch(
  () => props.part,
  (part, previous) => {
    if (part && !previous) {
      edgePickerState.value = cloneEdgeStateFromPart(part)
      const clickedEdgeId = props.initialSide
        ? edgePickerState.value[props.initialSide]?.material_id
        : null
      const initialActiveId =
        clickedEdgeId ??
        mostUsedEdgeId(edgePickerState.value) ??
        props.preferredEdgeId ??
        recommendedEdgeForPart()?.id ??
        null
      showTapeList.value =
        props.edgeRegistry.length === 0 && bandedEdgeFields(edgePickerState.value).length === 0
      activeEdgeId.value = initialActiveId
      lastPickedEdgeId.value = initialActiveId
      edgePickerSearch.value = ''
      edgePickerThickness.value = 'all'
      addedCatalogEdgeIds.value = []
      lockBodyScroll()
      document.addEventListener('keydown', onDocumentKeydown)
      void nextTick(() => edgeDialogRef.value?.focus())
    } else if (!part && previous) {
      unlockBodyScroll()
      document.removeEventListener('keydown', onDocumentKeydown)
      edgePickerState.value = blankEdgeState()
      edgePickerSearch.value = ''
      edgePickerThickness.value = 'all'
      lastPickedEdgeId.value = null
      activeEdgeId.value = null
      addedCatalogEdgeIds.value = []
    }
  },
)

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onDocumentKeydown)
  if (props.part) unlockBodyScroll()
})
</script>

<template>
  <template v-if="part">
    <div class="client-modal-scrim" @click="emit('close')"></div>
    <section
      ref="edgeDialogRef"
      class="client-edge-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="edge-picker-title"
      tabindex="-1"
    >
      <div class="client-edge-modal-h">
        <h3
          id="edge-picker-title"
          class="min-w-0 truncate"
          :title="showTapeList ? 'Yana kromka qo\'shish' : (titleSuffix ?? partDisplayName)"
        >
          {{
            showTapeList
              ? "Yana kromka qo'shish"
              : `Kromka yopishtirish — ${titleSuffix ?? partDisplayName}`
          }}
        </h3>
        <button
          type="button"
          class="client-edge-close"
          aria-label="Kromka oynasini yopish"
          @click="emit('close')"
        >
          ×
        </button>
      </div>

      <div class="client-edge-modal-b">
        <template v-if="!showTapeList">
          <div class="flex flex-col gap-3 sm:flex-row sm:items-start">
            <div
              class="mx-auto grid w-full max-w-[314px] flex-1 grid-cols-[62px_minmax(0,1fr)_62px] grid-rows-[44px_92px_44px] items-stretch gap-1.5 sm:grid-rows-[38px_92px_38px]"
              aria-label="Kromka tomonlari"
            >
              <span></span>
              <button
                type="button"
                class="flex items-center justify-center gap-1.5 rounded-md px-1 text-center text-[11px] font-bold leading-tight transition"
                :class="sideClass('edge_top')"
                :style="sideStyle('edge_top')"
                :aria-pressed="Boolean(edgePickerState.edge_top)"
                :aria-label="sideAria('edge_top')"
                :disabled="!activeEdgeId"
                @click="togglePickerSide('edge_top')"
              >
                <span>{{ sideNames.edge_top }}</span>
                <template v-if="edgePickerState.edge_top">
                  <span
                    v-if="tapeEntryForMaterial(edgePickerState.edge_top.material_id)"
                    class="grid size-4 place-items-center rounded-full text-[10px] leading-none"
                    :class="{
                      'border border-dashed border-current': tapeEntryForMaterial(
                        edgePickerState.edge_top.material_id,
                      )?.tentative,
                    }"
                    :style="badgeStyle(tapeEntryForMaterial(edgePickerState.edge_top.material_id)!)"
                    :title="
                      tentativeTitle(tapeEntryForMaterial(edgePickerState.edge_top.material_id))
                    "
                  >
                    {{ tapeEntryForMaterial(edgePickerState.edge_top.material_id)?.number }}
                  </span>
                </template>
                <span v-else class="text-sm leading-none opacity-70">+</span>
              </button>
              <span></span>

              <button
                type="button"
                class="flex items-center justify-center gap-1 rounded-md px-1 text-center text-[11px] font-bold leading-tight transition"
                :class="sideClass('edge_left')"
                :style="sideStyle('edge_left')"
                :aria-pressed="Boolean(edgePickerState.edge_left)"
                :aria-label="sideAria('edge_left')"
                :disabled="!activeEdgeId"
                @click="togglePickerSide('edge_left')"
              >
                <span>{{ sideNames.edge_left }}</span>
                <span
                  v-if="
                    edgePickerState.edge_left &&
                    tapeEntryForMaterial(edgePickerState.edge_left.material_id)
                  "
                  class="grid size-4 place-items-center rounded-full text-[10px] leading-none"
                  :class="{
                    'border border-dashed border-current': tapeEntryForMaterial(
                      edgePickerState.edge_left.material_id,
                    )?.tentative,
                  }"
                  :style="badgeStyle(tapeEntryForMaterial(edgePickerState.edge_left.material_id)!)"
                  :title="
                    tentativeTitle(tapeEntryForMaterial(edgePickerState.edge_left.material_id))
                  "
                >
                  {{ tapeEntryForMaterial(edgePickerState.edge_left.material_id)?.number }}
                </span>
              </button>
              <div
                class="flex flex-col items-center justify-center gap-1 rounded-md border border-hairline text-ink-muted"
                style="
                  background: repeating-linear-gradient(
                    45deg,
                    var(--color-sunk),
                    var(--color-sunk) 7px,
                    var(--color-elevated) 7px,
                    var(--color-elevated) 14px
                  );
                "
              >
                <span
                  data-test="edge-part-name"
                  class="max-w-full truncate px-2 text-xs font-bold"
                  :title="partDisplayName"
                  >{{ partDisplayName }}</span
                >
                <span class="font-mono text-[11px] font-bold text-ink-soft">
                  <template v-if="part">{{ part.length_mm }} × {{ part.width_mm }}</template>
                </span>
              </div>
              <button
                type="button"
                class="flex items-center justify-center gap-1 rounded-md px-1 text-center text-[11px] font-bold leading-tight transition"
                :class="sideClass('edge_right')"
                :style="sideStyle('edge_right')"
                :aria-pressed="Boolean(edgePickerState.edge_right)"
                :aria-label="sideAria('edge_right')"
                :disabled="!activeEdgeId"
                @click="togglePickerSide('edge_right')"
              >
                <span>{{ sideNames.edge_right }}</span>
                <span
                  v-if="
                    edgePickerState.edge_right &&
                    tapeEntryForMaterial(edgePickerState.edge_right.material_id)
                  "
                  class="grid size-4 place-items-center rounded-full text-[10px] leading-none"
                  :class="{
                    'border border-dashed border-current': tapeEntryForMaterial(
                      edgePickerState.edge_right.material_id,
                    )?.tentative,
                  }"
                  :style="badgeStyle(tapeEntryForMaterial(edgePickerState.edge_right.material_id)!)"
                  :title="
                    tentativeTitle(tapeEntryForMaterial(edgePickerState.edge_right.material_id))
                  "
                >
                  {{ tapeEntryForMaterial(edgePickerState.edge_right.material_id)?.number }}
                </span>
              </button>

              <span></span>
              <button
                type="button"
                class="flex items-center justify-center gap-1.5 rounded-md px-1 text-center text-[11px] font-bold leading-tight transition"
                :class="sideClass('edge_bottom')"
                :style="sideStyle('edge_bottom')"
                :aria-pressed="Boolean(edgePickerState.edge_bottom)"
                :aria-label="sideAria('edge_bottom')"
                :disabled="!activeEdgeId"
                @click="togglePickerSide('edge_bottom')"
              >
                <span>{{ sideNames.edge_bottom }}</span>
                <template v-if="edgePickerState.edge_bottom">
                  <span
                    v-if="tapeEntryForMaterial(edgePickerState.edge_bottom.material_id)"
                    class="grid size-4 place-items-center rounded-full text-[10px] leading-none"
                    :class="{
                      'border border-dashed border-current': tapeEntryForMaterial(
                        edgePickerState.edge_bottom.material_id,
                      )?.tentative,
                    }"
                    :style="
                      badgeStyle(tapeEntryForMaterial(edgePickerState.edge_bottom.material_id)!)
                    "
                    :title="
                      tentativeTitle(tapeEntryForMaterial(edgePickerState.edge_bottom.material_id))
                    "
                  >
                    {{ tapeEntryForMaterial(edgePickerState.edge_bottom.material_id)?.number }}
                  </span>
                </template>
                <span v-else class="text-sm leading-none opacity-70">+</span>
              </button>
              <span></span>
            </div>

            <div
              class="grid shrink-0 grid-cols-2 gap-2 sm:w-28 sm:grid-cols-1"
              aria-label="Kromka tomoni shablonlari"
            >
              <span class="col-span-2 text-xs font-medium text-ink-muted sm:col-span-1"
                >Shablonlar</span
              >
              <button
                v-for="pattern in edgePatterns"
                :key="pattern.key"
                type="button"
                class="inline-flex items-center justify-center gap-1.5 rounded-full border px-3 py-2 text-xs font-bold transition disabled:cursor-not-allowed disabled:opacity-50"
                :class="
                  edgePickerPatternKey === pattern.key
                    ? 'border-accent bg-accent-soft text-accent'
                    : 'border-hairline-strong bg-elevated text-ink hover:border-ink-soft'
                "
                :disabled="pattern.sides.length > 0 && !activeEdgeId"
                @click="applyEdgePattern(pattern.key)"
              >
                <svg
                  viewBox="0 0 24 18"
                  class="size-[18px] shrink-0"
                  fill="none"
                  aria-hidden="true"
                >
                  <rect
                    x="3"
                    y="3"
                    width="18"
                    height="12"
                    rx="1"
                    stroke="currentColor"
                    :stroke-width="pattern.sides.length ? 2.6 : 1"
                    :opacity="pattern.sides.length ? 1 : 0.35"
                  />
                </svg>
                {{ pattern.label }}
              </button>
            </div>
          </div>

          <p v-if="!activeEdgeId" class="text-xs text-ink-muted">
            Avval kromka tanlang — keyin tomonlarni bosing.
          </p>

          <div class="grid gap-2" aria-label="Kromkalar">
            <h4 class="text-xs font-semibold text-ink-soft">Chizmadagi kromkalar</h4>
            <p v-if="tapeEntries.length === 0" class="text-xs text-ink-muted">
              Chizmada hali kromka yo'q.
            </p>
            <!-- The tape list scrolls on its own (~3 rows) so the part diagram,
                 `Shablonlar` and the footer never scroll away (QAD-152). The
                 outer `.client-edge-modal-b` stays the fallback scroller for
                 very short viewports. -->
            <div v-else class="grid max-h-[200px] gap-2 overflow-y-auto overscroll-contain p-0.5">
              <button
                v-for="entry in tapeEntries"
                :key="entry.materialId"
                type="button"
                class="flex items-center gap-3 rounded-xl border bg-elevated p-3 text-left transition hover:border-ink-soft"
                :class="
                  activeEdgeId === entry.materialId
                    ? 'border-accent shadow-[0_0_0_1px_var(--color-accent)]'
                    : 'border-hairline'
                "
                @click="setActiveTape(entry.materialId)"
              >
                <span
                  class="grid size-7 shrink-0 place-items-center rounded-full text-xs font-black"
                  :class="{ 'border border-dashed border-current': entry.tentative }"
                  :style="badgeStyle(entry)"
                  :title="tentativeTitle(entry)"
                >
                  {{ entry.number }}
                </span>
                <span class="min-w-0 flex-1">
                  <span class="flex min-w-0 items-center gap-2">
                    <span class="truncate text-sm font-bold text-ink">{{
                      edgeShortLabel(entry.material)
                    }}</span>
                    <span
                      v-if="activeEdgeId === entry.materialId"
                      class="rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-black uppercase tracking-wide text-accent"
                    >
                      Joriy
                    </span>
                    <span
                      v-if="narrowWarning(entry.material)"
                      class="rounded-full bg-warning-soft px-2 py-0.5 text-[10px] font-black text-warning"
                      :title="narrowWarning(entry.material) ?? undefined"
                    >
                      Qirradan tor
                    </span>
                  </span>
                  <span class="font-mono text-[11.5px] text-ink-muted">
                    {{ entry.meta.join(' · ') }}
                  </span>
                </span>
              </button>
            </div>
          </div>

          <div v-if="edgePickerBranchNote" class="ep-branch-note">
            {{ edgePickerBranchNote }}
          </div>
        </template>

        <template v-else>
          <input
            v-model="edgePickerSearch"
            class="mp-input"
            type="search"
            placeholder="Kromka nomi yoki dekor kodi"
            aria-label="Kromka qidirish"
          />

          <div class="flex flex-wrap gap-2" role="group" aria-label="Qalinlik filtri">
            <button
              type="button"
              class="rounded-full border px-3 py-1.5 text-xs font-bold transition"
              :class="
                edgePickerThickness === 'all'
                  ? 'border-accent bg-accent text-white'
                  : 'border-hairline-strong bg-elevated text-ink-soft hover:border-ink-soft'
              "
              @click="edgePickerThickness = 'all'"
            >
              Hammasi
            </button>
            <button
              v-for="thickness in edgeThicknesses"
              :key="thickness"
              type="button"
              class="rounded-full border px-3 py-1.5 text-xs font-bold transition"
              :class="
                edgePickerThickness === thickness
                  ? 'border-accent bg-accent text-white'
                  : 'border-hairline-strong bg-elevated text-ink-soft hover:border-ink-soft'
              "
              @click="edgePickerThickness = thickness"
            >
              {{ thickness }} mm
            </button>
          </div>

          <section v-if="catalogMatchedEdges.length" class="grid gap-2">
            <h4 class="text-xs font-semibold text-ink-soft">
              Shu panelga mos
              <span class="font-normal text-ink-muted">· {{ catalogPanelName }} bo'yicha</span>
            </h4>
            <button
              v-for="{ material, rank } in catalogMatchedEdges"
              :key="material.id"
              type="button"
              class="flex items-center gap-3 rounded-md border border-hairline bg-elevated px-3 py-2.5 text-left transition hover:border-accent-tint hover:bg-accent-soft/20"
              @click="selectPickerMaterial(material.id)"
            >
              <span
                class="size-4 shrink-0 rounded border border-hairline-strong"
                :style="{ background: colorForMaterial(material.color) }"
              ></span>
              <span class="min-w-0 flex-1">
                <span class="block truncate text-sm font-bold text-ink">{{
                  edgeShortLabel(material)
                }}</span>
                <span class="block text-xs text-ink-muted">
                  {{ material.thickness_mm }} mm · {{ material.edge_width_mm }} mm
                </span>
                <span v-if="narrowWarning(material)" class="block text-xs text-warning">
                  {{ narrowWarning(material) }}
                </span>
              </span>
              <span
                class="shrink-0 rounded-full border border-hairline bg-sunk px-2 py-0.5 text-[10.5px] font-bold text-accent"
              >
                {{ rank === 0 ? 'dekor mos' : 'rang mos' }}
              </span>
            </button>
          </section>

          <section v-if="catalogOtherEdges.length" class="grid gap-2">
            <h4 class="text-xs font-semibold text-ink-soft">Boshqa kromkalar</h4>
            <button
              v-for="{ material } in catalogOtherEdges"
              :key="material.id"
              type="button"
              class="flex items-center gap-3 rounded-md border border-hairline bg-elevated px-3 py-2.5 text-left transition hover:border-accent-tint hover:bg-accent-soft/20"
              @click="selectPickerMaterial(material.id)"
            >
              <span
                class="size-4 shrink-0 rounded border border-hairline-strong"
                :style="{ background: colorForMaterial(material.color) }"
              ></span>
              <span class="min-w-0 flex-1">
                <span class="block truncate text-sm font-bold text-ink">{{
                  edgeShortLabel(material)
                }}</span>
                <span class="block text-xs text-ink-muted">
                  {{ material.thickness_mm }} mm · {{ material.edge_width_mm }} mm
                </span>
                <span v-if="narrowWarning(material)" class="block text-xs text-warning">
                  {{ narrowWarning(material) }}
                </span>
              </span>
            </button>
          </section>

          <p v-if="catalogOnlyAddedHint" class="text-xs text-ink-muted">
            Bu kromka allaqachon chizmada — 1-ro'yxatdan tanlang.
          </p>
          <p v-else-if="edgePickerMaterials.length === 0" class="text-xs text-ink-muted">
            Mos kromka topilmadi. Qidiruv yoki qalinlikni o'zgartiring.
          </p>
        </template>
      </div>

      <!-- Fixed footer, rendered in both panels so the modal height doesn't
           jump when switching between them (QAD-153). `Tayyor` only closes —
           every side click already writes onto the part live. -->
      <div class="client-edge-modal-f">
        <button
          v-if="!showTapeList"
          type="button"
          class="mp-button mp-button-outline mr-auto"
          @click="openCatalogForAdd"
        >
          + Yana kromka
        </button>
        <button
          v-else
          type="button"
          class="mp-button mp-button-outline mr-auto"
          @click="showTapeList = false"
        >
          ← Orqaga
        </button>
        <button type="button" class="mp-button mp-button-primary" @click="emit('close')">
          Tayyor
        </button>
      </div>
    </section>
  </template>
</template>
