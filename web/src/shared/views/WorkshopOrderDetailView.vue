<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { traceLine, traceSuffix } from '@/shared/app/errorTrace'
import { snapshotMaterialLabel } from '@/shared/app/materialLabel'
import { useRolePath } from '@/shared/app/paths'
import {
  isRevisionEvent,
  orderPhaseSteps,
  productionTimelineDetails,
  revertTargetLabelForOrder,
  revisionTimelineDetails,
  type WorkshopAdjustmentKind,
} from '@/shared/app/workshopOrderDetail'
import { ownMaterialRows } from '@/shared/app/ownMaterial'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import {
  orderPillClass,
  stockShortfallMessage,
  workshopErrorMessage,
  workshopStatusUz,
} from '@/shared/app/workshopUi'
import AppIcon from '@/shared/components/AppIcon.vue'
import AppModal from '@/shared/components/AppModal.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import CuttingPartsByMaterial from '@/shared/components/CuttingPartsByMaterial.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import OrderOwnMaterialModal from '@/shared/components/OrderOwnMaterialModal.vue'
import OrderPriceAdjustmentModal from '@/shared/components/OrderPriceAdjustmentModal.vue'
import OrderPricesModal from '@/shared/components/OrderPricesModal.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { formatDate, formatTiyin } from '@/shared/formatters'
import { translatePlural } from '@/shared/i18n'
import { useAuthStore } from '@/shared/stores/auth'
import {
  useOrdersStore,
  type OrderDetail,
  type OrderEvent,
  type OrderPriceLine,
  type OrderStockWarning,
} from '@/shared/stores/orders'
import {
  metres,
  useCuttingStore,
  type CuttingPanel,
  type CuttingPlacement,
  type CuttingResult,
} from '@/shared/stores/cutting'

const route = useRoute()
const router = useRouter()
const rolePath = useRolePath()
const cutting = useCuttingStore()
const auth = useAuthStore()
const permissions = useWorkshopPermissions()
const toast = useToast()
const orders = useOrdersStore()
const { t } = useI18n()
const orderId = computed(() => String(route.params.order_id))
const cutterId = ref<string | null>(null)
const edgerId = ref<string | null>(null)
const noteDraft = ref('')
const loadedOrderId = ref<string | null>(null)
const actionError = ref<string | null>(null)
const actionTraceId = ref<string | null>(null)
// Which single button is mid-request, so only the clicked one shows a busy
// label while orders.actionLoading still locks the rest (QAD-77).
const pendingAction = ref<string | null>(null)
const activePanelId = ref<string | null>(null)
const activePlacementId = ref<string | null>(null)
const reasonDialogAction = ref<'revert' | 'cancel' | null>(null)
const reasonDraft = ref('')
const markCollectedOpen = ref(false)
const discardEditOpen = ref(false)
const menuOpen = ref(false)
const discountOpen = ref(false)
const surchargeOpen = ref(false)
// Server-side apply/remove errors surfaced inside each modal (the page-level
// banner would otherwise hide behind the open overlay).
const discountSubmitError = ref<string | null>(null)
const surchargeSubmitError = ref<string | null>(null)
const chizmaOpen = ref(false)
const historyOpen = ref(false)
const noteEditing = ref(false)
const noteInput = ref<HTMLTextAreaElement | null>(null)

const order = computed(() => orders.currentOrder)
const result = computed(() => order.value?.cutting_result ?? null)
// An authorization outcome is not a transport failure (QAD-171). The API answers
// 404 for an order outside the reader's branches — deliberately, so the id is no
// existence oracle — and the same 404 reaches `process_production` staff for any
// order not assigned to them, which is their ordinary case, not an edge one.
// Retrying a connection that is working never turns either into a 200.
const orderOutOfReach = computed(
  () => orders.error === 'order_not_found' || orders.error === 'permission_denied',
)
const canManageOrders = computed(() =>
  permissions.canOnBranch(p.manageOrders, order.value?.branch_id),
)
const canProcessProduction = computed(() =>
  permissions.canOnBranch(p.processProduction, order.value?.branch_id),
)
// The back link goes where the reader can actually go. This page admits
// `view_orders` and `process_production`, but the orders board itself requires
// `manage_orders` — the fixed link bounced everyone else off the router guard
// (QAD-170). Branch-blind, like the guard it has to agree with, and independent
// of `order` so it doesn't change under the loading and error states.
const backLink = computed(() =>
  permissions.can(p.manageOrders)
    ? { to: rolePath('/workshop/orders'), label: t('orders.detail.backOrders') }
    : { to: rolePath('/workshop'), label: t('orders.detail.backHome') },
)
const canCompleteCutting = computed(() => {
  const current = order.value
  if (!current) return false
  return (
    canManageOrders.value ||
    (canProcessProduction.value && current.assigned_cutter_user_id === auth.me?.principal_id)
  )
})
const canCompleteBanding = computed(() => {
  const current = order.value
  if (!current) return false
  return (
    canManageOrders.value ||
    (canProcessProduction.value && current.assigned_edger_user_id === auth.me?.principal_id)
  )
})
const canViewSettlement = computed(() =>
  permissions.canAnyOnBranch([p.manageFinance, p.viewFinanceReports], order.value?.branch_id),
)
// Revision (orders.md "Revising a placed order"): pre-production only.
const canEditOrder = computed(
  () => canManageOrders.value && ['new', 'confirmed'].includes(order.value?.status ?? ''),
)
// Assignment locks per role once that stage starts: the cutter the moment the
// order leaves `confirmed`, the edger once banding is stamped started. After
// the lock the deliberate fix path is revert (which clears the start stamp).
const canAssignCutter = computed(() => canManageOrders.value && order.value?.status === 'confirmed')
const canAssignEdger = computed(() => {
  const current = order.value
  if (!current || !canManageOrders.value || !current.has_banding) return false
  if (current.status === 'confirmed' || current.status === 'cutting') return true
  return current.status === 'edge_banding' && !current.banding_started_at
})
// Both role slots share one skeleton (label + 40px box): a live select while
// assignable, a quiet value-box once locked or done — with a one-line status
// beneath. The completion line absorbs the cut counters, so there is no
// separate "Kesilgan" row.
type SlotSub = { kind: 'done' | 'hint'; text: string } | null
const cutterSub = computed<SlotSub>(() => {
  const current = order.value
  if (!current) return null
  if (current.cut_completed_at) {
    const bits = [formatDate(current.cut_completed_at)]
    if (current.cut_count_snapshot !== null)
      bits.push(translatePlural('orders.unit.cuts', current.cut_count_snapshot))
    if (current.panels_used_snapshot !== null)
      bits.push(translatePlural('orders.unit.panels', current.panels_used_snapshot))
    return { kind: 'done', text: bits.join(' · ') }
  }
  if (canManageOrders.value && current.status === 'cutting')
    return { kind: 'hint', text: t('orders.detail.cutterLocked') }
  return null
})
const edgerSub = computed<SlotSub>(() => {
  const current = order.value
  if (!current || !current.has_banding) return null
  if (current.edge_completed_at)
    return { kind: 'done', text: formatDate(current.edge_completed_at) }
  if (canManageOrders.value && current.status === 'edge_banding' && current.banding_started_at)
    return { kind: 'hint', text: t('orders.detail.edgerLocked') }
  // The open slot doesn't block the saw, so from `cutting` on it carries the
  // nudge that used to live on the (blocked) start button.
  if (canManageOrders.value && !current.assigned_edger_user_id) {
    if (current.status === 'cutting') return { kind: 'hint', text: t('orders.detail.edgerPending') }
    if (current.status === 'edge_banding')
      return { kind: 'hint', text: t('orders.detail.edgerRequired') }
  }
  return null
})
// What still blocks the start tap — surface the gap instead of a dead click.
// The edger is deliberately not required here: its gate sits at the banding
// start, so the saw never waits on a later stage's staffing.
// A branch may carry a format long before it prices it, and both catalogs show
// those rows — so an order can arrive selling one. Confirming is what turns the
// order into money owed, so that is where the backend draws the line; this is
// the same list, named on screen while it can still be fixed.
const unpricedMaterials = computed(() => order.value?.unpriced_materials ?? [])
const unpricedMissing = computed(() => {
  const current = order.value
  if (!current || current.status !== 'new' || unpricedMaterials.value.length === 0) return null
  return t('orders.detail.unpricedBlocksApprove', { count: unpricedMaterials.value.length })
})

