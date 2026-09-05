<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'

import { ApiError, apiErrorCode, apiTraceId } from '@/shared/api/client'
import { clientErrorLabel, draftDisplayName } from '@/shared/app/clientUi'
import { MAX_PARTS, MIN_PART_MM } from '@/shared/app/constants'
import { traceLine, traceSuffix } from '@/shared/app/errorTrace'
import {
  clientCuttingEditorAdapter,
  cuttingEditorAdapterKey,
  type CuttingEditorAdapterFactory,
} from '@/shared/app/cuttingEditorAdapter'
import {
  colorForMaterial,
  edgeFields,
  materialSwatchStyle,
  type EdgeField,
} from '@/shared/app/cuttingDisplay'
import {
  formatMm,
  isTape,
  materialIdentityLabel,
  snapshotMaterialLabel,
} from '@/shared/app/materialLabel'
import { pinnedWorkshopId, scopedBranchOptions } from '@/shared/app/clientEntry'
import { edgeTooNarrow } from '@/shared/app/cuttingEdgeDisplay'
import {
  deriveEdgeRegistry,
  edgeRegistryKey,
  groupCuttingParts,
  isGeometryNeutralEdit,
  partDisplayName,
  syncEdgeAssignments,
  type EdgeRegistryEntry,
} from '@/shared/app/cuttingEditorDerived'
import {
  autoTapeDecorForPanel,
  groupHasBandedSide,
  groupTapeDecors,
  preferredVariant,
  reResolveGroupTape,
  resolveGroupTape,
  type TapeDecor,
} from '@/shared/app/cuttingGroupTape'
import { useDraftAutosave } from '@/shared/composables/useDraftAutosave'
import { useToast } from '@/shared/composables/useToast'
import ActionMenu from '@/shared/components/ActionMenu.vue'
import Icon from '@/shared/components/AppIcon.vue'
import OrderWizardHead from '@/shared/components/OrderWizardHead.vue'
import AppModal from '@/shared/components/AppModal.vue'
import { useRolePath } from '@/shared/app/paths'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import CuttingBranchPicker from '@/shared/components/CuttingBranchPicker.vue'
import CuttingEdgePickerModal from '@/shared/components/CuttingEdgePickerModal.vue'
import CuttingGroupTapeLine from '@/shared/components/CuttingGroupTapeLine.vue'
import CuttingKromkaPanel from '@/shared/components/CuttingKromkaPanel.vue'
import CuttingMaterialPicker from '@/shared/components/CuttingMaterialPicker.vue'
import CuttingPartCard from '@/shared/components/CuttingPartCard.vue'
import CuttingPartSheet from '@/shared/components/CuttingPartSheet.vue'
import CuttingTapePicker from '@/shared/components/CuttingTapePicker.vue'
import CuttingEdgeTapeRegistry from '@/shared/components/CuttingEdgeTapeRegistry.vue'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import CuttingImportWizard from '@/shared/components/CuttingImportWizard.vue'
import CuttingPartRow from '@/shared/components/CuttingPartRow.vue'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'
import SegmentedControl from '@/shared/components/SegmentedControl.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import {
  materialLabel,
  partFitError,
  useCuttingStore,
  type ClientCatalogMaterialOption,
  type CuttingEdgeBand,
  type CuttingPart,
} from '@/shared/stores/cutting'
import { applyImportedParts, type ImportLoadMode } from '@/shared/stores/cuttingImport'
import { overlayRect } from '@/shared/app/overlayGeometry'
import { useAuthStore } from '@/shared/stores/auth'
import type { OrderDetail } from '@/shared/stores/orders'

const route = useRoute()
const router = useRouter()
const rolePath = useRolePath()
const auth = useAuthStore()
const cutting = useCuttingStore()
const toast = useToast()
const { t } = useI18n()
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
// The client editor (SPEC_CLIENT_UX_MVP §7). Every §7 change is gated on this,
// never on `inOrderWizard`: that flag is false for a workshop revision and for
// a read-only bound draft too, and those are workshop screens that must keep
// the registry, the tape picker, the import and the own-material flow exactly
// as they are today.
const isClientEditor = computed(() => cutting.scope === 'client')
const draftId = computed(() => String(route.params.id))
// New editor: it has no server id until it contains a complete detail, which
// creates the draft through autosave.
const isNewDraft = computed(() => route.name === adapter.newRouteName)
// Branch pre-filter while the editor is still empty — seeded from the client
// profile default for parity with a server-created draft.
const localBranchId = ref<string | null>(null)
const localDraftName = ref<string | null>(null)
const draftNameEditing = ref(false)
const draftNameValue = ref('')
const branchTouched = ref(false)
// A draft created by a previous failed optimise attempt — reused on retry so a
// transient failure doesn't orphan a second empty draft.
const pendingDraftId = ref<string | null>(null)
const creatingDraft = ref(false)
// Set before the new-editor route is replaced with the persisted draft route.
const leavingAfterCreate = ref(false)
// True when the user leaves the new-editor route before its background save has
// completed. It prevents that save from navigating them back into the editor.
let abandoningNewDraft = false
const parts = ref<CuttingPart[]>([])
const draftRecoveryPrefix = 'mebel-pro:cutting-draft:'
const recoveryKey = computed(
  () => `${draftRecoveryPrefix}${isNewDraft.value ? 'new' : draftId.value}`,
)

type DraftRecovery = {
  parts: CuttingPart[]
  name: string | null
  branchId: string | null
}

function writeDraftRecovery() {
  try {
    const snapshot: DraftRecovery = {
      parts: parts.value,
      name: isNewDraft.value ? localDraftName.value : (draft.value?.name ?? null),
      branchId: activeBranchId.value,
    }
    window.localStorage.setItem(recoveryKey.value, JSON.stringify(snapshot))
  } catch {
    // Browser storage is only a last-mile recovery layer; server autosave stays
    // authoritative when it is unavailable (private mode, quota, and so on).
  }
}

function readDraftRecovery(): DraftRecovery | null {
  try {
    const raw = window.localStorage.getItem(recoveryKey.value)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<DraftRecovery>
    if (!Array.isArray(parsed.parts)) return null
    return {
      parts: parsed.parts as CuttingPart[],
      name: typeof parsed.name === 'string' ? parsed.name : null,
      branchId: typeof parsed.branchId === 'string' ? parsed.branchId : null,
    }
  } catch {
    return null
  }
}

function clearDraftRecovery(key = recoveryKey.value) {
  try {
    window.localStorage.removeItem(key)
  } catch {
    // See writeDraftRecovery: recovery storage is best effort.
  }
}

function moveDraftRecovery(fromKey: string) {
  try {
    const raw = window.localStorage.getItem(fromKey)
    if (raw) window.localStorage.setItem(recoveryKey.value, raw)
    window.localStorage.removeItem(fromKey)
  } catch {
    // See writeDraftRecovery: recovery storage is best effort.
  }
}
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
const deleteDraftDialogOpen = ref(false)
const deletingDraft = ref(false)
const deleteDraftError = ref<string | null>(null)
const deleteDraftTraceId = ref<string | null>(null)
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
// This screen is step 2 of the staff order flow only when it is actually on
// that journey: the client SPA reaches it on its own, a revision edits a placed
// order rather than creating one, and a bound draft is a read-only record.
const inOrderWizard = computed(
  () => isWorkshopScope.value && !isReadOnly.value && revisionOrderId.value === null,
)
/**
 * Whether kromka is edited in a card docked beside the board rather than in a
 * modal — the staff order wizard, and now the client editor too (§7.5). Both
 * select a row on click or focus and render the panel for that row; the client
 * variant just carries a smaller block. Below `lg` the client's panel is not
 * rendered at all and the phone sheet owns the job instead.
 */
const docksKromka = computed(() => inOrderWizard.value || isClientEditor.value)
// The locked-branch strip names the branch the editor actually operates on. For a
// resumed walk-in draft that's the draft's frozen branch (which may differ from
// the topbar the adapter froze at mount); fall back to the topbar name.
// The app's current branch, read live through the adapter (workshop only) — see
// the `context` note on CuttingEditorAdapter. Its presence marks "the app owns
// the branch", which is what keeps the in-editor picker out of the workshop app
// even before the context has finished loading.
const contextBranchId = computed(() => adapter.branch.context?.() ?? null)
const appSuppliesBranch = computed(
  () => Boolean(fixedBranch.value) || typeof adapter.branch.context === 'function',
)
const appBranchName = computed(() => {
  if (fixedBranch.value) return fixedBranch.value.name
  const id = contextBranchId.value
  return id ? (adapter.branchNameById?.(id) ?? null) : null
})
const lockedBranchName = computed(() => {
  const draftBranchId = draft.value?.preferred_branch_id
  if (draftBranchId && adapter.branchNameById) {
    return adapter.branchNameById(draftBranchId) ?? appBranchName.value
  }
  return appBranchName.value
})
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
  return draft.value?.preferred_branch_id ?? fixedBranch.value?.id ?? contextBranchId.value
})
const preferredBranch = computed(() =>
  cutting.branchOptions.find((branch) => branch.branch_id === activeBranchId.value),
)
/**
 * The naming rule (decision 16), system-wide: a workshop with ONE branch is
 * named by the workshop alone — the branch name never appears — and a workshop
 * with several reads «{Workshop} · {Branch}», always in that order. A branch
 * name is never shown on its own. (This line used to render branch-first,
 * which is the reverse of how a client says it out loud.)
 */
const clientBranchLabel = computed(() => {
  const branch = preferredBranch.value
  if (!branch) return ''
  const siblings = cutting.branchOptions.filter(
    (option) => option.workshop_id === branch.workshop_id,
  ).length
  return siblings > 1 ? `${branch.workshop_name} · ${branch.branch_name}` : branch.workshop_name
})
// Editor scoping (spec §4). The pin scopes what the picker *offers*; it never
// touches data, so the full option list stays loaded and an existing draft on a
// foreign branch keeps naming its own branch (and its kerf/trim) through
// `preferredBranch` above. Only `pickerOptions` is narrowed, and only for a
// client the principal says is pinned — the workshop editor and the un-pinned
// organic client both fall through to the list as it was.
const pinnedWorkshop = computed(() =>
  isWorkshopScope.value
    ? null
    : pinnedWorkshopId(
        cutting.branchOptions,
        auth.me?.preferred_branch_id,
        auth.me?.pinned_workshop_name,
      ),
)
const pinnedWorkshopName = computed(() =>
  pinnedWorkshop.value ? (auth.me?.pinned_workshop_name ?? null) : null,
)
const pickerOptions = computed(() =>
  scopedBranchOptions(cutting.branchOptions, pinnedWorkshop.value),
)
// What the in-page picker should start on. A draft already bound to a branch
// keeps it — the topbar must never retarget an in-progress drawing. Only when
// nothing is bound do we fall back to the app's branch, instead of demanding a
// fresh pick the user has already made in the topbar.
function seededBranchId(preferredBranchId: string | null | undefined): string | null {
  return preferredBranchId ?? fixedBranch.value?.id ?? contextBranchId.value
}
// The edge trim actually in effect for this editor: the saved draft's
// resolved value first (server-authoritative), then the client-picked branch,
// then the workshop's fixed branch. Null only when no branch is chosen yet —
// canOptimize already gates on a branch being picked, so fit validation is
// simply skipped rather than guessing a number (cutting.md).
const activeTrimMm = computed(
  () =>
    draft.value?.edge_trim_mm ??
    preferredBranch.value?.edge_trim_mm ??
    fixedBranch.value?.edgeTrimMm ??
    null,
)
// The catalog endpoint is branch-scoped — a branch is chosen before the flow
// reaches materials — so every row it returns is one this branch carries. There
// is no client-side carried filter left and no "not carried" state to annotate.
function catalogChoice(material: ClientCatalogMaterialOption): ChoiceOption {
  return {
    value: material.id,
    label: materialLabel(material),
    meta: `${material.name}${material.code ? ` · ${material.code}` : ''}`,
  }
}
const panelChoices = computed<ChoiceOption[]>(() => cutting.panelOptions.map(catalogChoice))
const edgeChoices = computed<ChoiceOption[]>(() => cutting.edgeOptions.map(catalogChoice))
// Do not create or update a draft until it contains at least one fully filled
// detail. `every()` alone treats an empty list as valid.
const hasPersistableParts = computed(
  () => parts.value.length > 0 && parts.value.every((part) => !partIsInvalid(part)),
)
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
// A result is actionable only when the draft explicitly chooses it and it was
// calculated for the exact parts currently visible in the editor. This rejects
// stale ids and preserved MAP layouts after a geometry edit, while allowing an
// unchanged MAP layout to return to its result stage.
const currentChosenResult = computed(() => {
  const currentDraft = draft.value
  if (!currentDraft?.chosen_result_id) return null
  const result = currentDraft.results.find((item) => item.id === currentDraft.chosen_result_id)
  if (!result || result.status === 'invalidated' || !Array.isArray(result.parts_snapshot))
    return null
  return partsSignature(result.parts_snapshot) === partsSignature() ? result : null
})
const hasCurrentChosenResult = computed(() => currentChosenResult.value !== null)
// docs/ref/features/cutting.md — at most MAX_PARTS per optimisation (CB-102).
const canOptimize = computed(
  () =>
    !isReadOnly.value &&
    // A branch is mandatory: the catalog is scoped to the chosen workshop, so
    // there's nothing to optimise against until one is picked.
    !!activeBranchId.value &&
    parts.value.length > 0 &&
    hasPersistableParts.value &&
    totalQuantity.value <= MAX_PARTS,
)
const optimizeDisabledHint = computed(() => {
  if (isReadOnly.value) return t('cutting.editor.hintReadOnly')
  if (!activeBranchId.value) return t('cutting.editor.hintNoBranch')
  if (parts.value.length === 0) return t('cutting.editor.hintNoParts')
  if (!hasPersistableParts.value) return t('cutting.editor.hintIncomplete')
  if (totalQuantity.value > MAX_PARTS) return t('cutting.editor.hintOverCap', { max: MAX_PARTS })
  return ''
})
const primaryCtaLabel = computed(() => {
  if (cutting.optimizing || creatingDraft.value) return t('cutting.editor.ctaCalculating')
  // §7.0 fixes the client's two labels: the button says what the tap does —
  // it runs the optimiser, or it opens the result that is already current.
  if (isClientEditor.value) {
    return hasCurrentChosenResult.value
      ? t('cutting.editor.ctaViewResult')
      : t('cutting.editor.ctaCalculate')
  }
  // «Optimallashtirish» is the wizard's word for this step, and it is only true
  // when the click will actually run one: with a chosen result already matching
  // these parts the button just opens that result, and on a read-only drawing it
  // does nothing at all. Both of those keep the neutral «Davom etish», as does
  // the client SPA, whose editor is a screen of its own rather than step 2 of
  // anything.
  if (!inOrderWizard.value || hasCurrentChosenResult.value) return t('cutting.editor.ctaContinue')
  return t('cutting.editor.ctaOptimize')
})
const primaryCtaDisabled = computed(
  () =>
    cutting.optimizing ||
    creatingDraft.value ||
    (!hasCurrentChosenResult.value && !canOptimize.value),
)
const primaryCtaHint = computed(() =>
  hasCurrentChosenResult.value || cutting.optimizing || creatingDraft.value
    ? ''
    : optimizeDisabledHint.value,
)
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
    follow_grain: false,
    thickened: false,
    length_mm: 0,
    width_mm: 0,
    quantity: 0,
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

