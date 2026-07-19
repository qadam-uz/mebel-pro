<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import { RouterLink, onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'

import { ApiError, apiErrorCode } from '@/shared/api/client'
import { clientErrorLabel, draftDisplayName } from '@/shared/app/clientUi'
import { MAX_PARTS, MIN_PART_MM } from '@/shared/app/constants'
import {
  clientCuttingEditorAdapter,
  cuttingEditorAdapterKey,
  type CuttingEditorAdapterFactory,
} from '@/shared/app/cuttingEditorAdapter'
import { colorForMaterial, edgeFields, type EdgeField } from '@/shared/app/cuttingDisplay'
import { edgeTooNarrow } from '@/shared/app/cuttingEdgeDisplay'
import {
  deriveEdgeRegistry,
  edgeRegistryKey,
  groupCuttingParts,
  partDisplayName,
  syncEdgeAssignments,
  type EdgeRegistryEntry,
} from '@/shared/app/cuttingEditorDerived'
import { useDraftAutosave } from '@/shared/composables/useDraftAutosave'
import { useToast } from '@/shared/composables/useToast'
import Icon from '@/shared/components/AppIcon.vue'
import AppModal from '@/shared/components/AppModal.vue'
import { useRolePath } from '@/shared/app/paths'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import CuttingBranchPicker from '@/shared/components/CuttingBranchPicker.vue'
import CuttingEdgePickerModal from '@/shared/components/CuttingEdgePickerModal.vue'
import CuttingEdgeTapeRegistry from '@/shared/components/CuttingEdgeTapeRegistry.vue'
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
import type { OrderDetail } from '@/shared/stores/orders'
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
const localDraftName = ref<string | null>(null)
const draftNameEditing = ref(false)
const draftNameValue = ref('')
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
const importedLayoutWarningOpen = ref(false)
const importedLayoutWarningAccepted = ref(false)
const collapsedGroupKeys = ref<Set<string>>(new Set())
const errorFilterEnabled = ref(false)
const registryPickerOpen = ref(false)
const registryReplaceEntry = ref<EdgeRegistryEntry | null>(null)
const registryPickedEdgeId = ref<string | null>(null)
const activeResultId = ref<string | null>(null)
const activePanelId = ref<string | null>(null)
const preferredEdgeByPart = ref<Record<string, string>>({})
const edgeAssignments = ref(new Map<string, number>())
const edgePickerPart = ref<CuttingPart | null>(null)
const edgePickerInitialSide = ref<EdgeField | null>(null)
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
// Revision mode (orders.md "Revising a placed order"): the draft edits a placed
// order — the strip and the results CTA switch to the revision flow. The order
// context loads lazily and non-fatally; the editor works without it.
const revisionOrderId = computed(() => draft.value?.revision_of_order_id ?? null)
const revisionOrder = ref<OrderDetail | null>(null)
watch(
  revisionOrderId,
  async (value) => {
    if (!value || !adapter.orderRevision) {
      revisionOrder.value = null
      return
    }
    if (revisionOrder.value?.id === value) return
    revisionOrder.value = await adapter.orderRevision.loadOrder(value).catch(() => null)
  },
  { immediate: true },
)
const hasImportedMapResult = computed(
  () =>
    draft.value?.results.some(
      (result) => result.source === 'imported_map' && result.status === 'candidate',
    ) ?? false,
)
// The active branch pre-filter: the local pick while unsaved, the draft's saved
// preference otherwise. Every branch-dependent read routes through this.
const activeBranchId = computed(() => {
  // Fixed-branch mode locks an UNSAVED editor to the app context; a saved
  // workshop draft prefers its own frozen branch — a revision draft is locked
  // to the order's branch, which may differ from the current topbar context.
  if (isNewDraft.value) return fixedBranch.value?.id ?? localBranchId.value
  return draft.value?.preferred_branch_id ?? fixedBranch.value?.id ?? null
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
  if (!hasPersistableParts.value) return "To'ldirilmagan qatorlarni to'ldiring"
  if (totalQuantity.value > MAX_PARTS) return `${MAX_PARTS} donadan oshib ketdi`
  if (optimizedUnchanged.value) return "Natija allaqachon hisoblangan — qismni o'zgartiring"
  return ''
})
const totalQuantity = computed(() =>
  parts.value.reduce((sum, part) => sum + Math.max(0, Number(part.quantity) || 0), 0),
)
const totalAreaM2 = computed(() =>
  parts.value.reduce(
    (sum, part) =>
      sum +
      (Math.max(0, Number(part.length_mm) || 0) *
        Math.max(0, Number(part.width_mm) || 0) *
        Math.max(0, Number(part.quantity) || 0)) /
        1_000_000,
    0,
  ),
)
const materialCount = computed(
  () => new Set(parts.value.map((part) => part.material_id).filter(Boolean)).size,
)

function blankPart(previous?: CuttingPart | null): CuttingPart {
  return {
    part_ref: crypto.randomUUID?.() ?? `part-${Date.now()}`,
    name: null,
    // Start with no material: the panel is a deliberate catalog choice, so the
    // row shows "Panel tanlang" / "Material tanlang" until the user picks one —
    // auto-selecting the first catalog panel silently risked the wrong material.
    material_id: previous?.material_id ?? '',
    material_source: 'shop',
    follow_grain: previous?.follow_grain ?? true,
    length_mm: 0,
    width_mm: 0,
    quantity: 0,
    edge_top: previous?.edge_top ? { ...previous.edge_top } : null,
    edge_bottom: previous?.edge_bottom ? { ...previous.edge_bottom } : null,
    edge_left: previous?.edge_left ? { ...previous.edge_left } : null,
    edge_right: previous?.edge_right ? { ...previous.edge_right } : null,
  }
}

function materialById(id: string | null | undefined) {
  return cutting.panelOptions.find((material) => material.id === id) ?? null
}

function edgeById(id: string | null | undefined) {
  return cutting.edgeOptions.find((material) => material.id === id) ?? null
}

const edgeRegistry = computed(() => deriveEdgeRegistry(parts.value, edgeAssignments.value))
const edgeAssignmentEntries = computed(() => [...edgeAssignments.value.entries()])
const groupedParts = computed(() =>
  groupCuttingParts(parts.value, (materialId) => materialLabel(materialById(materialId))),
)
const errorCount = computed(
  () => parts.value.filter((part, index) => rowHasError(part, index)).length,
)
const visibleGroups = computed(() =>
  groupedParts.value
    .map((group) => ({
      ...group,
      parts: errorFilterEnabled.value
        ? group.parts.filter(({ part, index }) => rowHasError(part, index))
        : group.parts,
    }))
    .filter((group) => group.parts.length > 0),
)
const displayPartIndex = computed(() => {
  const positions = new Map<string, number>()
  let position = 0
  for (const group of groupedParts.value) {
    for (const { part } of group.parts) positions.set(part.part_ref, position++)
  }
  return positions
})

function edgeRegistryLabel(materialId: string) {
  return edgeById(materialId)?.name ?? materialId
}

function groupEdgeRegistryEntries(group: { parts: Array<{ part: CuttingPart }> }) {
  const keys = new Set<string>()
  for (const { part } of group.parts) {
    for (const side of edgeFields) {
      const band = part[side]
      if (band?.material_id) keys.add(edgeRegistryKey(band.material_id, band.source))
    }
  }
  return edgeRegistry.value.filter((entry) => keys.has(entry.key))
}

function edgeIdsForParts(rows: CuttingPart[]) {
  const counts = new Map<string, { count: number; firstSeen: number }>()
  let order = 0
  for (const row of rows) {
    for (const side of edgeFields) {
      const materialId = row[side]?.material_id
      if (!materialId) continue
      const existing = counts.get(materialId)
      if (existing) existing.count += 1
      else {
        counts.set(materialId, { count: 1, firstSeen: order })
        order += 1
      }
    }
  }
  return [...counts.entries()]
    .sort((left, right) => right[1].count - left[1].count || left[1].firstSeen - right[1].firstSeen)
    .map(([materialId]) => materialId)
}

function groupEdgeIds(part: CuttingPart | null) {
  if (!part?.material_id) return []
  return edgeIdsForParts(parts.value.filter((row) => row.material_id === part.material_id))
}

function otherGroupEdgeIds(part: CuttingPart | null) {
  if (!part?.material_id) return []
  return edgeIdsForParts(parts.value.filter((row) => row.material_id !== part.material_id))
}

function edgeRegistryEntryForPartNumber(part: CuttingPart, number: number) {
  const groupRows = parts.value
    .filter((row) => row.material_id === part.material_id)
    .map((row) => ({ part: row }))
  return groupEdgeRegistryEntries({ parts: groupRows }).find((entry) => entry.number === number)
}

function applyEdgeNumberToPartSide(part: CuttingPart, side: EdgeField, number: number) {
  const entry = edgeRegistryEntryForPartNumber(part, number)
  if (!entry) return
  part[side] = { material_id: entry.materialId, source: entry.source }
  rememberEdgeMaterial(part, entry.materialId)
}

function edgeRegistryNarrowWarning(entry: EdgeRegistryEntry) {
  const edge = edgeById(entry.materialId)
  if (!edge) return null
  for (const part of parts.value) {
    const usesEdge = edgeFields.some(
      (side) => part[side]?.material_id === entry.materialId && part[side]?.source === entry.source,
    )
    if (!usesEdge) continue
    const panel = materialById(part.material_id)
    const panelThickness = Number(panel?.thickness_mm)
    if (Number.isFinite(panelThickness) && edgeTooNarrow(panelThickness, edge)) {
      return `Lenta eni (${edge.edge_width_mm} mm) panel qalinligidan (${panelThickness} mm) tor — qirrani to'liq yopmaydi.`
    }
  }
  return null
}

function groupErrorCount(groupKey: string) {
  const group = groupedParts.value.find((item) => item.key === groupKey)
  return group?.parts.filter(({ part, index }) => rowHasError(part, index)).length ?? 0
}

function toggleGroup(groupKey: string) {
  const next = new Set(collapsedGroupKeys.value)
  if (next.has(groupKey)) next.delete(groupKey)
  else next.add(groupKey)
  collapsedGroupKeys.value = next
}

watch(errorCount, (count) => {
  if (count === 0) errorFilterEnabled.value = false
})

watch(
  parts,
  (rows) => {
    syncEdgeAssignments(edgeAssignments.value, rows)
    edgeAssignments.value = new Map(edgeAssignments.value)
  },
  { deep: true, immediate: true },
)

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

function addRow(
  materialId?: string,
  previous?: CuttingPart | null,
  afterIndex = parts.value.length - 1,
) {
  const row = blankPart(previous ?? parts.value[parts.value.length - 1] ?? null)
  if (materialId) row.material_id = materialId
  const insertionIndex = Math.max(-1, Math.min(afterIndex, parts.value.length - 1)) + 1
  parts.value = [...parts.value.slice(0, insertionIndex), row, ...parts.value.slice(insertionIndex)]
  void nextTick(() => focusCell(insertionIndex, 'name'))
}

function duplicateRow(index: number) {
  const source = parts.value[index]
  if (!source) return
  const copy: CuttingPart = {
    ...source,
    part_ref: crypto.randomUUID?.() ?? `part-${Date.now()}`,
    edge_top: source.edge_top ? { ...source.edge_top } : null,
    edge_bottom: source.edge_bottom ? { ...source.edge_bottom } : null,
    edge_left: source.edge_left ? { ...source.edge_left } : null,
    edge_right: source.edge_right ? { ...source.edge_right } : null,
  }
  parts.value = [...parts.value.slice(0, index + 1), copy, ...parts.value.slice(index + 1)]
  void nextTick(() => focusCell(index + 1, 'length'))
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
    const label = partDisplayName(removed, index)
    toast.action(
      `«${label}» o'chirildi`,
      'Qaytarish',
      () => {
        parts.value = [...parts.value.slice(0, index), removed, ...parts.value.slice(index)]
      },
      'warn',
      6000,
    )
  }
}