const startCuttingMissing = computed(() => {
  const current = order.value
  if (!current || current.status !== 'confirmed') return null
  if (!current.assigned_cutter_user_id) return t('orders.detail.cutterNotChosen')
  return null
})
// Start is gated like completion: the assigned master, or the office on-behalf.
const canStartCutting = computed(() => {
  const current = order.value
  if (!current || current.status !== 'confirmed') return false
  return startCuttingMissing.value === null && canCompleteCutting.value
})
// The banding start owns the edger gate (backend `edger_required`) — only the
// office can ever see this state, a worker without the assignment gets no
// button at all.
const startBandingMissing = computed(() => {
  const current = order.value
  if (!current || current.status !== 'edge_banding' || current.banding_started_at) return null
  if (!current.assigned_edger_user_id) return t('orders.detail.edgerNotChosen')
  return null
})
const workerOptions = computed<ChoiceOption[]>(() =>
  orders.workerOptions.map((worker) => ({
    value: worker.id,
    label: worker.full_name,
    meta: worker.is_owner ? t('orders.detail.roleOwner') : t('orders.detail.roleProduction'),
  })),
)
const activePanel = computed(() => {
  const current = result.value
  if (!current) return null
  return (
    current.panels.find((panel) => panel.id === activePanelId.value) ?? current.panels[0] ?? null
  )
})
const totalPanels = computed(() =>
  result.value
    ? Object.values(result.value.panels_used_by_material).reduce((sum, count) => sum + count, 0)
    : 0,
)
const totalPieces = computed(
  () => order.value?.items.reduce((sum, item) => sum + item.quantity, 0) ?? 0,
)
const productionMeta = computed(() => {
  const pieces = translatePlural('orders.unit.parts', totalPieces.value)
  return result.value
    ? `${pieces} · ${translatePlural('orders.unit.panels', totalPanels.value)}`
    : pieces
})
const phaseSteps = computed(() => (order.value ? orderPhaseSteps(order.value) : []))
const isCancelled = computed(() => order.value?.status === 'cancelled')
const discountButtonLabel = computed(() =>
  order.value?.discount_tiyin ? t('orders.detail.discountUpdate') : t('orders.detail.discountAdd'),
)
const surchargeButtonLabel = computed(() =>
  order.value?.surcharge_tiyin
    ? t('orders.detail.surchargeUpdate')
    : t('orders.detail.surchargeAdd'),
)
const noteDirty = computed(() => noteDraft.value.trim() !== (order.value?.note_workshop ?? ''))
// Cutting would oversell stock (projected balance below zero), not just dip low —
// escalate the warning banner to danger and reword it (QAD-82).
const hasShortfall = computed(
  () => order.value?.stock_warnings.some((warning) => warning.projected_after < 0) ?? false,
)
const revertTargetLabel = computed(() =>
  order.value ? revertTargetLabelForOrder(order.value) : '',
)
const revertButtonLabel = computed(() => {
  if (!revertTargetLabel.value) return t('orders.action.revertFallback')
  const label = t('orders.action.revertTo', { target: revertTargetLabel.value })
  return label.charAt(0).toUpperCase() + label.slice(1)
})

// The single status-appropriate primary action, pinned in the header. Everything
// rarer lives in the overflow menu — one obvious "do this next" per screen.
type PrimaryAction = {
  key: string
  label: string
  busyLabel: string
  disabled?: boolean
  hint?: string | null
  run: () => void
}
const primaryAction = computed<PrimaryAction | null>(() => {
  const current = order.value
  if (!current) return null
  if (current.status === 'new' && canManageOrders.value)
    return {
      key: 'approve',
      label: t('orders.action.approve'),
      busyLabel: t('orders.busy.approving'),
      // Gated like startCutting: the backend refuses this transition while any
      // material on the order has no price, so the button says so instead of
      // letting the operator discover it from a failed request.
      disabled: unpricedMaterials.value.length > 0,
      hint: unpricedMissing.value,
      run: approve,
    }
  if (current.status === 'confirmed' && (canManageOrders.value || canCompleteCutting.value))
    return {
      key: 'startCutting',
      label: t('orders.action.startCutting'),
      busyLabel: t('orders.busy.starting'),
      disabled: !canStartCutting.value,
      hint: startCuttingMissing.value,
      run: startCutting,
    }
  if (current.status === 'cutting' && canCompleteCutting.value)
    return {
      key: 'completeCutting',
      label: t('orders.action.completeCutting'),
      busyLabel: t('orders.busy.running'),
      run: completeCutting,
    }
  if (current.status === 'edge_banding' && canCompleteBanding.value) {
    // Guided two-tap flow: start stamps the duration, then the same slot turns
    // into the completion action.
    return current.banding_started_at
      ? {
          key: 'completeBanding',
          label: t('orders.action.completeBanding'),
          busyLabel: t('orders.busy.running'),
          run: completeBanding,
        }
      : {
          key: 'startBanding',
          label: t('orders.action.startBanding'),
          busyLabel: t('orders.busy.starting'),
          disabled: startBandingMissing.value !== null,
          hint: startBandingMissing.value,
          run: startBanding,
        }
  }
  if (current.status === 'ready' && canManageOrders.value)
    return {
      key: 'markCollected',
      label: t('orders.action.markCollected'),
      busyLabel: t('orders.busy.running'),
      run: () => (markCollectedOpen.value = true),
    }
  return null
})

type OrderMenuItem = { key: string; label: string; danger?: boolean; run: () => void }
const menuItems = computed<OrderMenuItem[]>(() => {
  const current = order.value
  if (!current) return []
  const items: OrderMenuItem[] = []
  if (canEditOrder.value && !current.revision_draft_id)
    items.push({ key: 'edit', label: t('orders.action.edit'), run: startEdit })
  if (canManageOrders.value && ['new', 'confirmed'].includes(current.status)) {
    items.push({
      key: 'discount',
      label: discountButtonLabel.value,
      run: () => {
        discountSubmitError.value = null
        discountOpen.value = true
      },
    })
    items.push({
      key: 'surcharge',
      label: surchargeButtonLabel.value,
      run: () => {
        surchargeSubmitError.value = null
        surchargeOpen.value = true
      },
    })
  }
  if (canManageOrders.value && ['cutting', 'edge_banding', 'ready'].includes(current.status))
    items.push({
      key: 'revert',
      label: revertButtonLabel.value,
      danger: true,
      run: requestRevertOrder,
    })
  if (canManageOrders.value && !['completed', 'cancelled'].includes(current.status))
    items.push({
      key: 'cancel',
      label: t('orders.action.cancelOrder'),
      danger: true,
      run: requestCancelOrder,
    })
  return items
})

