<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { ORDERS_PAGE_LIMIT } from '@/shared/app/constants'
import type { DateRangePreset } from '@/shared/app/dateRange'
import { traceLine } from '@/shared/app/errorTrace'
import type { DropdownOption } from '@/shared/app/roleConfig'
import { useRolePath } from '@/shared/app/paths'
import { assignmentChipsForOrder, edgerMissingForOrder } from '@/shared/app/workshopAssignments'
import {
  revertTargetLabelForOrder,
  workshopBoardColumns,
  workshopOrderListActions,
  type WorkshopOrderListAction,
} from '@/shared/app/workshopOrderDetail'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import {
  orderPillClass,
  stockShortfallMessage,
  workshopErrorMessage,
  workshopStatusUz,
} from '@/shared/app/workshopUi'
import AppIcon from '@/shared/components/AppIcon.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import DateRangePicker from '@/shared/components/DateRangePicker.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { formatDate, formatOrderNumber, formatRelative, formatTiyin } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { useCuttingStore } from '@/shared/stores/cutting'
import {
  activeWorkshopStatuses,
  useOrdersStore,
  type OrderStatus,
  type OrderSummary,
  type WorkshopWorkerOption,
} from '@/shared/stores/orders'
import { useWorkshopStore, type ProductionMode } from '@/shared/stores/workshop'

const orders = useOrdersStore()
const workshop = useWorkshopStore()
const auth = useAuthStore()
const permissions = useWorkshopPermissions()
const cutting = useCuttingStore()
// Saved walk-in drafts are a workshop-wide surface (manage_orders anywhere), not
// branch-scoped like the create gate. The count gives ambient awareness of
// unfinished cuttings waiting to become orders.
const canViewDrafts = computed(() => permissions.can(p.manageOrders))
const draftCount = computed(() => cutting.workshopDrafts.length)
const toast = useToast()
const rolePath = useRolePath()
const route = useRoute()
const router = useRouter()
const { t } = useI18n()
// "+ Yangi buyurtma" moved to the shell sidebar, which owns the gate now (an
// open branch the staffer may place orders on). It is on screen from every page,
// so this list does not repeat it.
const mode = ref<'board' | 'table'>('board')
const branchId = ref('all')
const status = ref('active')
const search = ref('')
// Digits-contains phone filter — the operator types whatever the client
// dictates (partial tail, spaced, +998…); the backend strips formatting.
const phoneFilter = ref('')
const datePreset = ref<DateRangePreset>('all')
const dateFrom = ref('')
const dateTo = ref('')
const listActionError = ref<string | null>(null)
const listActionTraceId = ref<string | null>(null)
const pendingConfirmAction = ref<{
  action: WorkshopOrderListAction
  order: OrderSummary
  title: string
  message: string
  confirmLabel: string
  danger?: boolean
} | null>(null)
const pendingReasonAction = ref<{
  action: WorkshopOrderListAction
  order: OrderSummary
  title: string
  message: string
  confirmLabel: string
  danger?: boolean
} | null>(null)
const reasonDraft = ref('')
const workerOptionsByBranch = ref<Record<string, WorkshopWorkerOption[]>>({})
const workerOptionLoadingBranches = new Set<string>()
let timer: number | undefined
// The onMounted branch/route resolution mutates `branchId`, which the filter
// watcher below would treat as a user edit and schedule a *second* debounced
// refresh right after the initial one — flashing the skeleton twice. Stay
// unhydrated until the first explicit load lands so that mount-time mutation
// doesn't double-fetch.
const hydrated = ref(false)

