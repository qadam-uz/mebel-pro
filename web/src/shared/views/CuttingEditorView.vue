<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import { RouterLink, onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'

import { ApiError, apiErrorCode } from '@/shared/api/client'
import { clientErrorLabel } from '@/shared/app/clientUi'
import { MAX_PARTS, MIN_PART_MM } from '@/shared/app/constants'
import {
  clientCuttingEditorAdapter,
  cuttingEditorAdapterKey,
  type CuttingEditorAdapterFactory,
} from '@/shared/app/cuttingEditorAdapter'
import { edgeFields, type EdgeField } from '@/shared/app/cuttingDisplay'
import { useDraftAutosave } from '@/shared/composables/useDraftAutosave'
import { useToast } from '@/shared/composables/useToast'
import Icon from '@/shared/components/AppIcon.vue'
import { useRolePath } from '@/shared/app/paths'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import CuttingBranchPicker from '@/shared/components/CuttingBranchPicker.vue'
import CuttingEdgePickerModal from '@/shared/components/CuttingEdgePickerModal.vue'
import CuttingImportWizard from '@/shared/components/CuttingImportWizard.vue'
import CuttingPartRow from '@/shared/components/CuttingPartRow.vue'
import CuttingResultsSection from '@/shared/components/CuttingResultsSection.vue'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import {
  EDGE_TRIM_MM,
  materialLabel,
  partFitError,
  partNotCarried,
  useCuttingStore,
  type ClientCatalogMaterialOption,
  type CuttingEdgeBand,
  type CuttingPart,
} from '@/shared/stores/cutting'
import { applyImportedParts, type ImportLoadMode } from '@/shared/stores/cuttingImport'
import { useClientProfileStore } from '@/shared/stores/clientProfile'

const route = useRoute()
const router = useRouter()
const rolePath = useRolePath()
const cutting = useCuttingStore()
const clientProfile = useClientProfileStore()
const toast = useToast()
// Role adapter (see cuttingEditorAdapter.ts): the route carries a factory under
// `meta.cuttingEditorAdapter`; resolve it once at mount and provide it so the
// results section (a grandchild) can read the same link targets. No route
// adapter → the client default, so the client app needs zero configuration.
const adapter = (
  (route.meta.cuttingEditorAdapter as CuttingEditorAdapterFactory | undefined) ??
  clientCuttingEditorAdapter
)()
provide(cuttingEditorAdapterKey, adapter)
// Fixed-branch mode (workshop): the branch comes from the app's current context,
// not a picker; the walk-in identity strip shows in workshop scope.
const fixedBranch = computed(() => adapter.branch.fixed ?? null)
const isWorkshopScope = computed(() => cutting.scope === 'workshop')
const draftId = computed(() => String(route.params.id))
// Unsaved editor: opened via the adapter's new-draft route, the draft has no
// server id yet. It's created and persisted on the first optimise
// (docs/ref/features/cutting.md).
const isNewDraft = computed(() => route.name === adapter.newRouteName)
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
const clearPartsConfirmOpen = ref(false)
const importWizardOpen = ref(false)
const importReplaceConfirmOpen = ref(false)
const pendingImportedParts = ref<CuttingPart[] | null>(null)
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
const activeBranchId = computed(() => {
  // Fixed-branch mode locks every branch-dependent read to the app context.
  if (fixedBranch.value) return fixedBranch.value.id
  return isNewDraft.value ? localBranchId.value : (draft.value?.preferred_branch_id ?? null)
})
const preferredBranch = computed(() =>
  cutting.branchOptions.find((branch) => branch.branch_id === activeBranchId.value),
)
// Every row's panel picker draws from this branch-filtered catalog; the picker's
// own search narrows further. With a branch selected only its carried materials show.
const panelOptions = computed(() =>
  cutting.panelOptions.filter((material) =>
    activeBranchId.value ? material.branch_carried : true,
  ),
)
function catalogChoice(material: ClientCatalogMaterialOption): ChoiceOption {
  return {
    value: material.id,
    label: materialLabel(material),
    meta: `${material.color}${material.decor_code ? ` · ${material.decor_code}` : ''}${
      material.branch_carried ? '' : " · filialda yo'q"
    }`,
  }
}
const branchPanelChoices = computed<ChoiceOption[]>(() => panelOptions.value.map(catalogChoice))
const allPanelChoices = computed<ChoiceOption[]>(() => cutting.panelOptions.map(catalogChoice))
const edgeOptions = computed(() =>
  cutting.edgeOptions.filter((material) => (activeBranchId.value ? material.branch_carried : true)),
)
const edgeChoices = computed<ChoiceOption[]>(() => edgeOptions.value.map(catalogChoice))
const allEdgeChoices = computed<ChoiceOption[]>(() => cutting.edgeOptions.map(catalogChoice))
const panelChoices = computed<ChoiceOption[]>(() => {
  // Always keep a material a row already references in the options, even if the
  // branch filter would drop it — otherwise the picker shows an empty
  // "Panel tanlang" for a row that does have a (not-carried) panel, which
  // reads as "nothing selected" while the not-carried warning fires.
  const list = [...panelOptions.value]
  const present = new Set(list.map((material) => material.id))
  for (const part of parts.value) {
    if (!part.material_id || present.has(part.material_id)) continue
    const material = cutting.panelOptions.find((option) => option.id === part.material_id)
    if (material) {
      list.push(material)
      present.add(material.id)
    }
  }
  return list.map(catalogChoice)
})
const hasPersistableParts = computed(() => parts.value.every((part) => !partIsInvalid(part)))
const lastOptimizedSignature = ref<string | null>(null)
function partsSignature(list: CuttingPart[] = parts.value) {
  return JSON.stringify(
    list.map((part) => [
      part.material_id,
      part.material_source,
      part.follow_grain !== false,
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
    // A branch is mandatory: the catalog is scoped to the chosen workshop, so
    // there's nothing to optimise against until one is picked.
    !!activeBranchId.value &&
    parts.value.length > 0 &&
    hasPersistableParts.value &&
    totalQuantity.value <= MAX_PARTS &&
    !optimizedUnchanged.value,
)
const optimizeDisabledHint = computed(() => {
  if (!activeBranchId.value) return 'Avval ustaxona tanlang'
  if (parts.value.length === 0) return "Avval qism qo'shing"
  if (!hasPersistableParts.value) return "Qatorlardagi xatolarni to'g'rilang"
  if (totalQuantity.value > MAX_PARTS) return `${MAX_PARTS} donadan oshib ketdi`
  if (optimizedUnchanged.value) return "Natija allaqachon hisoblangan — qismni o'zgartiring"
  return ''
})
const totalQuantity = computed(() =>
  parts.value.reduce((sum, part) => sum + Math.max(0, Number(part.quantity) || 0), 0),
)
function blankPart(): CuttingPart {
  return {
    part_ref: crypto.randomUUID?.() ?? `part-${Date.now()}`,
    // Start with no material: the panel is a deliberate catalog choice, so the
    // row shows "Panel tanlang" / "Material tanlang" until the user picks one —
    // auto-selecting the first catalog panel silently risked the wrong material.
    material_id: '',
    material_source: 'shop',
    follow_grain: true,
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
  const code = partFitError(part.length_mm, part.width_mm, panel, part.follow_grain !== false)
  if (!code) return null
  const usableLength = panel.panel_length_mm - 2 * EDGE_TRIM_MM
  const usableWidth = panel.panel_width_mm - 2 * EDGE_TRIM_MM
  if (code === 'impossible_grain')
    return `Tekstura yo'nalishi qat'iy — qism ${usableLength}×${usableWidth} mm ichiga sig'ishi kerak (aylantirib bo'lmaydi).`
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
    return "Tekstura yo'nalishi bu qismni joylashtirishga to'sqinlik qiladi."
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

function openImportWizard() {
  importWizardOpen.value = true
}

function closeImportWizard() {
  importWizardOpen.value = false
  importReplaceConfirmOpen.value = false
  pendingImportedParts.value = null
}

function commitImportedParts(mode: ImportLoadMode, importedParts: CuttingPart[]) {
  parts.value = applyImportedParts(parts.value, importedParts, mode).map(normalizeSources)
  if (mode === 'replace') preferredEdgeByPart.value = {}
  optimizeError.value = null
  optimizeRowError.value = null
  clearSelection()
  importWizardOpen.value = false
}

function onImportLoad(payload: { mode: ImportLoadMode; parts: CuttingPart[] }) {
  if (payload.mode === 'replace' && parts.value.length > 0) {
    pendingImportedParts.value = payload.parts
    importReplaceConfirmOpen.value = true
    return
  }
  commitImportedParts(payload.mode, payload.parts)
}

function confirmImportReplace() {
  const importedParts = pendingImportedParts.value
  pendingImportedParts.value = null
  importReplaceConfirmOpen.value = false
  if (importedParts) commitImportedParts('replace', importedParts)
}

function cancelImportReplace() {
  pendingImportedParts.value = null
  importReplaceConfirmOpen.value = false
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

function setPanel(part: CuttingPart, value: string | null) {
  part.material_id = value ?? ''
}

function setFollowGrain(part: CuttingPart, value: boolean) {
  part.follow_grain = value
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

// The client flow no longer offers "I'll bring it" — every material is
// workshop-supplied. Legacy drafts saved with `own` parts/sides are coerced
// back to `shop` on hydration so the not-carried warnings and pricing read
// consistently; the next autosave persists the normalized snapshot.
function normalizeSources(part: CuttingPart): CuttingPart {
  const next: CuttingPart = { ...part, material_source: 'shop' }
  for (const side of edgeFields) {
    const band = next[side]
    if (band && band.source !== 'shop') next[side] = { ...band, source: 'shop' }
  }
  return next
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
    // second empty draft. In fixed-branch (workshop) mode the store seeds the
    // draft with the walk-in client + context branch; the client path passes no
    // args and the backend seeds the profile default.
    if (!pendingDraftId.value) {
      pendingDraftId.value = (
        await cutting.createDraft(
          fixedBranch.value ? { branchId: fixedBranch.value.id } : undefined,
        )
      ).id
    }
    const id = pendingDraftId.value
    await cutting.updateDraft(id, {
      parts_snapshot: parts.value,
      // Only send the branch when the user changed it — otherwise let the
      // backend's seed stand (profile default on the client path, the fixed
      // context branch on the workshop path).
      ...(branchTouched.value && !fixedBranch.value
        ? { preferred_branch_id: localBranchId.value }
        : {}),
    })
    await cutting.optimizeDraft(id)
    lastOptimizedSignature.value = partsSignature()
    // Hand off to the saved editor; the guard must not treat this as discarding.
    leavingAfterCreate.value = true
    await router.replace(rolePath(adapter.paths.editor(id)))
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
  // A branch is mandatory and the catalog is always scoped to it. With no branch
  // there's nothing to show — clear the options so a stale per-branch list can't
  // linger, and let the "pick a workshop" gate stand.
  const branchId = activeBranchId.value
  if (!branchId) {
    cutting.clearMaterials()
    return
  }
  await Promise.all([
    cutting.loadMaterials({ kind: 'panel', branchId, carriedOnly: false }),
    cutting.loadMaterials({ kind: 'edge', branchId, carriedOnly: false }),
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
        parts.value = value.parts_snapshot.map((part) =>
          normalizeSources({ ...part, follow_grain: part.follow_grain !== false }),
        )
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
    // Fixed-branch mode: the branch is the app context — skip the client-only
    // branch-options + profile-default seed and lock the pre-filter to it.
    if (fixedBranch.value) {
      localBranchId.value = fixedBranch.value.id
      selectedBranchId.value = fixedBranch.value.id
      await loadMaterials()
      return
    }
    // Unsaved editor: nothing to load. Populate the branch picker and seed the
    // pre-filter from the client's profile default (parity with a server draft).
    await cutting.loadBranchOptions()
    if (adapter.useProfileDefaultBranch) {
      const profile = await clientProfile.load().catch(() => null)
      localBranchId.value = profile?.preferred_branch_id ?? null
    }
    selectedBranchId.value = localBranchId.value
    await loadMaterials()
    return
  }
  // Reuse an already-loaded draft (e.g. just optimised from the new editor) to
  // avoid a load flash; otherwise fetch it.
  if (cutting.currentDraft?.id !== draftId.value) await cutting.loadDraft(draftId.value)
  // Branch options power the picker; in fixed-branch mode there's no picker and
  // no workshop branch-options endpoint, so skip the load.
  if (!fixedBranch.value) await cutting.loadBranchOptions()
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
        :to="rolePath(adapter.paths.orderDetail(String(boundOrderId)))"
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
        <!-- Walk-in identity strip (workshop scope only): staff always sees who
             the order is being created for. -->
        <section
          v-if="isWorkshopScope && cutting.walkInClient"
          class="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-hairline bg-elevated px-4 py-2.5 text-sm"
        >
          <span
            class="grid size-6 shrink-0 place-items-center rounded-md bg-accent-soft font-mono font-black text-accent"
            aria-hidden="true"
          >
            @
          </span>
          <div class="min-w-0 flex-1">
            <b class="text-ink">{{ cutting.walkInClient.name }}</b>
            <span class="ml-2 font-mono text-xs text-ink-muted">{{
              cutting.walkInClient.phone
            }}</span>
          </div>
        </section>

        <!-- Fixed-branch mode: a locked label, no picker (the branch is the app
             context and can't change mid-draft). -->
        <section
          v-if="fixedBranch"
          class="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-hairline bg-elevated px-4 py-2.5 text-sm text-ink-soft"
        >
          <span
            class="grid size-6 shrink-0 place-items-center rounded-md bg-info-soft font-mono font-black text-info"
            aria-hidden="true"
          >
            i
          </span>
          <div class="min-w-0 flex-1">
            <b class="text-ink">{{ fixedBranch.name }}</b>
          </div>
        </section>

        <template v-else>
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
              <b class="text-ink">
                {{
                  preferredBranch
                    ? `${preferredBranch.branch_name} · ${preferredBranch.workshop_name}`
                    : 'Ustaxona tanlanmagan'
                }}
              </b>
            </div>
            <button
              v-if="preferredBranch"
              type="button"
              class="mp-button mp-button-outline"
              @click="branchPickerOpen = true"
            >
              O'zgartirish
            </button>
            <p v-if="!preferredBranch" class="basis-full text-xs text-ink-muted">
              Kesish ro'yxati tanlangan ustaxona katalogi asosida tuziladi — davom etish uchun
              ustaxona tanlang.
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
        </template>

        <section class="client-card">
          <div class="client-card-h">
            <div>
              <h2>Qismlar ro'yxati</h2>
              <p class="mt-1 text-sm text-ink-muted">
                {{ parts.length }} qator · {{ totalQuantity }} dona
              </p>
            </div>
            <div v-if="!isReadOnly && activeBranchId" class="flex flex-wrap items-center gap-2">
              <div class="inline-flex rounded-lg border border-hairline bg-sunk p-1">
                <button
                  type="button"
                  class="rounded-md px-3 py-2 text-sm font-bold transition"
                  :class="
                    importWizardOpen
                      ? 'text-ink-muted hover:bg-elevated hover:text-ink'
                      : 'bg-elevated text-ink shadow-sm'
                  "
                  :aria-pressed="!importWizardOpen"
                  @click="importWizardOpen = false"
                >
                  Qo'lda kiritish
                </button>
                <button
                  type="button"
                  class="rounded-md px-3 py-2 text-sm font-bold transition"
                  :class="
                    importWizardOpen
                      ? 'bg-elevated text-ink shadow-sm'
                      : 'text-ink-muted hover:bg-elevated hover:text-ink'
                  "
                  :aria-pressed="importWizardOpen"
                  @click="openImportWizard"
                >
                  Fayldan yuklash
                </button>
              </div>
            </div>
          </div>

          <!-- Bulk bar: actions only — the row checkboxes already show what's
               selected, so a "N selected" counter would repeat them; the count
               still reads out via the group label and the bulk-dialog titles. -->
          <div
            v-if="selectedParts.length > 0"
            role="group"
            :aria-label="`${selectedParts.length} qism tanlandi — guruh amallari`"
            class="hidden flex-wrap items-center gap-x-5 gap-y-2 border-b border-accent-tint bg-accent-soft px-5 py-3 text-sm font-bold lg:flex"
          >
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

          <div v-if="!activeBranchId" class="client-card-b">
            <div class="client-empty">
              <div class="client-empty-icon"><Icon name="store" /></div>
              <h3>Avval ustaxona tanlang</h3>
              <p>
                Qism qo'shish uchun kesish qaysi ustaxonada bajarilishini tanlang — katalog o'sha
                ustaxona materiallaridan tuziladi.
              </p>
              <button
                type="button"
                class="mp-button mp-button-primary mt-4"
                @click="branchPickerOpen = true"
              >
                Ustaxona tanlash
              </button>
            </div>
          </div>

          <div v-else-if="parts.length === 0" class="client-card-b">
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
                class="grid grid-cols-[30px_30px_minmax(200px,1.4fr)_74px_82px_82px_66px_minmax(150px,1fr)_44px] items-center gap-2 text-[11px] font-extrabold uppercase tracking-wide text-ink-muted"
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
                <span aria-hidden="true">Tekstura</span>
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
              @update:follow-grain="setFollowGrain(part, $event)"
              @delete="deleteRow(index)"
              @open-edge-picker="openEdgePicker(part, $event)"
            />
            <!-- Add the next row where it appears: a dashed tile under the last
                 row, echoing the empty-state CTA. Replaces the header button so
                 the add affordance follows the content. -->
            <button
              type="button"
              class="flex min-h-12 items-center justify-center gap-2 rounded-lg border border-dashed border-hairline-strong text-sm font-bold text-ink-muted transition hover:border-accent hover:bg-accent-soft/40 hover:text-accent"
              @click="addRow"
            >
              <Icon name="plus" class="size-4" />
              Qism qo'shish
            </button>
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

          <div v-if="saveError" class="border-t border-hairline p-5">
            <p class="text-sm font-bold text-danger">{{ saveError }}</p>
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
        v-if="draft && (draft.results.length > 0 || optimizeError)"
        :draft="draft"
        :optimize-error="optimizeError"
        :checkout-path="adapter.paths.checkout(draft.id)"
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

    <CuttingImportWizard
      :open="importWizardOpen"
      :panel-choices="branchPanelChoices"
      :all-panel-choices="allPanelChoices"
      :edge-choices="edgeChoices"
      :all-edge-choices="allEdgeChoices"
      :has-existing-parts="parts.length > 0"
      :current-pieces="totalQuantity"
      :preferred-branch-name="preferredBranch?.branch_name ?? null"
      @close="closeImportWizard"
      @load="onImportLoad"
    />

    <ConfirmDialog
      :open="importReplaceConfirmOpen"
      title="Qismlarni almashtirish"
      :message="`Hozirgi ${parts.length} qator import qilingan ro'yxat bilan almashtirilsinmi? Bu amalni qaytarib bo'lmaydi.`"
      confirm-label="Almashtirish"
      cancel-label="Bekor qilish"
      danger
      @cancel="cancelImportReplace"
      @confirm="confirmImportReplace"
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