// Itemized breakdown (always expanded): one row per material actually used,
// panel or kromka alike, from the backend's snapshot-exact price_lines.
const panelLines = computed<OrderPriceLine[]>(
  () => order.value?.price_lines.filter((line) => line.kind === 'panel') ?? [],
)
const edgeLines = computed<OrderPriceLine[]>(
  () => order.value?.price_lines.filter((line) => line.kind === 'edge') ?? [],
)
// What the client owes the shop floor. Sits in the production card, not the
// receipt: it is a precondition for starting work, not a line of the bill.
const ownRows = computed(() => ownMaterialRows(order.value?.price_lines ?? []))
// Staff may arrange client-supplied sheets whatever the branch's self-serve
// policy says — that setting governs the client app, not the counter.
const pricesOpen = ref(false)
const pricesSubmitError = ref<string | null>(null)
// Every millimetre the order bands, whoever supplies the tape — the figure the
// banding rate multiplies, so the editor can show what it is changing.
const bandedMm = computed(() => {
  const current = result.value
  if (!current) return 0
  return (
    Object.values(current.edge_consumed_shop_by_material).reduce((sum, v) => sum + v, 0) +
    Object.values(current.edge_consumed_own_by_material).reduce((sum, v) => sum + v, 0)
  )
})
const panelsUsed = computed(() =>
  result.value
    ? Object.values(result.value.panels_used_by_material).reduce((sum, v) => sum + v, 0)
    : 0,
)

async function savePrices(payload: {
  cutting_rate_tiyin: number | null
  edge_banding_rate_tiyin: number | null
  material_prices: Record<string, number>
}) {
  const current = order.value
  if (!current) return
  pricesSubmitError.value = null
  try {
    await orders.setPrices(current.id, { version: current.version, ...payload })
  } catch {
    pricesSubmitError.value = t('orders.prices.saveFailed')
    return
  }
  pricesOpen.value = false
  toast.success(t('orders.prices.saved'))
}

const ownEditOpen = ref(false)
const ownSubmitError = ref<string | null>(null)

async function saveOwnMaterial(ownPanelCounts: Record<string, number>) {
  const current = order.value
  if (!current) return
  ownSubmitError.value = null
  try {
    await orders.setOwnMaterial(current.id, {
      version: current.version,
      own_panel_counts: ownPanelCounts,
    })
  } catch {
    ownSubmitError.value = t('orders.own.saveFailed')
    return
  }
  ownEditOpen.value = false
  toast.success(t('orders.own.saved'))
}

function edgeMaterialTotal(current: OrderDetail) {
  return current.items.reduce((sum, item) => sum + item.edge_cost_tiyin, 0)
}

// The kromka material share comes from price_lines when present — the per-item
// edge_cost sum floors per side and can drift a few tiyin, which would keep the
// breakdown from summing exactly to Jami.
function edgeServiceTotal(current: OrderDetail) {
  const materialShare =
    current.price_lines.length > 0
      ? current.price_lines
          .filter((line) => line.kind === 'edge')
          .reduce((sum, line) => sum + line.line_total_tiyin, 0)
      : edgeMaterialTotal(current)
  return Math.max(current.subtotal_edge_banding_tiyin - materialShare, 0)
}

function edgeConsumedTotal(current: OrderDetail) {
  return current.planned_edge_lines.reduce((sum, line) => sum + line.consumed_mm, 0)
}

function workerName(id: string | null) {
  if (!id) return t('orders.detail.unassigned')
  return (
    orders.workerOptions.find((worker) => worker.id === id)?.full_name ??
    t('orders.detail.unknownWorker')
  )
}

function timelineProductionDetails(event: OrderEvent) {
  return productionTimelineDetails(event, (id) => workerName(id))
}

// Mark the latest event as the live phase (CB-113 ".now" dot) unless the order
// already reached a terminal state, where the final row stays done/cancelled (QAD-80).
function timelineStepClass(event: OrderEvent, index: number) {
  if (event.to_status === 'cancelled') return 'bad'
  const events = order.value?.events ?? []
  const terminal = order.value ? ['completed', 'cancelled'].includes(order.value.status) : true
  return index === events.length - 1 && !terminal ? 'now' : 'done'
}

function warningQuantity(
  warning: OrderStockWarning,
  key: 'on_hand' | 'required' | 'projected_after',
) {
  const value = warning[key]
  return warning.kind === 'edge' ? metres(value) : t('orders.detail.pieces', { count: value })
}

function panelTitle(current: CuttingResult, panel: CuttingPanel) {
  // New snapshots carry no `name` column; the label is composed from the same
  // fields the server would use, reading the legacy keys for frozen history.
  const snapshot = current.material_snapshots[panel.branch_material_id]
  const label = snapshotMaterialLabel(snapshot, t('orders.detail.sheetFallback'))
  return `${label} · ${panel.panel_index}`
}

function selectPlacement(placement: CuttingPlacement) {
  activePlacementId.value = placement.id
}

async function loadDetail() {
  await orders.loadWorkshopOrder(orderId.value)
  const current = orders.currentOrder
  // The worker list feeds the assignment pickers, and the endpoint behind it is
  // gated on `manage_orders` for the branch. This page also admits `view_orders`
  // and `process_production` — asking for the list as one of those bought them
  // nothing but a 403 on a page they are entitled to (QAD-173).
  if (current && permissions.canOnBranch(p.manageOrders, current.branch_id)) {
    await orders.loadWorkers(current.branch_id).catch(() => undefined)
  }
}

async function run(action: () => Promise<unknown>, successMessage?: string, key?: string) {
  actionError.value = null
  actionTraceId.value = null
  if (key) pendingAction.value = key
  try {
    await action()
    if (successMessage) toast.success(successMessage)
    return true
  } catch {
    actionError.value = workshopErrorMessage(orders.actionError ?? 'order_action_failed')
    actionTraceId.value = orders.actionTraceId
    return false
  } finally {
    if (key) pendingAction.value = null
  }
}

function runMenuItem(item: OrderMenuItem) {
  menuOpen.value = false
  item.run()
}

function onDocumentClick(event: MouseEvent) {
  if (!(event.target instanceof Element)) return
  if (!event.target.closest('[data-od-menu]')) menuOpen.value = false
}

async function approve() {
  const current = order.value
  if (!current || !canManageOrders.value) return
  await run(
    () => orders.approve(current.id, current.version),
    t('orders.toast.approved'),
    'approve',
  )
}

// Auto-apply assignment: picking a worker saves immediately — null leaves the
// other role unchanged on the API. Selects are disabled while a request is in
// flight, so version bumps can't race; on failure the select snaps back to the
// server value (a 409 refetch resyncs it via the order watcher anyway).
async function applyCutter(value: string | null) {
  const current = order.value
  if (!current || !canAssignCutter.value) return
  if (!value || value === current.assigned_cutter_user_id) return
  const ok = await run(
    () =>
      orders.assign(current.id, {
        version: current.version,
        cutter_user_id: value,
        edger_user_id: null,
      }),
    t('orders.toast.cutterAssigned'),
    'assignCutter',
  )
  if (!ok) cutterId.value = current.assigned_cutter_user_id
}

async function applyEdger(value: string | null) {
  const current = order.value
  if (!current || !canAssignEdger.value) return
  if (!value || value === current.assigned_edger_user_id) return
  const ok = await run(
    () =>
      orders.assign(current.id, {
        version: current.version,
        cutter_user_id: null,
        edger_user_id: value,
      }),
    t('orders.toast.edgerAssigned'),
    'assignEdger',
  )
  if (!ok) edgerId.value = current.assigned_edger_user_id
}

async function startCutting() {
  const current = order.value
  if (!current || !canStartCutting.value) return
  await run(
    () => orders.startCutting(current.id, current.version),
    t('orders.toast.cuttingStarted'),
    'startCutting',
  )
}

async function startBanding() {
  const current = order.value
  if (!current || !canCompleteBanding.value || current.banding_started_at) return
  if (!current.assigned_edger_user_id) return
  await run(
    () => orders.startBanding(current.id, current.version),
    t('orders.toast.bandingStarted'),
    'startBanding',
  )
}

// Completion always credits the assigned worker — attribution follows the
// assignment locks; swapping credit is a deliberate revert → reassign.
async function completeCutting() {
  const current = order.value
  if (!current || !canCompleteCutting.value) return
  const completedBy = current.assigned_cutter_user_id
  if (!completedBy) {
    actionError.value = t('orders.error.cuttingWorkerMissing')
    actionTraceId.value = null
    return
  }
  const ok = await run(
    () =>
      orders.cuttingDone(current.id, {
        version: current.version,
        completed_by_user_id: completedBy,
      }),
    t('orders.toast.cuttingDone'),
    'completeCutting',
  )
  if (ok) warnOnStockShortfall()
}

