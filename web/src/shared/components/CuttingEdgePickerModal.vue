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
import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
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
  // Overrides the "qism #N" part of the title — used for bulk apply ("N qismga").
  titleSuffix?: string
  edgeRegistry: EdgeRegistryEntry[]
  edgeAssignmentEntries: Array<[string, number]>
  groupEdgeIds: string[]
  otherGroupEdgeIds: string[]
}>()
const emit = defineEmits<{
  apply: [{ edges: Record<EdgeField, CuttingEdgeBand | null>; rememberedMaterialId: string | null }]
  close: []
}>()

const cutting = useCuttingStore()

const edgePickerState = ref<Record<EdgeField, CuttingEdgeBand | null>>(blankEdgeState())
const edgePickerSearch = ref('')
const edgePickerThickness = ref<string | null>('all')
const edgeDialogRef = ref<HTMLElement | null>(null)
// The searchable tape list is revealed on demand. Open it by default only when the
// part has no banding yet (the first-time pick); when editing a part that already
// has a tape, collapse to the compact summary + an "O'zgartirish" toggle.
const showTapeList = ref(false)
// The tape currently used by side cards and preset chips. Picking a tape never
// auto-bands a side; side cards paint with this active tape.
const lastPickedEdgeId = ref<string | null>(null)
const activeEdgeId = ref<string | null>(null)
const catalogReplaceEdgeId = ref<string | null>(null)

const sideNames: Record<EdgeField, string> = {
  edge_top: 'Yuqori',
  edge_bottom: 'Pastki',
  edge_left: 'Chap',
  edge_right: "O'ng",
}

const edgePatterns: Array<{ key: string; label: string; hint: string; sides: EdgeField[] }> = [
  { key: 'none', label: 'Hech qaysi', hint: '— joriy tasma bilan', sides: [] },
  { key: 'all', label: 'Hamma tomon', hint: '— joriy tasma bilan', sides: [...edgeFields] },
  {
    key: 'tb',
    label: 'Yuqori + pastki',
    hint: '— joriy tasma bilan',
    sides: ['edge_top', 'edge_bottom'],
  },
  {
    key: 'lr',
    label: "Chap + o'ng",
    hint: '— joriy tasma bilan',
    sides: ['edge_left', 'edge_right'],
  },
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

function materialThicknessLabel(materialId: string | null | undefined) {
  const material = edgeById(materialId)
  return material?.thickness_mm ? `${material.thickness_mm}mm` : ''
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
  const recommendedId = recommendedEdgeForPart()?.id
  add(recommendedId, Boolean(recommendedId && recommendedId === activeEdgeId.value))
  if (ids.length <= 6) return ids
  const limited: string[] = []
  for (const id of ids) {
    if (limited.length < 6 || required.has(id)) limited.push(id)
  }
  return limited
}

function originMeta(materialId: string, count: number) {
  if (count > 0) return `Shu qismda ${count} tomonga`
  if (props.groupEdgeIds.includes(materialId)) return 'Shu guruhda ishlatilgan'
  if (props.otherGroupEdgeIds.includes(materialId)) return 'Chizmaning boshqa guruhida'
  if (recommendedEdgeForPart()?.id === materialId) return 'Tavsiya - dekor mos'
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
    ? "Bu tasma chizmada hali ishlatilmagan — qo'llangach shu raqam va rangni oladi."
    : undefined
}

function sideAria(side: EdgeField) {
  const edge = edgePickerState.value[side]
  const active = activeEdgeId.value
  if (edge?.material_id && edge.material_id === active)
    return `${sideNames[side]} tomon — joriy krom bor, bosib olib tashlang`
  if (edge?.material_id)
    return `${sideNames[side]} tomon — boshqa krom bor, bosib joriy kromga almashtiring`
  return `${sideNames[side]} tomon — joriy kromni qo'shing`
}

const edgeThicknessOptions = computed<ChoiceOption[]>(() => {
  const values = [...new Set(carriedEdgeOptions.value.map((material) => material.thickness_mm))]
    .filter(Boolean)
    .sort((left, right) => Number(left) - Number(right))
  return [
    { value: 'all', label: 'Hamma qalinlik', meta: 'Barcha kromlar' },
    ...values.map((value) => ({ value, label: `${value} mm`, meta: 'Qalinlik' })),
  ]
})
const edgePickerMaterials = computed(() => {
  const part = props.part
  if (!part) return []
  const query = edgePickerSearch.value.trim().toLowerCase()
  const selectedIds = new Set(
    edgeFields
      .map((side) => edgePickerState.value[side]?.material_id)
      .filter((id): id is string => Boolean(id)),
  )
  return rankedEdges(materialById(part.material_id), cutting.edgeOptions)
    .filter(({ material }) => material.branch_carried || selectedIds.has(material.id))
    .filter(({ material }) =>
      edgePickerThickness.value && edgePickerThickness.value !== 'all'
        ? material.thickness_mm === edgePickerThickness.value
        : true,
    )
    .filter(({ material }) => {
      if (!query) return true
      return edgeSearchText(material).includes(query)
    })
})
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
const highlightedEdgeId = computed(() => activeEdgeId.value)
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
  return `${props.preferredBranchName} filialida ${[...missing.values()].join(' · ')} hozir mavjud emas. Boshqa krom tanlang.`
})