// ── The client's group tape (§7.1) ──────────────────────────────────────────
// Nothing below is persisted: a side still stores the concrete kromka material
// id it always did, and the group's decor is resolved from the parts snapshot
// plus the branch's tape catalog on every read (see app/cuttingGroupTape.ts).
// `pickedTapeByMaterial` only records the choice made in THIS editor, which is
// the one thing the parts cannot say when no side is banded yet.
const pickedTapeByMaterial = ref<Record<string, string>>({})
/** The thickness the next banded side takes — «Qalinlikni tanlab, tomonga bosing». */
const armedThicknessMm = ref<number | null>(null)
const tapePickerGroupKey = ref<string | null>(null)
const gateGroupKey = ref<string | null>(null)

const tapeDecors = computed(() =>
  isClientEditor.value ? groupTapeDecors(cutting.edgeOptions) : [],
)

function partsOfMaterial(materialId: string | null) {
  return parts.value.filter((part) => (part.material_id || null) === materialId)
}

function groupTapeFor(materialId: string | null): TapeDecor | null {
  if (!materialId) return null
  return resolveGroupTape({
    panel: materialById(materialId),
    groupParts: partsOfMaterial(materialId),
    decors: tapeDecors.value,
    pickedKey: pickedTapeByMaterial.value[materialId] ?? null,
  }).decor
}

function tapeThicknessOf(materialId: string): number | null {
  const edge = edgeById(materialId)
  if (!edge) return null
  const value = Number(edge.thickness_mm)
  return Number.isFinite(value) ? value : null
}

function foreignTapeLabel(materialId: string) {
  const edge = edgeById(materialId)
  return edge ? materialLabel(edge) : materialId
}

/**
 * §7.1's auto-attach, as a side effect of the catalog and the parts settling
 * rather than of the click that added the material: a material can arrive by
 * picker, by hydration or by recovery, and all three owe the group the same
 * tape. `resolveGroupTape` already prefers what the sides carry, so writing the
 * auto-match into `pickedTapeByMaterial` only pins the case where nothing is
 * banded — and never overwrites a pick the client made.
 */
watch(
  [() => parts.value.map((part) => part.material_id).join('|'), tapeDecors],
  () => {
    if (!isClientEditor.value || tapeDecors.value.length === 0) return
    const next = { ...pickedTapeByMaterial.value }
    let changed = false
    for (const materialId of new Set(parts.value.map((part) => part.material_id).filter(Boolean))) {
      if (next[materialId]) continue
      const auto = autoTapeDecorForPanel(materialById(materialId), tapeDecors.value)
      if (!auto) continue
      next[materialId] = auto.key
      changed = true
    }
    if (changed) pickedTapeByMaterial.value = next
  },
  { immediate: true },
)

/** Groups that band a side but have no tape decor — the «Hisoblash» gate. */
const groupsMissingGroupTape = computed(() =>
  isClientEditor.value
    ? groupedParts.value.filter(
        (group) =>
          group.materialId &&
          groupHasBandedSide(group.parts.map((entry) => entry.part)) &&
          groupTapeFor(group.materialId) === null,
      )
    : [],
)

function openTapePicker(materialId: string | null) {
  if (!materialId) return
  tapePickerGroupKey.value = materialId
}

function closeTapePicker() {
  tapePickerGroupKey.value = null
}

const tapePickerPanel = computed(() =>
  tapePickerGroupKey.value ? materialById(tapePickerGroupKey.value) : null,
)
const tapePickerCurrentKey = computed(() =>
  tapePickerGroupKey.value ? (groupTapeFor(tapePickerGroupKey.value)?.key ?? null) : null,
)

/**
 * Changing the group's tape re-points every banded side of that group at the
 * new decor, keeping each side's thickness where the decor has it. A thickness
 * the new decor does not carry falls back to the nearest one — and says so
 * once, because a band silently changing from 2 mm to 0.4 mm is a price change
 * the client did not ask for.
 */
function applyGroupTape(decorKey: string) {
  const materialId = tapePickerGroupKey.value
  const decor = tapeDecors.value.find((item) => item.key === decorKey)
  if (!materialId || !decor) return
  pickedTapeByMaterial.value = { ...pickedTapeByMaterial.value, [materialId]: decorKey }
  const outcome = reResolveGroupTape({
    parts: parts.value,
    groupMaterialId: materialId,
    decor,
    thicknessById: tapeThicknessOf,
  })
  if (outcome.changed) parts.value = outcome.parts
  if (outcome.fellBack) toast.warn(t('cutting.edge.thicknessFallback', { name: decor.label }))
  if (gateGroupKey.value === materialId) gateGroupKey.value = null
  closeTapePicker()
}

/** The armed thickness, clamped to what the open part's group decor carries. */
function armedThicknessFor(decor: TapeDecor | null): number | null {
  if (!decor) return null
  const armed = decor.variants.find((variant) => variant.thicknessMm === armedThicknessMm.value)
  return (armed ?? preferredVariant(decor, null))?.thicknessMm ?? null
}

function setPartSide(part: CuttingPart, side: EdgeField, materialId: string | null) {
  part[side] = materialId ? { material_id: materialId, source: 'shop' } : null
  if (materialId) {
    const thickness = tapeThicknessOf(materialId)
    if (thickness != null) armedThicknessMm.value = thickness
    rememberEdgeMaterial(part, materialId)
  }
}