async function completeBanding() {
  const current = order.value
  if (!current || !canCompleteBanding.value) return
  const completedBy = current.assigned_edger_user_id
  if (!completedBy) {
    actionError.value = t('orders.error.bandingWorkerMissing')
    actionTraceId.value = null
    return
  }
  const ok = await run(
    () =>
      orders.bandingDone(current.id, {
        version: current.version,
        completed_by_user_id: completedBy,
      }),
    t('orders.toast.bandingDone'),
    'completeBanding',
  )
  if (ok) warnOnStockShortfall()
}

// The completion mutation stores the fresh order on the store, so the shortfall
// flag rides along with it — a warn toast next to the success one, never in
// place of it (QAD-150).
function warnOnStockShortfall() {
  if (orders.currentOrder?.stock_shortfall) toast.warn(stockShortfallMessage())
}

async function markCollected() {
  const current = order.value
  if (!current || !canManageOrders.value) return
  const ok = await run(
    () => orders.markCollected(current.id, current.version),
    t('orders.toast.collected'),
  )
  if (ok) markCollectedOpen.value = false
}

function requestRevertOrder() {
  if (!canManageOrders.value) return
  // Start the reason blank so the destructive confirm isn't armed the instant the
  // dialog opens — the required-reason guard keeps confirm disabled until typed.
  reasonDraft.value = ''
  reasonDialogAction.value = 'revert'
}

function requestCancelOrder() {
  if (!canManageOrders.value) return
  reasonDraft.value = ''
  reasonDialogAction.value = 'cancel'
}

async function confirmReasonedAction() {
  const current = order.value
  if (!current || !canManageOrders.value) return
  const action = reasonDialogAction.value
  const reason = reasonDraft.value.trim()
  if (!action || !reason) return
  const ok =
    action === 'revert'
      ? await run(
          () => orders.revert(current.id, current.version, reason),
          t('orders.toast.reverted'),
        )
      : await run(
          () => orders.cancelWorkshopOrder(current.id, current.version, reason),
          t('orders.toast.cancelled'),
        )
  if (ok) reasonDialogAction.value = null
}

// Discount (chegirma −) and surcharge (ustama +) share the shape and the
// pre-production gate; each modal emits an already-parsed {kind, value, reason}
// (value in tiyin for a fixed sum) and the store posts it to the matching
// endpoint. Removal posts a zeroed adjustment, which clears the reason + actor.
// The removal `reason` below is API payload, not copy: the server drops it with
// the adjustment, so it never reaches a screen and stays out of the catalog —
// translating it would write the operator's locale into the audit trail.
type AdjustmentPayload = { kind: WorkshopAdjustmentKind; value: number; reason: string }

async function applyDiscount(payload: AdjustmentPayload) {
  const current = order.value
  if (!current || !canManageOrders.value) return
  discountSubmitError.value = null
  const ok = await run(
    () => orders.discount(current.id, { version: current.version, ...payload }),
    t('orders.toast.discountSaved'),
    'discount',
  )
  if (ok) discountOpen.value = false
  else discountSubmitError.value = actionError.value
}

async function removeDiscount() {
  const current = order.value
  if (!current || !canManageOrders.value || current.discount_tiyin <= 0) return
  discountSubmitError.value = null
  const ok = await run(
    () =>
      orders.discount(current.id, {
        version: current.version,
        kind: 'fixed',
        value: 0,
        reason: 'Chegirma olib tashlandi',
      }),
    t('orders.toast.discountRemoved'),
    'removeDiscount',
  )
  if (ok) discountOpen.value = false
  else discountSubmitError.value = actionError.value
}

async function applySurcharge(payload: AdjustmentPayload) {
  const current = order.value
  if (!current || !canManageOrders.value) return
  surchargeSubmitError.value = null
  const ok = await run(
    () => orders.surcharge(current.id, { version: current.version, ...payload }),
    t('orders.toast.surchargeSaved'),
    'surcharge',
  )
  if (ok) surchargeOpen.value = false
  else surchargeSubmitError.value = actionError.value
}

async function removeSurcharge() {
  const current = order.value
  if (!current || !canManageOrders.value || current.surcharge_tiyin <= 0) return
  surchargeSubmitError.value = null
  const ok = await run(
    () =>
      orders.surcharge(current.id, {
        version: current.version,
        kind: 'fixed',
        value: 0,
        reason: 'Ustama olib tashlandi',
      }),
    t('orders.toast.surchargeRemoved'),
    'removeSurcharge',
  )
  if (ok) surchargeOpen.value = false
  else surchargeSubmitError.value = actionError.value
}

// Display-first note: the editor opens on demand and saves on blur — a note is
// content, not a standing form. An empty save clears the note entirely.
function openNoteEditor() {
  noteDraft.value = order.value?.note_workshop ?? ''
  noteEditing.value = true
  void nextTick(() => noteInput.value?.focus())
}

async function onNoteBlur() {
  const current = order.value
  if (!current) return
  if (!noteDirty.value) {
    noteEditing.value = false
    return
  }
  const ok = await run(
    () => orders.updateNote(current.id, noteDraft.value.trim() || null),
    t('orders.toast.noteSaved'),
    'note',
  )
  // On failure the editor stays open so the draft isn't lost; the error banner
  // above the grid names the cause.
  if (ok) noteEditing.value = false
}

// Begin (or resume) the order's revision and hand off to the shared editor.
async function startEdit() {
  const current = order.value
  if (!current || !canEditOrder.value) return
  if (current.revision_draft_id) {
    void router.push(rolePath(`/workshop/orders/cutting/${current.revision_draft_id}`))
    return
  }
  actionError.value = null
  actionTraceId.value = null
  pendingAction.value = 'edit'
  try {
    const draft = await orders.beginRevision(current.id)
    void router.push(rolePath(`/workshop/orders/cutting/${draft.id}`))
  } catch {
    actionError.value = workshopErrorMessage(orders.actionError ?? 'order_revision_failed')
    actionTraceId.value = orders.actionTraceId
  } finally {
    pendingAction.value = null
  }
}

async function discardEdit() {
  const current = order.value
  const revisionId = current?.revision_draft_id
  if (!current || !revisionId) return
  const ok = await run(
    async () => {
      await cutting.deleteDraft(revisionId)
      await orders.loadWorkshopOrder(current.id)
    },
    t('orders.toast.editDiscarded'),
    'discardEdit',
  )
  if (ok) discardEditOpen.value = false
}

watch(
  order,
  (value) => {
    if (!value) return
    cutterId.value = value.assigned_cutter_user_id
    edgerId.value = value.assigned_edger_user_id
    // Don't clobber a half-typed note when an action reassigns the same order;
    // only reset when navigating to a different order or the field is clean (QAD-79).
    if (value.id !== loadedOrderId.value || !noteDirty.value) {
      noteDraft.value = value.note_workshop ?? ''
    }
    loadedOrderId.value = value.id
  },
  { immediate: true },
)

watch(
  result,
  (value) => {
    if (!value) {
      activePanelId.value = null
      activePlacementId.value = null
      return
    }
    if (!value.panels.some((panel) => panel.id === activePanelId.value)) {
      activePanelId.value = value.panels[0]?.id ?? null
      activePlacementId.value = null
    }
  },
  { immediate: true },
)

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  void loadDetail()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
})
</script>

