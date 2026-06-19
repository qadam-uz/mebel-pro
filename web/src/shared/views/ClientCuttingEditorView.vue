<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { ApiError } from '@/shared/api/client'
import { clientErrorLabel } from '@/shared/app/clientUi'
import { MAX_PARTS, MIN_PART_MM } from '@/shared/app/constants'
import { rankedEdges, recommendedEdge } from '@/shared/app/cuttingEdgeDisplay'
import {
  colorForMaterial,
  edgeFields,
  edgeSearchText,
  edgeShortLabel,
  edgeTinyLabel,
  type EdgeField,
} from '@/shared/app/cuttingDisplay'
import { useDraftAutosave } from '@/shared/composables/useDraftAutosave'
import { useToast } from '@/shared/composables/useToast'
import { lockBodyScroll, unlockBodyScroll } from '@/shared/app/scrollLock'
import Icon from '@/shared/components/AppIcon.vue'
import { useRolePath } from '@/shared/app/paths'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import CuttingBranchPicker from '@/shared/components/CuttingBranchPicker.vue'
import CuttingPartRow from '@/shared/components/CuttingPartRow.vue'
import CuttingResultsSection from '@/shared/components/CuttingResultsSection.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import MultiSelectFilter from '@/shared/components/MultiSelectFilter.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import type { PanelMaterialType } from '@/shared/stores/admin'
import {
  EDGE_TRIM_MM,
  materialLabel,
  partFitError,
  partNotCarried,
  useCuttingStore,
  type CuttingEdgeBand,
  type CuttingPart,
  type MaterialSource,
} from '@/shared/stores/cutting'

const route = useRoute()
const rolePath = useRolePath()
const cutting = useCuttingStore()
const toast = useToast()
const draftId = computed(() => String(route.params.id))
const parts = ref<CuttingPart[]>([])
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
const recoveryDismissed = ref(false)
const activeResultId = ref<string | null>(null)
const activePanelId = ref<string | null>(null)
const preferredEdgeByPart = ref<Record<string, string>>({})
const edgePickerPart = ref<CuttingPart | null>(null)
const edgePickerState = ref<Record<EdgeField, CuttingEdgeBand | null>>(blankEdgeState())
const edgePickerSource = ref<MaterialSource>('shop')
const edgePickerSearch = ref('')
const edgePickerThickness = ref<string | null>('all')
const edgeDialogRef = ref<HTMLElement | null>(null)
let edgeReturnFocus: HTMLElement | null = null
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
const totalQuantity = computed(() =>
  parts.value.reduce((sum, part) => sum + Math.max(0, Number(part.quantity) || 0), 0),
)
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

function pickerSideLabel(side: EdgeField) {
  return edgeTinyLabel(edgeById(edgePickerState.value[side]?.material_id))
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

// Debounced autosave (700ms) — the timing core, status mirror, don't-persist gate,
// the deep `parts` watch, and the CB-15 hydration guard all live in the
// `useDraftAutosave` composable (CB-93 seam). The gate skips incomplete/out-of-bounds
// rows (they show their own inline validation) and a read-only bound draft.
const autosave = useDraftAutosave({
  parts,
  persist: () => cutting.updateDraft(draftId.value, { parts_snapshot: parts.value }).then(),
  canPersist: () => hasPersistableParts.value,
  isReadOnly: () => isReadOnly.value,
  // A row-attributed optimiser error is stale once the parts change.
  onSchedule: () => {
    optimizeRowError.value = null
  },
})
const saveState = autosave.saveState
const saveError = autosave.saveError

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
      autosave.hydrate(() => {
        parts.value = value.parts_snapshot.map((part) => ({ ...part }))
        hydratedDraftId = value.id
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
            <CuttingPartRow
              v-for="(part, index) in parts"
              :key="part.part_ref"
              :part="part"
              :index="index"
              :panel-choices="panelChoices"
              :has-error="rowHasError(part, index)"
              :size-error="partSizeError(part)"
              :material-missing="rowMaterialMissing(part)"
              :optimize-error="rowOptimizeError(part, index)"
              :not-carried="rowNotCarried(part)"
              :preferred-branch-name="preferredBranch?.branch_name ?? 'tanlangan filial'"
              @update:length="part.length_mm = $event"
              @update:width="part.width_mm = $event"
              @update:quantity="part.quantity = $event"
              @update:material="setPanel(part, $event)"
              @update:source="setPanelSource(part, $event)"
              @duplicate="duplicateRow(part)"
              @delete="deleteRow(index)"
              @open-edge-picker="openEdgePicker(part, $event)"
              @bring-own="bringOwn(part)"
            />
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

      <CuttingResultsSection
        :draft="draft"
        :optimize-error="optimizeError"
        v-model:active-result-id="activeResultId"
        v-model:active-panel-id="activePanelId"
      />
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
