<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { traceLine, traceSuffix } from '@/shared/app/errorTrace'
import { useRolePath } from '@/shared/app/paths'
import {
  isRevisionEvent,
  orderPhaseSteps,
  productionTimelineDetails,
  revisionTimelineDetails,
  type WorkshopAdjustmentKind,
} from '@/shared/app/workshopOrderDetail'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import {
  STOCK_SHORTFALL_MESSAGE,
  orderPillClass,
  workshopErrorMessage,
  workshopStatusUz,
} from '@/shared/app/workshopUi'
import AppIcon from '@/shared/components/AppIcon.vue'
import AppModal from '@/shared/components/AppModal.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import OrderPriceAdjustmentModal from '@/shared/components/OrderPriceAdjustmentModal.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { formatDate, formatTiyin } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import {
  useOrdersStore,
  type OrderDetail,
  type OrderEvent,
  type OrderItem,
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
    ? { to: rolePath('/workshop/orders'), label: '← Buyurtmalar' }
    : { to: rolePath('/workshop'), label: '← Asosiy' },
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
    if (current.cut_count_snapshot !== null) bits.push(`${current.cut_count_snapshot} kesim`)
    if (current.panels_used_snapshot !== null) bits.push(`${current.panels_used_snapshot} panel`)
    return { kind: 'done', text: bits.join(' · ') }
  }
  if (canManageOrders.value && current.status === 'cutting')
    return { kind: 'hint', text: "Kesish boshlangan — kesuvchini o'zgartirib bo'lmaydi." }
  return null
})
const edgerSub = computed<SlotSub>(() => {
  const current = order.value
  if (!current || !current.has_banding) return null
  if (current.edge_completed_at)
    return { kind: 'done', text: formatDate(current.edge_completed_at) }
  if (canManageOrders.value && current.status === 'edge_banding' && current.banding_started_at)
    return { kind: 'hint', text: "Kromka boshlangan — ustani o'zgartirib bo'lmaydi." }
  // The open slot doesn't block the saw, so from `cutting` on it carries the
  // nudge that used to live on the (blocked) start button.
  if (canManageOrders.value && !current.assigned_edger_user_id) {
    if (current.status === 'cutting')
      return { kind: 'hint', text: 'Hali tayinlanmagan — kromka boshlanishidan oldin tanlang.' }
    if (current.status === 'edge_banding')
      return { kind: 'hint', text: 'Kromka ustasi tayinlanmaguncha ish boshlanmaydi.' }
  }
  return null
})
// What still blocks the start tap — surface the gap instead of a dead click.
// The edger is deliberately not required here: its gate sits at the banding
// start, so the saw never waits on a later stage's staffing.
const startCuttingMissing = computed(() => {
  const current = order.value
  if (!current || current.status !== 'confirmed') return null
  if (!current.assigned_cutter_user_id) return 'Kesuvchi tanlanmagan'
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
  if (!current.assigned_edger_user_id) return 'Kromka yopishtiruvchi tanlanmagan'
  return null
})
const workerOptions = computed<ChoiceOption[]>(() =>
  orders.workerOptions.map((worker) => ({
    value: worker.id,
    label: worker.full_name,
    meta: worker.is_owner ? 'rahbar' : 'production',
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
  const pieces = `${totalPieces.value} detal`
  return result.value ? `${pieces} · ${totalPanels.value} panel` : pieces
})
const phaseSteps = computed(() => (order.value ? orderPhaseSteps(order.value) : []))
const isCancelled = computed(() => order.value?.status === 'cancelled')
const discountButtonLabel = computed(() =>
  order.value?.discount_tiyin ? 'Chegirmani yangilash' : "Chegirma qo'shish",
)
const surchargeButtonLabel = computed(() =>
  order.value?.surcharge_tiyin ? 'Ustamani yangilash' : "Ustama qo'shish",
)
const noteDirty = computed(() => noteDraft.value.trim() !== (order.value?.note_workshop ?? ''))
// Cutting would oversell stock (projected balance below zero), not just dip low —
// escalate the warning banner to danger and reword it (QAD-82).
const hasShortfall = computed(
  () => order.value?.stock_warnings.some((warning) => warning.projected_after < 0) ?? false,
)
const revertTargetLabel = computed(() => {
  const current = order.value
  if (!current) return ''
  if (current.status === 'cutting') return 'tasdiqlangan holatiga'
  if (current.status === 'edge_banding') return 'kesishga'
  if (current.status === 'ready') return current.has_banding ? 'kromkaga' : 'kesishga'
  return ''
})
const revertButtonLabel = computed(() => {
  if (!revertTargetLabel.value) return 'Bir qadam orqaga'
  const label = `${revertTargetLabel.value} qaytarish`
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
    return { key: 'approve', label: 'Tasdiqlash', busyLabel: 'Tasdiqlanmoqda…', run: approve }
  if (current.status === 'confirmed' && (canManageOrders.value || canCompleteCutting.value))
    return {
      key: 'startCutting',
      label: 'Kesishni boshlash',
      busyLabel: 'Boshlanmoqda…',
      disabled: !canStartCutting.value,
      hint: startCuttingMissing.value,
      run: startCutting,
    }
  if (current.status === 'cutting' && canCompleteCutting.value)
    return {
      key: 'completeCutting',
      label: 'Kesish tugadi',
      busyLabel: 'Bajarilmoqda…',
      run: completeCutting,
    }
  if (current.status === 'edge_banding' && canCompleteBanding.value) {
    // Guided two-tap flow: start stamps the duration, then the same slot turns
    // into the completion action.
    return current.banding_started_at
      ? {
          key: 'completeBanding',
          label: 'Kromka tugadi',
          busyLabel: 'Bajarilmoqda…',
          run: completeBanding,
        }
      : {
          key: 'startBanding',
          label: 'Kromka boshlash',
          busyLabel: 'Boshlanmoqda…',
          disabled: startBandingMissing.value !== null,
          hint: startBandingMissing.value,
          run: startBanding,
        }
  }
  if (current.status === 'ready' && canManageOrders.value)
    return {
      key: 'markCollected',
      label: 'Mijoz olib ketdi',
      busyLabel: 'Bajarilmoqda…',
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
    items.push({ key: 'edit', label: 'Tahrirlash', run: startEdit })
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
      label: 'Buyurtmani bekor qilish',
      danger: true,
      run: requestCancelOrder,
    })
  return items
})

function snapshotName(item: OrderItem) {
  const value = item.material_snapshot.name
  return typeof value === 'string' ? value : item.material_id.slice(0, 8)
}

function edgeCountLabel(item: OrderItem) {
  const count = edgeSideDetails(item).length
  return count > 0 ? `Kromka · ${count} tomon` : "kromka yo'q"
}

function edgeSideDetails(item: OrderItem) {
  return [
    { label: 'Yuqori', edge: item.edge_top, length: item.length_mm },
    { label: 'Past', edge: item.edge_bottom, length: item.length_mm },
    { label: 'Chap', edge: item.edge_left, length: item.width_mm },
    { label: "O'ng", edge: item.edge_right, length: item.width_mm },
  ]
    .filter((side) => side.edge)
    .map((side) => {
      const data = side.edge as Record<string, unknown>
      const snapshot =
        data.snapshot && typeof data.snapshot === 'object'
          ? (data.snapshot as Record<string, unknown>)
          : {}
      const thickness =
        snapshot.thickness_mm || snapshot.thickness || snapshot.size_mm
          ? `${snapshot.thickness_mm ?? snapshot.thickness ?? snapshot.size_mm} mm`
          : 'qalinlik yo‘q'
      const color =
        typeof snapshot.color === 'string' && snapshot.color ? ` · ${snapshot.color}` : ''
      const material =
        typeof snapshot.name === 'string' && snapshot.name ? ` · ${snapshot.name}` : ''
      const source = data.source === 'own' ? ' · mijoz materiali' : ''
      return `${side.label}: ${thickness}${color}${material} · ${metres(side.length * item.quantity)}${source}`
    })
}

// Itemized breakdown (always expanded): one row per material actually used,
// panel or kromka alike, from the backend's snapshot-exact price_lines.
const panelLines = computed<OrderPriceLine[]>(
  () => order.value?.price_lines.filter((line) => line.kind === 'panel') ?? [],
)
const edgeLines = computed<OrderPriceLine[]>(
  () => order.value?.price_lines.filter((line) => line.kind === 'edge') ?? [],
)

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
  if (!id) return 'Tayinlanmagan'
  return orders.workerOptions.find((worker) => worker.id === id)?.full_name ?? "Noma'lum xodim"
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
  return warning.kind === 'edge' ? metres(value) : `${value} pcs`
}