// Lifecycle buckets, not a per-status picker — the board's columns already
// break down the active statuses, so listing them here only duplicated that.
// "Hammasi" stays (last) so a search can span old orders. Dots mirror the
// order-status pill palette (orderPillClass).
const statusOptions = computed<DropdownOption[]>(() => [
  { value: 'active', label: t('orders.list.statusActive'), dot: 'accent' },
  { value: 'completed', label: t('orders.list.statusCompleted'), dot: 'muted' },
  { value: 'cancelled', label: t('orders.list.statusCancelled'), dot: 'danger' },
  { value: 'all', label: t('orders.list.statusAll') },
])
// The board's shape follows the SELECTED branch (list surfaces read the sidebar
// picker, orders.md): a simple branch gets the three grouped columns, and «Hammasi»
// — which mixes branches — keeps the full lifecycle so no branch's orders are
// folded into a column its own mode does not have.
const boardMode = computed<ProductionMode>(() =>
  workshop.branches.find((branch) => branch.id === branchId.value)?.production_mode === 'simple'
    ? 'simple'
    : 'full',
)
const isSimpleBoard = computed(() => boardMode.value === 'simple')
const boardColumns = computed(() => workshopBoardColumns(orders.workshopOrders, boardMode.value))
// Per ORDER, not per board: with «Hammasi» selected the list mixes branches, and
// a simple branch's order must not be nagged about an assignment it will never get.
function isSimpleOrder(order: OrderSummary) {
  return (
    workshop.branches.find((branch) => branch.id === order.branch_id)?.production_mode === 'simple'
  )
}
// Same rule, as a mode — the status vocabulary a row is labelled in. A simple
// branch's order reads «Tayyorlanmoqda» wherever it is listed, including a
// leftover still sitting in `cutting`.
function orderStatusMode(order: OrderSummary): ProductionMode {
  return isSimpleOrder(order) ? 'simple' : 'full'
}
const terminalStatus = computed(() => ['completed', 'cancelled'].includes(status.value))
// Branches whose worker list this reader may actually fetch. The board admits
// anyone with `manage_orders` *somewhere*, and then lists orders from every
// branch they can read — so a `view_orders`-only branch would otherwise have its
// worker lookup requested and refused (QAD-173).
const visibleOrderBranchIds = computed(() =>
  [...new Set(orders.workshopOrders.map((order) => order.branch_id))].filter((branchId) =>
    permissions.canOnBranch(p.manageOrders, branchId),
  ),
)
// Branch and search are driven by the topbar (context + global search), so the
// in-page reset only counts the status / date / phone controls.
const activeFilterCount = computed(
  () =>
    Number(status.value !== 'active') +
    Number(datePreset.value !== 'all') +
    Number(phoneFilter.value.trim() !== ''),
)
const hasActiveFilters = computed(() => activeFilterCount.value > 0)
// Every filter already clears itself (the dropdowns via their default option,
// the phone via its inline ×), so reset-all only earns its place once it does
// more than any single inline clear — i.e. from the second active filter on.
const showResetAll = computed(() => activeFilterCount.value > 1)

function resetFilters() {
  status.value = 'active'
  // DateRangePicker re-derives from/to (to open) when the preset flips to 'all'.
  datePreset.value = 'all'
  phoneFilter.value = ''
}

function applyContextBranch() {
  const contextBranchId = workshop.selectedBranchContext
  if (!contextBranchId) return
  if (!workshop.branches.some((branch) => branch.id === contextBranchId)) return
  branchId.value = contextBranchId
}

function routeSearchValue() {
  const value = route.query.search
  return typeof value === 'string' ? value : ''
}

function routeBranchValue() {
  const value = route.query.branch
  return typeof value === 'string' ? value : ''
}

function applyRouteSearch() {
  const value = routeSearchValue()
  if (value !== search.value) search.value = value
}

function applyRouteBranch() {
  const value = routeBranchValue()
  if (!value) return false
  if (value === 'all' || workshop.branches.some((branch) => branch.id === value)) {
    branchId.value = value
    return true
  }
  return false
}

function listFilters() {
  return {
    branch_id: branchId.value === 'all' ? null : branchId.value,
    status: status.value,
    search: search.value,
    contact_phone: phoneFilter.value.trim() || null,
    date_from: dateFrom.value || null,
    date_to: dateTo.value || null,
  }
}

// Assignment STATUS only (never a piece count). The board meta already prints
// "{item_count} detal", so returning the count here too double-printed it.
function assignedText(order: OrderSummary) {
  // A simple-mode order has no assignment to be missing — "kesuvchi yo'q" there
  // names a gap that does not exist.
  if (isSimpleOrder(order)) return ''
  if (order.status === 'cutting')
    return order.assigned_cutter_user_id
      ? t('orders.assignment.cutterAssigned')
      : t('orders.assignment.cutterMissing')
  if (order.status === 'edge_banding')
    return order.assigned_edger_user_id
      ? t('orders.assignment.edgerAssigned')
      : t('orders.assignment.edgerMissing')
  if (order.status === 'confirmed') return t('orders.assignment.needed')
  return ''
}

function resolveAssignmentWorker(branchId: string, userId: string) {
  return (
    workerOptionsByBranch.value[branchId]?.find((worker) => worker.id === userId) ??
    Object.values(workerOptionsByBranch.value)
      .flat()
      .find((worker) => worker.id === userId) ??
    null
  )
}

function assignmentChips(order: OrderSummary) {
  if (isSimpleOrder(order)) return []
  return assignmentChipsForOrder(order, resolveAssignmentWorker)
}

/** The no-edger warning is a full-mode staffing nudge; simple mode has no
 *  station to stall at, so the chip would be pure noise. */
function edgerMissing(order: OrderSummary) {
  return !isSimpleOrder(order) && edgerMissingForOrder(order)
}