const edgeRegistry = computed(() => deriveEdgeRegistry(parts.value, edgeAssignments.value))
const edgeAssignmentEntries = computed(() => [...edgeAssignments.value.entries()])
const groupedParts = computed(() =>
  groupCuttingParts(parts.value, (materialId) =>
    inOrderWizard.value
      ? materialIdentityLabel(materialById(materialId))
      : materialLabel(materialById(materialId)),
  ),
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
// D3.3: whose sheets a material group is cut from — display only. The claim is
// entered after the optimizer (CuttingOwnMaterialDialog), so on a first pass
// through the editor every group is correctly `Ombordan`; the chip earns its
// place on a resumed or revised draft, where the claim already exists and is
// otherwise invisible until the result screen. `draft` is null for the whole
// unsaved first pass, hence the optional chain.
// `2750×1830×18` — the sheet the group's parts are cut from, on the sub-line
// where the design puts it. Blank when the branch material is gone or unpicked;
// the counts after it still read.
function groupSize(materialId: string | null) {
  if (!materialId) return ''
  const material = materialById(materialId)
  if (!material) return ''
  const parts = [material.length_mm, material.width_mm, material.thickness_mm].filter(Boolean)
  return parts.length >= 2 ? parts.join('×') : ''
}

function materialIsOwn(materialId: string | null) {
  if (!materialId) return false
  // A customer board IS the customer's material by construction — it says so on
  // the row. The claim is the other half: on a catalog format the only thing
  // that makes it theirs is the count entered after the optimiser.
  if (materialById(materialId)?.customer_supplied) return true
  return (draft.value?.own_panel_counts?.[materialId] ?? 0) > 0
}

// Three literal keys so `pnpm i18n:check` can see them; the client branch is
// the same second-person rule the result screen follows.
function materialSourceLabel(materialId: string | null) {
  if (!materialIsOwn(materialId)) return t('cutting.source.shop')
  return isWorkshopScope.value ? t('cutting.source.own') : t('cutting.source.ownClient')
}

const displayPartIndex = computed(() => {
  const positions = new Map<string, number>()
  let position = 0
  for (const group of groupedParts.value) {
    for (const { part } of group.parts) positions.set(part.part_ref, position++)
  }
  return positions
})

function edgeRegistryLabel(materialId: string) {
  const edge = edgeById(materialId)
  return edge ? materialLabel(edge) : materialId
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
  const ids: string[] = []
  const seen = new Set<string>()
  for (const row of rows) {
    for (const side of edgeFields) {
      const materialId = row[side]?.material_id
      if (!materialId || seen.has(materialId)) continue
      seen.add(materialId)
      ids.push(materialId)
    }
  }
  return ids
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
      return t('cutting.edge.narrowWarning', {
        width: edge.tape_width_mm,
        thickness: panelThickness,
      })
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

function partSizeError(part: CuttingPart): string | null {
  const panel = materialById(part.material_id)
  if (!panel || panel.length_mm == null || panel.width_mm == null) return null
  const trimMm = activeTrimMm.value
  if (trimMm == null) return null
  const code = partFitError(
    part.length_mm,
    part.width_mm,
    panel,
    part.follow_grain !== false,
    trimMm,
  )
  if (!code) return null
  const usableLength = panel.length_mm - 2 * trimMm
  const usableWidth = panel.width_mm - 2 * trimMm
  if (code === 'impossible_grain')
    return t('cutting.editor.grainFitError', { length: usableLength, width: usableWidth })
  return t('cutting.editor.sizeFitError', {
    length: usableLength,
    width: usableWidth,
    trim: trimMm,
  })
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

const OPTIMIZE_ROW_CODES = ['part_too_large', 'impossible_grain', 'material_not_found'] as const

function optimizeRowMessage(code: string | undefined): string {
  if (code && (OPTIMIZE_ROW_CODES as readonly string[]).includes(code)) {
    return t(`cutting.error.${code}`)
  }
  return t('cutting.error.rowOptimizeFailed')
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
  if (saveState.value === 'saved') return t('cutting.editor.saveSaved')
  if (saveState.value === 'saving') return t('cutting.editor.saveSaving')
  if (saveState.value === 'editing') return t('cutting.editor.saveEditing')
  return t('cutting.editor.saveError')
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
    // The panel's subject just stopped existing. Clearing here rather than
    // letting `activePart` resolve to null keeps `activeSide` from surviving
    // into whatever row is selected next.
    if (activePartRef.value === removed.part_ref) clearActivePart()
    // Same for the phone sheet — deleting from its ⋯ menu closes it, and the
    // undo toast below is then the only thing on screen about that part.
    if (sheetPartRef.value === removed.part_ref) closePartSheet()
    const label = partDisplayName(removed, index)
    toast.action(
      t('cutting.editor.partDeleted', { name: label }),
      t('cutting.action.undo'),
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

// Leaving is free here: the draft autosaves, so Bekor qilish abandons the
// *order*, not the work. It lands on the drafts list — where the thing just
// left behind actually is — rather than on the orders list the prototype
// picked, which would show no trace of it. No confirmation: nothing is
// destroyed, and DESIGN.md rules a nag out where there is nothing to lose.
// ── Customer-supplied board ─────────────────────────────────────────────────
// The picker's second tab. Workshop only, and only once a draft exists on the
// server: the board is recorded against that draft, so it is what scopes the
// row to this customer instead of offering it to the whole branch.
type MaterialPickerMode = 'shop' | 'own'

const materialPickerMode = ref<MaterialPickerMode>('shop')
const customerBoardSaving = ref(false)
const customerBoardError = ref<string | null>(null)
const customerBoard = ref({
  name: '',
  uzunlik: '',
  eni: '',
  qalinlik: '16',
  sheets: '',
  has_grain: false,
})

// The draft whose customer boards the picker may see. Null on the unsaved first
// pass — nothing is recorded yet — and null outside the workshop, where the
// listing must never widen.
const boardScopeDraftId = computed(() =>
  isWorkshopScope.value ? (draft.value?.id ?? pendingDraftId.value) : null,
)
const canAddCustomerBoard = computed(
  () => isWorkshopScope.value && !isReadOnly.value && Boolean(activeBranchId.value),
)
const materialPickerModes = computed(() => [
  { value: 'shop', label: t('cutting.source.shop') },
  { value: 'own', label: t('cutting.source.own') },
])

function resetCustomerBoard() {
  materialPickerMode.value = 'shop'
  customerBoardError.value = null
  customerBoardSaving.value = false
  customerBoard.value = {
    name: '',
    uzunlik: '',
    eni: '',
    qalinlik: '16',
    sheets: '',
    has_grain: false,
  }
}

async function submitCustomerBoard() {
  customerBoardError.value = null
  const uzunlik = Number(customerBoard.value.uzunlik)
  const eni = Number(customerBoard.value.eni)
  const qalinlik = Number(customerBoard.value.qalinlik.replace(',', '.'))
  const sheets = Number(customerBoard.value.sheets)
  if (!Number.isFinite(uzunlik) || !Number.isFinite(eni) || uzunlik <= 0 || eni <= 0) {
    customerBoardError.value = t('cutting.customerBoard.sizeError')
    return
  }
  if (!Number.isFinite(qalinlik) || qalinlik <= 0) {
    customerBoardError.value = t('cutting.customerBoard.thicknessError')
    return
  }
  if (!Number.isFinite(sheets) || sheets <= 0) {
    customerBoardError.value = t('cutting.customerBoard.sheetsError')
    return
  }
  customerBoardSaving.value = true
  try {
    // A board needs a draft to belong to. On the unsaved first pass there is
    // none yet, so mint it here rather than making the operator save first.
    // A board needs a draft row to belong to. On the unsaved first pass there
    // is none, so mint one here — the same `pendingDraftId` the autosave uses,
    // so the two never create two drafts for one drawing.
    if (isNewDraft.value && !pendingDraftId.value) {
      pendingDraftId.value = (
        await cutting.createDraft(
          fixedBranch.value ? { branchId: fixedBranch.value.id } : undefined,
        )
      ).id
    }
    const boardDraftId = isNewDraft.value ? pendingDraftId.value : draftId.value
    if (!boardDraftId) {
      customerBoardError.value = t('cutting.customerBoard.saveFailed')
      return
    }
    const option = await cutting.createCustomerBoard({
      draftId: boardDraftId,
      name: customerBoard.value.name.trim() || null,
      length_mm: uzunlik,
      width_mm: eni,
      thickness_mm: qalinlik,
      sheets,
      has_grain: customerBoard.value.has_grain,
    })
    closeMaterialPicker()
    addRow(option.id, null)
  } catch (caught) {
    customerBoardError.value =
      clientErrorLabel(apiErrorCode(caught)) || t('cutting.customerBoard.saveFailed')
  } finally {
    customerBoardSaving.value = false
  }
}

function requestCancelWizard() {
  void router.push(rolePath(adapter.paths.drafts))
}

function requestDeleteDraft() {
  deleteDraftError.value = null
  deleteDraftTraceId.value = null
  deleteDraftDialogOpen.value = true
}

function closeDeleteDraftDialog() {
  deleteDraftDialogOpen.value = false
  deleteDraftError.value = null
  deleteDraftTraceId.value = null
}

async function confirmDeleteDraft() {
  if (!draft.value) return
  deletingDraft.value = true
  deleteDraftError.value = null
  deleteDraftTraceId.value = null
  try {
    await cutting.deleteDraft(draft.value.id)
    await router.push(rolePath(adapter.paths.drafts))
  } catch (errorValue) {
    deleteDraftError.value = clientErrorLabel(
      apiErrorCode(errorValue),
      t('cutting.error.draftDeleteFailed'),
    )
    deleteDraftTraceId.value = apiTraceId(errorValue)
  } finally {
    deletingDraft.value = false
  }
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
  void router.replace(rolePath(adapter.paths.result(nextDraftId)))
}

// --- Bulk selection (desktop power-feature) --------------------------------
// Select rows, then apply edges / change material / delete in one action so
// banding or re-materialing many identical parts isn't N modal round-trips.
const selectedRefs = ref<Set<string>>(new Set())
const selectedParts = computed(() =>
  parts.value.filter((part) => selectedRefs.value.has(part.part_ref)),
)
const bulkEdgeMode = ref(false)

// The wizard's docked kromka panel edits ONE row, and this is that row. Kept
// apart from `selectedRefs` on purpose: that set is the bulk-apply selection,
// a different question ("which rows does this action fan out to") with a
// different affordance. Folding them together would make tabbing through the
// board silently arm a bulk edit.
const activePartRef = ref<string | null>(null)
const activePart = computed(
  () => parts.value.find((part) => part.part_ref === activePartRef.value) ?? null,
)
/** The side the operator pointed at, so the panel can flash that toggle. */
const activeSide = ref<EdgeField | null>(null)

function selectPart(part: CuttingPart, side?: EdgeField) {
  activePartRef.value = part.part_ref
  activeSide.value = side ?? null
}

// ── The phone «Detal» sheet (§7.0) ──────────────────────────────────────────
// One ref, not a copy of the part: the sheet edits the live object through
// granular emits and the debounced autosave carries it, so «Saqlash» closes
// rather than commits and there is no second copy of the truth to reconcile.
const sheetPartRef = ref<string | null>(null)
const sheetPart = computed(
  () => parts.value.find((part) => part.part_ref === sheetPartRef.value) ?? null,
)
const sheetPartIndex = computed(() =>
  parts.value.findIndex((part) => part.part_ref === sheetPartRef.value),
)
const sheetGroupTape = computed(() => groupTapeFor(sheetPart.value?.material_id ?? null))

function openPartSheet(part: CuttingPart) {
  sheetPartRef.value = part.part_ref
  armedThicknessMm.value = armedThicknessFor(groupTapeFor(part.material_id))
}

function closePartSheet() {
  sheetPartRef.value = null
}

/** «Saqlash va yana»: keep the flow going with a fresh part in the same group. */
function savePartAndNext() {
  const current = sheetPart.value
  if (!current) return
  const index = sheetPartIndex.value
  addRow(current.material_id, current, index)
  const next = parts.value[index + 1]
  if (next) sheetPartRef.value = next.part_ref
}

function clearActivePart() {
  activePartRef.value = null
  activeSide.value = null
}

// Keeping the panel level with the row it edits. The measurement has to cross
// the `zoom: 90%` boundary: `getBoundingClientRect` reports painted pixels while
// a written `margin-top` is local layout pixels, so a raw delta would land the
// panel 10% short. `overlayRect` divides the zoom out once, at the measurement,
// and everything after it stays in one unit.
const stepShell = ref<HTMLElement | null>(null)
const kromkaPanel = ref<{ $el: HTMLElement } | null>(null)
const panelOffset = ref(0)
/** Board + gap + panel. Under this the panel has wrapped and there is no row to
 *  level with. */
const PANEL_SIDE_BY_SIDE_MIN = 318

// Centres, not aligns: a 44px row against a ~330px panel put the row at the
// panel's shoulder, and the pair read as two unrelated things that happened to
// start at the same height.
function syncPanelOffset() {
  const shell = stepShell.value
  const part = activePart.value
  const panel = kromkaPanel.value?.$el as HTMLElement | undefined
  if (!shell || !part || !panel) {
    panelOffset.value = 0
    return
  }
  const board = shell.firstElementChild?.firstElementChild
  const row = shell.querySelector(`#part-row-${CSS.escape(part.part_ref)}`)
  if (!board || !row) return
  const shellBox = overlayRect(shell)
  if (shellBox.width < overlayRect(board).width + PANEL_SIDE_BY_SIDE_MIN) {
    panelOffset.value = 0
    return
  }
  const rowBox = overlayRect(row)
  const rowMid = rowBox.top + rowBox.height / 2 - shellBox.top
  panelOffset.value = Math.max(0, Math.round(rowMid - overlayRect(panel).height / 2))
}

watch([activePartRef, () => parts.value.length], () => void nextTick(syncPanelOffset))

// The panel's own height changes without the row moving — opening the tape list
// is the common case — and a centre that is not re-measured then drifts by half
// the list's height.
let panelResize: ResizeObserver | null = null
watch(
  () => kromkaPanel.value?.$el as HTMLElement | undefined,
  (panel) => {
    panelResize?.disconnect()
    if (!panel || typeof ResizeObserver === 'undefined') return
    panelResize = new ResizeObserver(() => syncPanelOffset())
    panelResize.observe(panel)
  },
  { immediate: true },
)

onMounted(() => window.addEventListener('resize', syncPanelOffset))
onBeforeUnmount(() => {
  window.removeEventListener('resize', syncPanelOffset)
  panelResize?.disconnect()
})

// Writes to the PANEL's subject, not the modal's. `onEdgePickerChange` targets
// `edgePickerPart`, which the wizard never sets because it never opens the
// modal — routing through it made every toggle a silent no-op. Thickening is a
// property of the detal rather than of its banding, so it is carried through
// untouched rather than asked of the panel.
function onPanelEdgesChange(payload: {
  edges: Record<EdgeField, CuttingEdgeBand | null>
  rememberedMaterialId: string | null
}) {
  const part = activePart.value
  if (!part) return
  part.edge_top = payload.edges.edge_top
  part.edge_bottom = payload.edges.edge_bottom
  part.edge_left = payload.edges.edge_left
  part.edge_right = payload.edges.edge_right
  rememberEdgeMaterial(part, payload.rememberedMaterialId)
}

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

// Server-side search over the branch's own list. It has to be server-side: the
// backend folds both the stored key and the query through one normalizer
// (app/core/search_fold.py), so "сонома" finds "Sonoma eman" and "yongok" finds
// "Yong'oq". Filtering the loaded array here would only ever match the script the
// decor happens to be stored in — the exact complaint this replaces.
const materialPickerSearch = ref('')
let materialSearchTimer: ReturnType<typeof setTimeout> | null = null

watch(materialPickerTarget, (target) => {
  resetCustomerBoard()
  // Each open starts from the whole list; a query left over from the previous
  // open would silently hide materials.
  if (!target) return
  if (materialPickerSearch.value === '') return
  materialPickerSearch.value = ''
  void reloadPanelOptions('')
})

watch(materialPickerSearch, (value) => {
  if (materialSearchTimer) clearTimeout(materialSearchTimer)
  // 250ms: long enough that a typed word is one request, short enough that the
  // list feels attached to the keyboard.
  materialSearchTimer = setTimeout(() => void reloadPanelOptions(value), 250)
})

onBeforeUnmount(() => {
  if (materialSearchTimer) clearTimeout(materialSearchTimer)
})

async function reloadPanelOptions(search: string) {
  const branchId = activeBranchId.value
  if (!branchId) return
  // `force`: the store caches per branch, and a query change must defeat that.
  await cutting.loadMaterials({
    tape: false,
    branchId,
    search: search.trim(),
    force: true,
    draftId: boardScopeDraftId.value,
  })
}

// The picker reads like the catalog table: one photo + identity line per decor,
// its formats listed beneath as the selectable rows. Grouping only changes how
// the same list is drawn — picking is still one format, one click.
interface MaterialPickerGroup {
  key: string
  imageFileId: string | null
  title: string
  grainLabel: string
  materials: ClientCatalogMaterialOption[]
}

// `ClientCatalogMaterialOption` carries no `decor_id`, so the decor is keyed by
// the tuple that identifies one: manufacturer + type + code/name.
function decorKey(material: ClientCatalogMaterialOption) {
  return [material.manufacturer_id, material.type, material.code ?? '', material.name].join('|')
}

// The identity half of the canonical label — the same composer the format rows
// use, handed a snapshot with no dimensions so it stops after «· name».
function decorTitle(material: ClientCatalogMaterialOption) {
  return snapshotMaterialLabel(
    {
      manufacturer_name: material.manufacturer_name,
      type: material.type,
      code: material.code,
      name: material.name,
    },
    material.name || material.id.slice(0, 8),
  )
}

function materialFormatLabel(material: ClientCatalogMaterialOption) {
  const thickness = formatMm(material.thickness_mm)
  if (isTape(material.type) && material.tape_width_mm != null) {
    return t('catalog.meta.tapeFormat', { thickness, width: material.tape_width_mm })
  }
  if (material.length_mm != null && material.width_mm != null) {
    return t('catalog.meta.panelFormat', {
      length: material.length_mm,
      width: material.width_mm,
      thickness,
    })
  }
  return thickness ? `${thickness} mm` : materialLabel(material)
}

const materialPickerGroups = computed<MaterialPickerGroup[]>(() => {
  const groups: MaterialPickerGroup[] = []
  const indexByKey = new Map<string, number>()
  for (const material of cutting.panelOptions) {
    const key = decorKey(material)
    let group = groups[indexByKey.get(key) ?? -1]
    if (!group) {
      group = {
        key,
        imageFileId: material.image_file_id,
        title: decorTitle(material),
        grainLabel: materialPickerGrainLabel(material),
        materials: [],
      }
      indexByKey.set(key, groups.length)
      groups.push(group)
    }
    group.materials.push(material)
  }
  return groups
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
    return part
      ? t('cutting.material.forPart', { name: partDisplayName(part, index) })
      : t('cutting.material.forPartGeneric')
  }
  if (target.type === 'group') {
    const count = groupedParts.value.find((item) => item.key === target.key)?.parts.length ?? 0
    return t('cutting.material.forGroup', { n: count }, count)
  }
  if (target.type === 'new') return t('cutting.material.pick')
  const selected = selectedParts.value.length
  return t('cutting.material.forSelection', { n: selected }, selected)
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

// `{workshop} katalogi · N ta dekor` — the picker's foot line, so the client
// can see WHOSE prices these are without leaving the sheet.
const materialCatalogCaption = computed(() =>
  t('cutting.editor.catalogCaption', {
    workshopBranch: clientBranchLabel.value,
    n: materialPickerGroups.value.length,
  }),
)
const tapeCatalogCaption = computed(() =>
  t('cutting.editor.tapeCatalogCaption', {
    workshopBranch: clientBranchLabel.value,
    n: tapeDecors.value.length,
  }),
)

function materialPickerGrainLabel(material: ClientCatalogMaterialOption) {
  return material.has_grain ? t('cutting.material.grained') : t('cutting.material.grainless')
}

function groupDecorImageId(materialId: string | null) {
  return materialById(materialId)?.image_file_id ?? null
}

function groupSwatchStyle(materialId: string) {
  const material = materialById(materialId)
  return materialSwatchStyle({
    name: material?.name ?? null,
    customer_supplied: material?.customer_supplied === true,
  })
}

function materialPickerSwatchStyle(material: ClientCatalogMaterialOption) {
  return {
    background: colorForMaterial(material.name || material.id),
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
  bulkEdgeMode.value = false
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

type EdgePickerPayload = {
  edges: Record<EdgeField, CuttingEdgeBand | null>
  rememberedMaterialId: string | null
  thickened: boolean
}

function applyEdgesToRefs(refs: Set<string>, payload: EdgePickerPayload) {
  const preferred = { ...preferredEdgeByPart.value }
  parts.value = parts.value.map((part) => {
    if (!refs.has(part.part_ref)) return part
    if (payload.rememberedMaterialId) preferred[part.part_ref] = payload.rememberedMaterialId
    else delete preferred[part.part_ref]
    return {
      ...part,
      thickened: payload.thickened,
      edge_top: payload.edges.edge_top ? { ...payload.edges.edge_top } : null,
      edge_bottom: payload.edges.edge_bottom ? { ...payload.edges.edge_bottom } : null,
      edge_left: payload.edges.edge_left ? { ...payload.edges.edge_left } : null,
      edge_right: payload.edges.edge_right ? { ...payload.edges.edge_right } : null,
    }
  })
  preferredEdgeByPart.value = preferred
}

function onEdgePickerChange(payload: EdgePickerPayload) {
  const targets = bulkEdgeMode.value
    ? new Set(selectedParts.value.map((part) => part.part_ref))
    : null
  if (targets) {
    applyEdgesToRefs(targets, payload)
  } else if (edgePickerPart.value) {
    const part = edgePickerPart.value
    part.thickened = payload.thickened
    part.edge_top = payload.edges.edge_top
    part.edge_bottom = payload.edges.edge_bottom
    part.edge_left = payload.edges.edge_left
    part.edge_right = payload.edges.edge_right
    rememberEdgeMaterial(part, payload.rememberedMaterialId)
  }
}

// The client flow no longer offers "I'll bring it" — every material is
// workshop-supplied. Legacy drafts saved with `own` parts/sides are coerced
// back to `shop` on hydration; when that changed anything, hydration schedules
// a save so the SERVER snapshot matches what the user sees — optimise/order
// price the persisted snapshot, and a display-only rewrite would invisibly
// bill legacy parts as client-supplied (no material charge).
function normalizeSources(part: CuttingPart): CuttingPart {
  // `thickened` post-dates existing drafts, so a hydrated snapshot can arrive
  // without it — coerce to a real boolean here rather than letting `undefined`
  // reach the row toggle and the saved snapshot.
  const next: CuttingPart = {
    ...part,
    material_source: 'shop',
    thickened: part.thickened === true,
  }
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
  const savedParts = draft.value?.parts_snapshot ?? []
  if (
    !hasImportedMapResult.value ||
    importedLayoutWarningAccepted.value ||
    isGeometryNeutralEdit(savedParts, parts.value)
  ) {
    return Promise.resolve(true)
  }
  importedLayoutWarningOpen.value = true
  return new Promise<boolean>((resolve) => {
    importedLayoutWarningResolve = resolve
  })
}

async function persistPartsSnapshot() {
  const startedAsNew = isNewDraft.value
  const oldRecoveryKey = recoveryKey.value
  let id = draftId.value

  if (startedAsNew) {
    if (!pendingDraftId.value) {
      pendingDraftId.value = (
        await cutting.createDraft(
          fixedBranch.value ? { branchId: fixedBranch.value.id } : undefined,
        )
      ).id
    }
    id = pendingDraftId.value
  }

  await cutting.updateDraft(id, {
    parts_snapshot: parts.value,
    ...(startedAsNew && localDraftName.value !== null ? { name: localDraftName.value } : {}),
    ...(startedAsNew && branchTouched.value && !fixedBranch.value
      ? { preferred_branch_id: localBranchId.value }
      : {}),
  })

  if (!startedAsNew) {
    clearDraftRecovery(oldRecoveryKey)
    return
  }

  if (abandoningNewDraft) return
  hydratedDraftId = id
  leavingAfterCreate.value = true
  await router.replace(rolePath(adapter.paths.editor(id)))
  moveDraftRecovery(oldRecoveryKey)
}

// Debounced autosave (700ms) — the timing core, status mirror, draft creation,
// the deep `parts` watch, and the hydration guard all live in this seam. A draft
// accepts unfinished rows; only optimization applies the strict part validation.
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
    await persistPartsSnapshot()
  },
  canPersist: () => hasPersistableParts.value,
  isReadOnly: () => isReadOnly.value,
  // A row-attributed optimiser error is stale once the parts change.
  onSchedule: () => {
    optimizeRowError.value = null
    writeDraftRecovery()
  },
})
const saveState = autosave.saveState
const saveError = autosave.saveError

async function setPreferredBranch(branchId: string | null) {
  // New editor: keep the pick local until a complete detail can create the draft.
  if (isNewDraft.value) {
    localBranchId.value = branchId
    branchTouched.value = true
    branchPickerOpen.value = false
    selectedBranchId.value = branchId
    writeDraftRecovery()
    await loadMaterials()
    autosave.schedule()
    return
  }
  // Surface a failure instead of an unhandled rejection that leaves the local
  // pick disagreeing with the server (CB-57).
  try {
    await cutting.updateDraft(draftId.value, { preferred_branch_id: branchId })
  } catch {
    toast.danger(t('cutting.error.branchSaveFailed'))
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
    autosave.schedule()
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

async function runPrimaryCta() {
  if (primaryCtaDisabled.value) return
  if (hasCurrentChosenResult.value && draft.value) {
    await router.push(rolePath(adapter.paths.result(draft.value.id)))
    return
  }
  await optimize()
}

/**
 * The §7.1 gate. A group that bands a side but has no tape decor cannot be
 * priced — the tape is a line on the bill, and every order is fully priced at
 * placement. So «Hisoblash» refuses, scrolls the offending group's line into
 * view and arms it, rather than optimising into a quote that cannot be made.
 */
async function blockedByMissingGroupTape(): Promise<boolean> {
  const group = groupsMissingGroupTape.value[0]
  if (!group?.materialId) return false
  gateGroupKey.value = group.materialId
  toast.warn(t('cutting.edge.pickFirstGroup'))
  await nextTick()
  document
    .getElementById(`group-tape-${group.materialId}`)
    ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  return true
}

async function optimize() {
  if (cutting.optimizing || creatingDraft.value || !canOptimize.value) return
  if (await blockedByMissingGroupTape()) return
  optimizeError.value = null
  optimizeRowError.value = null
  if (isNewDraft.value) {
    creatingDraft.value = true
    try {
      // A pending autosave may mint and route to the saved editor. Mark the
      // one CTA busy before that round-trip so it cannot be triggered twice.
      await autosave.flush()
      if (!isNewDraft.value) {
        creatingDraft.value = false
        await optimize()
        return
      }
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
    await cutting.optimizeDraft(draftId.value)
    await router.push(rolePath(adapter.paths.result(draftId.value)))
    return
  } catch (errorValue) {
    optimizeError.value = clientErrorLabel(cutting.error, t('cutting.error.optimizeFailed'))
    optimizeRowError.value = optimizeRowFromError(errorValue)
    if (optimizeRowError.value?.partRef) failedRowRef = optimizeRowError.value.partRef
    else if (optimizeRowError.value?.rowIndex != null) {
      // row_index is 1-indexed (backend enumerate start=1) → 0-indexed array.
      failedRowRef = parts.value[optimizeRowError.value.rowIndex - 1]?.part_ref ?? null
    }
  }
  await nextTick()
  // On a row-attributed failure, keep the user in the editor and bring that
  // row into view. General errors stay beside the sticky optimise action.
  if (failedRowRef) {
    document
      .getElementById(`part-row-${failedRowRef}`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
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
    if (abandoningNewDraft) return
    // Hand off to the standalone result stage; the guard must not treat this as discarding.
    leavingAfterCreate.value = true
    await router.replace(rolePath(adapter.paths.result(id)))
  } catch (errorValue) {
    // The parts are still in local state, so the user keeps their work and can
    // retry; the row attribution still maps because the parts are unchanged.
    optimizeError.value = clientErrorLabel(
      cutting.error ?? apiErrorCode(errorValue),
      t('cutting.error.optimizeFailed'),
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
    cutting.loadMaterials({ tape: false, branchId, draftId: boardScopeDraftId.value }),
    cutting.loadMaterials({ tape: true, branchId }),
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
    // Don't clobber a pending pick while the picker is open (e.g. a debounced
    // autosave round-trips mid-selection); mirror the saved preference otherwise.
    if (!branchPickerOpen.value) selectedBranchId.value = seededBranchId(value.preferred_branch_id)
  },
  { immediate: true },
)

onMounted(async () => {
  window.addEventListener('beforeunload', onBeforeUnload)
  if (isNewDraft.value) {
    // `/cutting/new` is always a distinct drawing. A shared recovery key here
    // would otherwise repopulate this editor with the previous new draft.
    clearDraftRecovery()
    // Fixed-branch mode: the branch is the app context, so it cannot be
    // unselected by the user.
    if (fixedBranch.value) {
      localBranchId.value = fixedBranch.value.id
      selectedBranchId.value = fixedBranch.value.id
      await loadMaterials()
      return
    }
    // A client-side new drawing always starts with no branch selection.
    await cutting.loadBranchOptions()
    selectedBranchId.value = null
    // Decision 17: the branch is settled BEFORE the editor opens (the pin, or
    // the branch whose «Yangi chizma» was tapped), so the client editor never
    // opens a picker of its own. A pin-less URL is a route-guard redirect to
    // Ustaxonalarim; the empty state below is the last-resort recovery when
    // that guard has not run.
    branchPickerOpen.value = !isClientEditor.value
    await loadMaterials()
    return
  }
  // Reuse an already-loaded draft (e.g. just optimised from the new editor) to
  // avoid a load flash; otherwise fetch it.
  if (cutting.currentDraft?.id !== draftId.value) await cutting.loadDraft(draftId.value)
  // Resuming a saved walk-in draft (from the saved-drafts list, or after a
  // reload): the walk-in identity strip needs its client, which the resolve step
  // seeded only during the continuous flow. Re-hydrate it here so a resumed draft
  // still names who it's for. Revision drafts hide the strip, so skip them.
  const resumedDraft = draft.value
  if (
    isWorkshopScope.value &&
    resumedDraft &&
    !resumedDraft.revision_of_order_id &&
    cutting.walkInClient?.id !== resumedDraft.client_id
  ) {
    try {
      await cutting.loadWalkInClient(resumedDraft.client_id)
    } catch {
      // A missing/blocked client shouldn't block editing the drawing itself.
    }
  }
  // Branch options power the picker; when the app supplies the branch there's no
  // picker and no workshop branch-options endpoint, so skip the load. Keyed on
  // `appSuppliesBranch`, not `fixedBranch`: on a cold load the frozen branch is
  // still null here and calling the client-only endpoint would just 404.
  if (!appSuppliesBranch.value) await cutting.loadBranchOptions()
  selectedBranchId.value = seededBranchId(draft.value?.preferred_branch_id)
  const recovered = readDraftRecovery()
  if (recovered) {
    autosave.hydrate(() => {
      parts.value = recovered.parts.map((part) => normalizeSources(part))
    })
    void nextTick(() => autosave.schedule())
  }
  // The workshop takes its branch from the app context and has no options to
  // show; the client's branch is settled before the editor opens (decision 17).
  // Neither raises a picker here any more.
  if (!selectedBranchId.value && !appSuppliesBranch.value && !isClientEditor.value) {
    branchPickerOpen.value = true
  }
  await loadMaterials()
})

// Cold load into the editor: the app's branch context arrives after mount, so
// adopt it as soon as it lands for a draft that has none of its own.
watch(contextBranchId, (value) => {
  if (!value || isNewDraft.value || selectedBranchId.value) return
  if (draft.value?.preferred_branch_id) return
  selectedBranchId.value = value
  branchPickerOpen.value = false
  void loadMaterials()
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', onBeforeUnload)
  if (isNewDraft.value) {
    autosave.cancel()
    return
  }
  // Flush a debounced edit before teardown so navigating away within the 700ms
  // window doesn't silently drop it (CB-15). The store action outlives the
  // component, so the PATCH still completes.
  if (
    hasImportedMapResult.value &&
    !importedLayoutWarningAccepted.value &&
    !isGeometryNeutralEdit(draft.value?.parts_snapshot ?? [], parts.value)
  ) {
    return
  }
  void autosave.flush()
})

function onBeforeUnload() {
  // Browsers do not wait for an async request here. The recovery snapshot was
  // written synchronously on every edit; flush still helps when the browser
  // keeps the request alive during unload.
  void autosave.flush()
}

onBeforeRouteLeave(async () => {
  // A `/cutting/new` entry is disposable. Do not hold Back navigation for an
  // autosave, and prevent an in-flight save from replacing the destination.
  if (isNewDraft.value) {
    if (!leavingAfterCreate.value) {
      abandoningNewDraft = true
      autosave.cancel()
    }
    // The first autosave itself replaces `/new` with the persisted draft URL.
    // Waiting for that autosave here would make the save and navigation wait on
    // each other indefinitely.
    return true
  }
  await autosave.flush()
  return saveState.value !== 'error'
})
</script>

<template>
  <section :class="inOrderWizard ? 'wizard-page' : ''">
    <!-- The editor is a leaf with no other way out — every other client detail
         screen carries this link. `adapter.paths.drafts` so the workshop shell
         lands on its own list, and the route guard still flushes the autosave
         on the way out. -->
    <RouterLink v-if="!inOrderWizard" :to="rolePath(adapter.paths.drafts)" class="client-back">
      <span aria-hidden="true">←</span> {{ $t('cutting.editor.backToDrafts') }}
    </RouterLink>

    <!-- In the staff order flow this screen is step 2 of four, so it wears the
         wizard's head instead of naming itself. Everywhere else — the client
         SPA, a revision, a placed order's read-only drawing — it is a screen in
         its own right and keeps its own title and its back link. -->
    <OrderWizardHead v-if="inOrderWizard" :step="2" cancellable @cancel="requestCancelWizard">
      <template #tools>
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
      </template>
    </OrderWizardHead>

    <!-- §7.0, phones: the draft NAME is the page title — inline-editable, with
         the saved chip beside it and delete demoted into a ⋯ menu. There is no
         «Chizma» H1 above it: two titles for one screen, one of them generic,
         is the duplicate the phone shell explicitly drops. Desktop keeps the
         H1 + name + outline delete the canvas draws. -->
    <div v-else-if="isClientEditor" class="mb-3 flex items-center gap-2.5 md:hidden">
      <input
        v-if="draftNameEditing"
        v-model="draftNameValue"
        class="mp-input min-w-0 flex-1 text-lg font-bold"
        maxlength="64"
        :placeholder="$t('cutting.editor.namePlaceholder')"
        :aria-label="$t('cutting.editor.namePlaceholder')"
        autofocus
        @keydown.enter.prevent="commitDraftName"
        @keydown.esc.prevent="cancelDraftNameEdit"
        @blur="commitDraftName"
      />
      <button
        v-else-if="!isReadOnly"
        type="button"
        class="flex min-w-0 flex-1 items-center gap-1.5 border-b border-dashed border-hairline-strong pb-0.5 text-left font-display text-[22px] font-bold tracking-[-0.02em] text-ink"
        @click="beginDraftNameEdit"
      >
        <span class="min-w-0 truncate">{{
          isNewDraft
            ? localDraftName || $t('cutting.editor.untitled')
            : draft
              ? draftDisplayName(draft)
              : $t('cutting.editor.untitled')
        }}</span>
        <Icon name="pencil" class="size-4 shrink-0 text-ink-muted" />
      </button>
      <span v-else class="min-w-0 flex-1 truncate text-lg font-bold text-ink">{{
        draft ? draftDisplayName(draft) : $t('cutting.editor.untitled')
      }}</span>
      <span
        v-if="!isNewDraft && !isReadOnly"
        class="mp-chip shrink-0"
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
      <!-- Decision 20: the drawing's ⋯ stays a single item. -->
      <ActionMenu
        v-if="!isNewDraft && !isReadOnly"
        :label="$t('cutting.editor.draftActionsAria')"
        trigger-class="mp-action-icon-button size-9 min-h-0 shrink-0 text-ink-muted"
        :items="[{ label: $t('cutting.editor.deleteDraft'), icon: 'trash', danger: true }]"
        @select="requestDeleteDraft"
      />
    </div>

    <div
      v-if="!inOrderWizard"
      class="client-page-head"
      :class="isClientEditor ? 'max-md:hidden' : ''"
    >
      <div>
        <h1>{{ $t('cutting.editor.title') }}</h1>
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
          v-if="!isNewDraft"
          type="button"
          class="mp-button mp-button-outline gap-2 border-danger text-danger hover:border-danger hover:bg-danger-soft"
          :aria-label="$t('cutting.editor.deleteDraft')"
          @click="requestDeleteDraft"
        >
          <Icon name="trash" class="size-[18px]" />
          {{ $t('cutting.editor.deleteDraft') }}
        </button>
      </div>
    </div>

    <section v-if="cutting.loading" class="grid gap-3" aria-live="polite">
      <div class="client-skeleton h-28"></div>
      <div class="client-skeleton h-64"></div>
    </section>

    <section v-else-if="cutting.error" class="client-error">
      <div class="client-error-icon">!</div>
      <h3>{{ $t('cutting.editor.loadErrorTitle') }}</h3>
      <p>{{ $t('cutting.editor.loadErrorBody') }}</p>
      <p class="client-trace">{{ traceLine(cutting.traceId) }}</p>
    </section>

    <template v-else-if="draft || isNewDraft">
      <RouterLink
        v-if="isReadOnly"
        :to="rolePath(adapter.paths.orderDetail(String(boundOrderId)))"
        class="client-banner info hover:border-accent"
      >
        <span class="grid size-6 shrink-0 place-items-center text-ink" aria-hidden="true">
          <Icon name="lock" />
        </span>
        <span class="min-w-0 flex-1">
          {{ $t('cutting.editor.readOnlyBanner') }}
          <span class="font-bold text-accent-deep">{{ $t('cutting.editor.openOrder') }} →</span>
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
            class="grid size-6 shrink-0 place-items-center rounded-md bg-accent-soft text-accent-strong"
            aria-hidden="true"
          >
            <Icon name="pencil" class="size-4" />
          </span>
          <div class="min-w-0 flex-1">
            <b class="text-ink">
              {{
                revisionOrder
                  ? $t('cutting.editor.revisionOf', { order: revisionOrder.order_number })
                  : $t('cutting.editor.revisionGeneric')
              }}
            </b>
            <span v-if="revisionOrder" class="ml-2 text-xs text-ink-muted">{{
              revisionOrder.contact_name
            }}</span>
          </div>
          <RouterLink
            :to="rolePath(adapter.paths.orderDetail(String(revisionOrderId)))"
            class="text-xs font-bold text-accent-deep"
          >
            {{ $t('cutting.editor.backToOrder') }} →
          </RouterLink>
        </section>

        <!-- Walk-in identity strip: staff always sees who the order is being
             created for. Not in the wizard — step 1 identified the client one
             screen ago and step 4 states them again before the commit, so a
             third copy here is a band of chrome above the work. -->
        <section
          v-if="isWorkshopScope && cutting.walkInClient && !revisionOrderId && !inOrderWizard"
          class="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-hairline bg-elevated px-4 py-2.5 text-sm"
        >
          <span
            class="grid size-6 shrink-0 place-items-center rounded-md bg-accent-soft font-black text-accent-strong"
            aria-hidden="true"
          >
            @
          </span>
          <div class="min-w-0 flex-1">
            <b class="text-ink">{{ cutting.walkInClient.name }}</b>
            <span class="ml-2 text-xs text-ink-muted">{{ cutting.walkInClient.phone }}</span>
          </div>
        </section>

        <!-- App-supplied branch: a locked label, no picker (the branch is the
             app context and can't change mid-draft). Keyed on
             `appSuppliesBranch` so a cold load — where the frozen branch is
             still null — names the branch instead of showing nothing. -->
        <!-- Not in the wizard: the branch is named in the wizard head's subtitle
             on the step that chose it, and again in the sidebar's workshop card. -->
        <section
          v-if="appSuppliesBranch && !inOrderWizard"
          class="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-hairline bg-elevated px-4 py-2.5 text-sm text-ink-soft"
        >
          <span
            class="grid size-6 shrink-0 place-items-center rounded-md bg-info-soft font-black text-info"
            aria-hidden="true"
          >
            i
          </span>
          <div class="min-w-0 flex-1">
            <!-- A revision is locked to the ORDER's branch, and a resumed walk-in
                 draft to its own frozen branch — both may differ from the topbar
                 context the adapter froze at mount. -->
            <b class="text-ink">{{
              revisionOrder ? revisionOrder.branch_name : lockedBranchName
            }}</b>
          </div>
        </section>

        <template v-else>
          <!-- The wizard's head names the journey; a drawing name above the card
               is a second title for a thing the operator has not saved as a
               drawing yet. It comes back on the standalone editor, where the
               name is how a saved drawing is found again. -->
          <section
            v-if="!inOrderWizard"
            class="mb-3 flex items-center gap-2"
            :class="isClientEditor ? 'max-md:hidden' : ''"
          >
            <input
              v-if="draftNameEditing"
              v-model="draftNameValue"
              class="mp-input max-w-sm"
              maxlength="64"
              :placeholder="$t('cutting.editor.namePlaceholder')"
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
                  ? localDraftName || $t('cutting.editor.untitled')
                  : draft
                    ? draftDisplayName(draft)
                    : $t('cutting.editor.untitled')
              }}</span>
              <Icon name="pencil" class="inline size-4 text-ink-muted" />
            </button>
            <span v-else class="text-lg font-bold text-ink">{{
              draft ? draftDisplayName(draft) : $t('cutting.editor.untitled')
            }}</span>
          </section>
          <section
            v-if="preferredBranch && !branchPickerOpen"
            class="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-hairline bg-elevated px-4 py-2.5 text-sm text-ink-soft"
          >
            <span
              class="grid size-6 shrink-0 place-items-center rounded-md bg-info-soft font-black text-info"
              aria-hidden="true"
            >
              i
            </span>
            <!-- Decision 17: read-only. The branch is fixed at creation — the
                 pin, or the branch whose «Yangi chizma» started this drawing —
                 so there is no «O'zgartirish» and no picker here. Decision 16
                 gives the name: workshop first, branch only when the workshop
                 has more than one. -->
            <div class="min-w-0 flex-1">
              <b class="text-ink">{{
                isClientEditor
                  ? clientBranchLabel
                  : `${preferredBranch.branch_name} · ${preferredBranch.workshop_name}`
              }}</b>
            </div>
            <button
              v-if="!isClientEditor"
              type="button"
              class="mp-button mp-button-outline"
              @click="branchPickerOpen = true"
            >
              {{ $t('cutting.editor.change') }}
            </button>
          </section>
        </template>

        <!-- The board sizes to its own content and the kromka panel sits next to
             it — a wrap, not a breakpoint. The board's columns are fixed, so its
             width is knowable, and `flex-wrap` puts the panel underneath exactly
             when there is no room beside it. No media query, no container query,
             and nothing to re-tune when a column width changes. -->
        <!-- Esc clears the selection from anywhere in step 2, including from
             inside a number cell. `.stop` so it does not travel on to the
             wizard's own cancel — the operator is dismissing the panel, not
             the order. -->
        <div ref="stepShell" @keydown.esc.stop="docksKromka && clearActivePart()">
          <!-- §7.5: on the client this is a real two-column grid at `lg`
               (`minmax(0,1fr) 340px`), not the wizard's measured wrap — the
               client board is fluid, so there is no knowable width to wrap
               against, and the docked card wants a fixed column. -->
          <div
            :class="
              inOrderWizard
                ? 'flex flex-wrap items-start gap-[18px]'
                : isClientEditor && activePart
                  ? 'grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_340px]'
                  : ''
            "
          >
            <!-- `contents` normally dissolves this wrapper so the card and the
                 sticky bar are siblings of the page. Under the client's docked
                 grid it must stay a real box, or both would become grid items
                 and the bar would land in the kromka column. -->
            <div
              :class="
                inOrderWizard ? 'shrink' : isClientEditor && activePart ? 'min-w-0' : 'contents'
              "
            >
              <!-- A panel, not a bordered block: `.client-card` also sets
             `overflow: hidden`, which would trap the row grid's own horizontal
             scroller on a narrow viewport. `w-max` is what makes the wrap work:
             the card asks for exactly its columns' width, so the panel either
             fits beside it or drops below. -->
              <section
                :class="
                  inOrderWizard
                    ? 'mp-scroll w-max max-w-full overflow-x-auto rounded-2xl bg-elevated px-6 pb-6 pt-5 shadow-panel lg:min-w-[745px]'
                    : 'client-card'
                "
              >
                <div
                  :class="
                    inOrderWizard
                      ? 'mb-1 flex flex-wrap items-center gap-3.5 border-b border-divider pb-4'
                      : 'client-card-h'
                  "
                >
                  <div>
                    <!-- The wizard's head already names the screen; a second heading
                   here would say "Detallar" one line under the chip that says
                   the same thing. What is left is the count, which is the one
                   fact this row carries. -->
                    <h2 v-if="!inOrderWizard">{{ $t('cutting.parts.heading') }}</h2>
                    <p
                      :class="
                        inOrderWizard
                          ? 'text-[14.5px] font-semibold text-ink'
                          : 'mt-1 text-sm text-ink-muted'
                      "
                    >
                      <!-- Counts only. The m² was an estimate of the parts, not
                           of what gets bought, and it sat one line above a board
                           where the operator is entering the numbers it is
                           derived from; step 3 gives the figure that matters. -->
                      {{ totalQuantity }} {{ $t('cutting.unit.part', totalQuantity) }} ·
                      {{ materialCount }} {{ $t('cutting.unit.material', materialCount) }}
                      <template v-if="!inOrderWizard">
                        · ~{{ totalAreaM2.toFixed(1) }} {{ $t('cutting.unit.areaM2') }}
                      </template>
                    </p>
                  </div>
                  <div
                    v-if="!isReadOnly && activeBranchId"
                    class="flex flex-wrap items-center gap-2"
                  >
                    <button
                      v-if="errorCount > 0"
                      type="button"
                      class="mp-chip bg-danger-soft text-danger"
                      :aria-pressed="errorFilterEnabled"
                      @click="errorFilterEnabled = !errorFilterEnabled"
                    >
                      {{ $t('cutting.editor.unfilledCount', { n: errorCount }, errorCount) }}
                    </button>
                    <!-- Outside the wizard the two entry modes are a segmented pair.
                   Inside it the import lives with the other "add something"
                   actions at the foot of the list, where the design puts it.
                   Decision 18 / §7.6: the CLIENT app has no import surface at
                   all — no mode switch, no flag, no workshop setting. The
                   wizard and the backend parsers stay for the walk-in flow. -->
                    <div
                      v-if="!inOrderWizard && !isClientEditor"
                      class="inline-flex rounded-lg border border-hairline bg-sunk p-1"
                    >
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
                        {{ $t('cutting.editor.manualEntry') }}
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
                        {{ $t('cutting.import.title') }}
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
                  :aria-label="
                    $t(
                      'cutting.editor.bulkGroupLabel',
                      { n: selectedParts.length },
                      selectedParts.length,
                    )
                  "
                  class="hidden flex-wrap items-center gap-x-5 gap-y-2 border-b border-accent-tint bg-accent-soft px-5 py-3 text-sm font-bold lg:flex"
                >
                  <button
                    type="button"
                    class="text-accent-strong hover:underline"
                    @click="openBulkEdge"
                  >
                    {{ $t('cutting.editor.bulkApplyEdge') }}
                  </button>
                  <button
                    type="button"
                    class="text-accent-strong hover:underline"
                    @click="openBulkMaterial"
                  >
                    {{ $t('cutting.editor.bulkChangeMaterial') }}
                  </button>
                  <button type="button" class="text-danger hover:underline" @click="bulkDelete">
                    {{ $t('cutting.action.delete') }}
                  </button>
                  <button
                    type="button"
                    class="ml-auto text-ink-muted hover:text-ink"
                    @click="clearSelection"
                  >
                    {{ $t('cutting.action.cancel') }}
                  </button>
                </div>

                <div v-if="!activeBranchId" class="client-card-b">
                  <div class="client-empty">
                    <div class="client-empty-icon"><Icon name="store" /></div>
                    <h3>{{ $t('cutting.editor.pickBranchTitle') }}</h3>
                    <p>{{ $t('cutting.editor.pickBranchBody') }}</p>
                    <button
                      type="button"
                      class="mp-button mp-button-primary mt-4"
                      @click="branchPickerOpen = true"
                    >
                      {{ $t('cutting.branch.pick') }}
                    </button>
                  </div>
                </div>

                <div v-else-if="parts.length === 0" class="client-card-b">
                  <div class="client-empty">
                    <h3>{{ $t('cutting.editor.emptyTitle') }}</h3>
                    <p>{{ $t('cutting.editor.emptyBody') }}</p>
                    <div class="mt-4 flex flex-wrap justify-center gap-2.5">
                      <button
                        type="button"
                        class="mp-button mp-button-primary"
                        @click="openNewMaterial"
                      >
                        {{
                          isClientEditor
                            ? $t('cutting.editor.addMaterialClient')
                            : `+ ${$t('cutting.editor.emptyAction')}`
                        }}
                      </button>
                      <!-- The import is a first-run path, not an advanced one: a shop
                     that already keeps its cut lists in a file should not have
                     to find the mode switch to use one. -->
                      <button
                        v-if="inOrderWizard"
                        type="button"
                        class="mp-button mp-button-outline"
                        @click="openImportWizard"
                      >
                        {{ $t('cutting.import.title') }}
                      </button>
                    </div>
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
                  <!-- One header above every group outside the wizard; inside it the
                 design repeats the header per group, right under the material it
                 belongs to, which is what a list of two materials needs. -->
                  <div
                    v-if="!inOrderWizard"
                    class="hidden border-b border-hairline bg-sunk px-3 py-2 @min-[660px]:block"
                  >
                    <div
                      class="grid grid-cols-[26px_208px_80px_80px_56px_62px_54px_44px] items-center gap-[7px] w-max text-[11px] font-extrabold text-ink-muted"
                    >
                      <span aria-hidden="true" class="text-center">#</span>
                      <span aria-hidden="true" class="text-center">{{
                        $t('cutting.column.name')
                      }}</span>
                      <span aria-hidden="true" class="text-center">{{
                        $t('cutting.column.length')
                      }}</span>
                      <span aria-hidden="true" class="text-center">{{
                        $t('cutting.column.width')
                      }}</span>
                      <span aria-hidden="true" class="text-center">{{
                        $t('cutting.column.quantity')
                      }}</span>
                      <span aria-hidden="true" class="text-center">{{
                        $t('cutting.column.rotation')
                      }}</span>
                      <span aria-hidden="true" class="text-center">{{
                        $t('cutting.column.edge')
                      }}</span>
                      <span aria-hidden="true"></span>
                    </div>
                  </div>
                  <!-- In the wizard a group is a block with a rule under it, not a
                       bordered tinted box: the card already frames the board, and a
                       box inside a box put a line hard against the row numbers. -->
                  <section
                    v-for="group in visibleGroups"
                    :key="group.key"
                    :class="
                      inOrderWizard
                        ? 'overflow-visible border-b border-divider py-[18px] last:border-b-0'
                        : 'overflow-visible rounded-lg border border-hairline bg-sunk/40'
                    "
                  >
                    <div
                      :class="
                        inOrderWizard
                          ? 'mb-3 flex flex-wrap items-center gap-2'
                          : 'sticky top-0 z-10 flex flex-wrap items-center gap-2 border-b border-hairline bg-elevated px-3 py-2'
                      "
                    >
                      <button
                        type="button"
                        class="flex min-w-0 flex-1 flex-wrap items-center justify-between gap-3 text-left"
                        @click="toggleGroup(group.key)"
                      >
                        <span class="flex min-w-0 flex-1 items-center gap-3">
                          <Icon
                            :name="
                              collapsedGroupKeys.has(group.key) ? 'chevron-right' : 'chevron-down'
                            "
                            class="size-4 shrink-0 text-ink-muted"
                            aria-hidden="true"
                          />
                          <!-- One decor, one colour, all the way through: this swatch,
                         the picker one step back and the result one step on all
                         hash the decor's `name`. Hashing the composed label here
                         instead would repaint the same board between two screens
                         of the same wizard. -->
                          <span
                            v-if="inOrderWizard"
                            class="size-[30px] shrink-0 rounded-lg border border-hairline"
                            :style="
                              group.materialId
                                ? groupSwatchStyle(group.materialId)
                                : { background: 'var(--color-sunk)' }
                            "
                            aria-hidden="true"
                          ></span>
                          <!-- §7.3: on the client the decor's own picture takes
                               the colour dot's place — a 6px dot of a hashed
                               pastel never told anyone which board this is.
                               No image → the shared swatch, at the same size,
                               so the row never loses its leading mark. -->
                          <AuthFileImage
                            v-else-if="isClientEditor && groupDecorImageId(group.materialId)"
                            :file-id="groupDecorImageId(group.materialId)"
                            alt=""
                            class="size-6 shrink-0 rounded-md border border-hairline object-cover"
                          />
                          <span
                            v-else
                            class="shrink-0 rounded-full"
                            :class="
                              isClientEditor ? 'size-6 rounded-md border border-hairline' : 'size-3'
                            "
                            :style="
                              group.materialId
                                ? groupSwatchStyle(group.materialId)
                                : { background: 'var(--color-ink-muted)' }
                            "
                            aria-hidden="true"
                          ></span>
                          <!-- In the wizard the name owns the first line and the counts
                         drop under it, so a long decor name has the row's whole
                         width instead of competing with the figures for it. -->
                          <span class="min-w-0 flex-1">
                            <span class="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
                              <button
                                v-if="!isReadOnly && group.materialId"
                                type="button"
                                class="min-w-0 max-w-full truncate border-b border-dashed border-ink-muted text-left font-extrabold text-ink hover:border-accent"
                                :class="inOrderWizard ? 'text-[15px]' : 'text-sm'"
                                @click.stop="openGroupMaterial(group)"
                              >
                                {{ group.label }}
                              </button>
                              <span
                                v-else
                                class="min-w-0 truncate font-extrabold text-ink"
                                :class="inOrderWizard ? 'text-[15px]' : 'text-sm'"
                                >{{ group.label }}</span
                              >
                            </span>
                            <span
                              v-if="inOrderWizard"
                              class="num mt-0.5 block text-[12.5px] text-ink-muted"
                            >
                              <template v-if="groupSize(group.materialId)"
                                >{{ groupSize(group.materialId) }} · </template
                              >{{ group.quantity }} {{ $t('cutting.unit.part', group.quantity) }}
                            </span>
                          </span>
                        </span>
                        <span
                          class="flex items-center gap-2 text-xs font-bold text-ink-muted"
                          :class="inOrderWizard ? 'shrink-0' : ''"
                        >
                          <span v-if="!inOrderWizard"
                            >{{ group.quantity }} {{ $t('cutting.unit.part', group.quantity) }} ·
                            {{ group.areaM2.toFixed(1) }} {{ $t('cutting.unit.areaM2') }}</span
                          >
                          <span
                            v-if="groupErrorCount(group.key) > 0"
                            class="rounded-md bg-danger-soft px-2 py-1 text-danger"
                          >
                            {{
                              $t(
                                'cutting.editor.unfilledCount',
                                { n: groupErrorCount(group.key) },
                                groupErrorCount(group.key),
                              )
                            }}
                          </span>
                        </span>
                      </button>
                      <!-- Sibling of the collapse button, never a child of it: inside,
                     the chip would join that button's accessible name and read
                     as a control. It is a statement about the material, and the
                     counts behind it belong to the post-optimizer dialog. -->
                      <span
                        v-if="group.materialId && !inOrderWizard"
                        class="shrink-0 rounded px-1.5 py-0.5 text-[11px] font-bold"
                        :class="
                          materialIsOwn(group.materialId)
                            ? 'bg-accent-soft text-accent-strong'
                            : 'bg-neutral-soft text-ink-nav'
                        "
                        >{{ materialSourceLabel(group.materialId) }}</span
                      >
                      <button
                        v-if="!isReadOnly"
                        type="button"
                        class="inline-flex min-h-9 items-center gap-1.5 rounded-md border border-hairline-strong bg-sunk px-3 text-xs font-bold text-ink transition hover:border-accent-tint"
                        :class="isClientEditor ? 'max-md:hidden' : ''"
                        @click="addGroupRow(group)"
                      >
                        <Icon name="plus" class="size-3.5" />
                        {{ $t('cutting.editor.addPart') }}
                      </button>
                    </div>
                    <div v-if="inOrderWizard" class="hidden pb-1.5 @min-[660px]:block">
                      <div
                        class="grid grid-cols-[26px_208px_80px_80px_56px_62px_54px_44px] items-center gap-[7px] w-max text-[11px] font-extrabold text-ink-muted"
                      >
                        <span aria-hidden="true" class="text-center">№</span>
                        <span aria-hidden="true" class="text-center">{{
                          $t('cutting.column.name')
                        }}</span>
                        <span aria-hidden="true" class="text-center">{{
                          $t('cutting.column.length')
                        }}</span>
                        <span aria-hidden="true" class="text-center">{{
                          $t('cutting.column.width')
                        }}</span>
                        <span aria-hidden="true" class="text-center">{{
                          $t('cutting.column.quantity')
                        }}</span>
                        <span aria-hidden="true" class="text-center">{{
                          $t('cutting.column.rotation')
                        }}</span>
                        <span aria-hidden="true" class="text-center">{{
                          $t('cutting.column.edge')
                        }}</span>
                        <span aria-hidden="true"></span>
                      </div>
                    </div>
                    <!-- §7.1: on the client the registry line is REPLACED by the
                         group's tape line — it names one tape decor and the
                         thicknesses the branch stocks it in, and it is itself
                         the control that changes them. A numbering has nothing
                         left to number once a material group carries one tape. -->
                    <CuttingGroupTapeLine
                      v-if="isClientEditor && group.materialId"
                      :id="`group-tape-${group.materialId}`"
                      :decor="groupTapeFor(group.materialId)"
                      :armed="gateGroupKey === group.materialId"
                      :dense="false"
                      @open="openTapePicker(group.materialId)"
                    />

                    <!-- The registry names every tape in the drawing; on the parts
                         screen it is a second list of things the operator is not
                         editing here. The kromka panel names the tape it is
                         setting, and step 3 totals them. -->
                    <div
                      v-if="
                        !inOrderWizard &&
                        !isClientEditor &&
                        groupEdgeRegistryEntries(group).length > 0
                      "
                      class="border-t border-hairline px-3 pb-2 pt-1.5"
                    >
                      <CuttingEdgeTapeRegistry
                        :entries="groupEdgeRegistryEntries(group)"
                        :label-for-material="edgeRegistryLabel"
                        :narrow-warning-for-entry="edgeRegistryNarrowWarning"
                        @replace="openRegistryReplace"
                      />
                    </div>
                    <!-- §7.0: the phone list is read-only cards that open the
                         «Detal» sheet; the table below is the same parts at
                         `md` and up, where a mouse and a keyboard make eight
                         live columns the faster shape. -->
                    <div
                      v-if="isClientEditor && !collapsedGroupKeys.has(group.key)"
                      class="grid gap-2 p-2 md:hidden"
                    >
                      <CuttingPartCard
                        v-for="{ part, index } in group.parts"
                        :key="part.part_ref"
                        :part="part"
                        :index="index"
                        :display-index="displayPartIndex.get(part.part_ref)"
                        :has-error="rowHasError(part, index)"
                        @open="openPartSheet(part)"
                      />
                      <button
                        v-if="!isReadOnly"
                        type="button"
                        class="flex min-h-11 items-center justify-center gap-1.5 rounded-[10px] border border-dashed border-hairline-strong text-[13.5px] font-bold text-ink-soft transition hover:border-accent hover:text-ink"
                        @click="addGroupRow(group)"
                      >
                        <Icon name="plus" class="size-4" />
                        {{ $t('cutting.editor.addPart') }}
                      </button>
                    </div>

                    <div
                      v-if="!collapsedGroupKeys.has(group.key)"
                      :class="[
                        inOrderWizard ? 'overflow-visible' : 'overflow-visible bg-elevated',
                        isClientEditor ? 'max-md:hidden' : '',
                      ]"
                    >
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
                        :edge-registry="edgeRegistry"
                        :bare-index="inOrderWizard"
                        :selected="docksKromka && activePartRef === part.part_ref"
                        @select="docksKromka && selectPart(part)"
                        @toggle-select="toggleSelect(part.part_ref)"
                        @update:name="setPartName(part, $event)"
                        @update:length="part.length_mm = $event"
                        @update:width="part.width_mm = $event"
                        @update:quantity="part.quantity = $event"
                        @update:follow-grain="setFollowGrain(part, $event)"
                        @duplicate="duplicateRow(index)"
                        @cell-enter="(cell, side) => onCellEnter(index, cell, side)"
                        @delete="deleteRow(index)"
                        @open-edge-picker="
                          (event, side) =>
                            docksKromka ? selectPart(part, side) : openEdgePicker(part, event, side)
                        "
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
                  <!-- One control row, not two: the dashed add tiles and the CTA
                       that acts on what they added belong to the same decision.
                       `ml-auto` rides on whichever of chip / CTA comes first, so
                       the right group stays right in both states. -->
                  <div
                    :class="
                      inOrderWizard ? 'mt-[18px] flex flex-wrap items-center gap-2.5' : 'grid'
                    "
                  >
                    <button
                      type="button"
                      class="flex min-h-12 items-center justify-center gap-2 rounded-lg border border-dashed border-hairline-strong text-sm font-bold text-ink-muted transition hover:border-accent hover:bg-neutral-soft hover:text-ink"
                      :class="
                        inOrderWizard ? 'h-10 min-h-10 rounded-[11px] px-4 text-[13.5px]' : ''
                      "
                      @click="openNewMaterial"
                    >
                      <Icon name="plus" class="size-4" />
                      <!-- §7.0 fixes the client's label to «+ Material» on both
                           breakpoints; the workshop keeps «Boshqa material». -->
                      {{
                        isClientEditor
                          ? $t('cutting.editor.addMaterialClient')
                          : $t('cutting.editor.addMaterial')
                      }}
                    </button>
                    <button
                      v-if="inOrderWizard"
                      type="button"
                      class="flex h-10 min-h-10 items-center justify-center gap-2 rounded-[11px] border border-dashed border-hairline-strong px-4 text-[13.5px] font-bold text-ink-muted transition hover:border-accent hover:bg-neutral-soft hover:text-ink"
                      @click="openImportWizard"
                    >
                      {{ $t('cutting.import.title') }}
                    </button>
                    <template v-if="inOrderWizard && parts.length > 0">
                      <span
                        v-if="!cutting.optimizing && !creatingDraft && primaryCtaHint"
                        class="ml-auto inline-flex items-center rounded-[10px] bg-warning-soft px-[11px] py-[9px] text-[12.5px] font-semibold text-warning"
                      >
                        {{ primaryCtaHint }}
                      </span>
                      <button
                        type="button"
                        class="mp-button mp-button-primary h-10 min-h-10 rounded-[11px] px-[22px] text-sm"
                        :class="
                          !cutting.optimizing && !creatingDraft && primaryCtaHint ? '' : 'ml-auto'
                        "
                        :disabled="primaryCtaDisabled"
                        :title="primaryCtaHint"
                        @click="runPrimaryCta"
                      >
                        {{ primaryCtaLabel }}
                      </button>
                    </template>
                  </div>
                </div>

                <div v-if="optimizeError" class="client-banner danger mx-5 mt-4" role="alert">
                  <span class="font-black">!</span>
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

              <!-- Sticky action bar: its single primary CTA stays reachable without
             scrolling to the bottom of a long parts list. It opens a current
             chosen result or starts optimisation; disabled reasons remain visible
             inline (including on touch) instead of only in a title tooltip. -->
              <!-- In the wizard the action row is a plain right-aligned row under the
             card, as the design draws it: the list is one card on one screen, so
             a sticky bar would be chrome floating over content it never covers. -->
              <div
                v-if="!inOrderWizard && parts.length > 0"
                class="sticky bottom-0 z-20 mt-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-xl border border-hairline-strong bg-elevated/95 px-4 py-3 shadow-[0_-6px_24px_-14px_color-mix(in_srgb,var(--color-ink)_30%,transparent)] backdrop-blur"
              >
                <div class="text-sm">
                  <span class="font-bold text-ink"
                    >{{ parts.length }} {{ $t('cutting.unit.kind', parts.length) }} ·
                    {{ totalQuantity }} {{ $t('cutting.unit.piece', totalQuantity) }}</span
                  >
                  <span class="text-ink-muted"> / {{ MAX_PARTS }}</span>
                </div>
                <div class="flex flex-wrap items-center justify-end gap-3">
                  <!-- The blocker states itself as a chip rather than a whispered
                 note: it is the reason the button beside it will not move, and
                 on a touch screen a `title` tooltip never appears at all. -->
                  <span
                    v-if="!cutting.optimizing && !creatingDraft && primaryCtaHint"
                    class="inline-flex items-center rounded-[10px] bg-warning-soft px-[11px] py-[9px] text-[12.5px] font-semibold text-warning"
                  >
                    {{ primaryCtaHint }}
                  </span>
                  <button
                    type="button"
                    class="mp-button mp-button-primary"
                    :disabled="primaryCtaDisabled"
                    :title="primaryCtaHint"
                    @click="runPrimaryCta"
                  >
                    {{ primaryCtaLabel }}
                  </button>
                </div>
              </div>
            </div>
            <!-- Levelled with the row it is editing rather than pinned to the
                 top: on a three-material board the selected row can be 600px
                 down, and a panel at the top would have the operator reading two
                 places at once. The offset animates so the move is legible as
                 "the panel followed you". When the panel wraps under the board
                 there is no row to level with, so the offset is dropped. -->
            <CuttingKromkaPanel
              v-if="inOrderWizard && activePart"
              ref="kromkaPanel"
              class="transition-[margin] duration-150 ease-out"
              :style="{ marginTop: `${panelOffset}px` }"
              :part="activePart"
              :part-number="(displayPartIndex.get(activePart.part_ref) ?? 0) + 1"
              :panel-material="materialById(activePart.material_id)"
              :edge-options="cutting.edgeOptions"
              :edge-registry="edgeRegistry"
              :flash-side="activeSide"
              @edges-change="onPanelEdgesChange"
              @close="clearActivePart"
            />

            <!-- §7.5, client: the same docked card carrying §7.1's reduced
                 block. Hidden below `lg`, where the phone sheet owns kromka —
                 a 340px column has nowhere to go on a narrow viewport, and the
                 sheet is the better control there anyway. -->
            <CuttingKromkaPanel
              v-if="isClientEditor && activePart"
              variant="client"
              class="max-lg:hidden"
              :part="activePart"
              :part-number="(displayPartIndex.get(activePart.part_ref) ?? 0) + 1"
              :panel-material="materialById(activePart.material_id)"
              :edge-options="cutting.edgeOptions"
              :edge-registry="edgeRegistry"
              :flash-side="activeSide"
              :group-tape-decor="groupTapeFor(activePart.material_id)"
              :selected-thickness-mm="armedThicknessFor(groupTapeFor(activePart.material_id))"
              :foreign-tape-label="foreignTapeLabel"
              @update:selected-thickness-mm="armedThicknessMm = $event"
              @set-side="(side, materialId) => setPartSide(activePart!, side, materialId)"
              @need-tape="openTapePicker(activePart.material_id)"
              @open-group-tape="openTapePicker(activePart.material_id)"
              @close="clearActivePart"
            />
          </div>
        </div>
      </fieldset>
    </template>

    <ConfirmDialog
      :open="deleteDraftDialogOpen"
      :title="$t('cutting.editor.deleteDraft')"
      :message="
        draft
          ? $t(
              'cutting.editor.deleteDraftMessage',
              { name: draftDisplayName(draft), n: totalQuantity },
              totalQuantity,
            )
          : ''
      "
      :confirm-label="$t('cutting.action.delete')"
      :cancel-label="$t('cutting.action.cancel')"
      danger
      :busy="deletingDraft"
      @cancel="closeDeleteDraftDialog"
      @confirm="confirmDeleteDraft"
    >
      <p v-if="deleteDraftError" class="text-sm font-bold text-danger">
        {{ deleteDraftError }}{{ traceSuffix(deleteDraftTraceId) }}
      </p>
    </ConfirmDialog>

    <!-- Workshop-only mount (§7.6). Not merely hidden: the client app must not
         carry the wizard's state, its store calls or its copy at all. -->
    <CuttingImportWizard
      v-if="!isClientEditor"
      :open="importWizardOpen"
      :panel-choices="panelChoices"
      :edge-choices="edgeChoices"
      :has-existing-parts="parts.length > 0"
      :current-pieces="totalQuantity"
      :current-parts="parts.length"
      :preferred-branch-name="preferredBranch?.branch_name ?? null"
      :preferred-branch-id="activeBranchId"
      @close="closeImportWizard"
      @load="onImportLoad"
      @committed="onImportCommitted"
    />
    <AppModal
      :open="branchPickerOpen"
      :title="$t('cutting.branch.modalTitle')"
      max-width="max-w-2xl"
      @close="closeBranchPicker"
    >
      <CuttingBranchPicker
        :model-value="selectedBranchId"
        :options="pickerOptions"
        :pinned-workshop-name="pinnedWorkshopName"
        @update:model-value="setPreferredBranch"
      />
    </AppModal>

    <ConfirmDialog
      :open="importReplaceConfirmOpen"
      :title="$t('cutting.import.replaceTitle')"
      :message="$t('cutting.import.replaceMessage', { n: parts.length }, parts.length)"
      :confirm-label="$t('cutting.import.replaceConfirm')"
      :cancel-label="$t('cutting.action.cancel')"
      danger
      @cancel="cancelImportReplace"
      @confirm="confirmImportReplace"
    />

    <ConfirmDialog
      :open="importedLayoutWarningOpen"
      :title="$t('cutting.import.layoutWarningTitle')"
      :message="$t('cutting.import.layoutWarningBody')"
      :confirm-label="$t('cutting.import.layoutWarningConfirm')"
      :cancel-label="$t('cutting.action.cancel')"
      @cancel="resolveImportedLayoutWarning(false)"
      @confirm="resolveImportedLayoutWarning(true)"
    />

    <CuttingEdgePickerModal
      :part="edgePickerPart"
      :initial-side="edgePickerInitialSide"
      :part-number="edgePickerPart ? parts.indexOf(edgePickerPart) + 1 : 0"
      :title-suffix="
        bulkEdgeMode
          ? $t('cutting.edge.bulkSuffix', { n: selectedParts.length }, selectedParts.length)
          : undefined
      "
      :preferred-edge-id="edgePickerPart ? preferredEdgeId(edgePickerPart) : null"
      :edge-registry="edgeRegistry"
      :edge-assignment-entries="edgeAssignmentEntries"
      :group-edge-ids="groupEdgeIds(edgePickerPart)"
      :other-group-edge-ids="otherGroupEdgeIds(edgePickerPart)"
      @edges-change="onEdgePickerChange"
      @close="closeEdgePicker"
    />

    <div
      v-if="registryPickerOpen"
      class="fixed inset-0 z-[70] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      :aria-label="$t('cutting.edge.pickTitle')"
      @keydown.esc="closeRegistryPicker"
    >
      <div
        class="absolute inset-0 bg-ink/45 backdrop-blur-[2px]"
        @click="closeRegistryPicker"
      ></div>
      <div
        class="relative z-10 w-[min(420px,100%)] rounded-2xl border border-hairline bg-elevated p-5 shadow-[0_28px_60px_-14px_color-mix(in_srgb,var(--color-ink)_30%,transparent)]"
      >
        <div class="mb-3 flex items-start justify-between gap-3">
          <div>
            <h3 class="font-display text-lg font-semibold text-ink">
              {{ $t('cutting.edge.replaceTitle') }}
            </h3>
            <p v-if="registryReplaceEntry" class="mt-1 text-sm text-ink-muted">
              {{
                $t('cutting.edge.replaceBody', {
                  name: edgeRegistryLabel(registryReplaceEntry.materialId),
                })
              }}
            </p>
          </div>
          <button
            type="button"
            class="client-edge-close"
            :aria-label="$t('cutting.action.close')"
            @click="closeRegistryPicker"
          >
            ×
          </button>
        </div>
        <SearchCombobox
          :model-value="registryPickedEdgeId"
          :label="$t('cutting.edge.label')"
          :options="edgeChoices"
          :placeholder="$t('cutting.edge.placeholder')"
          @update:model-value="registryPickedEdgeId = $event"
        />
        <div class="mt-4 flex flex-wrap justify-end gap-2">
          <button type="button" class="mp-button mp-button-outline" @click="closeRegistryPicker">
            {{ $t('cutting.action.cancel') }}
          </button>
          <button
            type="button"
            class="mp-button mp-button-primary"
            :disabled="!registryPickedEdgeId"
            @click="applyRegistryPicker"
          >
            {{ $t('cutting.action.apply') }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── The client's three overlays (§7.0, §7.2, §7.3) ─────────────────── -->
    <CuttingPartSheet
      v-if="isClientEditor && sheetPart"
      :open="Boolean(sheetPart)"
      :part="sheetPart"
      :index="sheetPartIndex"
      :display-index="displayPartIndex.get(sheetPart.part_ref) ?? sheetPartIndex"
      :decor="sheetGroupTape"
      :selected-thickness-mm="armedThicknessFor(sheetGroupTape)"
      :foreign-tape-label="foreignTapeLabel"
      @close="closePartSheet"
      @save="closePartSheet"
      @save-and-next="savePartAndNext"
      @delete="deleteRow(sheetPartIndex)"
      @update:name="setPartName(sheetPart, $event)"
      @update:length="sheetPart.length_mm = $event"
      @update:width="sheetPart.width_mm = $event"
      @update:quantity="sheetPart.quantity = $event"
      @update:follow-grain="setFollowGrain(sheetPart, $event)"
      @update:selected-thickness-mm="armedThicknessMm = $event"
      @set-side="(side, materialId) => setPartSide(sheetPart!, side, materialId)"
      @need-tape="openTapePicker(sheetPart.material_id)"
      @open-group-tape="openTapePicker(sheetPart.material_id)"
    />

    <CuttingTapePicker
      v-if="isClientEditor"
      :open="Boolean(tapePickerGroupKey)"
      :decors="tapeDecors"
      :panel="tapePickerPanel"
      :panel-image-file-id="tapePickerPanel?.image_file_id ?? null"
      :current-key="tapePickerCurrentKey"
      :caption="tapeCatalogCaption"
      @close="closeTapePicker"
      @pick="applyGroupTape"
    />

    <CuttingMaterialPicker
      v-if="isClientEditor"
      :open="Boolean(materialPickerTarget)"
      :materials="cutting.panelOptions"
      :loading="cutting.materialsLoading"
      :current-id="materialPickerCurrentId"
      :search="materialPickerSearch"
      :caption="materialCatalogCaption"
      @close="closeMaterialPicker"
      @update:search="materialPickerSearch = $event"
      @pick="applyMaterialPicker"
    />

    <!-- The workshop's own picker: the customer-board tab and the format list
         it has always had. The client never mounts it. -->
    <div
      v-if="materialPickerTarget && !isClientEditor"
      class="fixed inset-0 z-[70] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      :aria-label="$t('cutting.material.replaceTitle')"
      @keydown.esc="closeMaterialPicker"
    >
      <div
        class="absolute inset-0 bg-ink/45 backdrop-blur-[2px]"
        @click="closeMaterialPicker"
      ></div>
      <div
        class="relative z-10 w-[min(460px,100%)] overflow-hidden rounded-2xl border border-hairline bg-elevated shadow-[0_28px_60px_-14px_color-mix(in_srgb,var(--color-ink)_30%,transparent)]"
      >
        <div class="flex items-start justify-between gap-3 border-b border-hairline px-5 py-4">
          <div>
            <h3 class="text-base font-extrabold text-ink">
              {{ $t('cutting.material.replaceTitle') }}
            </h3>
            <p class="mt-1 text-sm text-ink-muted">{{ materialPickerSubtitle }}</p>
          </div>
          <button
            type="button"
            class="client-edge-close"
            :aria-label="$t('cutting.action.close')"
            @click="closeMaterialPicker"
          >
            ×
          </button>
        </div>
        <div class="border-b border-hairline px-5 py-3">
          <!-- Workshop only: the client SPA has no counter to hand a board
               across, and no draft of its own to scope one to. -->
          <SegmentedControl
            v-if="canAddCustomerBoard"
            v-model="materialPickerMode"
            class="mb-3"
            hide-label
            :label="$t('cutting.customerBoard.modeLabel')"
            :options="materialPickerModes"
          />
          <template v-if="materialPickerMode === 'shop'">
            <label class="sr-only" for="material-picker-search">
              {{ $t('cutting.material.searchLabel') }}
            </label>
            <input
              id="material-picker-search"
              v-model="materialPickerSearch"
              type="search"
              class="mp-input w-full"
              :placeholder="$t('cutting.material.searchPlaceholder')"
            />
          </template>
        </div>

        <!-- `v-if`, never `v-show`: the stock list's own assertions count the
             dialog's sections, and a hidden panel is still in the tree. -->
        <div v-if="materialPickerMode === 'own'" class="grid gap-3 p-5">
          <p class="text-sm leading-[1.45] text-ink-soft">
            {{ $t('cutting.customerBoard.intro') }}
          </p>
          <label class="field !mb-0">
            <span
              >{{ $t('cutting.customerBoard.nameLabel') }}
              <small class="text-ink-muted">{{ $t('cutting.customerBoard.optional') }}</small></span
            >
            <input
              v-model="customerBoard.name"
              class="mp-input"
              maxlength="80"
              :placeholder="$t('cutting.customerBoard.namePlaceholder')"
            />
          </label>
          <div class="grid grid-cols-2 gap-3">
            <label class="field !mb-0">
              <span>{{ $t('cutting.customerBoard.length') }}</span>
              <input
                v-model="customerBoard.uzunlik"
                class="mp-input"
                inputmode="numeric"
                placeholder="2750"
              />
            </label>
            <label class="field !mb-0">
              <span>{{ $t('cutting.customerBoard.width') }}</span>
              <input
                v-model="customerBoard.eni"
                class="mp-input"
                inputmode="numeric"
                placeholder="1830"
              />
            </label>
            <label class="field !mb-0">
              <span>{{ $t('cutting.customerBoard.thickness') }}</span>
              <input
                v-model="customerBoard.qalinlik"
                class="mp-input"
                inputmode="decimal"
                placeholder="16"
              />
            </label>
            <label class="field !mb-0">
              <span>{{ $t('cutting.customerBoard.sheets') }}</span>
              <input
                v-model="customerBoard.sheets"
                class="mp-input"
                inputmode="numeric"
                placeholder="2"
              />
            </label>
          </div>
          <button
            type="button"
            class="inline-flex h-[38px] w-fit items-center gap-2 rounded-lg border border-hairline px-3.5 text-[13.5px] font-semibold transition"
            :class="
              customerBoard.has_grain
                ? 'bg-accent-soft text-accent-strong'
                : 'bg-elevated text-ink hover:bg-sunk'
            "
            :aria-pressed="customerBoard.has_grain"
            @click="customerBoard.has_grain = !customerBoard.has_grain"
          >
            {{ $t('cutting.customerBoard.textured') }}
          </button>
          <p v-if="customerBoardError" class="mp-field-error !mt-0">{{ customerBoardError }}</p>
          <div class="mt-1 flex justify-end gap-2.5">
            <button type="button" class="mp-button mp-button-outline" @click="closeMaterialPicker">
              {{ $t('cutting.action.cancel') }}
            </button>
            <button
              type="button"
              class="mp-button mp-button-primary"
              :disabled="customerBoardSaving"
              @click="submitCustomerBoard"
            >
              {{
                customerBoardSaving
                  ? $t('cutting.editor.saveSaving')
                  : $t('cutting.customerBoard.submit')
              }}
            </button>
          </div>
        </div>
        <div v-if="materialPickerMode === 'shop'" class="grid max-h-[52vh] gap-3 overflow-auto p-3">
          <p
            v-if="materialPickerGroups.length === 0"
            class="px-2 py-6 text-center text-sm text-ink-muted"
          >
            {{
              materialPickerSearch.trim()
                ? $t('cutting.material.searchEmpty')
                : $t('cutting.material.pickerEmpty')
            }}
          </p>
          <section
            v-for="group in materialPickerGroups"
            :key="group.key"
            class="grid gap-1.5 rounded-lg border border-hairline bg-elevated p-2"
          >
            <header class="flex items-center gap-3 px-1 pt-1">
              <AuthFileImage
                v-if="group.imageFileId"
                :file-id="group.imageFileId"
                :alt="group.title"
                class="size-10 shrink-0 rounded-md object-cover shadow-[inset_0_0_0_1px_color-mix(in_srgb,var(--color-ink)_12%,transparent)]"
              />
              <span
                v-else
                class="size-10 shrink-0 rounded-md shadow-[inset_0_0_0_1px_color-mix(in_srgb,var(--color-ink)_12%,transparent)]"
                :style="materialPickerSwatchStyle(group.materials[0])"
                aria-hidden="true"
              ></span>
              <span class="min-w-0">
                <span class="block truncate text-sm font-extrabold text-ink">{{
                  group.title
                }}</span>
                <span class="mt-0.5 block text-xs font-semibold text-ink-muted">
                  {{ group.grainLabel }}
                </span>
              </span>
            </header>
            <button
              v-for="material in group.materials"
              :key="material.id"
              type="button"
              class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-md border px-3 py-2.5 text-left transition hover:border-accent-tint hover:bg-sunk"
              :class="
                material.id === materialPickerCurrentId
                  ? 'border-accent-tint bg-accent-soft'
                  : 'border-hairline'
              "
              @click="applyMaterialPicker(material.id)"
            >
              <span class="flex min-w-0 flex-wrap items-center gap-2">
                <span class="truncate text-sm font-bold text-ink">
                  {{ materialFormatLabel(material) }}
                </span>
                <span
                  v-if="material.price_unset"
                  class="rounded-full bg-warning-soft px-2 py-0.5 text-[12.5px] font-semibold text-warning"
                >
                  {{ $t('cutting.material.priceUnset') }}
                </span>
                <!-- Retired by the platform, still on the shelf: a hint, not a
                     block — the operator may well be cutting the last of it. -->
                <span
                  v-if="material.discontinued"
                  class="rounded-full bg-sunk px-2 py-0.5 text-[12.5px] font-semibold text-ink-muted"
                >
                  {{ $t('cutting.material.discontinued') }}
                </span>
              </span>
              <span
                v-if="material.id === materialPickerCurrentId"
                class="grid size-6 place-items-center rounded-full bg-accent-soft text-accent-strong"
                :aria-label="$t('cutting.material.selected')"
              >
                <Icon name="check" class="size-3.5" />
              </span>
            </button>
          </section>
          <p v-if="materialPickerGroups.length === 0" class="p-4 text-sm text-ink-muted">
            {{ $t('cutting.material.emptyInBranch') }}
          </p>
        </div>
        <!-- The own tab carries its own Bekor qilish beside its primary, where
             a form's actions belong; a second one under it would be two ways to
             do the same thing on one short dialog. -->
        <div
          v-if="materialPickerMode === 'shop'"
          class="flex justify-end border-t border-hairline px-5 py-3"
        >
          <button type="button" class="mp-button mp-button-outline" @click="closeMaterialPicker">
            {{ $t('cutting.action.cancel') }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