function applyEdgePattern(key: string) {
  if (!props.part) return
  const pattern = edgePatterns.find((item) => item.key === key)
  if (!pattern) return
  if (pattern.sides.length === 0) {
    edgePickerState.value = blankEdgeState()
    return
  }
  const materialId = activeEdgeId.value ?? recommendedEdgeForPart()?.id
  if (!materialId) return
  activeEdgeId.value = materialId
  lastPickedEdgeId.value = materialId
  const next = blankEdgeState()
  for (const side of pattern.sides) {
    next[side] = { material_id: materialId, source: 'shop' }
  }
  edgePickerState.value = next
}

function togglePickerSide(side: EdgeField) {
  if (!props.part) return
  const materialId = activeEdgeId.value ?? recommendedEdgeForPart()?.id
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
}

function selectPickerMaterial(materialId: string) {
  lastPickedEdgeId.value = materialId
  activeEdgeId.value = materialId
  if (catalogReplaceEdgeId.value && catalogReplaceEdgeId.value !== materialId) {
    const next = { ...edgePickerState.value }
    for (const side of edgeFields) {
      if (next[side]?.material_id === catalogReplaceEdgeId.value) {
        next[side] = { material_id: materialId, source: 'shop' }
      }
    }
    edgePickerState.value = next
  }
  catalogReplaceEdgeId.value = null
  showTapeList.value = false
}

function setActiveTape(materialId: string) {
  activeEdgeId.value = materialId
  lastPickedEdgeId.value = materialId
}

function openCatalogForAdd() {
  catalogReplaceEdgeId.value = null
  edgePickerSearch.value = ''
  edgePickerThickness.value = 'all'
  showTapeList.value = true
}

function openCatalogForReplace(materialId: string) {
  setActiveTape(materialId)
  catalogReplaceEdgeId.value = materialId
  edgePickerSearch.value = ''
  edgePickerThickness.value = 'all'
  showTapeList.value = true
}