async function loadWorkerOptionsForBranches(branchIds: string[]) {
  for (const id of branchIds) {
    if (workerOptionsByBranch.value[id] || workerOptionLoadingBranches.has(id)) continue
    workerOptionLoadingBranches.add(id)
    try {
      await orders.loadWorkers(id)
      workerOptionsByBranch.value = {
        ...workerOptionsByBranch.value,
        [id]: [...orders.workerOptions],
      }
    } catch {
      workerOptionsByBranch.value = {
        ...workerOptionsByBranch.value,
        [id]: [],
      }
    } finally {
      workerOptionLoadingBranches.delete(id)
    }
  }
}

function actionAccess(order: OrderSummary) {
  const canManageOrders = permissions.canOnBranch(p.manageOrders, order.branch_id)
  return {
    canManageOrders,
    canCompleteCutting:
      canManageOrders ||
      (permissions.canOnBranch(p.processProduction, order.branch_id) &&
        order.assigned_cutter_user_id === auth.me?.principal_id),
    canCompleteBanding:
      canManageOrders ||
      (permissions.canOnBranch(p.processProduction, order.branch_id) &&
        order.assigned_edger_user_id === auth.me?.principal_id),
  }
}

function actionsFor(order: OrderSummary) {
  return workshopOrderListActions(order, actionAccess(order))
}

// Whole table row opens detail (the board card body is already a link).
function openOrder(orderId: string) {
  void router.push(rolePath(`/workshop/orders/${orderId}`))
}

// --- Kanban drag-and-drop (desktop, full mode only). Status transitions are
// guarded, so a drop doesn't move the card directly — it triggers that order's
// forward action (approve / assign / done) or revert, reusing the existing
// dialogs. All other actions live on the order detail page.
//
// Simple mode has no drag: its forward move is the composite **Tayyor**, whose
// dialog names the stock it spends and offers the optional worker credit
// (orders.md). A drag cannot stand in for that, and a drop that merely opened
// the detail page would be a drag that is not a drag — so the card stays a link
// and the two taps live where their dialogs are.
const draggingOrderId = ref<string | null>(null)
const dragOverState = ref<OrderStatus | null>(null)

const FORWARD_ACTION_KIND: Record<string, WorkshopOrderListAction['kind']> = {
  new: 'approve',
  // Assignment no longer starts the job — the forward move out of `confirmed`
  // is start_cutting; an unassigned order falls back to the assign→detail path.
  confirmed: 'start_cutting',
  cutting: 'complete_cutting',
  edge_banding: 'complete_banding',
}

function isValidDropTarget(targetState: OrderStatus) {
  const order = orders.workshopOrders.find((item) => item.id === draggingOrderId.value)
  if (!order) return false
  const from = activeWorkshopStatuses.indexOf(order.status)
  const to = activeWorkshopStatuses.indexOf(targetState)
  if (from === -1 || to === -1) return false
  // Forward one stage, or back to any earlier stage (revert).
  return to === from + 1 || to < from
}

function onCardDragStart(order: OrderSummary, event: DragEvent) {
  if (isSimpleBoard.value) return
  draggingOrderId.value = order.id
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', order.id)
  }
}

function onCardDragEnd() {
  draggingOrderId.value = null
  dragOverState.value = null
}

function onColumnDragOver(state: OrderStatus, event: DragEvent) {
  if (isSimpleBoard.value) return
  if (!draggingOrderId.value || !isValidDropTarget(state)) return
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  dragOverState.value = state
}

function onColumnDrop(state: OrderStatus) {
  if (isSimpleBoard.value) return
  const order = orders.workshopOrders.find((item) => item.id === draggingOrderId.value)
  draggingOrderId.value = null
  dragOverState.value = null
  if (order) moveOrderToColumn(order, state)
}

function moveOrderToColumn(order: OrderSummary, targetState: OrderStatus) {
  const from = activeWorkshopStatuses.indexOf(order.status)
  const to = activeWorkshopStatuses.indexOf(targetState)
  if (from === -1 || to === -1 || from === to) return
  const list = actionsFor(order)
  if (to < from) {
    const revert = list.find((action) => action.kind === 'revert')
    if (!revert) {
      toast.danger(t('orders.list.revertBlocked'))
      return
    }
    startListAction(revert, order)
    return
  }
  if (to > from + 1) {
    toast.danger(t('orders.list.forwardOnly'))
    return
  }
  // Forward one stage: the order's primary forward action, falling back to
  // "assign" (e.g. a cutting order with no cutter yet) which routes to detail.
  const action =
    list.find((item) => item.kind === FORWARD_ACTION_KIND[order.status]) ??
    list.find((item) => item.kind === 'assign')
  if (!action) {
    toast.danger(t('orders.list.transitionBlocked'))
    return
  }
  if (action.kind === 'assign') {
    openOrder(order.id)
    return
  }
  startListAction(action, order)
}

