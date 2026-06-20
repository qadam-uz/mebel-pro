<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'

import { ApiError, apiErrorCode } from '@/shared/api/client'
import { clientErrorLabel } from '@/shared/app/clientUi'
import { MAX_PARTS, MIN_PART_MM, NO_BRANCH_CATALOG_LIMIT } from '@/shared/app/constants'
import { edgeFields, type EdgeField } from '@/shared/app/cuttingDisplay'
import { useDraftAutosave } from '@/shared/composables/useDraftAutosave'
import { useToast } from '@/shared/composables/useToast'
import Icon from '@/shared/components/AppIcon.vue'
import { useRolePath } from '@/shared/app/paths'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import CuttingBranchPicker from '@/shared/components/CuttingBranchPicker.vue'
import CuttingEdgePickerModal from '@/shared/components/CuttingEdgePickerModal.vue'
import CuttingPartRow from '@/shared/components/CuttingPartRow.vue'
import CuttingResultsSection from '@/shared/components/CuttingResultsSection.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import MultiSelectFilter from '@/shared/components/MultiSelectFilter.vue'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'
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
import { useClientProfileStore } from '@/shared/stores/clientProfile'

const route = useRoute()
const router = useRouter()
const rolePath = useRolePath()
const cutting = useCuttingStore()
const clientProfile = useClientProfileStore()
const toast = useToast()
const draftId = computed(() => String(route.params.id))
// Unsaved editor: opened via `/c/cutting/new`, the draft has no server id yet.
// It's created and persisted on the first optimise (docs/ref/features/cutting.md).
const isNewDraft = computed(() => route.name === 'client-cutting-new')
// Branch pre-filter while unsaved — held locally (no draft to PATCH); seeded from
// the client profile default for parity with a server-created draft.
const localBranchId = ref<string | null>(null)
const branchTouched = ref(false)
// A draft created by a previous failed optimise attempt — reused on retry so a
// transient failure doesn't orphan a second empty draft.
const pendingDraftId = ref<string | null>(null)
const creatingDraft = ref(false)
// Set just before the optimise→navigate transition so the unsaved-work guard
// doesn't fire on our own navigation.
const leavingAfterCreate = ref(false)
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
let edgeReturnFocus: HTMLElement | null = null
// The draft whose parts are currently mirrored into `parts.value`. We only
// re-hydrate from a server snapshot when this changes — saves/optimizes return
// the same draft and must not clobber unsaved local edits (CB-15).
let hydratedDraftId: string | null = null

// In unsaved mode `draft` stays null regardless of `currentDraft`, so a draft
// minted mid-flow (createDraft sets currentDraft) never leaks into the editor
// until we navigate to the real route, which remounts on the saved path.
const draft = computed(() => (isNewDraft.value ? null : cutting.currentDraft))
// A draft is bound to an order once one of its results is confirmed onto an
// order (the backend enforces one result per order). Bound drafts are
// read-only — editing them would fire doomed saves and contradict the order.
const boundOrderId = computed(
  () => draft.value?.results.find((result) => result.order_id)?.order_id ?? null,
)
const isReadOnly = computed(() => boundOrderId.value !== null)
// The active branch pre-filter: the local pick while unsaved, the draft's saved
// preference otherwise. Every branch-dependent read routes through this.
const activeBranchId = computed(() =>
  isNewDraft.value ? localBranchId.value : (draft.value?.preferred_branch_id ?? null),
)
const preferredBranch = computed(() =>
  cutting.branchOptions.find((branch) => branch.branch_id === activeBranchId.value),
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
    activeBranchId.value && !showAllCatalog.value ? material.branch_carried : true,
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
  return partNotCarried(part, activeBranchId.value, materialById, edgeById)
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
    if (selectedRefs.value.has(removed.part_ref)) {
      const nextSel = new Set(selectedRefs.value)
      nextSel.delete(removed.part_ref)
      selectedRefs.value = nextSel
    }
  }
}

function requestClearParts() {
  clearPartsConfirmOpen.value = true
}

function clearParts() {
  parts.value = []
  preferredEdgeByPart.value = {}
  clearPartsConfirmOpen.value = false
  clearSelection()
}

// --- Bulk selection (desktop power-feature) --------------------------------
// Select rows, then apply edges / change material / delete in one action so
// banding or re-materialing many identical parts isn't N modal round-trips.
const selectedRefs = ref<Set<string>>(new Set())
const selectedParts = computed(() =>
  parts.value.filter((part) => selectedRefs.value.has(part.part_ref)),
)
const allSelected = computed(
  () => parts.value.length > 0 && selectedParts.value.length === parts.value.length,
)
const bulkEdgeMode = ref(false)
const bulkMaterialOpen = ref(false)
const bulkMaterialId = ref<string | null>(null)