function panelTitle(current: CuttingResult, panel: CuttingPanel) {
  const snapshot = current.material_snapshots[panel.material_id]
  return `${String(snapshot?.name ?? 'Panel')} · ${panel.panel_index}`
}

function selectPlacement(placement: CuttingPlacement) {
  activePlacementId.value = placement.id
}

async function loadDetail() {
  await orders.loadWorkshopOrder(orderId.value)
  const current = orders.currentOrder
  if (current) await orders.loadWorkers(current.branch_id).catch(() => undefined)
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
  await run(() => orders.approve(current.id, current.version), 'Buyurtma tasdiqlandi.', 'approve')
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
    'Kesuvchi tayinlandi.',
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
    'Kromka ustasi tayinlandi.',
    'assignEdger',
  )
  if (!ok) edgerId.value = current.assigned_edger_user_id
}

async function startCutting() {
  const current = order.value
  if (!current || !canStartCutting.value) return
  await run(
    () => orders.startCutting(current.id, current.version),
    'Kesish boshlandi.',
    'startCutting',
  )
}

async function startBanding() {
  const current = order.value
  if (!current || !canCompleteBanding.value || current.banding_started_at) return
  if (!current.assigned_edger_user_id) return
  await run(
    () => orders.startBanding(current.id, current.version),
    'Kromka boshlandi.',
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
    actionError.value = 'Kesishni bajargan xodim topilmadi.'
    actionTraceId.value = null
    return
  }
  const ok = await run(
    () =>
      orders.cuttingDone(current.id, {
        version: current.version,
        completed_by_user_id: completedBy,
      }),
    'Kesish yakunlandi.',
    'completeCutting',
  )
  if (ok) warnOnStockShortfall()
}

