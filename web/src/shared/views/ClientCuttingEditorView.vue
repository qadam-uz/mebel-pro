<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { ApiError } from '@/shared/api/client'
import { createAutosaveController } from '@/shared/app/autosaveController'
import { clientErrorLabel, formatPercent } from '@/shared/app/clientUi'
import { AUTOSAVE_DEBOUNCE_MS, MAX_PARTS, MIN_PART_MM } from '@/shared/app/constants'
import { rankedEdges, recommendedEdge } from '@/shared/app/cuttingEdgeDisplay'
import { useToast } from '@/shared/composables/useToast'
import { lockBodyScroll, unlockBodyScroll } from '@/shared/app/scrollLock'
import Icon from '@/shared/components/AppIcon.vue'
import { useRolePath } from '@/shared/app/paths'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import CuttingBranchPicker from '@/shared/components/CuttingBranchPicker.vue'
import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import MultiSelectFilter from '@/shared/components/MultiSelectFilter.vue'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import type { PanelMaterialType } from '@/shared/stores/admin'
import {
  EDGE_TRIM_MM,
  materialLabel,
  metres,
  partFitError,
  partNotCarried,
  useCuttingStore,
  type ClientCatalogMaterialOption,
  type CuttingEdgeBand,
  type CuttingPanel,
  type CuttingPart,
  type CuttingPlacement,
  type CuttingResult,
  type MaterialSource,
} from '@/shared/stores/cutting'

const route = useRoute()
const rolePath = useRolePath()
const cutting = useCuttingStore()
const toast = useToast()
const draftId = computed(() => String(route.params.id))
const parts = ref<CuttingPart[]>([])
const saveState = ref<'saved' | 'saving' | 'error' | 'editing'>('saved')
const saveError = ref<string | null>(null)
const optimizeError = ref<string | null>(null)
// Per-row optimiser-error attribution (CB-89): the backend returns
// details {part_ref, row_index} on a part-specific failure, so flag THAT row
// rather than only a single opaque banner.
const optimizeRowError = ref<{
  partRef: string | null
  rowIndex: number | null
  message: string
} | null>(null)
const branchPickerOpen = ref(false)
const selectedBranchId = ref<string | null>(null)
const showAllCatalog = ref(false)
const clearPartsConfirmOpen = ref(false)
const algorithmsOpen = ref(false)
const recoveryDismissed = ref(false)
const activeResultId = ref<string | null>(null)
const activePanelId = ref<string | null>(null)
const activePlacementId = ref<string | null>(null)
const preferredEdgeByPart = ref<Record<string, string>>({})
const edgePickerPart = ref<CuttingPart | null>(null)
const edgePickerState = ref<Record<EdgeField, CuttingEdgeBand | null>>(blankEdgeState())
const edgePickerSource = ref<MaterialSource>('shop')
const edgePickerSearch = ref('')
const edgePickerThickness = ref<string | null>('all')
const edgeDialogRef = ref<HTMLElement | null>(null)
let edgeReturnFocus: HTMLElement | null = null
let hydrating = false
// The draft whose parts are currently mirrored into `parts.value`. We only
// re-hydrate from a server snapshot when this changes — saves/optimizes return
// the same draft and must not clobber unsaved local edits (CB-15).
let hydratedDraftId: string | null = null

const draft = computed(() => cutting.currentDraft)
// A draft is bound to an order once one of its results is confirmed onto an
// order (the backend enforces one result per order). Bound drafts are
// read-only — editing them would fire doomed saves and contradict the order.
const boundOrderId = computed(
  () => draft.value?.results.find((result) => result.order_id)?.order_id ?? null,
)
const isReadOnly = computed(() => boundOrderId.value !== null)
const preferredBranch = computed(() =>
  cutting.branchOptions.find((branch) => branch.branch_id === draft.value?.preferred_branch_id),
)
// Panel picker filters (CB-84): manufacturer (multi-select), type, thickness, and
// a sort — applied to the shared option list every row's panel picker draws from.
const panelManufacturerFilter = ref<string[]>([])
const panelTypeFilter = ref<string | null>(null)
const panelThicknessFilter = ref<string | null>(null)
const panelSort = ref<string | null>('relevance')

const PANEL_TYPE_LABELS: Record<string, string> = {
  dsp: 'DSP',
  mdf: 'MDF',
  plywood: 'Fanera',
  natural_wood: "Tabiiy yog'och",
  other: 'Boshqa',
}
const panelManufacturerChoices = computed<ChoiceOption[]>(() => {
  const seen = new Map<string, string>()
  for (const material of cutting.panelOptions)
    seen.set(material.manufacturer_id, material.manufacturer_name)
  return [...seen]
    .map(([value, label]) => ({ value, label }))
    .sort((left, right) => left.label.localeCompare(right.label))
})
const panelTypeChoices = computed<ChoiceOption[]>(() => {
  const types = [
    ...new Set(
      cutting.panelOptions
        .map((material) => material.type)
        .filter((type): type is PanelMaterialType => type !== null),
    ),
  ].sort()
  return [
    { value: '', label: 'Barcha turlar' },
    ...types.map((type) => ({ value: type, label: PANEL_TYPE_LABELS[type] ?? type })),
  ]
})
const panelThicknessChoices = computed<ChoiceOption[]>(() => {
  const thicknesses = [
    ...new Set(cutting.panelOptions.map((material) => material.thickness_mm)),
  ].sort((left, right) => Number(left) - Number(right))
  return [
    { value: '', label: 'Barcha qalinliklar' },
    ...thicknesses.map((thickness) => ({ value: thickness, label: `${thickness} mm` })),
  ]
})
const panelSortChoices: ChoiceOption[] = [
  { value: 'relevance', label: 'Tartib: tavsiya' },
  { value: 'manufacturer', label: 'Tartib: ishlab chiqaruvchi' },
  { value: 'thickness', label: 'Tartib: qalinlik' },
]
const panelFiltersActive = computed(
  () =>
    panelManufacturerFilter.value.length > 0 ||
    !!panelTypeFilter.value ||
    !!panelThicknessFilter.value,
)
function clearPanelFilters() {
  panelManufacturerFilter.value = []
  panelTypeFilter.value = null
  panelThicknessFilter.value = null
}