function toggleSelect(partRef: string) {
  const next = new Set(selectedRefs.value)
  if (next.has(partRef)) next.delete(partRef)
  else next.add(partRef)
  selectedRefs.value = next
}
function toggleSelectAll() {
  selectedRefs.value = allSelected.value
    ? new Set()
    : new Set(parts.value.map((part) => part.part_ref))
}
function clearSelection() {
  selectedRefs.value = new Set()
}
function bulkDelete() {
  const removed = selectedRefs.value
  parts.value = parts.value.filter((part) => !removed.has(part.part_ref))
  const nextEdges = { ...preferredEdgeByPart.value }
  for (const ref of removed) delete nextEdges[ref]
  preferredEdgeByPart.value = nextEdges
  clearSelection()
}
function openBulkEdge() {
  if (selectedParts.value.length === 0) return
  // Reuse the single-part edge picker: seed it from the first selected part and
  // write the applied result to every selected part on apply (bulkEdgeMode).
  bulkEdgeMode.value = true
  edgePickerPart.value = { ...selectedParts.value[0], part_ref: '__bulk__' }
  edgeReturnFocus = null
}
function openBulkMaterial() {
  if (selectedParts.value.length === 0) return
  bulkMaterialId.value = selectedParts.value[0]?.material_id || null
  bulkMaterialOpen.value = true
}
function applyBulkMaterial() {
  if (bulkMaterialId.value) {
    for (const part of selectedParts.value) part.material_id = bulkMaterialId.value
  }
  bulkMaterialOpen.value = false
}

function setPanelSource(part: CuttingPart, source: MaterialSource) {
  part.material_source = source
}

function setPanel(part: CuttingPart, value: string | null) {
  part.material_id = value ?? ''
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

function openEdgePicker(part: CuttingPart, event?: Event) {
  // The modal seeds its own working selection from `part`; the editor only records
  // which part is open and the element to restore focus to on close.
  edgePickerPart.value = part
  edgeReturnFocus = event?.currentTarget instanceof HTMLElement ? event.currentTarget : null
}

function closeEdgePicker() {
  edgePickerPart.value = null
  bulkEdgeMode.value = false
  edgeReturnFocus?.focus()
  edgeReturnFocus = null
}

function onEdgePickerApply(payload: {
  edges: Record<EdgeField, CuttingEdgeBand | null>
  rememberedMaterialId: string | null
}) {
  // Bulk mode writes the same edge set to every selected part; single mode
  // writes to the one open part.
  const targets = bulkEdgeMode.value ? selectedParts.value : [edgePickerPart.value]
  for (const part of targets) {
    if (!part) continue
    part.edge_top = payload.edges.edge_top
    part.edge_bottom = payload.edges.edge_bottom
    part.edge_left = payload.edges.edge_left
    part.edge_right = payload.edges.edge_right
    rememberEdgeMaterial(part, payload.rememberedMaterialId)
  }
  closeEdgePicker()
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
  // Suspended while unsaved — there's no draft id to PATCH until the first
  // optimise creates one (docs/ref/features/cutting.md).
  enabled: () => !isNewDraft.value,
  // A row-attributed optimiser error is stale once the parts change.
  onSchedule: () => {
    optimizeRowError.value = null
  },
})
const saveState = autosave.saveState
const saveError = autosave.saveError