function confirmConfig(action: WorkshopOrderListAction, order: OrderSummary) {
  const named = { order: formatOrderNumber(order.order_number) }
  if (action.kind === 'approve') {
    return {
      title: t('orders.confirm.approveTitle'),
      message: t('orders.confirm.approveMessage', named),
      confirmLabel: t('orders.action.approve'),
    }
  }
  if (action.kind === 'start_cutting') {
    return {
      title: t('orders.confirm.startCuttingTitle'),
      message: t('orders.confirm.startCuttingMessage', named),
      confirmLabel: t('orders.confirm.startCuttingAction'),
    }
  }
  if (action.kind === 'start_banding') {
    return {
      title: t('orders.confirm.startBandingTitle'),
      message: t('orders.confirm.startBandingMessage', named),
      confirmLabel: t('orders.confirm.startBandingAction'),
    }
  }
  if (action.kind === 'complete_cutting') {
    return {
      title: t('orders.confirm.completeCuttingTitle'),
      message: t('orders.confirm.completeCuttingMessage', named),
      confirmLabel: t('orders.action.completeCutting'),
    }
  }
  if (action.kind === 'complete_banding') {
    return {
      title: t('orders.confirm.completeBandingTitle'),
      message: t('orders.confirm.completeBandingMessage', named),
      confirmLabel: t('orders.action.completeBanding'),
    }
  }
  if (action.kind === 'mark_collected') {
    return {
      title: t('orders.confirm.collectedTitle'),
      message: t('orders.confirm.collectedMessage', named),
      confirmLabel: t('orders.confirm.collectedAction'),
    }
  }
  return null
}

function reasonConfig(action: WorkshopOrderListAction, order: OrderSummary) {
  if (action.kind === 'revert') {
    return {
      title: t('orders.confirm.revertTitle'),
      message: t('orders.confirm.revertOrderMessage', {
        order: formatOrderNumber(order.order_number),
        target: revertTargetLabelForOrder(order),
      }),
      confirmLabel: t('orders.confirm.revertAction'),
      danger: true,
    }
  }
  if (action.kind === 'cancel') {
    return {
      title: t('orders.confirm.cancelTitle'),
      message: t('orders.confirm.cancelOrderMessage', {
        order: formatOrderNumber(order.order_number),
      }),
      confirmLabel: t('orders.action.cancel'),
      danger: true,
    }
  }
  return null
}

function listActionSuccessMessage(action: WorkshopOrderListAction) {
  if (action.kind === 'approve') return t('orders.toast.approved')
  if (action.kind === 'start_cutting') return t('orders.toast.cuttingStarted')
  if (action.kind === 'start_banding') return t('orders.toast.bandingStarted')
  if (action.kind === 'complete_cutting') return t('orders.toast.cuttingDone')
  if (action.kind === 'complete_banding') return t('orders.toast.bandingDone')
  if (action.kind === 'mark_collected') return t('orders.toast.collected')
  if (action.kind === 'revert') return t('orders.toast.reverted')
  if (action.kind === 'cancel') return t('orders.toast.cancelled')
  return t('orders.toast.done')
}

function startListAction(action: WorkshopOrderListAction, order: OrderSummary) {
  listActionError.value = null
  listActionTraceId.value = null
  if (action.kind === 'detail' || action.kind === 'assign') return
  const confirm = confirmConfig(action, order)
  if (confirm) {
    pendingConfirmAction.value = { action, order, ...confirm, danger: action.danger }
    return
  }
  const reason = reasonConfig(action, order)
  if (reason) {
    // Start the reason blank so a destructive confirm isn't armed the instant the
    // dialog opens — the required-reason guard keeps confirm disabled until typed.
    reasonDraft.value = ''
    pendingReasonAction.value = { action, order, ...reason }
  }
}

async function runListMutation(order: OrderSummary, action: () => Promise<unknown>) {
  listActionError.value = null
  listActionTraceId.value = null
  try {
    await action()
    await refresh()
    return true
  } catch {
    listActionError.value = workshopErrorMessage(orders.actionError ?? 'order_action_failed')
    listActionTraceId.value = orders.actionTraceId
    return false
  }
}