async function completeBanding() {
  const current = order.value
  if (!current || !canCompleteBanding.value) return
  const completedBy = current.assigned_edger_user_id
  if (!completedBy) {
    actionError.value = 'Kromka ishini bajargan xodim topilmadi.'
    actionTraceId.value = null
    return
  }
  const ok = await run(
    () =>
      orders.bandingDone(current.id, {
        version: current.version,
        completed_by_user_id: completedBy,
      }),
    'Kromka yakunlandi.',
    'completeBanding',
  )
  if (ok) warnOnStockShortfall()
}

// The completion mutation stores the fresh order on the store, so the shortfall
// flag rides along with it — a warn toast next to the success one, never in
// place of it (QAD-150).
function warnOnStockShortfall() {
  if (orders.currentOrder?.stock_shortfall) toast.warn(STOCK_SHORTFALL_MESSAGE)
}

async function markCollected() {
  const current = order.value
  if (!current || !canManageOrders.value) return
  const ok = await run(
    () => orders.markCollected(current.id, current.version),
    'Buyurtma topshirildi.',
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
      ? await run(() => orders.revert(current.id, current.version, reason), 'Buyurtma qaytarildi.')
      : await run(
          () => orders.cancelWorkshopOrder(current.id, current.version, reason),
          'Buyurtma bekor qilindi.',
        )
  if (ok) reasonDialogAction.value = null
}

// Discount (chegirma −) and surcharge (ustama +) share the shape and the
// pre-production gate; each modal emits an already-parsed {kind, value, reason}
// (value in tiyin for a fixed sum) and the store posts it to the matching
// endpoint. Removal posts a zeroed adjustment, which clears the reason + actor.
type AdjustmentPayload = { kind: WorkshopAdjustmentKind; value: number; reason: string }

async function applyDiscount(payload: AdjustmentPayload) {
  const current = order.value
  if (!current || !canManageOrders.value) return
  discountSubmitError.value = null
  const ok = await run(
    () => orders.discount(current.id, { version: current.version, ...payload }),
    'Chegirma saqlandi.',
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
    'Chegirma olib tashlandi.',
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
    'Ustama saqlandi.',
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
    'Ustama olib tashlandi.',
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
    'Izoh saqlandi.',
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
    'Tahrir bekor qilindi.',
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
      <h3>Bu buyurtmaga ruxsatingiz yo'q</h3>
      <p>
        Buyurtma boshqa filialga tegishli, sizga biriktirilmagan yoki mavjud emas. Ro'yxatdan
        o'zingizga tegishlisini oching.
      </p>
    </section>
    <section v-else-if="orders.error" class="st-error" role="alert">
      <h3>Buyurtmani yuklab bo'lmadi</h3>
      <p>Internet aloqasini tekshirib, qayta urinib ko'ring.</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        :disabled="orders.loading"
        @click="loadDetail"
      >
        Qayta urinish
      </button>
      <p class="mt-3 text-xs text-ink-muted">{{ traceLine(orders.traceId) }}</p>
    </section>
    <section v-else-if="!order" class="st-empty">
      <h3>Buyurtma topilmadi</h3>
      <p>Buyurtmalar ro'yxatidan qayta ochib ko'ring.</p>
    </section>

    <template v-else>
      <header class="od-head">
        <div class="od-top">
          <h1>{{ order.order_number }}</h1>
          <span :class="orderPillClass(order.status)">
            <span class="pd"></span>{{ workshopStatusUz[order.status] }}
          </span>
          <div class="actions">
            <button
              type="button"
              class="mp-action-icon-button"
              aria-label="Holat tarixi"
              title="Holat tarixi"
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
                aria-label="Boshqa amallar"
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
          {{ primaryAction.hint }} — tayinlangach boshlash mumkin
        </p>
        <div class="od-meta">
          <span
            ><b>{{ order.contact_name }}</b> · {{ order.contact_phone }}</span
          >
          <!-- &nbsp; in the label: the template compiler condenses away the
               bare newline between elements, which glued "Jami:" to the sum. -->
          <span
            ><span class="lbl">Jami:&nbsp;</span
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
              <span class="lbl">Izoh:</span>
              <span class="txt min-w-0 truncate" :title="order.note_workshop">{{
                order.note_workshop
              }}</span>
              <button
                type="button"
                class="od-note-edit"
                aria-label="Izohni tahrirlash"
                @click="openNoteEditor"
              >
                <AppIcon name="pencil" class="size-3.5" />
              </button>
            </span>
            <button v-else type="button" class="od-note-add ml-auto" @click="openNoteEditor">
              + Izoh qo'shish
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
            placeholder="Faqat ustaxona xodimlari ko'radi"
            :disabled="orders.actionLoading && pendingAction === 'note'"
            @blur="onNoteBlur"
          ></textarea>
          <p class="mt-1 w-full text-xs text-ink-muted">
            {{ pendingAction === 'note' ? 'Saqlanmoqda…' : 'Chetga bosilganda saqlanadi' }}
          </p>
        </div>
        <div v-if="!isCancelled" class="od-steps" role="list" aria-label="Buyurtma bosqichlari">
          <template v-for="(step, i) in phaseSteps" :key="step.status">
            <span
              class="od-step"
              :class="step.state"
              role="listitem"
              :aria-current="step.state === 'current' ? 'step' : undefined"
            >
              <span class="od-dot" aria-hidden="true"></span>
              <span class="od-lbl">{{ workshopStatusUz[step.status] }}</span>
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
          <template v-if="canEditOrder">Bu buyurtmada ochiq tahrir bor.</template>
          <template v-else>Ochiq tahrir eskirgan — buyurtma holati o'zgargan.</template>
        </div>
        <RouterLink
          v-if="canEditOrder"
          :to="rolePath(`/workshop/orders/cutting/${order.revision_draft_id}`)"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
        >
          Davom ettirish
        </RouterLink>
        <button
          type="button"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs text-danger"
          :disabled="orders.actionLoading"
          @click="discardEditOpen = true"
        >
          Tahrirni bekor qilish
        </button>
      </div>

      <div
        v-if="order.stock_warnings.length > 0"
        class="banner mb-4"
        :class="hasShortfall ? 'danger' : 'warn'"
        role="status"
      >
        <div class="grow">
          {{ hasShortfall ? 'Kesishdan keyin zaxira yetishmaydi:' : 'Kesishdan keyin kam qoladi:' }}
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
            <h2>Ishlab chiqarish</h2>
            <span class="collapse-meta">{{ productionMeta }}</span>
          </div>
          <!-- The card stretches to match its sibling (equal-height second
               row), but the content stacks sequentially from the top; the
               button pins to the bottom edge as a footer (mt-auto) so the
               free height collects in one deliberate gap, not between items. -->
          <div class="card-b flex min-h-0 flex-col !pb-0">
            <div class="flex flex-col gap-1 py-4">
              <FormSelect
                v-if="canAssignCutter"
                v-model="cutterId"
                label="Kesuvchi"
                :options="workerOptions"
                :disabled="workerOptions.length === 0 || orders.actionLoading"
                @update:model-value="applyCutter"
              />
              <template v-else>
                <span class="form-select-label block text-sm font-bold text-ink">Kesuvchi</span>
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
                  ><span class="font-bold text-success">✓ Bajardi</span> ·
                </template>
                {{ cutterSub.text }}
              </p>
            </div>
            <!-- The kromka slot is always present so the card reads the same on
                 every order; without banding it is a quiet disabled box. -->
            <div class="flex flex-col gap-1 border-t border-hairline py-4">
              <template v-if="!order.has_banding">
                <span class="form-select-label block text-sm font-bold text-ink"
                  >Kromka yopishtiruvchi</span
                >
                <div
                  class="flex min-h-10 items-center rounded-md border border-hairline bg-sunk px-3 text-sm font-semibold text-ink-muted"
                >
                  Bu buyurtmada kromka yo'q
                </div>
              </template>
              <FormSelect
                v-else-if="canAssignEdger"
                v-model="edgerId"
                label="Kromka yopishtiruvchi"
                :options="workerOptions"
                :disabled="workerOptions.length === 0 || orders.actionLoading"
                @update:model-value="applyEdger"
              />
              <template v-else>
                <span class="form-select-label block text-sm font-bold text-ink"
                  >Kromka yopishtiruvchi</span
                >
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
                Chizma va tarkib
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
              <div class="font-bold text-ink">Materiallar</div>
              <div class="mt-2 grid gap-2.5">
                <template v-if="order.price_lines.length > 0">
                  <div
                    v-for="line in panelLines"
                    :key="line.material_id"
                    class="flex items-baseline justify-between gap-3"
                  >
                    <span class="min-w-0 text-ink"
                      >{{ line.material_name
                      }}<small class="block text-xs text-ink-muted"
                        >{{ line.panels_used }} panel</small
                      ></span
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
                      }}<small class="block text-xs text-ink-muted">{{
                        metres(line.consumed_mm ?? 0)
                      }}</small></span
                    >
                    <span class="shrink-0 font-mono whitespace-nowrap text-ink">{{
                      formatTiyin(line.line_total_tiyin)
                    }}</span>
                  </div>
                </template>
                <template v-else>
                  <!-- Snapshot lines missing (no cutting result) — aggregate rows. -->
                  <div class="flex items-baseline justify-between gap-3">
                    <span class="min-w-0 text-ink">Panellar</span>
                    <span class="shrink-0 font-mono whitespace-nowrap text-ink">{{
                      formatTiyin(order.subtotal_materials_tiyin)
                    }}</span>
                  </div>
                  <div
                    v-if="edgeMaterialTotal(order) > 0"
                    class="flex items-baseline justify-between gap-3"
                  >
                    <span class="min-w-0 text-ink"
                      >Kromka<small class="block text-xs text-ink-muted">{{
                        metres(edgeConsumedTotal(order))
                      }}</small></span
                    >
                    <span class="shrink-0 font-mono whitespace-nowrap text-ink">{{
                      formatTiyin(edgeMaterialTotal(order))
                    }}</span>
                  </div>
                </template>
              </div>
              <div class="mt-3 font-bold text-ink">Xizmatlar</div>
              <div class="mt-2 grid gap-2.5">
                <div class="flex items-baseline justify-between gap-3">
                  <span class="min-w-0 text-ink"
                    >Kesish<small v-if="totalPanels > 0" class="block text-xs text-ink-muted"
                      >{{ totalPanels }} panel</small
                    ></span
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
                    >Kromka yopishtirish<small class="block text-xs text-ink-muted">{{
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
                    >Ustama<small
                      v-if="order.surcharge_reason"
                      class="block text-xs text-ink-muted"
                      >{{ order.surcharge_reason }}</small
                    ></span
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
                    >Chegirma<small
                      v-if="order.discount_reason"
                      class="block text-xs text-ink-muted"
                      >{{ order.discount_reason }}</small
                    ></span
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
                <span>Jami</span>
                <span class="font-mono text-base">{{ formatTiyin(order.total_tiyin) }}</span>
              </div>
              <template v-if="order.settlement && canViewSettlement">
                <div class="flex items-baseline justify-between text-sm text-ink-soft">
                  <span>To'langan</span>
                  <span
                    class="font-mono font-semibold"
                    :class="order.settlement.recorded_tiyin > 0 ? 'text-success' : ''"
                    >{{ formatTiyin(order.settlement.recorded_tiyin) }}</span
                  >
                </div>
                <div class="flex items-baseline justify-between text-sm">
                  <span class="text-ink-soft">Qoldiq</span>
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

    <AppModal :open="historyOpen" title="Holat tarixi" @close="historyOpen = false">
      <template v-if="order">
        <div v-if="order.events.length === 0" class="st-empty !border-0 !py-8">
          <h3>Holat tarixi hali yo'q</h3>
        </div>
        <ol v-else class="tl">
          <li
            v-for="(event, index) in order.events"
            :key="event.id"
            class="step"
            :class="timelineStepClass(event, index)"
          >
            <span class="when">{{ formatDate(event.changed_at) }}</span>
            <template v-if="isRevisionEvent(event)">Buyurtma tahrirlandi</template>
            <template v-else>
              {{ event.from_status ? workshopStatusUz[event.from_status] : 'Yaratildi' }}
              <span class="text-ink-muted">→</span>
              {{ workshopStatusUz[event.to_status] }}
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
      :title="reasonDialogAction === 'revert' ? 'Buyurtmani qaytarish' : 'Buyurtmani bekor qilish'"
      :message="
        reasonDialogAction === 'revert'
          ? `Buyurtma ${revertTargetLabel} qaytadi. Sababni yozing.`
          : 'Buyurtma yopiladi. Bekor qilish sababini yozing.'
      "
      :confirm-label="reasonDialogAction === 'revert' ? 'Ha, qaytarilsin' : 'Bekor qilish'"
      cancel-label="Yopish"
      busy-label="Bajarilmoqda"
      :danger="reasonDialogAction === 'cancel'"
      :busy="orders.actionLoading"
      :confirm-disabled="reasonDraft.trim().length === 0"
      @cancel="reasonDialogAction = null"
      @confirm="confirmReasonedAction"
    >
      <label class="field !mb-0">
        <span>Sabab</span>
        <textarea v-model="reasonDraft" class="mp-input min-h-24 resize-y" />
      </label>
    </ConfirmDialog>

    <ConfirmDialog
      :open="markCollectedOpen"
      title="Mijoz olib ketdimi?"
      message="Buyurtma yakuniy «topshirildi» holatiga o'tadi va ortga qaytarib bo'lmaydi."
      confirm-label="Ha, topshirildi"
      cancel-label="Orqaga"
      busy-label="Bajarilmoqda"
      :busy="orders.actionLoading"
      @cancel="markCollectedOpen = false"
      @confirm="markCollected"
    />

    <ConfirmDialog
      :open="discardEditOpen"
      title="Tahrirni bekor qilish"
      message="Tahrirdagi barcha o'zgarishlar o'chiriladi; buyurtma avvalgi holida qoladi."
      confirm-label="Ha, bekor qilinsin"
      cancel-label="Orqaga"
      busy-label="Bajarilmoqda"
      danger
      :busy="orders.actionLoading"
      @cancel="discardEditOpen = false"
      @confirm="discardEdit"
    />

    <AppModal
      :open="chizmaOpen"
      title="Chizma va tarkib"
      max-width="max-w-3xl"
      @close="chizmaOpen = false"
    >
      <div v-if="order" class="grid gap-5">
        <template v-if="result">
          <div class="grid gap-3 sm:grid-cols-4">
            <div class="rounded-md bg-sunk p-3">
              <div class="filter-label">Panel</div>
              <div class="mt-1 text-xl font-extrabold">{{ totalPanels }}</div>
            </div>
            <div class="rounded-md bg-sunk p-3">
              <div class="filter-label">Kesim</div>
              <div class="mt-1 text-xl font-extrabold">
                {{ metres(result.total_cut_length_mm) }}
              </div>
            </div>
            <div class="rounded-md bg-sunk p-3">
              <div class="filter-label">Kromka</div>
              <div class="mt-1 text-xl font-extrabold">
                {{ metres(result.total_edge_length_mm) }}
              </div>
            </div>
            <div class="rounded-md bg-sunk p-3">
              <div class="filter-label">Qoldiq</div>
              <div class="mt-1 text-xl font-extrabold">
                {{ (Number(result.waste_percentage) * 100).toFixed(2) }}%
              </div>
            </div>
          </div>
          <div class="flex flex-wrap gap-2" role="group" aria-label="Panellar">
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
            {{ orders.downloadingId === order.id ? 'Ochilmoqda…' : 'Chizma (PDF)' }}
          </button>
        </template>
        <div v-else class="st-empty !border-0 !py-6">
          <h3>Chizma biriktirilmagan</h3>
        </div>

        <div>
          <div class="mb-2 text-xs font-extrabold uppercase text-ink-muted">Buyurtma tarkibi</div>
          <details v-for="item in order.items" :key="item.id" class="bom-item">
            <summary class="bom-summary">
              <div class="bom-main">
                <div class="nm">
                  {{ snapshotName(item) }} · {{ item.length_mm }}x{{ item.width_mm }}
                </div>
                <small class="text-ink-muted"
                  >{{ item.material_source === 'own' ? 'mijoz paneli' : 'ustaxona paneli' }} ·
                  {{ edgeCountLabel(item) }}</small
                >
              </div>
              <span class="bom-qty">{{ item.quantity }} dona</span>
              <svg class="od-chev" viewBox="0 0 20 20" width="16" height="16" aria-hidden="true">
                <path
                  d="M5 7.5 10 12.5 15 7.5"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </summary>
            <div class="bom-body">
              <ul v-if="edgeSideDetails(item).length > 0" class="grid gap-1">
                <li
                  v-for="detail in edgeSideDetails(item)"
                  :key="detail"
                  class="text-xs text-ink-muted"
                >
                  {{ detail }}
                </li>
              </ul>
              <p v-else class="text-xs text-ink-muted">Bu panelda kromka yo'q — yaxlit panel.</p>
            </div>
          </details>
          <div v-if="order.items.length === 0" class="st-empty !border-0 !py-6">
            <h3>Chizma qismi yo'q</h3>
          </div>
        </div>

        <div v-if="order.planned_edge_lines.length > 0">
          <div class="mb-2 text-xs font-extrabold uppercase text-ink-muted">Kromka</div>
          <div v-for="line in order.planned_edge_lines" :key="line.material_id" class="row-item">
            <div>
              <div class="nm">{{ line.material_label }}</div>
              <small class="text-ink-muted">
                {{ line.thickness_mm ? `${line.thickness_mm} mm` : 'qalinlik yo‘q' }}
                <span v-if="line.color"> · {{ line.color }}</span>
              </small>
            </div>
            <div class="meta">{{ metres(line.consumed_mm) }}</div>
          </div>
        </div>
      </div>
    </AppModal>

    <OrderPriceAdjustmentModal
      v-if="order"
      :open="discountOpen"
      title="Chegirma"
      fixed-hint="aniq chegirma so'mda"
      :current-tiyin="order.discount_tiyin"
      :current-reason="order.discount_reason"
      :apply-label="discountButtonLabel"
      remove-label="Chegirmani olib tashlash"
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
      title="Ustama"
      fixed-hint="aniq ustama so'mda"
      :current-tiyin="order.surcharge_tiyin"
      :current-reason="order.surcharge_reason"
      :apply-label="surchargeButtonLabel"
      remove-label="Ustamani olib tashlash"
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