async function setPreferredBranch(branchId: string | null) {
  // Unsaved: there's no draft to PATCH yet — keep the pick locally and re-filter
  // the catalog. It's persisted with the draft on the first optimise.
  if (isNewDraft.value) {
    localBranchId.value = branchId
    branchTouched.value = true
    branchPickerOpen.value = false
    selectedBranchId.value = branchId
    recoveryDismissed.value = false
    await loadMaterials()
    return
  }
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

// Close the picker without applying — drop the pending pick back to the active
// preference so a re-open highlights what's actually active, not an abandoned choice.
function closeBranchPicker() {
  branchPickerOpen.value = false
  selectedBranchId.value = activeBranchId.value
}

async function optimize() {
  if (cutting.optimizing || creatingDraft.value || !canOptimize.value) return
  optimizeError.value = null
  optimizeRowError.value = null
  if (isNewDraft.value) {
    creatingDraft.value = true
    try {
      await optimizeNewDraft()
    } finally {
      creatingDraft.value = false
    }
    return
  }
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

// First optimise on an unsaved editor: create the draft, persist the parts (and
// the branch if the user changed it), optimise, then navigate to the real route
// — which remounts the editor on the saved path with the optimised result.
async function optimizeNewDraft() {
  try {
    // Reuse a draft from a previous failed attempt so a retry doesn't orphan a
    // second empty draft.
    if (!pendingDraftId.value) {
      pendingDraftId.value = (await cutting.createDraft()).id
    }
    const id = pendingDraftId.value
    await cutting.updateDraft(id, {
      parts_snapshot: parts.value,
      // Only send the branch when the user changed it — otherwise let the
      // backend's profile-default seed stand (docs/ref/features/cutting.md).
      ...(branchTouched.value ? { preferred_branch_id: localBranchId.value } : {}),
    })
    await cutting.optimizeDraft(id)
    lastOptimizedSignature.value = partsSignature()
    // Hand off to the saved editor; the guard must not treat this as discarding.
    leavingAfterCreate.value = true
    await router.replace(rolePath(`/c/cutting/${id}`))
  } catch (errorValue) {
    // The parts are still in local state, so the user keeps their work and can
    // retry; the row attribution still maps because the parts are unchanged.
    optimizeError.value = clientErrorLabel(
      cutting.error ?? apiErrorCode(errorValue),
      "Optimallashtirishda xatolik. Qayta urinib ko'ring.",
    )
    optimizeRowError.value = optimizeRowFromError(errorValue)
    // The error banner sits next to the optimise button, already in view — no
    // scroll target (the results section isn't rendered while unsaved).
  }
}

async function loadMaterials() {
  // Use the active pre-filter (local pick while unsaved, draft preference
  // otherwise) so picking a branch in the new editor scopes the catalog too.
  const branchId = activeBranchId.value
  // CB-40: cap ONLY the unbounded no-preferred-branch load so a fresh draft doesn't
  // pull the whole catalog. A branch-scoped load stays unlimited (CB-84 filters +
  // CB-19/86 recovery need the full per-branch list client-side).
  const limit = branchId ? undefined : NO_BRANCH_CATALOG_LIMIT
  await Promise.all([
    cutting.loadMaterials({ kind: 'panel', branchId, carriedOnly: false, limit }),
    cutting.loadMaterials({ kind: 'edge', branchId, carriedOnly: false, limit }),
  ])
}

watch(
  () => cutting.currentDraft,
  (value) => {
    if (!value) return
    // Unsaved mode owns `parts` locally and ignores `currentDraft` (which a
    // mid-flow createDraft may set); the saved editor mounts fresh after the
    // optimise→navigate handoff and hydrates there.
    if (isNewDraft.value) return
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
  window.addEventListener('beforeunload', onBeforeUnload)
  if (isNewDraft.value) {
    // Unsaved editor: nothing to load. Populate the branch picker and seed the
    // pre-filter from the client's profile default (parity with a server draft).
    await cutting.loadBranchOptions()
    const profile = await clientProfile.load().catch(() => null)
    localBranchId.value = profile?.preferred_branch_id ?? null
    selectedBranchId.value = localBranchId.value
    await loadMaterials()
    return
  }
  // Reuse an already-loaded draft (e.g. just optimised from the new editor) to
  // avoid a load flash; otherwise fetch it.
  if (cutting.currentDraft?.id !== draftId.value) await cutting.loadDraft(draftId.value)
  await cutting.loadBranchOptions()
  selectedBranchId.value = draft.value?.preferred_branch_id ?? null
  await loadMaterials()
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', onBeforeUnload)
  // Flush a debounced edit before teardown so navigating away within the 700ms
  // window doesn't silently drop it (CB-15). The store action outlives the
  // component, so the PATCH still completes.
  void autosave.flush()
})

// Warn before discarding unsaved work — an unsaved editor with entered parts has
// nothing persisted until the first optimise. Skipped during our own
// optimise→navigate handoff. (ui-ux: never lose the user's work.)
const hasUnsavedNewWork = computed(
  () => isNewDraft.value && !leavingAfterCreate.value && parts.value.length > 0,
)
// In-app leave confirmation via the design-system dialog (native window.confirm
// is banned, routeMatrix.spec). The route guard awaits the user's choice.
const leaveDialogOpen = ref(false)
let leaveResolve: ((allow: boolean) => void) | null = null

function resolveLeave(allow: boolean) {
  leaveDialogOpen.value = false
  leaveResolve?.(allow)
  leaveResolve = null
}

function onBeforeUnload(event: BeforeUnloadEvent) {
  if (!hasUnsavedNewWork.value) return
  event.preventDefault()
  event.returnValue = ''
}

onBeforeRouteLeave(() => {
  if (!hasUnsavedNewWork.value) return true
  leaveDialogOpen.value = true
  return new Promise<boolean>((resolve) => {
    leaveResolve = resolve
  })
})
</script>

<template>
  <section>
    <div class="client-page-head">
      <div>
        <h1>Chizma</h1>
        <p class="sub">
          Qismlarni kiriting, ustaxona katalogi bo'yicha tekshiring va kesish natijasini oling.
        </p>
      </div>
      <div v-if="!isReadOnly" class="flex flex-wrap items-center gap-2">
        <span
          v-if="!isNewDraft"
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
          v-if="parts.length > 0"
          type="button"
          class="mp-button mp-button-outline px-3 text-danger"
          aria-label="Ro'yxatni tozalash"
          title="Ro'yxatni tozalash"
          @click="requestClearParts"
        >
          <Icon name="trash" class="size-[18px]" />
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

    <template v-else-if="draft || isNewDraft">
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
          class="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-hairline bg-elevated px-4 py-2.5 text-sm text-ink-soft"
        >
          <span
            class="grid size-6 shrink-0 place-items-center rounded-md bg-info-soft font-mono font-black text-info"
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
            <span class="text-ink-muted"> — materiallarni cheklamaydi (ixtiyoriy)</span>
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
          <p v-if="!preferredBranch" class="basis-full text-xs text-ink-muted">
            Filial tanlanmagani uchun faqat dastlabki {{ NO_BRANCH_CATALOG_LIMIT }} ta material
            ko'rsatilmoqda — to'liq katalog uchun ustaxona tanlang.
          </p>
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

          <div
            v-if="selectedParts.length > 0"
            class="hidden flex-wrap items-center gap-x-5 gap-y-2 border-b border-accent-tint bg-accent-soft px-5 py-3 text-sm font-bold lg:flex"
          >
            <span class="text-accent">{{ selectedParts.length }} qism tanlandi</span>
            <button type="button" class="text-accent hover:underline" @click="openBulkEdge">
              Krom qo'llash
            </button>
            <button type="button" class="text-accent hover:underline" @click="openBulkMaterial">
              Material almashtirish
            </button>
            <button type="button" class="text-danger hover:underline" @click="bulkDelete">
              O'chirish
            </button>
            <button
              type="button"
              class="ml-auto text-ink-muted hover:text-ink"
              @click="clearSelection"
            >
              Bekor qilish
            </button>
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
            <!-- Desktop column header: same border + p-3 + grid template as a
                 CuttingPartRow card, so the columns line up; hidden on mobile,
                 where each row keeps its own field labels. The leading cell is a
                 real select-all checkbox; the rest are decorative labels. -->
            <div class="hidden rounded-lg border border-hairline bg-sunk p-3 lg:block">
              <div
                class="grid grid-cols-[30px_30px_minmax(210px,1.6fr)_82px_82px_66px_minmax(150px,1fr)_44px] items-center gap-2 text-[11px] font-extrabold uppercase tracking-wide text-ink-muted"
              >
                <input
                  type="checkbox"
                  class="size-4 justify-self-center"
                  :checked="allSelected"
                  :indeterminate.prop="selectedParts.length > 0 && !allSelected"
                  aria-label="Hamma qatorni tanlash"
                  @change="toggleSelectAll"
                />
                <span aria-hidden="true">#</span>
                <span aria-hidden="true">Panel materiali</span>
                <span aria-hidden="true">Uzunlik</span>
                <span aria-hidden="true">Eni</span>
                <span aria-hidden="true">Soni</span>
                <span aria-hidden="true">Krom</span>
                <span aria-hidden="true">Amallar</span>
              </div>
            </div>
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
              :selected="selectedRefs.has(part.part_ref)"
              @toggle-select="toggleSelect(part.part_ref)"
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
            v-if="isNewDraft && optimizeError"
            class="client-banner danger mx-5 mt-4"
            role="alert"
          >
            <span class="font-mono font-black">!</span>
            <span>
              {{ optimizeError }}
              <span v-if="cutting.traceId" class="mt-1 block text-xs font-normal opacity-80">
                trace {{ cutting.traceId }}
              </span>
            </span>
          </div>

          <div
            class="flex flex-wrap items-center justify-between gap-3 border-t border-hairline p-5"
          >
            <label class="inline-flex min-h-9 items-center gap-2 text-sm font-bold text-ink">
              <input v-model="showAllCatalog" type="checkbox" class="size-4" />
              Barcha katalogni ko'rsatish
            </label>
            <p v-if="saveError" class="text-sm font-bold text-danger">{{ saveError }}</p>
          </div>
        </section>

        <!-- Sticky action bar: the primary Optimise CTA stays reachable without
             scrolling to the bottom of a long parts list, and the disabled reason
             is shown inline (visible on touch) instead of only in a title tooltip. -->
        <div
          v-if="parts.length > 0"
          class="sticky bottom-0 z-20 mt-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-xl border border-hairline-strong bg-elevated/95 px-4 py-3 shadow-[0_-6px_24px_-14px_rgb(15_27_45_/_30%)] backdrop-blur"
        >
          <div class="text-sm">
            <span class="font-mono font-bold text-ink"
              >{{ parts.length }} qator · {{ totalQuantity }} dona</span
            >
            <span class="text-ink-muted"> / {{ MAX_PARTS }}</span>
          </div>
          <div class="flex flex-wrap items-center justify-end gap-3">
            <span
              v-if="!cutting.optimizing && !creatingDraft && optimizeDisabledHint"
              class="inline-flex items-center gap-1.5 text-xs font-semibold text-ink-muted"
            >
              <span class="font-black text-warning" aria-hidden="true">!</span>
              {{ optimizeDisabledHint }}
            </span>
            <button
              type="button"
              class="mp-button mp-button-primary"
              :disabled="cutting.optimizing || creatingDraft || !canOptimize"
              :title="optimizeDisabledHint"
              @click="optimize"
            >
              {{ cutting.optimizing || creatingDraft ? 'Hisoblanmoqda' : 'Optimallashtirish' }}
            </button>
          </div>
        </div>
      </fieldset>

      <CuttingResultsSection
        v-if="draft"
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
      cancel-label="Bekor qilish"
      danger
      @cancel="clearPartsConfirmOpen = false"
      @confirm="clearParts"
    />

    <ConfirmDialog
      :open="leaveDialogOpen"
      title="Saqlanmagan chizma"
      message="Bu chizma hali saqlanmagan — optimallashtirilmaguncha kiritilgan qismlar yo'qoladi. Chiqasizmi?"
      confirm-label="Chiqish"
      cancel-label="Bekor qilish"
      danger
      @cancel="resolveLeave(false)"
      @confirm="resolveLeave(true)"
    />

    <CuttingEdgePickerModal
      :part="edgePickerPart"
      :part-number="edgePickerPart ? parts.indexOf(edgePickerPart) + 1 : 0"
      :title-suffix="bulkEdgeMode ? `${selectedParts.length} qismga` : undefined"
      :preferred-edge-id="edgePickerPart ? preferredEdgeId(edgePickerPart) : null"
      :preferred-branch-id="activeBranchId"
      :preferred-branch-name="preferredBranch?.branch_name ?? 'tanlangan filial'"
      @apply="onEdgePickerApply"
      @close="closeEdgePicker"
    />

    <!-- Bulk material picker. A custom card (NOT .client-edge-modal, which has
         overflow:hidden) so the SearchCombobox dropdown isn't clipped. -->
    <div
      v-if="bulkMaterialOpen"
      class="fixed inset-0 z-[70] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Material almashtirish"
      @keydown.esc="bulkMaterialOpen = false"
    >
      <div
        class="absolute inset-0 bg-[rgb(15_27_45_/_45%)] backdrop-blur-[2px]"
        @click="bulkMaterialOpen = false"
      ></div>
      <div
        class="relative z-10 w-[min(420px,100%)] rounded-2xl border border-hairline bg-elevated p-5 shadow-[0_28px_60px_-14px_rgb(15_27_45_/_30%)]"
      >
        <div class="mb-3 flex items-start justify-between gap-3">
          <h3 class="font-serif text-lg font-semibold text-ink">
            Material almashtirish — {{ selectedParts.length }} qismga
          </h3>
          <button
            type="button"
            class="client-edge-close"
            aria-label="Yopish"
            @click="bulkMaterialOpen = false"
          >
            ×
          </button>
        </div>
        <SearchCombobox
          :model-value="bulkMaterialId"
          label="Panel materiali"
          :options="panelChoices"
          placeholder="Panel tanlang"
          @update:model-value="bulkMaterialId = $event"
        />
        <p class="mt-2 text-sm text-ink-muted">
          Tanlangan material {{ selectedParts.length }} ta qatorga qo'llanadi.
        </p>
        <div class="mt-4 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            class="mp-button mp-button-outline"
            @click="bulkMaterialOpen = false"
          >
            Bekor qilish
          </button>
          <button
            type="button"
            class="mp-button mp-button-primary"
            :disabled="!bulkMaterialId"
            @click="applyBulkMaterial"
          >
            Qo'llash
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