<template>
  <section class="od-page">
    <RouterLink :to="backLink.to" class="back">{{ backLink.label }}</RouterLink>

    <section v-if="orders.loading" aria-busy="true" aria-live="polite" class="od-fill">
      <div class="od-head">
        <span class="sk-line" style="height: 24px; width: 30%"></span>
        <span class="sk-line mt-3" style="width: 50%"></span>
        <span class="sk-line mt-4" style="width: 72%"></span>
      </div>
      <div class="od-grid">
        <section class="card">
          <div class="card-h"><span class="sk-line" style="height: 16px; width: 38%"></span></div>
          <div class="card-b grid content-start gap-3">
            <span v-for="n in 4" :key="n" class="sk-line"></span>
          </div>
        </section>
        <section class="card">
          <div class="card-b grid content-start gap-3 !pt-4">
            <span v-for="n in 3" :key="n" class="sk-line"></span>
          </div>
        </section>
      </div>
    </section>
    <section v-else-if="orderOutOfReach" class="st-empty">
      <h3>{{ $t('orders.detail.notAllowedTitle') }}</h3>
      <p>{{ $t('orders.detail.notAllowedBody') }}</p>
    </section>
    <section v-else-if="orders.error" class="st-error" role="alert">
      <h3>{{ $t('orders.detail.loadFailedTitle') }}</h3>
      <p>{{ $t('orders.state.connectionRetry') }}</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        :disabled="orders.loading"
        @click="loadDetail"
      >
        {{ $t('orders.state.retry') }}
      </button>
      <p class="mt-3 text-xs text-ink-muted">{{ traceLine(orders.traceId) }}</p>
    </section>
    <section v-else-if="!order" class="st-empty">
      <h3>{{ $t('orders.detail.notFoundTitle') }}</h3>
      <p>{{ $t('orders.detail.notFoundBody') }}</p>
    </section>

    <template v-else>
      <header class="od-head">
        <div class="od-top">
          <h1>{{ order.order_number }}</h1>
          <span :class="orderPillClass(order.status)">
            <span class="pd"></span>{{ workshopStatusUz(order.status) }}
          </span>
          <div class="actions">
            <button
              type="button"
              class="mp-action-icon-button"
              :aria-label="$t('orders.detail.history')"
              :title="$t('orders.detail.history')"
              @click="historyOpen = true"
            >
              <AppIcon name="clock" class="size-4" />
            </button>
            <div
              v-if="menuItems.length > 0"
              class="mp-action-menu-wrap"
              data-od-menu
              @keydown.esc.stop.prevent="menuOpen = false"
            >
              <button
                type="button"
                class="mp-action-icon-button"
                :aria-label="$t('orders.detail.moreActions')"
                :aria-expanded="menuOpen"
                @click="menuOpen = !menuOpen"
              >
                <span aria-hidden="true">...</span>
              </button>
              <div v-if="menuOpen" class="mp-action-menu">
                <template v-for="(item, index) in menuItems" :key="item.key">
                  <div
                    v-if="item.danger && index > 0 && !menuItems[index - 1].danger"
                    class="mp-action-menu-sep"
                    aria-hidden="true"
                  ></div>
                  <button
                    type="button"
                    class="mp-action-menu-item"
                    :class="{ danger: item.danger }"
                    :disabled="orders.actionLoading"
                    @click="runMenuItem(item)"
                  >
                    {{ item.label }}
                  </button>
                </template>
              </div>
            </div>
            <button
              v-if="primaryAction"
              type="button"
              class="mp-button mp-button-primary px-4"
              :disabled="orders.actionLoading || primaryAction.disabled"
              @click="primaryAction.run()"
            >
              {{
                pendingAction === primaryAction.key ? primaryAction.busyLabel : primaryAction.label
              }}
            </button>
          </div>
        </div>
        <!-- The disabled-primary hint rides directly under the action row it
             explains — below the meta line it read as a stray caption. -->
        <p v-if="primaryAction?.hint" class="od-hint">
          {{ $t('orders.detail.startHint', { reason: primaryAction.hint }) }}
        </p>
        <div class="od-meta">
          <span
            ><b>{{ order.contact_name }}</b> · {{ order.contact_phone }}</span
          >
          <!-- &nbsp; in the label: the template compiler condenses away the
               bare newline between elements, which glued "Jami:" to the sum. -->
          <span
            ><span class="lbl">{{ $t('orders.detail.totalLabel') }}&nbsp;</span
            ><b class="font-mono">{{ formatTiyin(order.total_tiyin) }}</b></span
          >
          <!-- The note rides the right end of the meta line. A long note
               truncates to the free space (full text on hover); an over-long
               one wraps to its own truncated line instead of breaking layout. -->
          <template v-if="!noteEditing">
            <span
              v-if="order.note_workshop"
              class="ml-auto flex max-w-full min-w-0 items-center gap-1"
            >
              <span class="lbl">{{ $t('orders.detail.noteLabel') }}</span>
              <span class="txt min-w-0 truncate" :title="order.note_workshop">{{
                order.note_workshop
              }}</span>
              <button
                type="button"
                class="od-note-edit"
                :aria-label="$t('orders.detail.noteEdit')"
                @click="openNoteEditor"
              >
                <AppIcon name="pencil" class="size-3.5" />
              </button>
            </span>
            <button v-else type="button" class="od-note-add ml-auto" @click="openNoteEditor">
              {{ $t('orders.detail.noteAdd') }}
            </button>
          </template>
        </div>
        <!-- Editing stays display-first (pencil opens, blur saves) and drops to
             a full-width editor under the meta line for room to type. -->
        <div v-if="noteEditing" class="od-note">
          <textarea
            ref="noteInput"
            v-model="noteDraft"
            class="mp-input min-h-20 w-full resize-y"
            :placeholder="$t('orders.detail.notePlaceholder')"
            :disabled="orders.actionLoading && pendingAction === 'note'"
            @blur="onNoteBlur"
          ></textarea>
          <p class="mt-1 w-full text-xs text-ink-muted">
            {{
              pendingAction === 'note' ? $t('orders.busy.saving') : $t('orders.detail.noteBlurHint')
            }}
          </p>
        </div>
        <div
          v-if="!isCancelled"
          class="od-steps"
          role="list"
          :aria-label="$t('orders.detail.phases')"
        >
          <template v-for="(step, i) in phaseSteps" :key="step.status">
            <span
              class="od-step"
              :class="step.state"
              role="listitem"
              :aria-current="step.state === 'current' ? 'step' : undefined"
            >
              <span class="od-dot" aria-hidden="true"></span>
              <span class="od-lbl">{{ workshopStatusUz(step.status) }}</span>
            </span>
            <span
              v-if="i < phaseSteps.length - 1"
              class="od-conn"
              :class="{ done: step.state === 'done' }"
              aria-hidden="true"
            ></span>
          </template>
        </div>
      </header>

      <div v-if="actionError" class="banner danger mb-4" role="alert">
        <div class="grow">
          {{ actionError }}
          <span v-if="actionTraceId"> · trace {{ actionTraceId }}</span>
        </div>
      </div>

      <div v-if="orders.downloadError" class="banner danger mb-4" role="alert">
        <div class="grow">{{ orders.downloadError }}{{ traceSuffix(orders.downloadTraceId) }}</div>
      </div>

      <!-- An open revision is important state — a quiet banner, not a menu item
           (orders.md "Revising a placed order"). -->
      <div v-if="canManageOrders && order.revision_draft_id" class="banner mb-4" role="status">
        <div class="grow">
          <template v-if="canEditOrder">{{ $t('orders.detail.revisionOpen') }}</template>
          <template v-else>{{ $t('orders.detail.revisionStale') }}</template>
        </div>
        <RouterLink
          v-if="canEditOrder"
          :to="rolePath(`/workshop/orders/cutting/${order.revision_draft_id}`)"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
        >
          {{ $t('orders.detail.revisionResume') }}
        </RouterLink>
        <button
          type="button"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs text-danger"
          :disabled="orders.actionLoading"
          @click="discardEditOpen = true"
        >
          {{ $t('orders.detail.revisionDiscard') }}
        </button>
      </div>

      <div
        v-if="order.stock_warnings.length > 0"
        class="banner mb-4"
        :class="hasShortfall ? 'danger' : 'warn'"
        role="status"
      >
        <div class="grow">
          {{ hasShortfall ? $t('orders.detail.shortfall') : $t('orders.detail.lowStock') }}
          <b>
            {{
              order.stock_warnings
                .map(
                  (warning) =>
                    `${warning.material_name} → ${warningQuantity(warning, 'projected_after')}`,
                )
                .join(' · ')
            }}
          </b>
        </div>
      </div>

      <div class="od-grid">
        <section class="card">
          <div class="card-h">
            <h2>{{ $t('orders.detail.production') }}</h2>
            <span class="collapse-meta">{{ productionMeta }}</span>
          </div>
          <!-- The card stretches to match its sibling (equal-height second
               row), but the content stacks sequentially from the top; the
               button pins to the bottom edge as a footer (mt-auto) so the
               free height collects in one deliberate gap, not between items. -->
          <div class="card-b flex min-h-0 flex-col !pb-0">
            <!-- Before the assignment controls: the shop cannot start until
                 this arrives, so it has to be read before a cutter is picked. -->
            <div v-if="ownRows.length > 0" class="banner warn mt-4 mb-1">
              <div class="grow">
                <b>{{ $t('orders.own.title') }}</b>
                <ul class="mt-1 grid gap-0.5">
                  <li v-for="row in ownRows" :key="row.materialId" class="text-sm">
                    {{ row.materialName }} —
                    <span class="font-mono font-bold">{{ row.amount }}</span>
                  </li>
                </ul>
                <small class="mt-1 block text-ink-muted">{{ $t('orders.own.body') }}</small>
                <button
                  v-if="canEditOrder"
                  type="button"
                  class="mp-button mt-2 min-h-11"
                  @click="ownEditOpen = true"
                >
                  {{ $t('orders.own.edit') }}
                </button>
              </div>
            </div>
            <!-- The counter usually hears "I'll bring my own" at approval, so
                 the entry point has to exist before any claim does — not only
                 as an edit on a banner that isn't there yet. -->
            <button
              v-else-if="canEditOrder"
              type="button"
              class="mp-button mt-4 mb-1 min-h-11 self-start"
              @click="ownEditOpen = true"
            >
              {{ $t('orders.own.edit') }}
            </button>
            <div class="flex flex-col gap-1 py-4">
              <FormSelect
                v-if="canAssignCutter"
                v-model="cutterId"
                :label="$t('orders.detail.cutter')"
                :options="workerOptions"
                :disabled="workerOptions.length === 0 || orders.actionLoading"
                @update:model-value="applyCutter"
              />
              <template v-else>
                <span class="form-select-label block text-sm font-bold text-ink">{{
                  $t('orders.detail.cutter')
                }}</span>
                <div
                  class="flex min-h-10 items-center rounded-md border border-hairline bg-sunk px-3 text-sm font-semibold text-ink"
                >
                  {{ workerName(order.cutter_user_id ?? order.assigned_cutter_user_id) }}
                </div>
              </template>
              <p
                v-if="cutterSub"
                class="text-xs"
                :class="cutterSub.kind === 'done' ? 'text-ink-soft' : 'text-ink-muted'"
              >
                <template v-if="cutterSub.kind === 'done'"
                  ><span class="font-bold text-success">{{ $t('orders.detail.completedBy') }}</span>
                  ·
                </template>
                {{ cutterSub.text }}
              </p>
            </div>
            <!-- The kromka slot is always present so the card reads the same on
                 every order; without banding it is a quiet disabled box. -->
            <div class="flex flex-col gap-1 border-t border-hairline py-4">
              <template v-if="!order.has_banding">
                <span class="form-select-label block text-sm font-bold text-ink">{{
                  $t('orders.detail.edger')
                }}</span>
                <div
                  class="flex min-h-10 items-center rounded-md border border-hairline bg-sunk px-3 text-sm font-semibold text-ink-muted"
                >
                  {{ $t('orders.detail.noBanding') }}
                </div>
              </template>
              <FormSelect
                v-else-if="canAssignEdger"
                v-model="edgerId"
                :label="$t('orders.detail.edger')"
                :options="workerOptions"
                :disabled="workerOptions.length === 0 || orders.actionLoading"
                @update:model-value="applyEdger"
              />
              <template v-else>
                <span class="form-select-label block text-sm font-bold text-ink">{{
                  $t('orders.detail.edger')
                }}</span>
                <div
                  class="flex min-h-10 items-center rounded-md border border-hairline bg-sunk px-3 text-sm font-semibold text-ink"
                >
                  {{ workerName(order.edger_user_id ?? order.assigned_edger_user_id) }}
                </div>
              </template>
              <p
                v-if="order.has_banding && edgerSub"
                class="text-xs"
                :class="edgerSub.kind === 'done' ? 'text-ink-soft' : 'text-ink-muted'"
              >
                <template v-if="edgerSub.kind === 'done'"
                  ><span class="font-bold text-success">✓ Bajardi</span> ·
                </template>
                {{ edgerSub.text }}
              </p>
            </div>
            <div class="mt-auto border-t border-hairline pt-4 pb-[22px]">
              <button
                type="button"
                class="mp-button mp-button-outline w-full gap-2"
                @click="chizmaOpen = true"
              >
                <svg
                  class="size-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  aria-hidden="true"
                >
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <path d="M3 12h9M12 3v9" />
                </svg>
                {{ $t('orders.detail.drawing') }}
              </button>
            </div>
          </div>
        </section>

        <section class="card">
          <div class="card-b grid content-start gap-2 !pt-4">
            <!-- Receipt order: the itemized breakdown leads, the bottom-line
                 figures close the card. Group titles are bold section heads;
                 quantities stay muted sub-lines and prices nowrap + shrink-0
                 so "so'm" can never wrap onto its own line. -->
            <div class="text-sm">
              <div class="font-bold text-ink">{{ $t('orders.detail.materials') }}</div>
              <div class="mt-2 grid gap-2.5">
                <template v-if="order.price_lines.length > 0">
                  <div
                    v-for="line in panelLines"
                    :key="line.material_id"
                    class="flex items-baseline justify-between gap-3"
                  >
                    <span class="min-w-0 text-ink"
                      >{{ line.material_name
                      }}<small class="block text-xs text-ink-muted">
                        <!-- With an own claim the charged count alone is
                             misleading — a fully client-supplied material would
                             read as `0 list` for free. Name both halves. -->
                        <template v-if="line.own_panels > 0">{{
                          $t('orders.own.sheetsSplit', {
                            own: line.own_panels,
                            shop: line.panels_used ?? 0,
                          })
                        }}</template>
                        <template v-else>{{
                          $t(
                            'orders.unit.sheets',
                            { n: line.panels_used ?? 0 },
                            line.panels_used ?? 0,
                          )
                        }}</template>
                        <template v-if="line.unit_price_tiyin > 0">
                          × {{ formatTiyin(line.unit_price_tiyin) }}
                        </template>
                      </small></span
                    >
                    <span class="shrink-0 font-mono whitespace-nowrap text-ink">{{
                      formatTiyin(line.line_total_tiyin)
                    }}</span>
                  </div>
                  <div
                    v-for="line in edgeLines"
                    :key="line.material_id"
                    class="flex items-baseline justify-between gap-3"
                  >
                    <span class="min-w-0 text-ink"
                      >{{ line.material_name
                      }}<small class="block text-xs text-ink-muted">
                        {{ metres(line.consumed_mm ?? 0) }}
                        <template v-if="line.unit_price_tiyin > 0">
                          × {{ formatTiyin(line.unit_price_tiyin) }}
                        </template>
                        <template v-if="line.own_mm > 0">
                          · {{ $t('orders.own.tapeOwn', { metres: metres(line.own_mm) }) }}
                        </template>
                      </small></span
                    >
                    <span class="shrink-0 font-mono whitespace-nowrap text-ink">{{
                      formatTiyin(line.line_total_tiyin)
                    }}</span>
                  </div>
                  <!-- Named where the money is, not as a toast on a failed
                       confirm: these are the rows blocking the order, and the
                       button that fixes them is the one already here. -->
                  <div
                    v-if="unpricedMaterials.length"
                    class="mt-2 grid gap-1 rounded-lg border border-warning/40 bg-warning-soft/40 px-3 py-2"
                  >
                    <span class="text-xs font-black text-warning">
                      {{ $t('orders.prices.unpricedTitle', { count: unpricedMaterials.length }) }}
                    </span>
                    <span
                      v-for="material in unpricedMaterials"
                      :key="material.material_id"
                      class="truncate text-xs text-ink"
                    >
                      {{ material.material_label }}
                    </span>
                  </div>
                  <button
                    v-if="canEditOrder"
                    type="button"
                    class="mp-button mt-1 min-h-11 self-start"
                    @click="pricesOpen = true"
                  >
                    {{
                      unpricedMaterials.length
                        ? $t('orders.prices.setMissing')
                        : $t('orders.prices.open')
                    }}
                  </button>
                </template>
                <template v-else>
                  <!-- Snapshot lines missing (no cutting result) — aggregate rows. -->
                  <div class="flex items-baseline justify-between gap-3">
                    <span class="min-w-0 text-ink">{{ $t('orders.detail.sheets') }}</span>
                    <span class="shrink-0 font-mono whitespace-nowrap text-ink">{{
                      formatTiyin(order.subtotal_materials_tiyin)
                    }}</span>
                  </div>
                  <div
                    v-if="edgeMaterialTotal(order) > 0"
                    class="flex items-baseline justify-between gap-3"
                  >
                    <span class="min-w-0 text-ink"
                      >{{ $t('orders.detail.edge')
                      }}<small class="block text-xs text-ink-muted">{{
                        metres(edgeConsumedTotal(order))
                      }}</small></span
                    >
                    <span class="shrink-0 font-mono whitespace-nowrap text-ink">{{
                      formatTiyin(edgeMaterialTotal(order))
                    }}</span>
                  </div>
                </template>
              </div>
              <div class="mt-3 font-bold text-ink">{{ $t('orders.detail.services') }}</div>
              <div class="mt-2 grid gap-2.5">
                <div class="flex items-baseline justify-between gap-3">
                  <span class="min-w-0 text-ink"
                    >{{ $t('orders.detail.cutting')
                    }}<small v-if="totalPanels > 0" class="block text-xs text-ink-muted">{{
                      $t('orders.unit.sheets', { n: totalPanels }, totalPanels)
                    }}</small></span
                  >
                  <span class="shrink-0 font-mono whitespace-nowrap text-ink">{{
                    formatTiyin(order.subtotal_cutting_tiyin)
                  }}</span>
                </div>
                <div
                  v-if="edgeServiceTotal(order) > 0"
                  class="flex items-baseline justify-between gap-3"
                >
                  <span class="min-w-0 text-ink"
                    >{{ $t('orders.detail.edgeService')
                    }}<small class="block text-xs text-ink-muted">{{
                      metres(edgeConsumedTotal(order))
                    }}</small></span
                  >
                  <span class="shrink-0 font-mono whitespace-nowrap text-ink">{{
                    formatTiyin(edgeServiceTotal(order))
                  }}</span>
                </div>
              </div>
              <div
                v-if="order.surcharge_tiyin > 0 || order.discount_tiyin > 0"
                class="mt-2 grid gap-2.5 border-t border-hairline pt-2"
              >
                <div
                  v-if="order.surcharge_tiyin > 0"
                  class="flex items-baseline justify-between gap-3"
                >
                  <span class="min-w-0 text-ink"
                    >{{ $t('orders.detail.surcharge')
                    }}<small v-if="order.surcharge_reason" class="block text-xs text-ink-muted">{{
                      order.surcharge_reason
                    }}</small></span
                  >
                  <span class="shrink-0 font-mono whitespace-nowrap text-ink"
                    >+ {{ formatTiyin(order.surcharge_tiyin) }}</span
                  >
                </div>
                <div
                  v-if="order.discount_tiyin > 0"
                  class="flex items-baseline justify-between gap-3"
                >
                  <span class="min-w-0 text-ink"
                    >{{ $t('orders.detail.discount')
                    }}<small v-if="order.discount_reason" class="block text-xs text-ink-muted">{{
                      order.discount_reason
                    }}</small></span
                  >
                  <span class="shrink-0 font-mono whitespace-nowrap text-ink"
                    >- {{ formatTiyin(order.discount_tiyin) }}</span
                  >
                </div>
              </div>
            </div>
            <!-- Bottom-line figures close the receipt: Jami leads, settlement
                 rows follow for those allowed to see them. -->
            <div class="mt-2 grid gap-2 border-t border-hairline pt-3">
              <div class="flex items-baseline justify-between font-bold text-ink">
                <span>{{ $t('orders.detail.total') }}</span>
                <span class="font-mono text-base">{{ formatTiyin(order.total_tiyin) }}</span>
              </div>
              <template v-if="order.settlement && canViewSettlement">
                <div class="flex items-baseline justify-between text-sm text-ink-soft">
                  <span>{{ $t('orders.detail.paid') }}</span>
                  <span
                    class="font-mono font-semibold"
                    :class="order.settlement.recorded_tiyin > 0 ? 'text-success' : ''"
                    >{{ formatTiyin(order.settlement.recorded_tiyin) }}</span
                  >
                </div>
                <div class="flex items-baseline justify-between text-sm">
                  <span class="text-ink-soft">{{ $t('orders.detail.balance') }}</span>
                  <span
                    class="font-mono font-bold"
                    :class="order.settlement.balance_tiyin === 0 ? 'text-success' : 'text-ink'"
                    >{{ formatTiyin(order.settlement.balance_tiyin) }}</span
                  >
                </div>
              </template>
            </div>
          </div>
        </section>
      </div>
    </template>

    <AppModal :open="historyOpen" :title="$t('orders.detail.history')" @close="historyOpen = false">
      <template v-if="order">
        <div v-if="order.events.length === 0" class="st-empty !border-0 !py-8">
          <h3>{{ $t('orders.detail.historyEmpty') }}</h3>
        </div>
        <ol v-else class="tl">
          <li
            v-for="(event, index) in order.events"
            :key="event.id"
            class="step"
            :class="timelineStepClass(event, index)"
          >
            <span class="when">{{ formatDate(event.changed_at) }}</span>
            <template v-if="isRevisionEvent(event)">{{ $t('orders.detail.edited') }}</template>
            <template v-else>
              {{
                event.from_status
                  ? workshopStatusUz(event.from_status)
                  : $t('orders.detail.created')
              }}
              <span class="text-ink-muted">→</span>
              {{ workshopStatusUz(event.to_status) }}
            </template>
            <span v-if="event.reason" class="block text-ink-soft">{{ event.reason }}</span>
            <span
              v-for="detail in revisionTimelineDetails(event, formatTiyin)"
              :key="detail"
              class="block text-ink-soft"
            >
              {{ detail }}
            </span>
            <span
              v-for="detail in timelineProductionDetails(event)"
              :key="detail"
              class="block text-ink-soft"
            >
              {{ detail }}
            </span>
          </li>
        </ol>
      </template>
    </AppModal>

    <ConfirmDialog
      :open="reasonDialogAction !== null"
      :title="
        reasonDialogAction === 'revert'
          ? $t('orders.confirm.revertTitle')
          : $t('orders.confirm.cancelTitle')
      "
      :message="
        reasonDialogAction === 'revert'
          ? $t('orders.confirm.revertMessage', { target: revertTargetLabel })
          : $t('orders.confirm.cancelMessage')
      "
      :confirm-label="
        reasonDialogAction === 'revert'
          ? $t('orders.confirm.revertAction')
          : $t('orders.action.cancel')
      "
      :cancel-label="$t('orders.confirm.closeLabel')"
      :busy-label="$t('orders.confirm.busyLabel')"
      :danger="reasonDialogAction === 'cancel'"
      :busy="orders.actionLoading"
      :confirm-disabled="reasonDraft.trim().length === 0"
      @cancel="reasonDialogAction = null"
      @confirm="confirmReasonedAction"
    >
      <label class="field !mb-0">
        <span>{{ $t('orders.confirm.reason') }}</span>
        <textarea v-model="reasonDraft" class="mp-input min-h-24 resize-y" />
      </label>
    </ConfirmDialog>

    <ConfirmDialog
      :open="markCollectedOpen"
      :title="$t('orders.confirm.collectedTitle')"
      :message="$t('orders.confirm.collectedDetailMessage')"
      :confirm-label="$t('orders.confirm.collectedAction')"
      :cancel-label="$t('orders.confirm.backLabel')"
      :busy-label="$t('orders.confirm.busyLabel')"
      :busy="orders.actionLoading"
      @cancel="markCollectedOpen = false"
      @confirm="markCollected"
    />

    <ConfirmDialog
      :open="discardEditOpen"
      :title="$t('orders.confirm.discardEditTitle')"
      :message="$t('orders.confirm.discardEditMessage')"
      :confirm-label="$t('orders.confirm.discardEditAction')"
      :cancel-label="$t('orders.confirm.backLabel')"
      :busy-label="$t('orders.confirm.busyLabel')"
      danger
      :busy="orders.actionLoading"
      @cancel="discardEditOpen = false"
      @confirm="discardEdit"
    />

    <AppModal
      :open="chizmaOpen"
      :title="$t('orders.detail.drawing')"
      max-width="max-w-3xl"
      @close="chizmaOpen = false"
    >
      <div v-if="order" class="grid gap-5">
        <template v-if="result">
          <div class="grid gap-3 sm:grid-cols-4">
            <div class="rounded-md bg-sunk p-3">
              <div class="filter-label">{{ $t('orders.detail.statPanels') }}</div>
              <div class="mt-1 text-xl font-extrabold">{{ totalPanels }}</div>
            </div>
            <div class="rounded-md bg-sunk p-3">
              <div class="filter-label">{{ $t('orders.detail.statCuts') }}</div>
              <div class="mt-1 text-xl font-extrabold">
                {{ metres(result.total_cut_length_mm) }}
              </div>
            </div>
            <div class="rounded-md bg-sunk p-3">
              <div class="filter-label">{{ $t('orders.detail.edge') }}</div>
              <div class="mt-1 text-xl font-extrabold">
                {{ metres(result.total_edge_length_mm) }}
              </div>
            </div>
            <div class="rounded-md bg-sunk p-3">
              <div class="filter-label">{{ $t('orders.detail.statWaste') }}</div>
              <div class="mt-1 text-xl font-extrabold">
                {{ (Number(result.waste_percentage) * 100).toFixed(2) }}%
              </div>
            </div>
          </div>
          <div class="flex flex-wrap gap-2" role="group" :aria-label="$t('orders.detail.sheets')">
            <button
              v-for="panel in result.panels"
              :key="panel.id"
              type="button"
              class="pill"
              :class="panel.id === activePanel?.id ? 'p-cut' : 'p-dn'"
              :aria-pressed="panel.id === activePanel?.id"
              @click="activePanelId = panel.id"
            >
              {{ panelTitle(result, panel) }}
            </button>
          </div>
          <CuttingPanelSvg
            v-if="activePanel"
            :result="result"
            :panel="activePanel"
            :active-placement-id="activePlacementId"
            @select-placement="selectPlacement"
          />
          <button
            type="button"
            class="mp-button mp-button-outline w-full"
            :disabled="orders.downloadingId === order.id"
            @click="orders.openWorkshopPdf(order.id)"
          >
            {{
              orders.downloadingId === order.id
                ? $t('orders.detail.pdfOpening')
                : $t('orders.detail.pdf')
            }}
          </button>
        </template>
        <div v-else class="st-empty !border-0 !py-6">
          <h3>{{ $t('orders.detail.noDrawing') }}</h3>
        </div>

        <div>
          <div class="mb-2 text-xs font-extrabold uppercase text-ink-muted">
            {{ $t('orders.detail.contents') }}
          </div>
          <!-- The same grouped, read-only list the client sees on their order
               and the operator fills in the editor: one layout across the three
               surfaces, so a cutter reading this against the drawing does not
               have to re-map it. -->
          <CuttingPartsByMaterial v-if="result" :result="result" />
          <div v-else class="st-empty !border-0 !py-6">
            <h3>{{ $t('orders.detail.noParts') }}</h3>
          </div>
        </div>

        <div v-if="order.planned_edge_lines.length > 0">
          <div class="mb-2 text-xs font-extrabold uppercase text-ink-muted">
            {{ $t('orders.detail.edge') }}
          </div>
          <div v-for="line in order.planned_edge_lines" :key="line.material_id" class="row-item">
            <div>
              <!-- material_label already carries thickness x width and color
                   (app/core/material_label.py's canonical edge shape) — no
                   separate thickness/color line needed underneath. -->
              <div class="nm">{{ line.material_label }}</div>
            </div>
            <div class="meta">{{ metres(line.consumed_mm) }}</div>
          </div>
        </div>
      </div>
    </AppModal>

    <OrderPricesModal
      v-if="order"
      :open="pricesOpen"
      :price-lines="order.price_lines"
      :cutting-rate-tiyin="order.cutting_rate_tiyin"
      :edge-banding-rate-tiyin="order.edge_banding_rate_tiyin"
      :panels-used="panelsUsed"
      :banded-mm="bandedMm"
      :busy="orders.actionLoading"
      :submit-error="pricesSubmitError"
      @save="savePrices"
      @close="pricesOpen = false"
    />

    <OrderOwnMaterialModal
      v-if="order"
      :open="ownEditOpen"
      :panel-lines="panelLines"
      :busy="orders.actionLoading"
      :submit-error="ownSubmitError"
      @save="saveOwnMaterial"
      @close="ownEditOpen = false"
    />

    <OrderPriceAdjustmentModal
      v-if="order"
      :open="discountOpen"
      :title="$t('orders.detail.discount')"
      :fixed-hint="$t('orders.detail.discountHint')"
      :current-tiyin="order.discount_tiyin"
      :current-reason="order.discount_reason"
      :apply-label="discountButtonLabel"
      :remove-label="$t('orders.detail.discountRemove')"
      :busy="orders.actionLoading"
      :pending="
        pendingAction === 'discount'
          ? 'apply'
          : pendingAction === 'removeDiscount'
            ? 'remove'
            : null
      "
      :submit-error="discountSubmitError"
      @apply="applyDiscount"
      @remove="removeDiscount"
      @close="discountOpen = false"
    />

    <OrderPriceAdjustmentModal
      v-if="order"
      :open="surchargeOpen"
      :title="$t('orders.detail.surcharge')"
      :fixed-hint="$t('orders.detail.surchargeHint')"
      :current-tiyin="order.surcharge_tiyin"
      :current-reason="order.surcharge_reason"
      :apply-label="surchargeButtonLabel"
      :remove-label="$t('orders.detail.surchargeRemove')"
      :busy="orders.actionLoading"
      :pending="
        pendingAction === 'surcharge'
          ? 'apply'
          : pendingAction === 'removeSurcharge'
            ? 'remove'
            : null
      "
      :submit-error="surchargeSubmitError"
      @apply="applySurcharge"
      @remove="removeSurcharge"
      @close="surchargeOpen = false"
    />
  </section>
</template>