async function confirmListAction() {
  const pending = pendingConfirmAction.value
  if (!pending) return
  const { action, order } = pending
  let ok = false
  // Set by the two completion branches when the consume they recorded drove a
  // branch balance below zero — informational, raised after the success toast.
  let shortfall = false
  if (action.kind === 'approve') {
    ok = await runListMutation(order, () => orders.approve(order.id, order.version))
  } else if (action.kind === 'start_cutting') {
    ok = await runListMutation(order, () => orders.startCutting(order.id, order.version))
  } else if (action.kind === 'start_banding') {
    ok = await runListMutation(order, () => orders.startBanding(order.id, order.version))
  } else if (action.kind === 'complete_cutting') {
    const completedBy = order.assigned_cutter_user_id
    if (!completedBy) {
      listActionError.value = t('orders.error.cuttingWorkerMissing')
      listActionTraceId.value = null
      ok = false
    } else {
      ok = await runListMutation(order, async () => {
        const updated = await orders.cuttingDone(order.id, {
          version: order.version,
          completed_by_user_id: completedBy,
        })
        shortfall = updated.stock_shortfall
      })
    }
  } else if (action.kind === 'complete_banding') {
    const completedBy = order.assigned_edger_user_id
    if (!completedBy) {
      listActionError.value = t('orders.error.bandingWorkerMissing')
      listActionTraceId.value = null
      ok = false
    } else {
      ok = await runListMutation(order, async () => {
        const updated = await orders.bandingDone(order.id, {
          version: order.version,
          completed_by_user_id: completedBy,
        })
        shortfall = updated.stock_shortfall
      })
    }
  } else if (action.kind === 'mark_collected') {
    ok = await runListMutation(order, () => orders.markCollected(order.id, order.version))
  }
  if (ok) {
    toast.success(listActionSuccessMessage(action))
    if (shortfall) toast.warn(stockShortfallMessage())
    pendingConfirmAction.value = null
  }
}

async function confirmReasonAction() {
  const pending = pendingReasonAction.value
  const reason = reasonDraft.value.trim()
  if (!pending || !reason) return
  const { action, order } = pending
  const ok =
    action.kind === 'revert'
      ? await runListMutation(order, () => orders.revert(order.id, order.version, reason))
      : await runListMutation(order, () =>
          orders.cancelWorkshopOrder(order.id, order.version, reason),
        )
  if (ok) {
    toast.success(listActionSuccessMessage(action))
    pendingReasonAction.value = null
  }
}

function setMode(next: 'board' | 'table') {
  mode.value = terminalStatus.value && next === 'board' ? 'table' : next
}

async function refresh() {
  await orders.loadWorkshopOrders({
    ...listFilters(),
  })
  await loadWorkerOptionsForBranches(visibleOrderBranchIds.value)
}

async function loadMore() {
  await orders.loadWorkshopOrders({
    ...listFilters(),
    limit: ORDERS_PAGE_LIMIT,
    offset: orders.workshopOrders.length,
  })
  await loadWorkerOptionsForBranches(visibleOrderBranchIds.value)
}

watch(status, () => {
  if (terminalStatus.value) mode.value = 'table'
})

watch(
  () => workshop.selectedBranchContext,
  (value) => {
    applyContextBranch()
    if (canViewDrafts.value) void cutting.loadWorkshopDrafts(value)
  },
)

watch(
  () => route.query.search,
  () => {
    applyRouteSearch()
  },
)

watch(
  () => route.query.branch,
  () => {
    applyRouteBranch()
  },
)

watch(branchId, (value) => {
  if (value !== 'all') workshop.setSelectedBranchContext(value)
})

watch([branchId, status, search, phoneFilter, dateFrom, dateTo], () => {
  if (!hydrated.value) return
  window.clearTimeout(timer)
  timer = window.setTimeout(() => void refresh(), 250)
})

onMounted(async () => {
  applyRouteSearch()
  await workshop.loadBranchContext().catch(() => undefined)
  if (!applyRouteBranch()) applyContextBranch()
  window.clearTimeout(timer)
  await refresh()
  // Now that the first load has landed, let user-driven filter edits refresh.
  hydrated.value = true
  // Ambient count for the Chizmalar entry; non-blocking so it never delays the
  // board/table. Scoped to the topbar branch so the badge matches what the
  // drafts page (also branch-scoped) will actually list.
  if (canViewDrafts.value) void cutting.loadWorkshopDrafts(workshop.selectedBranchContext)
})

onBeforeUnmount(() => {
  window.clearTimeout(timer)
})
</script>