function applyEdgePicker() {
  const edges: Record<EdgeField, CuttingEdgeBand | null> = {
    edge_top: edgePickerState.value.edge_top ? { ...edgePickerState.value.edge_top } : null,
    edge_bottom: edgePickerState.value.edge_bottom
      ? { ...edgePickerState.value.edge_bottom }
      : null,
    edge_left: edgePickerState.value.edge_left ? { ...edgePickerState.value.edge_left } : null,
    edge_right: edgePickerState.value.edge_right ? { ...edgePickerState.value.edge_right } : null,
  }
  emit('apply', { edges, rememberedMaterialId: activeEdgeId.value ?? firstEdgeId(edges) })
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
      showTapeList.value = false
      catalogReplaceEdgeId.value = null
      activeEdgeId.value = initialActiveId
      lastPickedEdgeId.value = initialActiveId
      edgePickerSearch.value = ''
      edgePickerThickness.value = 'all'
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
      catalogReplaceEdgeId.value = null
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
        <h3 id="edge-picker-title">
          Krom yopishtirish — {{ titleSuffix ?? `qism #${partNumber}` }}
        </h3>
        <button
          type="button"
          class="client-edge-close"
          aria-label="Krom oynasini yopish"
          @click="emit('close')"
        >
          ×
        </button>
      </div>

      <div class="client-edge-modal-b">
        <div class="flex flex-wrap gap-2" aria-label="Krom tomoni shablonlari">
          <button
            v-for="pattern in edgePatterns"
            :key="pattern.key"
            type="button"
            class="inline-flex items-center gap-1.5 rounded-full border px-3.5 py-2 text-xs font-bold transition disabled:cursor-not-allowed disabled:opacity-50"
            :class="
              edgePickerPatternKey === pattern.key
                ? 'border-accent bg-accent-soft text-accent'
                : 'border-hairline-strong bg-elevated text-ink hover:border-ink-soft'
            "
            :disabled="pattern.sides.length > 0 && !recommendedEdgeForPart()"
            @click="applyEdgePattern(pattern.key)"
          >
            <!-- Panel diagram: the banded sides are drawn thick, the rest thin,
                 so the chip reads spatially (which edges get tape) not just by
                 text. Strokes use currentColor → follow the chip's selected tint. -->
            <svg viewBox="0 0 24 18" class="size-[18px] shrink-0" fill="none" aria-hidden="true">
              <line
                v-for="side in [
                  { k: 'edge_top', x1: 3, y1: 3, x2: 21, y2: 3 },
                  { k: 'edge_bottom', x1: 3, y1: 15, x2: 21, y2: 15 },
                  { k: 'edge_left', x1: 3, y1: 3, x2: 3, y2: 15 },
                  { k: 'edge_right', x1: 21, y1: 3, x2: 21, y2: 15 },
                ]"
                :key="side.k"
                :x1="side.x1"
                :y1="side.y1"
                :x2="side.x2"
                :y2="side.y2"
                stroke="currentColor"
                stroke-linecap="round"
                :stroke-width="pattern.sides.includes(side.k as EdgeField) ? 2.6 : 1"
                :opacity="pattern.sides.includes(side.k as EdgeField) ? 1 : 0.3"
              />
            </svg>
            {{ pattern.label }}
            <span class="text-[10px] font-semibold opacity-70">{{ pattern.hint }}</span>
          </button>
        </div>

        <div
          class="mx-auto grid w-full max-w-[340px] grid-cols-[62px_minmax(0,1fr)_62px] grid-rows-[34px_92px_34px] items-stretch gap-1.5"
          aria-label="Krom tomonlari"
        >
          <span></span>
          <button
            type="button"
            class="flex items-center justify-center gap-1.5 rounded-md px-1 text-center text-[11px] font-bold leading-tight transition"
            :class="sideClass('edge_top')"
            :style="sideStyle('edge_top')"
            :aria-pressed="Boolean(edgePickerState.edge_top)"
            :aria-label="sideAria('edge_top')"
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
                :title="tentativeTitle(tapeEntryForMaterial(edgePickerState.edge_top.material_id))"
              >
                {{ tapeEntryForMaterial(edgePickerState.edge_top.material_id)?.number }}
              </span>
              <span class="font-mono text-[10px] opacity-90">{{
                materialThicknessLabel(edgePickerState.edge_top.material_id)
              }}</span>
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
              :title="tentativeTitle(tapeEntryForMaterial(edgePickerState.edge_left.material_id))"
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
            <span class="text-xs font-bold">Qism</span>
            <span v-if="part" class="font-mono text-[11px] font-bold text-ink-soft"
              >{{ part.length_mm }} × {{ part.width_mm }}</span
            >
          </div>
          <button
            type="button"
            class="flex items-center justify-center gap-1 rounded-md px-1 text-center text-[11px] font-bold leading-tight transition"
            :class="sideClass('edge_right')"
            :style="sideStyle('edge_right')"
            :aria-pressed="Boolean(edgePickerState.edge_right)"
            :aria-label="sideAria('edge_right')"
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
              :title="tentativeTitle(tapeEntryForMaterial(edgePickerState.edge_right.material_id))"
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
                :style="badgeStyle(tapeEntryForMaterial(edgePickerState.edge_bottom.material_id)!)"
                :title="
                  tentativeTitle(tapeEntryForMaterial(edgePickerState.edge_bottom.material_id))
                "
              >
                {{ tapeEntryForMaterial(edgePickerState.edge_bottom.material_id)?.number }}
              </span>
              <span class="font-mono text-[10px] opacity-90">{{
                materialThicknessLabel(edgePickerState.edge_bottom.material_id)
              }}</span>
            </template>
            <span v-else class="text-sm leading-none opacity-70">+</span>
          </button>
          <span></span>
        </div>

        <div class="grid gap-2" aria-label="Kromkalar">
          <div
            v-for="entry in tapeEntries"
            :key="entry.materialId"
            class="flex items-center gap-3 rounded-xl border bg-elevated p-3 text-left transition hover:border-ink-soft"
            :class="
              activeEdgeId === entry.materialId
                ? 'border-accent shadow-[0_0_0_1px_var(--color-accent)]'
                : 'border-hairline'
            "
          >
            <button
              type="button"
              class="flex min-w-0 flex-1 items-center gap-3 text-left"
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
              <span
                class="size-8 shrink-0 rounded-lg border border-hairline"
                :style="{ background: colorForMaterial(entry.material?.color) }"
              ></span>
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
            <button
              type="button"
              class="shrink-0 text-sm font-bold text-accent"
              @click="openCatalogForReplace(entry.materialId)"
            >
              O'zgartirish →
            </button>
          </div>
          <button
            type="button"
            class="rounded-xl border border-dashed border-hairline-strong bg-sunk px-3 py-2 text-sm font-bold text-accent transition hover:border-accent"
            @click="openCatalogForAdd"
          >
            + Yana tasma qo'shish
          </button>
        </div>

        <div v-if="showTapeList" class="ep-tools">
          <input
            v-model="edgePickerSearch"
            class="ep-search"
            type="search"
            placeholder="Krom nomi, decor yoki rang..."
            aria-label="Krom qidirish"
          />
          <FormSelect
            v-model="edgePickerThickness"
            class="picker-select"
            label="Qalinlik"
            :options="edgeThicknessOptions"
          />
          <div class="ep-edge-list">
            <button
              v-for="{ material, rank } in edgePickerMaterials"
              :key="material.id"
              type="button"
              class="ep-edge-opt"
              :class="{ on: highlightedEdgeId === material.id }"
              @click="selectPickerMaterial(material.id)"
            >
              <span class="rad" aria-hidden="true"></span>
              <span class="sw" :style="{ background: colorForMaterial(material.color) }"></span>
              <span class="lab">
                <span class="nm">
                  {{ edgeShortLabel(material) }}
                  <span v-if="rank < 2" class="fav">Mos</span>
                  <span
                    v-if="narrowWarning(material)"
                    class="rounded-full bg-warning-soft px-2 py-0.5 text-[10px] font-black text-warning"
                    :title="narrowWarning(material) ?? undefined"
                  >
                    Qirradan tor
                  </span>
                </span>
                <span class="meta">{{ material.name }}</span>
              </span>
              <span class="thk">{{ material.thickness_mm }} mm</span>
            </button>
            <div v-if="edgePickerMaterials.length === 0" class="ep-empty">
              Mos krom topilmadi. Qidiruv yoki qalinlikni o'zgartiring.
            </div>
          </div>
        </div>

        <div v-if="edgePickerBranchNote" class="ep-branch-note">
          {{ edgePickerBranchNote }}
        </div>
      </div>

      <div class="client-edge-modal-f">
        <button type="button" class="mp-button mp-button-outline" @click="emit('close')">
          Bekor qilish
        </button>
        <button type="button" class="mp-button mp-button-primary" @click="applyEdgePicker">
          Qo'llash
        </button>
      </div>
    </section>
  </template>
</template>