const panelOptions = computed(() => {
  let list = cutting.panelOptions.filter((material) =>
    draft.value?.preferred_branch_id && !showAllCatalog.value ? material.branch_carried : true,
  )
  if (panelManufacturerFilter.value.length > 0) {
    list = list.filter((material) =>
      panelManufacturerFilter.value.includes(material.manufacturer_id),
    )
  }
  if (panelTypeFilter.value)
    list = list.filter((material) => material.type === panelTypeFilter.value)
  if (panelThicknessFilter.value) {
    list = list.filter((material) => material.thickness_mm === panelThicknessFilter.value)
  }
  const sorted = [...list]
  if (panelSort.value === 'manufacturer') {
    sorted.sort((left, right) =>
      `${left.manufacturer_name} ${left.name}`.localeCompare(
        `${right.manufacturer_name} ${right.name}`,
      ),
    )
  } else if (panelSort.value === 'thickness') {
    sorted.sort((left, right) => Number(left.thickness_mm) - Number(right.thickness_mm))
  }
  return sorted
})
const panelChoices = computed<ChoiceOption[]>(() =>
  panelOptions.value.map((material) => ({
    value: material.id,
    label: materialLabel(material),
    meta: `${material.color}${material.decor_code ? ` · ${material.decor_code}` : ''}${
      material.branch_carried ? '' : " · filialda yo'q"
    }`,
  })),
)
const hasPersistableParts = computed(() => parts.value.every((part) => !partIsInvalid(part)))
const lastOptimizedSignature = ref<string | null>(null)
function partsSignature(list: CuttingPart[] = parts.value) {
  return JSON.stringify(
    list.map((part) => [
      part.material_id,
      part.material_source,
      part.length_mm,
      part.width_mm,
      part.quantity,
      part.edge_top,
      part.edge_bottom,
      part.edge_left,
      part.edge_right,
    ]),
  )
}
const optimizedUnchanged = computed(
  () => lastOptimizedSignature.value !== null && partsSignature() === lastOptimizedSignature.value,
)
// docs/ref/features/cutting.md — at most MAX_PARTS per optimisation (CB-102).
const canOptimize = computed(
  () =>
    !isReadOnly.value &&
    parts.value.length > 0 &&
    hasPersistableParts.value &&
    totalQuantity.value <= MAX_PARTS &&
    !optimizedUnchanged.value,
)
const optimizeDisabledHint = computed(() => {
  if (parts.value.length === 0) return "Avval qism qo'shing"
  if (!hasPersistableParts.value) return "Qatorlardagi xatolarni to'g'rilang"
  if (totalQuantity.value > MAX_PARTS) return `${MAX_PARTS} donadan oshib ketdi`
  if (optimizedUnchanged.value) return "Natija allaqachon hisoblangan — qismni o'zgartiring"
  return ''
})
// A single roll-up of everything blocking the optimiser, shown under the table.
const optimizeBlockers = computed(() => {
  if (parts.value.length === 0) return []
  const blockers: string[] = []
  if (!hasPersistableParts.value) blockers.push("Qatorlardagi xatolarni to'g'rilang")
  if (totalQuantity.value > MAX_PARTS)
    blockers.push(`Jami ${totalQuantity.value} dona — bir martada ${MAX_PARTS} donadan oshmasin`)
  return blockers
})
const notCarriedRows = computed(() => parts.value.filter((part) => rowNotCarried(part).length > 0))
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
const resultWaste = computed(() => formatPercent(chosenResult.value?.waste_percentage))
const totalQuantity = computed(() =>
  parts.value.reduce((sum, part) => sum + Math.max(0, Number(part.quantity) || 0), 0),
)
const placedCount = computed(() =>
  chosenResult.value
    ? chosenResult.value.panels.reduce((sum, panel) => sum + panel.placements.length, 0)
    : 0,
)
const requestedCount = computed(() =>
  chosenResult.value
    ? chosenResult.value.parts_snapshot.reduce((sum, part) => sum + part.quantity, 0)
    : 0,
)
const allPlaced = computed(() => placedCount.value >= requestedCount.value)
const edgeByMaterial = computed(() => {
  const result = chosenResult.value
  if (!result) return []
  const ids = new Set([
    ...Object.keys(result.edge_consumed_shop_by_material),
    ...Object.keys(result.edge_consumed_own_by_material),
  ])
  return [...ids]
    .map((id) => {
      const shop = result.edge_consumed_shop_by_material[id] ?? 0
      const own = result.edge_consumed_own_by_material[id] ?? 0
      const snapshot = result.material_snapshots[id]
      const name = typeof snapshot?.name === 'string' ? snapshot.name : id.slice(0, 8)
      return { id, name, total: shop + own }
    })
    .filter((row) => row.total > 0)
    .sort((left, right) => right.total - left.total)
})
const showRecovery = computed(
  () => !isReadOnly.value && !recoveryDismissed.value && notCarriedRows.value.length > 0,
)
const edgePickerOpen = computed(() => edgePickerPart.value !== null)
const edgeThicknessOptions = computed<ChoiceOption[]>(() => {
  const values = [...new Set(cutting.edgeOptions.map((material) => material.thickness_mm))]
    .filter(Boolean)
    .sort((left, right) => Number(left) - Number(right))
  return [
    { value: 'all', label: 'Hamma qalinlik', meta: 'Barcha kromlar' },
    ...values.map((value) => ({ value, label: `${value} mm`, meta: 'Qalinlik' })),
  ]
})
const edgePickerMaterials = computed(() => {
  const part = edgePickerPart.value
  if (!part) return []
  const query = edgePickerSearch.value.trim().toLowerCase()
  return rankedEdgesForPart(part)
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
const edgePickerBranchNote = computed(() => {
  if (!draft.value?.preferred_branch_id) return null
  const missing = new Map<string, string>()
  for (const side of edgeFields) {
    const edge = edgePickerState.value[side]
    if (!edge || edge.source === 'own') continue
    const material = edgeById(edge.material_id)
    if (material && !material.branch_carried) {
      missing.set(material.id, edgeShortLabel(material, true))
    }
  }
  if (!missing.size) return null
  const branch = preferredBranch.value?.branch_name ?? 'tanlangan filial'
  return `${branch} filialida ${[...missing.values()].join(' · ')} hozir mavjud emas. Manbani "O'zim olib kelaman" qiling yoki boshqa krom tanlang.`
})

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

function blankEdgeState(): Record<EdgeField, CuttingEdgeBand | null> {
  return {
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
  return partNotCarried(part, draft.value?.preferred_branch_id, materialById, edgeById)
}

function partSizeError(part: CuttingPart): string | null {
  const panel = materialById(part.material_id)
  if (!panel || panel.panel_length_mm == null || panel.panel_width_mm == null) return null
  const code = partFitError(part.length_mm, part.width_mm, panel)
  if (!code) return null
  const usableLength = panel.panel_length_mm - 2 * EDGE_TRIM_MM
  const usableWidth = panel.panel_width_mm - 2 * EDGE_TRIM_MM
  if (code === 'impossible_grain')
    return `Tola yo'nalishi qat'iy — qism ${usableLength}×${usableWidth} mm ichiga sig'ishi kerak (aylantirib bo'lmaydi).`
  return `Qism panelga sig'maydi — maksimal ${usableLength}×${usableWidth} mm (panel − 2×${EDGE_TRIM_MM} mm chetki qirqim).`
}

// A chosen panel id that no longer resolves in the loaded catalog — e.g. the
// material was deactivated while the draft sat (CB-89). Only meaningful once the
// catalog has loaded, so an empty list (mid-load) never false-flags.
function rowMaterialMissing(part: CuttingPart): boolean {
  if (cutting.panelOptions.length === 0) return false
  return !!part.material_id && !materialById(part.material_id)
}

function partIsInvalid(part: CuttingPart) {
  return (
    !part.material_id ||
    rowMaterialMissing(part) ||
    part.length_mm < MIN_PART_MM ||
    part.width_mm < MIN_PART_MM ||
    part.quantity < 1 ||
    !Number.isFinite(Number(part.length_mm)) ||
    !Number.isFinite(Number(part.width_mm)) ||
    !Number.isFinite(Number(part.quantity)) ||
    partSizeError(part) !== null
  )
}

function optimizeRowMessage(code: string | undefined): string {
  if (code === 'part_too_large')
    return "Bu qism panelga sig'maydi — o'lchamini kichraytiring yoki boshqa panel tanlang."
  if (code === 'impossible_grain')
    return "Tola yo'nalishi bu qismni joylashtirishga to'sqinlik qiladi."
  if (code === 'material_not_found')
    return "Bu qatordagi material endi katalogda yo'q — boshqasini tanlang."
  return "Bu qatorni optimallashtirib bo'lmadi."
}

function optimizeRowFromError(errorValue: unknown) {
  if (
    !(errorValue instanceof ApiError) ||
    typeof errorValue.body !== 'object' ||
    !errorValue.body
  ) {
    return null
  }
  const body = errorValue.body as {
    code?: string
    details?: { part_ref?: unknown; row_index?: unknown }
  }
  const details = body.details
  if (!details) return null
  const partRef = typeof details.part_ref === 'string' ? details.part_ref : null
  const rowIndex = typeof details.row_index === 'number' ? details.row_index : null
  if (partRef === null && rowIndex === null) return null
  return { partRef, rowIndex, message: optimizeRowMessage(body.code) }
}

function rowOptimizeError(part: CuttingPart, index: number): string | null {
  const error = optimizeRowError.value
  if (!error) return null
  if (error.partRef !== null) return part.part_ref === error.partRef ? error.message : null
  // Backend row_index is 1-indexed (enumerate(parts, start=1)); the array is 0-indexed.
  return error.rowIndex === index + 1 ? error.message : null
}

function rowHasError(part: CuttingPart, index: number): boolean {
  return partIsInvalid(part) || rowOptimizeError(part, index) !== null
}

function edgeCount(part: CuttingPart) {
  return edgeFields.filter((side) => part[side]).length
}

function edgeSummary(part: CuttingPart) {
  const count = edgeCount(part)
  if (count === 0) return "Krom yo'q"
  const sides = count === 4 ? '4 tomon' : `${count} tomon`
  // Name the tape in the visible cell, not just the hover title / 6.5px SVG text
  // (CB-91/CB-69): one label when every banded side shares a material, else
  // "Aralash" so a mixed row is obvious without opening the picker.
  const materialIds = [
    ...new Set(edgeFields.filter((side) => part[side]).map((side) => part[side]?.material_id)),
  ]
  if (materialIds.length === 1) {
    const material = edgeById(materialIds[0])
    if (material) return `${edgeShortLabel(material, true)} · ${sides}`
  } else if (materialIds.length > 1) {
    return `Aralash · ${sides}`
  }
  return sides
}

function edgeSourceSummary(part: CuttingPart) {
  const active = edgeFields.filter((side) => part[side])
  if (active.length === 0) return 'tomonlar tanlanmagan'
  const own = active.filter((side) => part[side]?.source === 'own').length
  if (own === active.length) return "o'zim olib kelaman"
  if (own > 0) return 'aralash manba'
  return 'ustaxonadan'
}

function edgeSearchText(material: ClientCatalogMaterialOption) {
  return `${material.manufacturer_name} ${material.name} ${material.color} ${material.decor_code ?? ''} ${material.thickness_mm}`.toLowerCase()
}

function rankedEdgesForPart(part: CuttingPart) {
  return rankedEdges(materialById(part.material_id), cutting.edgeOptions)
}

function recommendedEdgeForPart(part: CuttingPart) {
  return recommendedEdge(
    materialById(part.material_id),
    cutting.edgeOptions,
    edgePickerSelectedMaterialId.value,
    preferredEdgeId(part),
  )
}

function edgeShortLabel(
  material: ClientCatalogMaterialOption | null | undefined,
  withThickness = false,
) {
  if (!material) return '-'
  const decor = material.decor_code ? `${material.decor_code} ` : ''
  const thickness = withThickness ? ` · ${material.thickness_mm} mm` : ''
  return `${material.manufacturer_name} · ${decor}${material.color}${thickness}`
}

function edgeTinyLabel(material: ClientCatalogMaterialOption | null | undefined) {
  if (!material) return '-'
  return `${material.manufacturer_name.split(' ')[0] ?? material.manufacturer_name} ${material.thickness_mm}`
}

function edgeCellTitle(part: CuttingPart) {
  const lines = edgeFields.map((side) => {
    const edge = part[side]
    const material = edgeById(edge?.material_id)
    const source = edge?.source === 'own' ? " (o'zim)" : ''
    return `${sideLabels[side]}: ${edge ? `${edgeShortLabel(material, true)}${source}` : '-'}`
  })
  return `Krom yopishtirish - tahrirlash uchun bosing\n${lines.join(' · ')}`
}

function edgeStrokeWidth(edge: CuttingEdgeBand | null) {
  const material = edgeById(edge?.material_id)
  const thickness = Number(material?.thickness_mm ?? 0.4)
  return thickness >= 2 ? 3 : 1.3
}

function edgeCellLabel(part: CuttingPart, side: EdgeField) {
  const material = edgeById(part[side]?.material_id)
  return material?.thickness_mm ?? ''
}

function pickerSideLabel(side: EdgeField) {
  return edgeTinyLabel(edgeById(edgePickerState.value[side]?.material_id))
}

function swatchStyle(part: CuttingPart) {
  const material = materialById(part.material_id)
  return { background: colorForMaterial(material?.color ?? material?.name ?? part.material_id) }
}

function colorForMaterial(value: string | null | undefined) {
  const text = (value ?? '').toLowerCase()
  if (text.includes('white') || text.includes('oq')) return '#f7f4ec'
  if (text.includes('black') || text.includes('qora')) return '#2a2d33'
  if (text.includes('gray') || text.includes('grey') || text.includes('kul')) return '#a7adb5'
  if (text.includes('walnut') || text.includes('yong')) return '#805434'
  if (text.includes('oak') || text.includes('dub')) return '#c9aa73'
  let hash = 0
  for (const char of text || 'material') hash = (hash * 31 + char.charCodeAt(0)) % 360
  return `hsl(${hash} 34% 72%)`
}

function resultPanelCount(result: CuttingResult) {
  return Object.values(result.panels_used_by_material).reduce((sum, count) => sum + count, 0)
}

function saveLabel() {
  // Self-describing for SR users (CB-53): the autosave chip is a role=status live
  // region, so the announced text must stand on its own, not a bare "Saqlangan".
  if (saveState.value === 'saved') return 'Chizma saqlandi'
  if (saveState.value === 'saving') return 'Chizma saqlanmoqda'
  if (saveState.value === 'editing') return 'Tahrirlanmoqda'
  return "Saqlash xatosi — qayta urinib ko'ring"
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

function requestClearParts() {
  clearPartsConfirmOpen.value = true
}

function clearParts() {
  parts.value = []
  preferredEdgeByPart.value = {}
  clearPartsConfirmOpen.value = false
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

function cloneEdgeStateFromPart(part: CuttingPart) {
  return {
    edge_top: part.edge_top ? { ...part.edge_top } : null,
    edge_bottom: part.edge_bottom ? { ...part.edge_bottom } : null,
    edge_left: part.edge_left ? { ...part.edge_left } : null,
    edge_right: part.edge_right ? { ...part.edge_right } : null,
  }
}

function bandedEdgeFields(state: Record<EdgeField, CuttingEdgeBand | null>) {
  return edgeFields.filter((side) => state[side])
}

function openEdgePicker(part: CuttingPart, event?: Event) {
  edgePickerPart.value = part
  edgePickerState.value = cloneEdgeStateFromPart(part)
  const active = bandedEdgeFields(edgePickerState.value)
  edgePickerSource.value =
    active.length > 0 && active.every((side) => edgePickerState.value[side]?.source === 'own')
      ? 'own'
      : commonEdgeSource(part)
  edgePickerSearch.value = ''
  edgePickerThickness.value = 'all'
  edgeReturnFocus = event?.currentTarget instanceof HTMLElement ? event.currentTarget : null
  void nextTick(() => edgeDialogRef.value?.focus())
}

function closeEdgePicker(returnFocus = true) {
  edgePickerPart.value = null
  edgePickerState.value = blankEdgeState()
  edgePickerSearch.value = ''
  edgePickerThickness.value = 'all'
  if (returnFocus) edgeReturnFocus?.focus()
  edgeReturnFocus = null
}

function applyEdgePicker() {
  const part = edgePickerPart.value
  if (!part) {
    closeEdgePicker(false)
    return
  }
  part.edge_top = edgePickerState.value.edge_top ? { ...edgePickerState.value.edge_top } : null
  part.edge_bottom = edgePickerState.value.edge_bottom
    ? { ...edgePickerState.value.edge_bottom }
    : null
  part.edge_left = edgePickerState.value.edge_left ? { ...edgePickerState.value.edge_left } : null
  part.edge_right = edgePickerState.value.edge_right
    ? { ...edgePickerState.value.edge_right }
    : null
  const materialId = firstEdgeId(part)
  rememberEdgeMaterial(part, materialId)
  closeEdgePicker()
}

function applyEdgePattern(key: string) {
  const part = edgePickerPart.value
  if (!part) return
  const pattern = edgePatterns.find((item) => item.key === key)
  if (!pattern) return
  if (pattern.sides.length === 0) {
    edgePickerState.value = blankEdgeState()
    return
  }
  const fallback = recommendedEdgeForPart(part)
  if (!fallback) return
  const next = blankEdgeState()
  for (const side of pattern.sides) {
    next[side] = { material_id: fallback.id, source: edgePickerSource.value }
  }
  edgePickerState.value = next
}

function togglePickerSide(side: EdgeField) {
  const part = edgePickerPart.value
  if (!part) return
  const next = { ...edgePickerState.value }
  if (next[side]) {
    next[side] = null
  } else {
    const fallback = recommendedEdgeForPart(part)
    if (!fallback) return
    next[side] = { material_id: fallback.id, source: edgePickerSource.value }
  }
  edgePickerState.value = next
}

function setPickerSource(source: MaterialSource) {
  edgePickerSource.value = source
  const next = { ...edgePickerState.value }
  for (const side of edgeFields) {
    if (next[side]) next[side] = { ...next[side], source }
  }
  edgePickerState.value = next
}

function selectPickerMaterial(materialId: string) {
  const active = edgePickerActiveSides.value
  const targetSides = active.length ? active : edgeFields
  const next = { ...edgePickerState.value }
  for (const side of targetSides) {
    next[side] = { material_id: materialId, source: edgePickerSource.value }
  }
  edgePickerState.value = next
}

const EDGE_FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

// Trap Tab/Shift-Tab inside the edge modal so keyboard/SR users can't reach the
// obscured part rows behind the scrim (CB-06; mirrors ConfirmDialog).
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
  if (!edgePickerOpen.value) return
  if (event.key === 'Escape') {
    closeEdgePicker()
    return
  }
  if (event.key === 'Tab') trapEdgeFocus(event)
}

function bringOwn(part: CuttingPart) {
  // Flip only the not-carried panel/sides to "own" — sides whose tape IS carried
  // must stay shop-sourced so we don't silently change what the client is billed.
  const issues = rowNotCarried(part)
  if (issues.includes('panel')) part.material_source = 'own'
  for (const side of edgeFields) {
    if (issues.includes(side) && part[side]) {
      part[side] = { ...part[side], source: 'own' } as CuttingEdgeBand
    }
  }
}

// Debounced autosave (700ms). The timing core lives in the framework-agnostic
// `autosaveController` (unit-tested in autosaveController.spec.ts — CB-108); we
// only mirror its status onto `saveState`/`saveError` and feed it the gate:
// don't persist incomplete/out-of-bounds rows (they surface their own inline
// validation) or a read-only bound draft.
const autosave = createAutosaveController({
  delayMs: AUTOSAVE_DEBOUNCE_MS,
  persist: () => cutting.updateDraft(draftId.value, { parts_snapshot: parts.value }).then(),
  canPersist: () => hasPersistableParts.value && !isReadOnly.value,
  onStatus: (status) => {
    saveState.value = status
    saveError.value = status === 'error' ? "Chizmani saqlab bo'lmadi. Qayta urinib ko'ring." : null
  },
})

function scheduleSave() {
  if (hydrating || isReadOnly.value) return
  // A row-attributed optimiser error is stale once the parts change.
  optimizeRowError.value = null
  autosave.schedule()
}

async function setPreferredBranch(branchId: string | null) {
  // Surface a failure instead of an unhandled rejection that leaves the local
  // pick disagreeing with the server (CB-57).
  try {
    await cutting.updateDraft(draftId.value, { preferred_branch_id: branchId })
  } catch {
    toast.danger("Afzal filialni saqlab bo'lmadi. Qayta urinib ko'ring.")
    return
  }
  branchPickerOpen.value = false
  selectedBranchId.value = branchId
  recoveryDismissed.value = false
  await loadMaterials()
}

// Close the picker without applying — drop the pending pick back to the saved
// preference so a re-open highlights what's actually active, not an abandoned choice.
function closeBranchPicker() {
  branchPickerOpen.value = false
  selectedBranchId.value = draft.value?.preferred_branch_id ?? null
}

async function optimize() {
  if (cutting.optimizing || !canOptimize.value) return
  optimizeError.value = null
  optimizeRowError.value = null
  // Flush any pending debounced edit so we optimize the latest parts, not a
  // stale server snapshot.
  await autosave.flush()
  if (saveState.value === 'error') return
  let failedRowRef: string | null = null
  try {
    const updated = await cutting.optimizeDraft(draftId.value)
    activeResultId.value = updated.chosen_result_id
    activePanelId.value = updated.results[0]?.panels[0]?.id ?? null
    lastOptimizedSignature.value = partsSignature()
  } catch (errorValue) {
    optimizeError.value = clientErrorLabel(
      cutting.error,
      "Optimallashtirishda xatolik. Qayta urinib ko'ring.",
    )
    optimizeRowError.value = optimizeRowFromError(errorValue)
    if (optimizeRowError.value?.partRef) failedRowRef = optimizeRowError.value.partRef
    else if (optimizeRowError.value?.rowIndex != null) {
      // row_index is 1-indexed (backend enumerate start=1) → 0-indexed array.
      failedRowRef = parts.value[optimizeRowError.value.rowIndex - 1]?.part_ref ?? null
    }
  }
  await nextTick()
  // On a row-attributed failure, scroll the offending row into view; otherwise
  // the results section (CB-89).
  const target = failedRowRef
    ? document.getElementById(`part-row-${failedRowRef}`)
    : document.getElementById('cutting-results')
  target?.scrollIntoView({ behavior: 'smooth', block: failedRowRef ? 'center' : 'start' })
}

async function choose(result: CuttingResult) {
  // chooseResult can throw (stale/invalidated result, network) — surface it
  // rather than silently leaving the chosen result out of sync (CB-57).
  try {
    await cutting.chooseResult(draftId.value, result.id)
  } catch {
    toast.danger("Natijani tanlab bo'lmadi. Qayta urinib ko'ring.")
    return
  }
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

function snapshotDims(snapshot: Record<string, unknown> | undefined): string {
  const length = Number(snapshot?.panel_length_mm)
  const width = Number(snapshot?.panel_width_mm)
  return Number.isFinite(length) && Number.isFinite(width) && length > 0 && width > 0
    ? `${length}×${width}`
    : ''
}
// Group the result's panels by material so multi-material jobs read as
// "Material · LxW · N panel" tabs instead of an undifferentiated chip row (CB-87).
const panelGroups = computed(() => {
  const result = chosenResult.value
  if (!result) return []
  const byMaterial = new Map<string, CuttingPanel[]>()
  for (const panel of result.panels) {
    byMaterial.set(panel.material_id, [...(byMaterial.get(panel.material_id) ?? []), panel])
  }
  return [...byMaterial.entries()].map(([materialId, panels]) => {
    const snapshot = result.material_snapshots[materialId]
    return {
      materialId,
      name: String(snapshot?.name ?? 'Panel'),
      dims: snapshotDims(snapshot),
      count: panels.length,
      panels,
    }
  })
})

function selectPlacement(placement: CuttingPlacement) {
  activePlacementId.value = placement.id
}

watch(
  () => cutting.currentDraft,
  (value) => {
    if (!value) return
    // Only mirror the server snapshot into the editable `parts` when a
    // genuinely different draft loaded. Our own saves/optimizes return the
    // same draft id; re-hydrating then would discard a keystroke made during
    // the round-trip (CB-15). Result-derived state below always tracks the
    // latest payload so fresh optimize results show immediately.
    if (value.id !== hydratedDraftId) {
      hydrating = true
      parts.value = value.parts_snapshot.map((part) => ({ ...part }))
      hydratedDraftId = value.id
      autosave.markSaved()
      nextTick(() => {
        hydrating = false
      })
    }
    activeResultId.value = value.chosen_result_id ?? value.results[0]?.id ?? null
    const optimizedResult = value.results.find((result) => result.id === activeResultId.value)
    lastOptimizedSignature.value = optimizedResult
      ? partsSignature(optimizedResult.parts_snapshot)
      : null
    activePanelId.value =
      value.results.find((result) => result.id === activeResultId.value)?.panels[0]?.id ??
      value.results[0]?.panels[0]?.id ??
      null
    // Don't clobber a pending pick while the picker is open (e.g. a debounced
    // autosave round-trips mid-selection); mirror the saved preference otherwise.
    if (!branchPickerOpen.value) selectedBranchId.value = value.preferred_branch_id
  },
  { immediate: true },
)

watch(parts, scheduleSave, { deep: true })

onMounted(async () => {
  document.addEventListener('keydown', onDocumentKeydown)
  await cutting.loadDraft(draftId.value)
  await cutting.loadBranchOptions()
  selectedBranchId.value = draft.value?.preferred_branch_id ?? null
  await loadMaterials()
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onDocumentKeydown)
  // Flush a debounced edit before teardown so navigating away within the 700ms
  // window doesn't silently drop it (CB-15). The store action outlives the
  // component, so the PATCH still completes.
  void autosave.flush()
  if (edgePickerOpen.value) unlockBodyScroll()
})

watch(edgePickerOpen, (open) => {
  if (open) lockBodyScroll()
  else unlockBodyScroll()
})

const edgeFields = ['edge_top', 'edge_bottom', 'edge_left', 'edge_right'] as const
type EdgeField = (typeof edgeFields)[number]
const sideLabels: Record<EdgeField, string> = {
  edge_top: 'Yuqori',
  edge_bottom: 'Pastki',
  edge_left: 'Chap',
  edge_right: "O'ng",
}
const edgePatterns: Array<{
  key: string
  label: string
  hint: string
  sides: EdgeField[]
}> = [
  { key: 'none', label: 'Hech qaysi', hint: 'Krom olib tashlanadi', sides: [] },
  { key: 'all', label: 'Hamma tomon', hint: "Ko'p ishlatiladi", sides: [...edgeFields] },
  {
    key: 'tb',
    label: 'Yuqori + pastki',
    hint: 'Uzun tomonlar',
    sides: ['edge_top', 'edge_bottom'],
  },
  { key: 'lr', label: "Chap + o'ng", hint: 'Yon tomonlar', sides: ['edge_left', 'edge_right'] },
]
</script>

<template>
  <section>
    <RouterLink :to="rolePath('/c/cutting/drafts')" class="client-back">
      <span aria-hidden="true">←</span>
      Saqlangan chizmalar
    </RouterLink>

    <div class="client-page-head">
      <div>
        <h1>Chizma</h1>
        <p class="sub">
          Qismlarni kiriting, ustaxona katalogi bo'yicha tekshiring va kesish natijasini oling.
        </p>
      </div>
      <div v-if="!isReadOnly" class="flex flex-wrap items-center gap-2">
        <span
          class="mp-chip"
          :class="{
            'bg-success-soft text-success': saveState === 'saved',
            'bg-info-soft text-info': saveState === 'saving' || saveState === 'editing',
            'bg-danger-soft text-danger': saveState === 'error',
          }"
          role="status"
          aria-live="polite"
        >
          <span class="mp-dot" aria-hidden="true"></span>
          {{ saveLabel() }}
        </span>
        <button
          type="button"
          class="mp-button mp-button-outline text-danger"
          :disabled="parts.length === 0"
          @click="requestClearParts"
        >
          Ro'yxatni tozalash
        </button>
      </div>
    </div>

    <section v-if="cutting.loading" class="grid gap-3" aria-live="polite">
      <div class="client-skeleton h-28"></div>
      <div class="client-skeleton h-64"></div>
    </section>

    <section v-else-if="cutting.error" class="client-error">
      <div class="client-error-icon">!</div>
      <h3>Chizma yuklanmadi</h3>
      <p>Chizmani ochish uchun sahifani qayta yuklang yoki saqlangan chizmalarga qayting.</p>
      <p class="client-trace">trace {{ cutting.traceId ?? 'unavailable' }}</p>
    </section>

    <template v-else-if="draft">
      <RouterLink
        v-if="isReadOnly"
        :to="rolePath(`/c/orders/${boundOrderId}`)"
        class="client-banner info hover:border-accent"
      >
        <span class="grid size-6 shrink-0 place-items-center text-accent" aria-hidden="true">
          <Icon name="lock" />
        </span>
        <span class="min-w-0 flex-1">
          Bu chizma tasdiqlangan buyurtmaga bog'langan, shuning uchun faqat o'qish uchun.
          <span class="font-bold text-accent">Buyurtmani ochish →</span>
        </span>
      </RouterLink>

      <fieldset :disabled="isReadOnly" class="contents">
        <section
          class="mb-4 flex flex-wrap items-center gap-3 rounded-md border border-hairline border-l-4 border-l-accent bg-sunk px-4 py-3 text-sm text-ink-soft"
        >
          <span
            class="grid size-6 place-items-center rounded bg-elevated font-mono font-black text-accent"
            aria-hidden="true"
          >
            i
          </span>
          <div class="min-w-0 flex-1">
            <span>Katalog filtri: </span>
            <b class="text-ink">
              {{
                preferredBranch
                  ? `${preferredBranch.branch_name} · ${preferredBranch.workshop_name}`
                  : 'barcha ustaxonalar'
              }}
            </b>
          </div>
          <button
            type="button"
            class="mp-button mp-button-outline"
            @click="branchPickerOpen = true"
          >
            {{ preferredBranch ? "O'zgartirish" : 'Ustaxona tanlash' }}
          </button>
          <button
            v-if="preferredBranch"
            type="button"
            class="mp-button mp-button-outline"
            @click="setPreferredBranch(null)"
          >
            Tozalash
          </button>
        </section>

        <section v-if="branchPickerOpen" class="client-card mb-4 grid gap-3 p-4">
          <CuttingBranchPicker v-model="selectedBranchId" :options="cutting.branchOptions" />
          <div class="flex flex-wrap justify-end gap-2">
            <button type="button" class="mp-button mp-button-outline" @click="closeBranchPicker">
              Bekor qilish
            </button>
            <button
              type="button"
              class="mp-button mp-button-primary"
              :disabled="!selectedBranchId"
              @click="setPreferredBranch(selectedBranchId)"
            >
              Qo'llash
            </button>
          </div>
        </section>

        <section v-if="showRecovery" class="client-banner warn">
          <span class="grid size-6 place-items-center rounded bg-warning text-white">!</span>
          <span class="min-w-0 flex-1">
            {{ notCarriedRows.length }} qator tanlangan ustaxonada mavjud bo'lmagan materialdan
            foydalanadi. Shu qatorlarni o'zim olib kelaman deb belgilang yoki pre-filterni tozalang.
            <span class="mt-2 flex flex-wrap gap-2">
              <button
                type="button"
                class="mp-button mp-button-outline"
                @click="setPreferredBranch(null)"
              >
                Pre-filterni tozalash
              </button>
              <button
                type="button"
                class="mp-button mp-button-outline"
                @click="recoveryDismissed = true"
              >
                Yopish
              </button>
            </span>
          </span>
        </section>

        <section class="client-card">
          <div class="client-card-h">
            <div>
              <h2>Qismlar ro'yxati</h2>
              <p class="mt-1 text-sm text-ink-muted">
                {{ parts.length }} qator · {{ totalQuantity }} dona
              </p>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <div class="inline-flex rounded-lg border border-hairline bg-sunk p-1">
                <button
                  type="button"
                  class="rounded-md bg-elevated px-3 py-2 text-sm font-bold text-ink shadow-sm"
                >
                  Qo'lda
                </button>
                <button
                  type="button"
                  class="rounded-md px-3 py-2 text-sm font-bold text-ink-muted"
                  disabled
                >
                  Fayldan
                  <span class="ml-1 rounded-full bg-hairline px-2 py-0.5 text-[10px]"
                    >tez kunda</span
                  >
                </button>
              </div>
              <button type="button" class="mp-button mp-button-outline" @click="addRow">
                Qism qo'shish
              </button>
            </div>
          </div>

          <div
            v-if="parts.length > 0"
            class="border-b border-hairline px-4 py-3"
            aria-label="Panel filtri"
          >
            <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <MultiSelectFilter
                v-model="panelManufacturerFilter"
                label="Ishlab chiqaruvchi"
                :options="panelManufacturerChoices"
              />
              <FormSelect v-model="panelTypeFilter" label="Tur" :options="panelTypeChoices" />
              <FormSelect
                v-model="panelThicknessFilter"
                label="Qalinlik"
                :options="panelThicknessChoices"
              />
              <FormSelect v-model="panelSort" label="Saralash" :options="panelSortChoices" />
            </div>
            <div
              v-if="panelFiltersActive"
              class="mt-2 flex flex-wrap items-center justify-between gap-2 text-sm"
            >
              <span class="text-ink-muted">{{ panelOptions.length }} ta panel ko'rsatilmoqda</span>
              <button type="button" class="font-bold text-accent" @click="clearPanelFilters">
                Filtrlarni tozalash
              </button>
            </div>
          </div>

          <div v-if="parts.length === 0" class="client-card-b">
            <div class="client-empty">
              <div class="client-empty-icon"><Icon name="plus" /></div>
              <h3>Bu chizmada qism yo'q</h3>
              <p>Kesish ro'yxatini boshlash uchun birinchi qatorni qo'shing.</p>
              <button type="button" class="mp-button mp-button-primary mt-4" @click="addRow">
                Qism qo'shish
              </button>
            </div>
          </div>

          <div v-else class="grid gap-3 p-4">
            <article
              v-for="(part, index) in parts"
              :id="`part-row-${part.part_ref}`"
              :key="part.part_ref"
              class="rounded-lg border bg-elevated p-3 transition hover:border-ink-soft"
              :class="rowHasError(part, index) ? 'border-danger-soft' : 'border-hairline'"
            >
              <div
                class="grid gap-3 lg:grid-cols-[34px_minmax(240px,1.6fr)_90px_90px_76px_minmax(280px,1fr)_96px] lg:items-start"
              >
                <div class="font-mono text-xs font-extrabold text-ink-muted">#{{ index + 1 }}</div>

                <div class="min-w-0">
                  <SearchCombobox
                    label="Panel materiali"
                    :model-value="part.material_id"
                    :options="panelChoices"
                    placeholder="Panel tanlang"
                    :error="!part.material_id ? 'Material tanlang' : null"
                    @update:model-value="setPanel(part, $event)"
                  />
                  <div class="mt-2 flex flex-wrap items-center gap-2">
                    <span
                      class="size-5 rounded border border-hairline"
                      :style="swatchStyle(part)"
                    ></span>
                    <span
                      v-if="materialById(part.material_id)?.grain_direction"
                      class="mp-chip bg-info-soft text-info"
                      title="Tola yo'nalishi bor — bu qism burilmaydi"
                      aria-label="Tola yo'nalishi bor — bu qism burilmaydi"
                    >
                      <span aria-hidden="true">↕</span> Tola
                    </span>
                    <button
                      type="button"
                      class="mp-chip"
                      :class="part.material_source === 'shop' ? 'bg-accent-soft text-accent' : ''"
                      @click="setPanelSource(part, 'shop')"
                    >
                      Ustaxona
                    </button>
                    <button
                      type="button"
                      class="mp-chip"
                      :class="part.material_source === 'own' ? 'bg-accent-soft text-accent' : ''"
                      @click="setPanelSource(part, 'own')"
                    >
                      O'zim olib kelaman
                    </button>
                  </div>
                </div>

                <!-- Sub-lg: the three dimensions share one row; lg:contents
                     dissolves this wrapper so each input is a column of the
                     parent grid again (desktop layout unchanged) — CB-60. -->
                <div class="grid grid-cols-3 gap-2 lg:contents">
                  <label class="grid gap-1 text-xs font-bold text-ink-muted">
                    Uzunlik
                    <input
                      v-model.number="part.length_mm"
                      type="number"
                      :min="MIN_PART_MM"
                      inputmode="numeric"
                      enterkeyhint="next"
                      class="mp-input font-mono"
                      :class="
                        part.length_mm < MIN_PART_MM || partSizeError(part) ? 'border-danger' : ''
                      "
                      aria-label="Uzunlik millimetr"
                    />
                  </label>

                  <label class="grid gap-1 text-xs font-bold text-ink-muted">
                    Eni
                    <input
                      v-model.number="part.width_mm"
                      type="number"
                      :min="MIN_PART_MM"
                      inputmode="numeric"
                      enterkeyhint="next"
                      class="mp-input font-mono"
                      :class="
                        part.width_mm < MIN_PART_MM || partSizeError(part) ? 'border-danger' : ''
                      "
                      aria-label="Eni millimetr"
                    />
                  </label>

                  <label class="grid gap-1 text-xs font-bold text-ink-muted">
                    Soni
                    <input
                      v-model.number="part.quantity"
                      type="number"
                      min="1"
                      inputmode="numeric"
                      enterkeyhint="done"
                      class="mp-input font-mono"
                      :class="part.quantity < 1 ? 'border-danger' : ''"
                      aria-label="Soni"
                    />
                  </label>
                </div>

                <div class="min-w-0">
                  <span class="mb-1 block text-sm font-bold text-ink">Krom</span>
                  <button
                    type="button"
                    class="client-edges-btn"
                    :title="edgeCellTitle(part)"
                    :aria-label="`Qism #${index + 1} kromini tahrirlash`"
                    @click="openEdgePicker(part, $event)"
                  >
                    <svg viewBox="0 0 76 48" class="client-edge-svg" aria-hidden="true">
                      <rect class="frame" x="14" y="13" width="48" height="22" />
                      <line
                        v-if="part.edge_top"
                        class="side"
                        x1="14"
                        y1="13"
                        x2="62"
                        y2="13"
                        :stroke-width="edgeStrokeWidth(part.edge_top)"
                        :class="{ own: part.edge_top.source === 'own' }"
                      />
                      <line
                        v-if="part.edge_bottom"
                        class="side"
                        x1="14"
                        y1="35"
                        x2="62"
                        y2="35"
                        :stroke-width="edgeStrokeWidth(part.edge_bottom)"
                        :class="{ own: part.edge_bottom.source === 'own' }"
                      />
                      <line
                        v-if="part.edge_left"
                        class="side"
                        x1="14"
                        y1="13"
                        x2="14"
                        y2="35"
                        :stroke-width="edgeStrokeWidth(part.edge_left)"
                        :class="{ own: part.edge_left.source === 'own' }"
                      />
                      <line
                        v-if="part.edge_right"
                        class="side"
                        x1="62"
                        y1="13"
                        x2="62"
                        y2="35"
                        :stroke-width="edgeStrokeWidth(part.edge_right)"
                        :class="{ own: part.edge_right.source === 'own' }"
                      />
                      <text v-if="part.edge_top" class="lbl" x="38" y="7" text-anchor="middle">
                        {{ edgeCellLabel(part, 'edge_top') }}
                      </text>
                      <text v-if="part.edge_bottom" class="lbl" x="38" y="45" text-anchor="middle">
                        {{ edgeCellLabel(part, 'edge_bottom') }}
                      </text>
                      <text v-if="part.edge_left" class="lbl" x="6" y="24" text-anchor="middle">
                        {{ edgeCellLabel(part, 'edge_left') }}
                      </text>
                      <text v-if="part.edge_right" class="lbl" x="70" y="24" text-anchor="middle">
                        {{ edgeCellLabel(part, 'edge_right') }}
                      </text>
                    </svg>
                    <span class="client-edge-summary">
                      <b>{{ edgeSummary(part) }}</b>
                      <small>{{ edgeSourceSummary(part) }}</small>
                    </span>
                  </button>
                </div>

                <div class="grid grid-cols-2 gap-2 lg:grid-cols-1">
                  <button
                    type="button"
                    class="mp-button mp-button-outline"
                    @click="duplicateRow(part)"
                  >
                    Nusxa
                  </button>
                  <button
                    type="button"
                    class="mp-button mp-button-outline text-danger"
                    @click="deleteRow(index)"
                  >
                    O'chirish
                  </button>
                </div>
              </div>

              <p
                v-if="partSizeError(part)"
                class="mt-3 flex items-center gap-2 rounded-md border border-danger-soft bg-danger-soft p-3 text-sm font-bold text-danger"
              >
                <span aria-hidden="true">!</span>
                <span>{{ partSizeError(part) }}</span>
              </p>

              <p
                v-if="rowMaterialMissing(part)"
                class="mt-3 flex items-center gap-2 rounded-md border border-danger-soft bg-danger-soft p-3 text-sm font-bold text-danger"
              >
                <span aria-hidden="true">!</span>
                <span>Bu qatordagi panel materiali endi katalogda yo'q — boshqasini tanlang.</span>
              </p>

              <p
                v-if="rowOptimizeError(part, index)"
                class="mt-3 flex items-center gap-2 rounded-md border border-danger-soft bg-danger-soft p-3 text-sm font-bold text-danger"
              >
                <span aria-hidden="true">!</span>
                <span>{{ rowOptimizeError(part, index) }}</span>
              </p>

              <div
                v-if="rowNotCarried(part).length"
                class="mt-3 flex flex-wrap items-center gap-2 rounded-md border border-warning-soft bg-warning-soft p-3 text-sm text-warning"
              >
                <span class="font-black">!</span>
                <span class="min-w-0 flex-1">
                  Bu qator
                  <b>{{ preferredBranch?.branch_name ?? 'tanlangan filial' }}</b>
                  filialida mavjud bo'lmagan materialdan foydalanadi.
                </span>
                <button type="button" class="mp-button mp-button-outline" @click="bringOwn(part)">
                  O'zim olib kelaman
                </button>
                <button
                  v-if="rowNotCarried(part).some((issue) => issue !== 'panel')"
                  type="button"
                  class="mp-button mp-button-outline"
                  @click="openEdgePicker(part)"
                >
                  Boshqa krom tanlash
                </button>
              </div>
            </article>
          </div>

          <div v-if="optimizeBlockers.length" class="client-banner danger mx-5 mt-4" role="alert">
            <span class="font-mono font-black">!</span>
            <span>Optimallashtirib bo'lmaydi: {{ optimizeBlockers.join(' · ') }}</span>
          </div>

          <div
            class="flex flex-wrap items-center justify-between gap-3 border-t border-hairline p-5"
          >
            <div>
              <p v-if="saveError" class="text-sm font-bold text-danger">{{ saveError }}</p>
              <p v-else class="text-sm text-ink-soft">
                {{ parts.length }} qator · {{ totalQuantity }} dona · pre-filter
                {{ preferredBranch ? preferredBranch.branch_name : 'yoqilmagan' }}
              </p>
              <label class="mt-2 inline-flex min-h-9 items-center gap-2 text-sm font-bold text-ink">
                <input v-model="showAllCatalog" type="checkbox" class="size-4" />
                Barcha katalogni ko'rsatish
              </label>
            </div>
            <button
              type="button"
              class="mp-button mp-button-primary"
              :disabled="cutting.optimizing || !canOptimize"
              :title="optimizeDisabledHint"
              @click="optimize"
            >
              {{ cutting.optimizing ? 'Hisoblanmoqda' : 'Optimallashtirish' }}
            </button>
          </div>
        </section>
      </fieldset>

      <section id="cutting-results" class="client-card mt-6 scroll-mt-28 min-[860px]:scroll-mt-20">
        <div class="client-card-h">
          <div>
            <h2>Natija</h2>
            <p class="mt-1 text-sm text-ink-muted">
              Algoritmlarni solishtiring, PDF yuklab oling yoki tanlangan natijadan buyurtma bering.
            </p>
          </div>
          <span
            v-if="chosenResult"
            class="client-pill"
            :class="allPlaced ? 'client-pill-done' : 'client-pill-danger'"
          >
            Joylashtirildi {{ placedCount }}/{{ requestedCount }}
          </span>
          <span
            v-if="chosenResult?.status === 'invalidated'"
            class="client-pill client-pill-danger"
          >
            eskirgan
          </span>
        </div>

        <div v-if="optimizeError" class="client-card-b">
          <div class="client-banner danger" role="alert">
            <span class="font-mono font-black">!</span>
            <span>
              {{ optimizeError }}
              <span v-if="cutting.traceId" class="mt-1 block text-xs font-normal opacity-80">
                trace {{ cutting.traceId }}
              </span>
            </span>
          </div>
        </div>

        <div v-if="!chosenResult && !optimizeError" class="client-card-b">
          <div class="client-empty">
            <div class="client-empty-icon"><Icon name="layers" /></div>
            <h3>Optimizer natijasi yo'q</h3>
            <p>Qismlar saqlangach optimallashtirishni ishga tushiring.</p>
          </div>
        </div>

        <div v-if="chosenResult" class="grid gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_300px]">
          <div class="min-w-0 space-y-4">
            <div v-if="chosenResult.status === 'invalidated'" class="client-banner warn">
              <span class="font-mono font-black">!</span>
              <span
                >Qismlar o'zgargani uchun bu natija eskirgan. Yangi optimallashtirishni ishga
                tushiring.</span
              >
            </div>

            <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div class="rounded-md border border-hairline bg-elevated p-4">
                <div class="text-xs font-bold uppercase text-ink-muted">Chiqim</div>
                <div class="mt-1 font-serif text-2xl font-semibold text-success">
                  {{ resultWaste }}
                </div>
              </div>
              <div class="rounded-md border border-hairline bg-elevated p-4">
                <div class="text-xs font-bold uppercase text-ink-muted">Panellar</div>
                <div class="mt-1 font-serif text-2xl font-semibold text-ink">{{ totalPanels }}</div>
              </div>
              <div class="rounded-md border border-hairline bg-elevated p-4">
                <div class="text-xs font-bold uppercase text-ink-muted">Krom</div>
                <div class="mt-1 font-serif text-2xl font-semibold text-ink">
                  {{ metres(consumedShop + consumedOwn) }}
                </div>
              </div>
              <div class="rounded-md border border-hairline bg-elevated p-4">
                <div class="text-xs font-bold uppercase text-ink-muted">Kesish yo'li</div>
                <div class="mt-1 font-serif text-2xl font-semibold text-ink">
                  {{ metres(chosenResult.total_cut_length_mm) }}
                </div>
              </div>
            </div>

            <div v-if="!allPlaced" class="client-banner danger" role="alert">
              <span class="font-mono font-black">!</span>
              <span>
                {{ requestedCount - placedCount }} ta qism panelga joylashmadi — qism o'lchamini
                kichraytiring yoki boshqa panel tanlang.
              </span>
            </div>

            <section class="rounded-lg border border-hairline bg-elevated">
              <div
                class="flex flex-wrap items-center justify-between gap-3 border-b border-hairline p-4"
              >
                <div class="text-sm font-bold text-ink">
                  Algoritm: <span class="text-accent">{{ chosenResult.algorithm_name }}</span>
                </div>
                <button
                  type="button"
                  class="-mr-2 inline-flex min-h-11 items-center px-3 text-sm font-bold text-accent"
                  @click="algorithmsOpen = !algorithmsOpen"
                >
                  {{ algorithmsOpen ? 'Yopish' : 'Algoritmlarni solishtirish' }}
                </button>
              </div>
              <div v-if="algorithmsOpen" class="overflow-x-auto">
                <table class="w-full min-w-[560px] text-sm">
                  <thead class="bg-sunk text-left text-xs uppercase text-ink-muted">
                    <tr>
                      <th class="px-4 py-3">Algoritm</th>
                      <th class="px-4 py-3">Chiqim</th>
                      <th class="px-4 py-3">Panel</th>
                      <th class="px-4 py-3">Kesish yo'li</th>
                      <th class="px-4 py-3">Holat</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-hairline">
                    <tr
                      v-for="result in draft.results"
                      :key="result.id"
                      :class="result.id === draft.chosen_result_id ? 'bg-accent-soft/40' : ''"
                    >
                      <td class="px-4 py-3 font-bold text-ink">{{ result.algorithm_name }}</td>
                      <td class="px-4 py-3 font-mono">
                        {{ formatPercent(result.waste_percentage) }}
                      </td>
                      <td class="px-4 py-3 font-mono">{{ resultPanelCount(result) }}</td>
                      <td class="px-4 py-3 font-mono">{{ metres(result.total_cut_length_mm) }}</td>
                      <td class="px-4 py-3">
                        <button
                          type="button"
                          class="mp-button mp-button-outline"
                          @click="choose(result)"
                        >
                          {{ result.id === draft.chosen_result_id ? 'Tanlangan' : 'Shuni tanlash' }}
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            <section class="rounded-lg border border-hairline bg-elevated p-4">
              <div class="mb-3 grid gap-3">
                <div v-for="group in panelGroups" :key="group.materialId">
                  <p class="mb-1.5 text-xs font-bold text-ink-soft">
                    {{ group.name }}<span v-if="group.dims"> · {{ group.dims }}</span> ·
                    {{ group.count }} panel
                  </p>
                  <div class="flex flex-wrap gap-2">
                    <button
                      v-for="panel in group.panels"
                      :key="panel.id"
                      type="button"
                      class="mp-chip"
                      :class="panel.id === activePanel?.id ? 'bg-accent text-white' : ''"
                      @click="activePanelId = panel.id"
                    >
                      Panel {{ panel.panel_index }}
                    </button>
                  </div>
                </div>
              </div>

              <CuttingPanelSvg
                v-if="activePanel"
                :result="chosenResult"
                :panel="activePanel"
                :active-placement-id="activePlacementId"
                @select-placement="selectPlacement"
              />
            </section>
          </div>

          <aside class="space-y-4">
            <RouterLink
              v-if="draft.chosen_result_id"
              :to="rolePath(`/c/orders/new/${draft.id}`)"
              class="mp-button mp-button-primary w-full"
            >
              Buyurtma berish
            </RouterLink>
            <button
              type="button"
              class="mp-button mp-button-outline w-full"
              :disabled="cutting.downloadingId === chosenResult.id"
              @click="cutting.downloadClientPdf(chosenResult.id)"
            >
              {{ cutting.downloadingId === chosenResult.id ? 'Yuklanmoqda…' : 'PDF yuklab olish' }}
            </button>
            <p
              v-if="cutting.downloadError"
              class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
              role="alert"
            >
              {{ cutting.downloadError }}
              <span v-if="cutting.downloadTraceId" class="block text-xs font-normal opacity-80">
                trace {{ cutting.downloadTraceId }}
              </span>
            </p>
            <div class="rounded-lg border border-hairline bg-sunk p-4">
              <h3 class="text-sm font-extrabold text-ink">Krom (material bo'yicha)</h3>
              <template v-if="edgeByMaterial.length">
                <ul class="mt-2 space-y-1.5 text-sm">
                  <li
                    v-for="row in edgeByMaterial"
                    :key="row.id"
                    class="flex justify-between gap-3"
                  >
                    <span class="min-w-0 truncate text-ink-soft">{{ row.name }}</span>
                    <span class="shrink-0 font-mono text-ink">{{ metres(row.total) }}</span>
                  </li>
                </ul>
                <p class="mt-2 text-xs text-ink-muted">
                  Ustaxona {{ metres(consumedShop) }} · O'zim {{ metres(consumedOwn) }}
                </p>
              </template>
              <p v-else class="mt-2 text-sm text-ink-soft">Krom ishlatilmagan.</p>
            </div>
            <div v-if="activePanel" class="rounded-lg border border-hairline bg-sunk p-4">
              <h3 class="text-sm font-extrabold text-ink">Joylashuvlar</h3>
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
                  <span class="text-ink-muted"
                    >· {{ placement.length_mm }}×{{ placement.width_mm }} mm</span
                  >
                </button>
              </div>
            </div>
          </aside>
        </div>
      </section>
    </template>

    <ConfirmDialog
      :open="clearPartsConfirmOpen"
      title="Ro'yxatni tozalash"
      :message="`Barcha ${parts.length} qator o'chirilsinmi? Bu amalni qaytarib bo'lmaydi.`"
      confirm-label="Tozalash"
      danger
      @cancel="clearPartsConfirmOpen = false"
      @confirm="clearParts"
    />

    <template v-if="edgePickerPart">
      <div class="client-modal-scrim" @click="closeEdgePicker()"></div>
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
            Krom yopishtirish — qism #{{ parts.findIndex((part) => part === edgePickerPart) + 1 }}
          </h3>
          <button
            type="button"
            class="client-edge-close"
            aria-label="Krom oynasini yopish"
            @click="closeEdgePicker()"
          >
            ×
          </button>
        </div>

        <div class="client-edge-modal-b">
          <p class="ep-help">
            {{
              edgePickerMaterials.some((item) => item.rank < 2)
                ? "Mos kromlar ro'yxatda yuqorida turadi; kerak bo'lsa rang yoki qalinlik bo'yicha tanlang."
                : "Bu panel uchun mos krom topilmadi; katalogdan rang yoki qalinlik bo'yicha tanlang."
            }}
          </p>

          <div class="ep-patterns" aria-label="Krom tomoni shablonlari">
            <button
              v-for="pattern in edgePatterns"
              :key="pattern.key"
              type="button"
              class="ep-pattern"
              :class="{ on: edgePickerPatternKey === pattern.key }"
              :disabled="pattern.sides.length > 0 && !recommendedEdgeForPart(edgePickerPart)"
              @click="applyEdgePattern(pattern.key)"
            >
              <span class="nm">{{ pattern.label }}</span>
              <span class="meta">{{ pattern.hint }}</span>
            </button>
          </div>

          <div class="edge-diagram" aria-label="Krom tomonlari">
            <span class="lbl">Yuqori</span>
            <button
              type="button"
              class="edge-btn h"
              :class="{
                set: Boolean(edgePickerState.edge_top),
                own: edgePickerState.edge_top?.source === 'own',
              }"
              :aria-pressed="Boolean(edgePickerState.edge_top)"
              @click="togglePickerSide('edge_top')"
            >
              {{ edgePickerState.edge_top ? pickerSideLabel('edge_top') : '-' }}
            </button>
            <div class="mid">
              <button
                type="button"
                class="edge-btn v"
                :class="{
                  set: Boolean(edgePickerState.edge_left),
                  own: edgePickerState.edge_left?.source === 'own',
                }"
                :aria-pressed="Boolean(edgePickerState.edge_left)"
                @click="togglePickerSide('edge_left')"
              >
                {{ edgePickerState.edge_left ? pickerSideLabel('edge_left') : '-' }}
              </button>
              <div class="panel">Qism</div>
              <button
                type="button"
                class="edge-btn v"
                :class="{
                  set: Boolean(edgePickerState.edge_right),
                  own: edgePickerState.edge_right?.source === 'own',
                }"
                :aria-pressed="Boolean(edgePickerState.edge_right)"
                @click="togglePickerSide('edge_right')"
              >
                {{ edgePickerState.edge_right ? pickerSideLabel('edge_right') : '-' }}
              </button>
            </div>
            <button
              type="button"
              class="edge-btn h"
              :class="{
                set: Boolean(edgePickerState.edge_bottom),
                own: edgePickerState.edge_bottom?.source === 'own',
              }"
              :aria-pressed="Boolean(edgePickerState.edge_bottom)"
              @click="togglePickerSide('edge_bottom')"
            >
              {{ edgePickerState.edge_bottom ? pickerSideLabel('edge_bottom') : '-' }}
            </button>
            <span class="lbl">Pastki</span>
          </div>

          <div class="ep-source">
            <button
              type="button"
              :class="{ on: edgePickerSource === 'shop' }"
              :aria-pressed="edgePickerSource === 'shop'"
              @click="setPickerSource('shop')"
            >
              <span class="nm">Ustaxonadan</span>
              <span class="meta">Krom narxga qo'shiladi</span>
            </button>
            <button
              type="button"
              :class="{ on: edgePickerSource === 'own' }"
              :aria-pressed="edgePickerSource === 'own'"
              @click="setPickerSource('own')"
            >
              <span class="nm">O'zim olib kelaman</span>
              <span class="meta">Faqat yopishtirish xizmati</span>
            </button>
          </div>

          <div class="ep-tools">
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
                :class="{ on: edgePickerSelectedMaterialId === material.id }"
                @click="selectPickerMaterial(material.id)"
              >
                <span class="rad" aria-hidden="true"></span>
                <span class="sw" :style="{ background: colorForMaterial(material.color) }"></span>
                <span class="lab">
                  <span class="nm">
                    {{ edgeShortLabel(material) }}
                    <span v-if="rank < 2" class="fav">Mos</span>
                  </span>
                  <span class="meta">{{ material.name }}</span>
                </span>
                <span class="thk">{{ material.thickness_mm }} mm</span>
              </button>
              <div v-if="edgePickerMaterials.length === 0" class="ep-empty">
                Mos krom topilmadi. Qidiruv yoki qalinlikni o'zgartiring.
              </div>
            </div>
            <div v-if="edgePickerBranchNote" class="ep-branch-note">
              {{ edgePickerBranchNote }}
            </div>
          </div>
        </div>

        <div class="client-edge-modal-f">
          <button type="button" class="mp-button mp-button-outline" @click="closeEdgePicker()">
            Bekor qilish
          </button>
          <button type="button" class="mp-button mp-button-primary" @click="applyEdgePicker">
            Qo'llash
          </button>
        </div>
      </section>
    </template>
  </section>
</template>