<template>
  <section class="flex min-h-full flex-col">
    <div class="page-head">
      <div>
        <h1>{{ $t('orders.list.title') }}</h1>
        <p class="sub">{{ $t('orders.list.subtitle') }}</p>
      </div>
      <div class="tools">
        <RouterLink
          v-if="canViewDrafts"
          :to="rolePath('/workshop/orders/drafts')"
          class="mp-button mp-button-outline min-h-11 px-3 text-xs"
        >
          {{ $t('orders.list.drafts')
          }}<span v-if="draftCount > 0" class="ml-1 font-bold text-ink">· {{ draftCount }}</span>
        </RouterLink>
        <!-- Icon-only segmented view switch; each segment carries its accessible
             name (DESIGN.md icon rule) and a hover tooltip. -->
        <div
          class="flex gap-0.5 rounded-lg border border-hairline-strong bg-sunk p-0.5"
          role="group"
          :aria-label="$t('orders.list.viewGroup')"
        >
          <button
            type="button"
            class="grid size-10 place-items-center rounded-md transition disabled:cursor-not-allowed disabled:opacity-50"
            :class="
              mode === 'board'
                ? 'bg-accent text-on-accent'
                : 'text-ink-soft hover:bg-bg hover:text-ink'
            "
            :disabled="terminalStatus"
            :aria-pressed="mode === 'board'"
            :aria-label="$t('orders.list.boardView')"
            :title="terminalStatus ? $t('orders.list.boardLocked') : $t('orders.list.boardView')"
            @click="setMode('board')"
          >
            <AppIcon name="board" class="size-5" />
          </button>
          <button
            type="button"
            class="grid size-10 place-items-center rounded-md transition"
            :class="
              mode === 'table'
                ? 'bg-accent text-on-accent'
                : 'text-ink-soft hover:bg-bg hover:text-ink'
            "
            :aria-pressed="mode === 'table'"
            :aria-label="$t('orders.list.tableView')"
            :title="$t('orders.list.tableView')"
            @click="setMode('table')"
          >
            <AppIcon name="table" class="size-5" />
          </button>
        </div>
      </div>
    </div>

    <div class="mp-filters">
      <ProjectDropdown
        v-model="status"
        :label="$t('orders.list.statusFilter')"
        :options="statusOptions"
        top-label
      />
      <DateRangePicker
        v-model:preset="datePreset"
        v-model:date-from="dateFrom"
        v-model:date-to="dateTo"
      />
      <label class="mp-filter-input relative">
        <span>{{ $t('orders.list.phoneFilter') }}</span>
        <input
          v-model="phoneFilter"
          class="pr-9!"
          inputmode="tel"
          autocomplete="off"
          :placeholder="$t('orders.list.phonePlaceholder')"
          :aria-label="$t('orders.list.phoneFilterLabel')"
        />
        <!-- The input is the label's 40px bottom row; bottom-2 centers the 24px
             clear button on it (the CSS skin needs `> input`, so no wrapper). -->
        <button
          v-if="phoneFilter"
          type="button"
          class="absolute right-1.5 bottom-2 grid size-6 place-items-center rounded text-base text-ink-muted transition hover:bg-bg hover:text-ink"
          :aria-label="$t('orders.list.phoneFilterClear')"
          @click.prevent="phoneFilter = ''"
        >
          ×
        </button>
      </label>
      <button v-if="showResetAll" type="button" class="mp-filter-reset" @click="resetFilters">
        {{ $t('orders.list.resetFilters') }}
      </button>
      <!-- No create button here. The shell's sidebar carries `+ Yangi buyurtma`
           on every screen, with the same gate; a second copy on this page would
           be two identical primary controls competing on one screen. -->
    </div>

    <!-- The filtered state must announce itself (DESIGN.md UX bar: visible
         feedback) — a silent list swap reads as "nothing happened". -->
    <p
      v-if="hasActiveFilters"
      class="mb-3 -mt-2 text-xs font-bold text-ink-soft"
      role="status"
      aria-live="polite"
    >
      <template v-if="orders.loading">{{ $t('orders.list.refreshing') }}</template>
      <!-- A slot, not an interpolated string: the figure keeps its mono weight
           while the sentence around it stays one reorderable message. -->
      <i18n-t v-else keypath="orders.list.filterCount" scope="global">
        <template #count>
          <b class="text-ink"
            >{{ orders.workshopOrders.length }}{{ orders.workshopOrdersHasMore ? '+' : '' }}</b
          >
        </template>
      </i18n-t>
    </p>

    <section
      v-if="orders.loading && orders.workshopOrders.length === 0"
      aria-live="polite"
      aria-busy="true"
    >
      <div v-if="mode === 'board'" class="board">
        <div v-for="column in boardColumns" :key="column.key" class="board-col">
          <h4>{{ column.label }}</h4>
          <span class="sk mb-2 block h-24 w-full"></span>
          <span class="sk block h-24 w-full"></span>
        </div>
      </div>
      <div v-else class="card">
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>ID</th>
                <th>{{ $t('orders.list.colClient') }}</th>
                <th>{{ $t('orders.list.colBranch') }}</th>
                <th>{{ $t('orders.list.colStatus') }}</th>
                <th>{{ $t('orders.list.colAssignee') }}</th>
                <th class="right">{{ $t('orders.list.colTotal') }}</th>
                <th>{{ $t('orders.list.colTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="n in 6" :key="n">
                <td colspan="7"><span class="sk sk-line" style="width: 100%"></span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section
      v-else-if="orders.error && orders.workshopOrders.length === 0"
      class="st-error"
      role="alert"
    >
      <h3>{{ $t('orders.list.loadFailedTitle') }}</h3>
      <p>{{ $t('orders.state.connectionRetry') }}</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        :disabled="orders.loading"
        @click="refresh"
      >
        {{ $t('orders.state.retry') }}
      </button>
      <p v-if="orders.traceId" class="mt-3 text-xs text-ink-muted">
        trace_id: {{ orders.traceId }}
      </p>
    </section>

    <section v-else-if="workshop.branches.length === 0" class="st-empty">
      <h3>{{ $t('orders.list.noBranchTitle') }}</h3>
      <p>{{ $t('orders.list.noBranchBody') }}</p>
    </section>

    <!-- Filtered-empty and first-run are different situations and get different
         copy: "change the filter" is useless advice when no order exists yet. -->
    <section v-else-if="orders.workshopOrders.length === 0" class="st-empty">
      <h3>
        {{ hasActiveFilters ? $t('orders.list.emptyFilteredTitle') : $t('orders.list.emptyTitle') }}
      </h3>
      <p>
        {{ hasActiveFilters ? $t('orders.list.emptyFilteredBody') : $t('orders.list.emptyBody') }}
      </p>
    </section>

    <template v-else>
      <div v-if="orders.error" class="banner danger mb-4" aria-live="polite">
        <div class="grow">
          {{ $t('orders.list.loadErrorBanner') }} · {{ traceLine(orders.traceId) }}
        </div>
      </div>

      <div v-if="listActionError" class="banner danger mb-4" role="alert">
        <div class="grow">
          {{ listActionError }}
          <span v-if="listActionTraceId"> · trace_id: {{ listActionTraceId }}</span>
        </div>
      </div>

      <section v-if="mode === 'board'" class="board min-h-0 flex-1">
        <div
          v-for="column in boardColumns"
          :key="column.key"
          class="board-col"
          :class="{ 'drop-target': dragOverState === column.statuses[0] }"
          @dragover="onColumnDragOver(column.statuses[0], $event)"
          @drop.prevent="onColumnDrop(column.statuses[0])"
        >
          <h4>
            {{ column.label }}
            <span class="ct">{{ column.orders.length }}</span>
          </h4>
          <article
            v-for="order in column.orders"
            :key="order.id"
            class="board-card"
            :class="{ 'is-dragging': draggingOrderId === order.id }"
            :draggable="!isSimpleBoard"
            @dragstart="onCardDragStart(order, $event)"
            @dragend="onCardDragEnd"
          >
            <div
              class="block text-inherit no-underline"
              role="link"
              tabindex="0"
              :aria-label="
                $t('orders.list.cardLink', { order: formatOrderNumber(order.order_number) })
              "
              @click="openOrder(order.id)"
              @keydown.enter="openOrder(order.id)"
              @keydown.space.prevent="openOrder(order.id)"
            >
              <span class="top">
                <span class="id">{{ formatOrderNumber(order.order_number) }}</span>
                <span class="amt">{{ formatTiyin(order.total_tiyin) }}</span>
              </span>
              <span class="who">{{ order.contact_name }}</span>
              <!-- No per-card pill. The grouped «Tayyorlanmoqda» column used to
                   carry one because it folded three differently-named statuses
                   under one header; simple mode now names all three with that
                   single word, so the pill would repeat the header verbatim on
                   every card. In every column the header is the pill again. -->
              <span class="meta">
                <span>{{
                  $t('orders.unit.parts', { n: order.item_count }, order.item_count)
                }}</span>
                <span v-if="branchId === 'all'">{{ order.branch_name }}</span>
                <span :title="formatDate(order.created_at)">{{
                  formatRelative(order.created_at)
                }}</span>
                <span v-if="assignmentChips(order).length === 0 && assignedText(order)">{{
                  assignedText(order)
                }}</span>
              </span>
              <span
                v-if="order.stock_warnings.length > 0"
                class="mt-2 flex"
                :title="order.stock_warnings.map((warning) => warning.material_name).join(', ')"
              >
                <span
                  class="pill"
                  :class="
                    order.stock_warnings.some((warning) => warning.projected_after < 0)
                      ? 'p-bad'
                      : 'p-warn'
                  "
                >
                  <AppIcon name="alert" />
                  {{
                    order.stock_warnings.length > 1
                      ? $t('orders.list.stockWarningCount', {
                          count: order.stock_warnings.length,
                        })
                      : $t('orders.list.stockWarning')
                  }}
                </span>
              </span>
              <span
                v-if="assignmentChips(order).length > 0 || edgerMissing(order)"
                class="worker-chips mt-3"
                :aria-label="
                  $t('orders.list.assigneesLabel', { order: formatOrderNumber(order.order_number) })
                "
              >
                <span
                  v-for="chip in assignmentChips(order)"
                  :key="`${order.id}-${chip.key}-${chip.userId}`"
                  class="pill assignment-chip"
                  :class="chip.className"
                  :title="chip.label"
                  :aria-label="chip.label"
                >
                  <AppIcon :name="chip.icon" />
                  {{ chip.initials }}
                </span>
                <span
                  v-if="edgerMissing(order)"
                  class="pill p-warn"
                  :title="$t('orders.assignment.edgerMissingTitle')"
                >
                  <AppIcon name="alert" />
                  {{ $t('orders.assignment.edgerMissing') }}
                </span>
              </span>
            </div>
          </article>
        </div>
      </section>

      <section v-else class="card">
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>ID</th>
                <th>{{ $t('orders.list.colClient') }}</th>
                <th>{{ $t('orders.list.colBranch') }}</th>
                <th>{{ $t('orders.list.colStatus') }}</th>
                <th>{{ $t('orders.list.colAssignee') }}</th>
                <th class="right">{{ $t('orders.list.colTotal') }}</th>
                <th>{{ $t('orders.list.colTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="order in orders.workshopOrders"
                :key="order.id"
                class="clickable"
                tabindex="0"
                :aria-label="`${formatOrderNumber(order.order_number)} — ${order.contact_name}`"
                @click="openOrder(order.id)"
                @keydown.enter="openOrder(order.id)"
                @keydown.space.prevent="openOrder(order.id)"
              >
                <td class="id">{{ formatOrderNumber(order.order_number) }}</td>
                <td class="nm">
                  {{ order.contact_name }}<small>{{ order.contact_phone }}</small>
                </td>
                <td>{{ order.branch_name }}</td>
                <td>
                  <span
                    :class="orderPillClass(order.status as OrderStatus, orderStatusMode(order))"
                  >
                    <span class="pd"></span
                    >{{ workshopStatusUz(order.status, orderStatusMode(order)) }}
                  </span>
                </td>
                <td>
                  <span
                    v-if="assignmentChips(order).length > 0 || edgerMissing(order)"
                    class="worker-chips"
                  >
                    <span
                      v-for="chip in assignmentChips(order)"
                      :key="`${order.id}-table-${chip.key}-${chip.userId}`"
                      class="pill assignment-chip"
                      :class="chip.className"
                      :title="chip.label"
                      :aria-label="chip.label"
                    >
                      <AppIcon :name="chip.icon" />
                      {{ chip.initials }}
                    </span>
                    <span
                      v-if="edgerMissing(order)"
                      class="pill p-warn"
                      :title="$t('orders.assignment.edgerMissingTitle')"
                    >
                      <AppIcon name="alert" />
                      {{ $t('orders.assignment.edgerMissing') }}
                    </span>
                  </span>
                  <small v-else class="text-ink-soft">{{ assignedText(order) || '—' }}</small>
                </td>
                <td class="amt">{{ formatTiyin(order.total_tiyin) }}</td>
                <td class="num text-[11px] text-ink-muted">{{ formatDate(order.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <div v-if="orders.workshopOrdersHasMore" class="mt-4 flex justify-center">
        <button
          class="mp-button mp-button-outline min-h-10 px-4 text-sm"
          type="button"
          :disabled="orders.loading"
          @click="loadMore"
        >
          {{ orders.loading ? $t('orders.list.loadingMore') : $t('orders.list.loadMore') }}
        </button>
      </div>
    </template>

    <ConfirmDialog
      :open="pendingConfirmAction !== null"
      :title="pendingConfirmAction?.title ?? ''"
      :message="pendingConfirmAction?.message ?? ''"
      :confirm-label="pendingConfirmAction?.confirmLabel ?? $t('orders.confirm.defaultAction')"
      :cancel-label="$t('orders.confirm.backLabel')"
      :danger="pendingConfirmAction?.danger ?? false"
      :busy="orders.actionLoading"
      @cancel="pendingConfirmAction = null"
      @confirm="confirmListAction"
    />

    <ConfirmDialog
      :open="pendingReasonAction !== null"
      :title="pendingReasonAction?.title ?? ''"
      :message="pendingReasonAction?.message ?? ''"
      :confirm-label="pendingReasonAction?.confirmLabel ?? $t('orders.confirm.defaultAction')"
      :cancel-label="$t('orders.confirm.closeLabel')"
      :danger="pendingReasonAction?.danger ?? false"
      :busy="orders.actionLoading"
      :confirm-disabled="reasonDraft.trim().length === 0"
      @cancel="pendingReasonAction = null"
      @confirm="confirmReasonAction"
    >
      <label class="field !mb-0">
        <span>{{ $t('orders.confirm.reason') }}</span>
        <textarea v-model="reasonDraft" class="mp-input min-h-24 resize-y" />
      </label>
    </ConfirmDialog>
  </section>
</template>