function setPartName(part: CuttingPart, value: string | null) {
  part.name = value
}

type CellName = 'name' | 'length' | 'width' | 'quantity' | 'edge'
const cellOrder: CellName[] = ['name', 'length', 'width', 'quantity']
const edgeCellOrder: EdgeField[] = ['edge_top', 'edge_bottom', 'edge_left', 'edge_right']

function focusCell(index: number, cell: CellName, side?: EdgeField) {
  const selector =
    cell === 'edge' && side
      ? `[data-part-index="${index}"][data-cell="edge"][data-edge-side="${side}"]`
      : `[data-part-index="${index}"][data-cell="${cell}"]`
  const target = document.querySelector<HTMLElement>(selector)
  target?.focus()
  if (target instanceof HTMLInputElement && cell !== 'name') {
    const end = target.value.length
    target.setSelectionRange(end, end)
  }
}

function onCellEnter(index: number, cell: CellName, side?: EdgeField) {
  if (cell === 'edge' && side) {
    const currentSide = edgeCellOrder.indexOf(side)
    if (currentSide >= 0 && currentSide < edgeCellOrder.length - 1) {
      focusCell(index, 'edge', edgeCellOrder[currentSide + 1])
      return
    }
  }
  const currentCell = cellOrder.indexOf(cell)
  if (currentCell < cellOrder.length - 1) {
    focusCell(index, cellOrder[currentCell + 1])
    return
  }
  const current = parts.value[index]
  const next = parts.value[index + 1]
  // A quantity finishes its material block. Keep rapid entry within that
  // material even when another material block follows it in the full draft.
  if (!current || !next || next.material_id !== current.material_id) {
    addRow(current?.material_id, current, index)
    return
  }
  focusCell(index + 1, 'name')
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

function onImportCommitted(nextDraftId: string) {
  importWizardOpen.value = false
  importReplaceConfirmOpen.value = false
  pendingImportedParts.value = null
  leavingAfterCreate.value = true
  void router.replace(rolePath(adapter.paths.editor(nextDraftId)))
}

// --- Bulk selection (desktop power-feature) --------------------------------
// Select rows, then apply edges / change material / delete in one action so
// banding or re-materialing many identical parts isn't N modal round-trips.
const selectedRefs = ref<Set<string>>(new Set())
const selectedParts = computed(() =>
  parts.value.filter((part) => selectedRefs.value.has(part.part_ref)),
)
const bulkEdgeMode = ref(false)
type MaterialPickerTarget =
  | { type: 'part'; partRef: string }
  | { type: 'group'; key: string }
  | { type: 'bulk' }
  | { type: 'new' }
const materialPickerTarget = ref<MaterialPickerTarget | null>(null)

function toggleSelect(partRef: string) {
  const next = new Set(selectedRefs.value)
  if (next.has(partRef)) next.delete(partRef)
  else next.add(partRef)
  selectedRefs.value = next
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
  edgePickerInitialSide.value = null
  edgeReturnFocus = null
}
function openBulkMaterial() {
  if (selectedParts.value.length === 0) return
  materialPickerTarget.value = { type: 'bulk' }
}

function openNewMaterial() {
  materialPickerTarget.value = { type: 'new' }
}

function openGroupMaterial(group: { key: string }) {
  materialPickerTarget.value = { type: 'group', key: group.key }
}

function addGroupRow(group: { materialId: string | null; parts: Array<{ part: CuttingPart }> }) {
  if (!group.materialId) return openNewMaterial()
  const last = group.parts[group.parts.length - 1]?.part ?? null
  const lastIndex = last ? parts.value.findIndex((part) => part.part_ref === last.part_ref) : -1
  addRow(group.materialId, last, lastIndex)
}

function openPartMaterial(part: CuttingPart) {
  materialPickerTarget.value = { type: 'part', partRef: part.part_ref }
}

function closeMaterialPicker() {
  materialPickerTarget.value = null
}

const materialPickerMaterials = computed(() => {
  const seen = new Set<string>()
  return panelChoices.value
    .map((choice) => cutting.panelOptions.find((material) => material.id === choice.value))
    .filter((material): material is ClientCatalogMaterialOption => {
      if (!material || seen.has(material.id)) return false
      seen.add(material.id)
      return true
    })
})

const materialPickerCurrentId = computed(() => {
  const target = materialPickerTarget.value
  if (!target) return null
  if (target.type === 'part') {
    return parts.value.find((part) => part.part_ref === target.partRef)?.material_id ?? null
  }
  if (target.type === 'group') {
    const group = groupedParts.value.find((item) => item.key === target.key)
    return group?.materialId ?? null
  }
  if (target.type === 'new') return null
  return selectedParts.value[0]?.material_id ?? null
})

const materialPickerSubtitle = computed(() => {
  const target = materialPickerTarget.value
  if (!target) return ''
  if (target.type === 'part') {
    const index = parts.value.findIndex((part) => part.part_ref === target.partRef)
    const part = parts.value[index]
    return part ? `«${partDisplayName(part, index)}» detali uchun` : 'Detal uchun'
  }
  if (target.type === 'group') {
    const count = groupedParts.value.find((item) => item.key === target.key)?.parts.length ?? 0
    return `Ushbu guruhdagi ${count} detal uchun`
  }
  if (target.type === 'new') return 'Material tanlang'
  return `Tanlangan ${selectedParts.value.length} ta detal uchun`
})

function applyMaterialPicker(materialId: string) {
  const target = materialPickerTarget.value
  if (!target) return
  if (target.type === 'new') {
    const existing = groupedParts.value.find((group) => group.materialId === materialId)
    if (existing) addGroupRow(existing)
    else addRow(materialId, null)
  } else if (target.type === 'part') {
    const part = parts.value.find((item) => item.part_ref === target.partRef)
    if (part) part.material_id = materialId
  } else if (target.type === 'group') {
    const group = groupedParts.value.find((item) => item.key === target.key)
    if (!group) return
    for (const { part } of group.parts) {
      part.material_id = materialId
    }
  } else {
    for (const part of selectedParts.value) {
      part.material_id = materialId
    }
  }
  closeMaterialPicker()
}

function materialPickerGrainLabel(material: ClientCatalogMaterialOption) {
  return material.grain_direction ? 'Teksturali material' : 'Teksturasiz material'
}

function materialPickerSwatchStyle(material: ClientCatalogMaterialOption) {
  return {
    background: colorForMaterial(material.color ?? material.name ?? material.id),
  }
}

function openRegistryReplace(entry: EdgeRegistryEntry) {
  registryReplaceEntry.value = entry
  registryPickedEdgeId.value = entry.materialId
  registryPickerOpen.value = true
}

function closeRegistryPicker() {
  registryPickerOpen.value = false
  registryReplaceEntry.value = null
  registryPickedEdgeId.value = null
}

function applyRegistryPicker() {
  const materialId = registryPickedEdgeId.value
  const entry = registryReplaceEntry.value
  if (!materialId || !entry) return
  for (const part of parts.value) {
    for (const side of edgeFields) {
      const band = part[side]
      if (band?.material_id === entry.materialId && band.source === entry.source) {
        part[side] = { ...band, material_id: materialId }
      }
    }
  }
  closeRegistryPicker()
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

function openEdgePicker(part: CuttingPart, event?: Event, side?: EdgeField) {
  // The modal seeds its own working selection from `part`; the editor only records
  // which part is open and the element to restore focus to on close.
  edgePickerPart.value = part
  edgePickerInitialSide.value = side ?? null
  edgeReturnFocus = event?.currentTarget instanceof HTMLElement ? event.currentTarget : null
}

function closeEdgePicker() {
  edgePickerPart.value = null
  edgePickerInitialSide.value = null
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
// back to `shop` on hydration; when that changed anything, hydration schedules
// a save so the SERVER snapshot matches what the user sees — optimise/order
// price the persisted snapshot, and a display-only rewrite would invisibly
// bill legacy parts as client-supplied (no material charge).
function normalizeSources(part: CuttingPart): CuttingPart {
  const next: CuttingPart = { ...part, material_source: 'shop' }
  for (const side of edgeFields) {
    const band = next[side]
    if (band && band.source !== 'shop') next[side] = { ...band, source: 'shop' }
  }
  return next
}

function hasLegacyOwnSources(snapshot: CuttingPart[]) {
  return snapshot.some(
    (part) =>
      part.material_source !== 'shop' ||
      edgeFields.some((side) => {
        const band = part[side]
        return Boolean(band && band.source !== 'shop')
      }),
  )
}

let importedLayoutWarningResolve: ((allow: boolean) => void) | null = null

function resolveImportedLayoutWarning(allow: boolean) {
  importedLayoutWarningOpen.value = false
  if (allow) importedLayoutWarningAccepted.value = true
  importedLayoutWarningResolve?.(allow)
  importedLayoutWarningResolve = null
}

function confirmImportedLayoutMutation() {
  if (!hasImportedMapResult.value || importedLayoutWarningAccepted.value) {
    return Promise.resolve(true)
  }
  importedLayoutWarningOpen.value = true
  return new Promise<boolean>((resolve) => {
    importedLayoutWarningResolve = resolve
  })
}

// Debounced autosave (700ms) — the timing core, status mirror, don't-persist gate,
// the deep `parts` watch, and the CB-15 hydration guard all live in the
// `useDraftAutosave` composable (CB-93 seam). The gate skips incomplete/out-of-bounds
// rows (they show their own inline validation) and a read-only bound draft.
const autosave = useDraftAutosave({
  parts,
  persist: async () => {
    const allowMutation = await confirmImportedLayoutMutation()
    if (!allowMutation) {
      const snapshot = draft.value?.parts_snapshot ?? []
      autosave.hydrate(() => {
        parts.value = snapshot.map((part) =>
          normalizeSources({ ...part, follow_grain: part.follow_grain !== false }),
        )
      })
      return
    }
    await cutting.updateDraft(draftId.value, { parts_snapshot: parts.value })
  },
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

function beginDraftNameEdit() {
  if (isReadOnly.value) return
  draftNameValue.value = isNewDraft.value ? (localDraftName.value ?? '') : (draft.value?.name ?? '')
  draftNameEditing.value = true
}

async function commitDraftName() {
  if (!draftNameEditing.value) return
  draftNameEditing.value = false
  const name = draftNameValue.value.trim() || null
  if (isNewDraft.value) {
    localDraftName.value = name
    return
  }
  if (name !== draft.value?.name) await cutting.updateDraft(draftId.value, { name })
}

function cancelDraftNameEdit() {
  draftNameEditing.value = false
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
      ...(localDraftName.value !== null ? { name: localDraftName.value } : {}),
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
      const needsNormalization = hasLegacyOwnSources(value.parts_snapshot)
      importedLayoutWarningAccepted.value = false
      autosave.hydrate(() => {
        edgeAssignments.value = new Map()
        parts.value = value.parts_snapshot.map((part) =>
          normalizeSources({ ...part, follow_grain: part.follow_grain !== false }),
        )
        hydratedDraftId = value.id
      })
      // Normalization diverged from the server copy — persist it (debounced;
      // optimise flushes first) instead of marking the draft already-saved.
      // schedule() itself skips read-only bound drafts. Runs a tick later so
      // hydrate()'s watch suppression has lifted.
      if (needsNormalization) {
        void nextTick(() => {
          autosave.schedule()
        })
      }
    }
    if (!value.results.some((result) => result.source === 'imported_map')) {
      importedLayoutWarningAccepted.value = false
    }
    activeResultId.value = value.chosen_result_id ?? value.results[0]?.id ?? null
    // Only an OPTIMIZER-sourced result counts as "already optimized for these
    // parts" — an imported_map result (the map-import flow's kept layout) must
    // never block running our optimizer for the first time on the same parts.
    const optimizerResult = value.results.find((result) => result.source === 'optimizer')
    lastOptimizedSignature.value = optimizerResult
      ? partsSignature(optimizerResult.parts_snapshot)
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
    if (!localBranchId.value) branchPickerOpen.value = true
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
  if (!selectedBranchId.value) branchPickerOpen.value = true
  await loadMaterials()
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', onBeforeUnload)
  // Flush a debounced edit before teardown so navigating away within the 700ms
  // window doesn't silently drop it (CB-15). The store action outlives the
  // component, so the PATCH still completes.
  if (hasImportedMapResult.value && !importedLayoutWarningAccepted.value) return
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
        <!-- Revision strip: this draft edits a placed order (orders.md
             "Revising a placed order") — always name the order being revised. -->
        <section
          v-if="isWorkshopScope && revisionOrderId"
          class="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-hairline bg-elevated px-4 py-2.5 text-sm"
        >
          <span
            class="grid size-6 shrink-0 place-items-center rounded-md bg-accent-soft text-accent"
            aria-hidden="true"
          >
            <Icon name="pencil" class="size-4" />
          </span>
          <div class="min-w-0 flex-1">
            <b class="text-ink">
              {{
                revisionOrder
                  ? `${revisionOrder.order_number} tahrirlanmoqda`
                  : 'Buyurtma tahrirlanmoqda'
              }}
            </b>
            <span v-if="revisionOrder" class="ml-2 text-xs text-ink-muted">{{
              revisionOrder.contact_name
            }}</span>
          </div>
          <RouterLink
            :to="rolePath(adapter.paths.orderDetail(String(revisionOrderId)))"
            class="text-xs font-bold text-accent"
          >
            Buyurtmaga qaytish →
          </RouterLink>
        </section>

        <!-- Walk-in identity strip (workshop scope only): staff always sees who
             the order is being created for. -->
        <section
          v-if="isWorkshopScope && cutting.walkInClient && !revisionOrderId"
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
            <!-- A revision is locked to the ORDER's branch, which may differ
                 from the topbar context the adapter froze at mount. -->
            <b class="text-ink">{{
              revisionOrder ? revisionOrder.branch_name : fixedBranch.name
            }}</b>
          </div>
        </section>

        <template v-else>
          <section class="mb-3 flex items-center gap-2">
            <input
              v-if="draftNameEditing"
              v-model="draftNameValue"
              class="mp-input max-w-sm"
              maxlength="64"
              placeholder="Chizmaga nom bering"
              autofocus
              @keydown.enter.prevent="commitDraftName"
              @keydown.esc.prevent="cancelDraftNameEdit"
              @blur="commitDraftName"
            />
            <button
              v-else-if="!isReadOnly"
              type="button"
              class="border-b border-dashed border-ink-muted text-left text-lg font-bold text-ink"
              @click="beginDraftNameEdit"
              @keydown.enter.prevent="beginDraftNameEdit"
              @keydown.space.prevent="beginDraftNameEdit"
            >
              <span>{{
                isNewDraft
                  ? localDraftName || 'Nomsiz chizma'
                  : draft
                    ? draftDisplayName(draft)
                    : 'Nomsiz chizma'
              }}</span>
              <Icon name="pencil" class="inline size-4 text-ink-muted" />
            </button>
            <span v-else class="text-lg font-bold text-ink">{{
              draft ? draftDisplayName(draft) : 'Nomsiz chizma'
            }}</span>
          </section>
          <section
            v-if="preferredBranch && !branchPickerOpen"
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
                {{ `${preferredBranch.branch_name} · ${preferredBranch.workshop_name}` }}
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
          </section>
        </template>

        <section class="client-card">
          <div class="client-card-h">
            <div>
              <h2>Detallar</h2>
              <p class="mt-1 text-sm text-ink-muted">
                {{ totalQuantity }} detal · {{ materialCount }} material · ~{{
                  totalAreaM2.toFixed(1)
                }}
                m²
              </p>
            </div>
            <div v-if="!isReadOnly && activeBranchId" class="flex flex-wrap items-center gap-2">
              <button
                v-if="errorCount > 0"
                type="button"
                class="mp-chip bg-danger-soft text-danger"
                :aria-pressed="errorFilterEnabled"
                @click="errorFilterEnabled = !errorFilterEnabled"
              >
                {{ errorCount }} to'ldirilmagan
              </button>
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
                  Fayldan import
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
              <h3>Avval filial tanlang</h3>
              <p>Materiallar va narxlar filialga qarab farq qiladi — avval filialni tanlang.</p>
              <button
                type="button"
                class="mp-button mp-button-primary mt-4"
                @click="branchPickerOpen = true"
              >
                Filial tanlash
              </button>
            </div>
          </div>

          <div v-else-if="parts.length === 0" class="client-card-b">
            <div class="client-empty">
              <div class="client-empty-icon"><Icon name="plus" /></div>
              <h3>Bu chizmada qism yo'q</h3>
              <p>Kesish ro'yxatini boshlash uchun avval materialni tanlang.</p>
              <button
                type="button"
                class="mp-button mp-button-primary mt-4"
                @click="openNewMaterial"
              >
                + Material tanlash
              </button>
            </div>
          </div>

          <div v-else class="@container grid gap-3 p-4">
            <!-- Desktop column header: same border + p-3 + grid template as a
                 CuttingPartRow card, so the columns line up; hidden below the
                 single-row fit width, where each row keeps its own field labels.
                 The leading cell is a real select-all checkbox; the rest are
                 decorative labels. A container query (not a viewport breakpoint)
                 because this view is embedded both full-width (client) and next
                 to a persistent workshop sidebar — the same viewport width maps
                 to different available row widths in each shell. -->
            <div class="hidden border-b border-hairline bg-sunk px-3 py-2 @min-[680px]:block">
              <div
                class="grid grid-cols-[28px_minmax(150px,50%)_repeat(6,minmax(32px,1fr))] items-center gap-1.5 text-[11px] font-extrabold text-ink-muted"
              >
                <span aria-hidden="true" class="text-center">#</span>
                <span aria-hidden="true" class="text-center">Nomi</span>
                <span aria-hidden="true" class="text-center">Bo'y</span>
                <span aria-hidden="true" class="text-center">Eni</span>
                <span aria-hidden="true" class="text-center">Soni</span>
                <span aria-hidden="true" class="text-center">Tola</span>
                <span aria-hidden="true" class="text-center">Krom</span>
                <span aria-hidden="true"></span>
              </div>
            </div>
            <section
              v-for="group in visibleGroups"
              :key="group.key"
              class="overflow-visible rounded-lg border border-hairline bg-sunk/40"
            >
              <div
                class="sticky top-0 z-10 flex flex-wrap items-center gap-2 border-b border-hairline bg-elevated px-3 py-2"
              >
                <button
                  type="button"
                  class="flex min-w-0 flex-1 flex-wrap items-center justify-between gap-3 text-left"
                  @click="toggleGroup(group.key)"
                >
                  <span class="flex min-w-0 items-center gap-3">
                    <Icon
                      :name="collapsedGroupKeys.has(group.key) ? 'chevron-right' : 'chevron-down'"
                      class="size-4 shrink-0 text-ink-muted"
                      aria-hidden="true"
                    />
                    <span
                      class="size-3 shrink-0 rounded-full"
                      :style="{
                        background: group.materialId
                          ? colorForMaterial(group.label)
                          : 'var(--color-ink-muted)',
                      }"
                      aria-hidden="true"
                    ></span>
                    <button
                      v-if="!isReadOnly && group.materialId"
                      type="button"
                      class="min-w-0 truncate border-b border-dashed border-ink-muted text-left text-sm font-extrabold text-ink hover:border-accent hover:text-accent"
                      @click.stop="openGroupMaterial(group)"
                    >
                      {{ group.label }}
                    </button>
                    <span v-else class="min-w-0 truncate text-sm font-extrabold text-ink">{{
                      group.label
                    }}</span>
                  </span>
                  <span class="flex items-center gap-2 text-xs font-bold text-ink-muted">
                    <span>{{ group.quantity }} detal · {{ group.areaM2.toFixed(1) }} m²</span>
                    <span
                      v-if="groupErrorCount(group.key) > 0"
                      class="rounded-md bg-danger-soft px-2 py-1 text-danger"
                    >
                      {{ groupErrorCount(group.key) }} to'ldirilmagan
                    </span>
                  </span>
                </button>
                <button
                  v-if="!isReadOnly"
                  type="button"
                  class="inline-flex min-h-9 items-center gap-1.5 rounded-md border border-hairline bg-elevated px-3 text-xs font-bold text-ink-muted transition hover:border-accent-tint hover:text-accent"
                  @click="addGroupRow(group)"
                >
                  <Icon name="plus" class="size-3.5" />
                  Detal
                </button>
              </div>
              <div
                v-if="groupEdgeRegistryEntries(group).length > 0"
                class="border-t border-hairline px-3 pb-2 pt-1.5"
              >
                <CuttingEdgeTapeRegistry
                  :entries="groupEdgeRegistryEntries(group)"
                  :label-for-material="edgeRegistryLabel"
                  :narrow-warning-for-entry="edgeRegistryNarrowWarning"
                  @replace="openRegistryReplace"
                />
              </div>
              <div v-if="!collapsedGroupKeys.has(group.key)" class="overflow-visible bg-elevated">
                <CuttingPartRow
                  v-for="{ part, index } in group.parts"
                  :key="part.part_ref"
                  :part="part"
                  :index="index"
                  :display-index="displayPartIndex.get(part.part_ref)"
                  :has-error="rowHasError(part, index)"
                  :size-error="partSizeError(part)"
                  :material-missing="rowMaterialMissing(part)"
                  :optimize-error="rowOptimizeError(part, index)"
                  :not-carried="rowNotCarried(part)"
                  :preferred-branch-name="preferredBranch?.branch_name ?? 'tanlangan filial'"
                  :edge-registry="edgeRegistry"
                  @toggle-select="toggleSelect(part.part_ref)"
                  @update:name="setPartName(part, $event)"
                  @update:length="part.length_mm = $event"
                  @update:width="part.width_mm = $event"
                  @update:quantity="part.quantity = $event"
                  @update:follow-grain="setFollowGrain(part, $event)"
                  @duplicate="duplicateRow(index)"
                  @cell-enter="(cell, side) => onCellEnter(index, cell, side)"
                  @delete="deleteRow(index)"
                  @open-edge-picker="(event, side) => openEdgePicker(part, event, side)"
                  @apply-edge-number="
                    (side, number) => applyEdgeNumberToPartSide(part, side, number)
                  "
                  @open-material-picker="openPartMaterial(part)"
                />
              </div>
            </section>
            <!-- Add the next row where it appears: a dashed tile under the last
                 row, echoing the empty-state CTA. Replaces the header button so
                 the add affordance follows the content. -->
            <button
              type="button"
              class="flex min-h-12 items-center justify-center gap-2 rounded-lg border border-dashed border-hairline-strong text-sm font-bold text-ink-muted transition hover:border-accent hover:bg-accent-soft/40 hover:text-accent"
              @click="openNewMaterial"
            >
              <Icon name="plus" class="size-4" />
              Boshqa material
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
        :checkout-path="
          revisionOrderId && adapter.orderRevision
            ? adapter.orderRevision.reviewPath(draft.id)
            : adapter.paths.checkout(draft.id)
        "
        :checkout-label="revisionOrderId ? 'O\'zgarishlarni saqlash' : undefined"
        :branch-id="activeBranchId"
        :quote-for-draft="adapter.quoteForDraft"
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
      :preferred-branch-id="activeBranchId"
      @close="closeImportWizard"
      @load="onImportLoad"
      @committed="onImportCommitted"
    />
    <AppModal
      :open="branchPickerOpen"
      title="Filialni tanlang"
      max-width="max-w-2xl"
      @close="closeBranchPicker"
    >
      <CuttingBranchPicker
        :model-value="selectedBranchId"
        :options="cutting.branchOptions"
        @update:model-value="setPreferredBranch"
      />
    </AppModal>

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
      :open="importedLayoutWarningOpen"
      title="Import qilingan joylashuv bekor bo'ladi"
      message="Detallar o'zgartirilsa, fayldan olingan joylashuv o'chiriladi. Yangi joylashuv olish uchun qayta optimallashtiring."
      confirm-label="O'zgartirish"
      cancel-label="Bekor qilish"
      danger
      @cancel="resolveImportedLayoutWarning(false)"
      @confirm="resolveImportedLayoutWarning(true)"
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
      :initial-side="edgePickerInitialSide"
      :part-number="edgePickerPart ? parts.indexOf(edgePickerPart) + 1 : 0"
      :title-suffix="bulkEdgeMode ? `${selectedParts.length} qismga` : undefined"
      :preferred-edge-id="edgePickerPart ? preferredEdgeId(edgePickerPart) : null"
      :edge-registry="edgeRegistry"
      :edge-assignment-entries="edgeAssignmentEntries"
      :group-edge-ids="groupEdgeIds(edgePickerPart)"
      :other-group-edge-ids="otherGroupEdgeIds(edgePickerPart)"
      :preferred-branch-id="activeBranchId"
      :preferred-branch-name="preferredBranch?.branch_name ?? 'tanlangan filial'"
      @apply="onEdgePickerApply"
      @close="closeEdgePicker"
    />

    <div
      v-if="registryPickerOpen"
      class="fixed inset-0 z-[70] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Kromka tanlash"
      @keydown.esc="closeRegistryPicker"
    >
      <div
        class="absolute inset-0 bg-[rgb(15_27_45_/_45%)] backdrop-blur-[2px]"
        @click="closeRegistryPicker"
      ></div>
      <div
        class="relative z-10 w-[min(420px,100%)] rounded-2xl border border-hairline bg-elevated p-5 shadow-[0_28px_60px_-14px_rgb(15_27_45_/_30%)]"
      >
        <div class="mb-3 flex items-start justify-between gap-3">
          <div>
            <h3 class="font-serif text-lg font-semibold text-ink">Kromka almashtirish</h3>
            <p v-if="registryReplaceEntry" class="mt-1 text-sm text-ink-muted">
              {{ edgeRegistryLabel(registryReplaceEntry.materialId) }} ishlatilgan tomonlar
              almashtiriladi.
            </p>
          </div>
          <button
            type="button"
            class="client-edge-close"
            aria-label="Yopish"
            @click="closeRegistryPicker"
          >
            ×
          </button>
        </div>
        <SearchCombobox
          :model-value="registryPickedEdgeId"
          label="Kromka"
          :options="allEdgeChoices"
          placeholder="Kromka tanlang"
          @update:model-value="registryPickedEdgeId = $event"
        />
        <div class="mt-4 flex flex-wrap justify-end gap-2">
          <button type="button" class="mp-button mp-button-outline" @click="closeRegistryPicker">
            Bekor qilish
          </button>
          <button
            type="button"
            class="mp-button mp-button-primary"
            :disabled="!registryPickedEdgeId"
            @click="applyRegistryPicker"
          >
            Qo'llash
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="materialPickerTarget"
      class="fixed inset-0 z-[70] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Materialni almashtirish"
      @keydown.esc="closeMaterialPicker"
    >
      <div
        class="absolute inset-0 bg-[rgb(15_27_45_/_45%)] backdrop-blur-[2px]"
        @click="closeMaterialPicker"
      ></div>
      <div
        class="relative z-10 w-[min(460px,100%)] overflow-hidden rounded-2xl border border-hairline bg-elevated shadow-[0_28px_60px_-14px_rgb(15_27_45_/_30%)]"
      >
        <div class="flex items-start justify-between gap-3 border-b border-hairline px-5 py-4">
          <div>
            <h3 class="text-base font-extrabold text-ink">Materialni almashtirish</h3>
            <p class="mt-1 text-sm text-ink-muted">{{ materialPickerSubtitle }}</p>
          </div>
          <button
            type="button"
            class="client-edge-close"
            aria-label="Yopish"
            @click="closeMaterialPicker"
          >
            ×
          </button>
        </div>
        <div class="grid max-h-[52vh] gap-2 overflow-auto p-3">
          <button
            v-for="material in materialPickerMaterials"
            :key="material.id"
            type="button"
            class="grid grid-cols-[18px_minmax(0,1fr)_auto] items-center gap-3 rounded-lg border bg-elevated px-3 py-3 text-left transition hover:border-accent-tint hover:bg-accent-soft/20"
            :class="
              material.id === materialPickerCurrentId
                ? 'border-accent bg-accent-soft/30'
                : 'border-hairline'
            "
            @click="applyMaterialPicker(material.id)"
          >
            <span
              class="size-[18px] rounded-[5px] shadow-[inset_0_0_0_1px_rgb(15_27_45_/_12%)]"
              :style="materialPickerSwatchStyle(material)"
              aria-hidden="true"
            ></span>
            <span class="min-w-0">
              <span class="block truncate text-sm font-bold text-ink">
                {{ materialLabel(material) }}
              </span>
              <span class="mt-0.5 block text-xs font-semibold text-ink-muted">
                {{ materialPickerGrainLabel(material) }}
              </span>
            </span>
            <span
              v-if="material.id === materialPickerCurrentId"
              class="grid size-6 place-items-center rounded-full bg-accent-soft text-accent"
              aria-label="Tanlangan"
            >
              <Icon name="check" class="size-3.5" />
            </span>
          </button>
          <p v-if="materialPickerMaterials.length === 0" class="p-4 text-sm text-ink-muted">
            Bu filialda panel materiali topilmadi.
          </p>
        </div>
        <div class="flex justify-end border-t border-hairline px-5 py-3">
          <button type="button" class="mp-button mp-button-outline" @click="closeMaterialPicker">
            Bekor qilish
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
