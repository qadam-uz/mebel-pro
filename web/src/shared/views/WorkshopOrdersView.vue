<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { ORDERS_PAGE_LIMIT } from '@/shared/app/constants'
import type { DateRangePreset } from '@/shared/app/dateRange'
import type { DropdownOption } from '@/shared/app/roleConfig'
import { useRolePath } from '@/shared/app/paths'
import { assignmentChipsForOrder, edgerMissingForOrder } from '@/shared/app/workshopAssignments'
import {
  revertTargetLabelForOrder,
  workshopOrderListActions,
  type WorkshopOrderListAction,
} from '@/shared/app/workshopOrderDetail'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import { orderPillClass, workshopErrorMessage, workshopStatusUz } from '@/shared/app/workshopUi'
import AppIcon from '@/shared/components/AppIcon.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import DateRangePicker from '@/shared/components/DateRangePicker.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { formatDate, formatRelativeUz, formatTiyin } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { useCuttingStore } from '@/shared/stores/cutting'
import {
  activeWorkshopStatuses,
  useOrdersStore,
  type OrderStatus,
  type OrderSummary,
  type WorkshopWorkerOption,
} from '@/shared/stores/orders'
import { useWorkshopStore } from '@/shared/stores/workshop'

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
// "+ Yangi buyurtma" is enabled only when the staffer can place orders on the
// CURRENT topbar branch and that branch is open — the flow is fixed to it.
const currentBranch = computed(() =>
  workshop.branches.find((item) => item.id === workshop.selectedBranchContext),
)
const canCreateWalkIn = computed(
  () =>
    !!currentBranch.value &&
    currentBranch.value.status === 'active' &&
    permissions.canOnBranch(p.manageOrders, currentBranch.value.id),
)
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
const statusOptions: DropdownOption[] = [
  { value: 'active', label: 'Faol', dot: 'accent' },
  { value: 'completed', label: 'Tugatilgan', dot: 'muted' },
  { value: 'cancelled', label: 'Bekor qilingan', dot: 'danger' },
  { value: 'all', label: 'Hammasi' },
]
const boardColumns = computed(() =>
  activeWorkshopStatuses.map((state) => ({
    state,
    orders: orders.workshopOrders.filter((order) => order.status === state),
  })),
)
const terminalStatus = computed(() => ['completed', 'cancelled'].includes(status.value))
const visibleOrderBranchIds = computed(() => [
  ...new Set(orders.workshopOrders.map((order) => order.branch_id)),
])
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
// "{item_count} qism", so returning the count here too double-printed it.
function assignedText(order: OrderSummary) {
  if (order.status === 'cutting')
    return order.assigned_cutter_user_id ? 'kesuvchi tayinlangan' : 'kesuvchi yo‘q'
  if (order.status === 'edge_banding')
    return order.assigned_edger_user_id ? 'kromka ustasi tayinlangan' : 'kromka ustasi yo‘q'
  if (order.status === 'confirmed') return 'tayinlash kerak'
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
  return assignmentChipsForOrder(order, resolveAssignmentWorker)
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

// --- Kanban drag-and-drop (desktop). Status transitions are guarded, so a drop
// doesn't move the card directly — it triggers that order's forward action
// (approve / assign / done) or revert, reusing the existing dialogs. All other
// actions live on the order detail page.
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
  if (!draggingOrderId.value || !isValidDropTarget(state)) return
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  dragOverState.value = state
}

function onColumnDrop(state: OrderStatus) {
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
      toast.danger('Bu buyurtmani orqaga qaytarib bo‘lmaydi.')
      return
    }
    startListAction(revert, order)
    return
  }
  if (to > from + 1) {
    toast.danger('Faqat keyingi bosqichga o‘tkazish mumkin.')
    return
  }
  // Forward one stage: the order's primary forward action, falling back to
  // "assign" (e.g. a cutting order with no cutter yet) which routes to detail.
  const action =
    list.find((item) => item.kind === FORWARD_ACTION_KIND[order.status]) ??
    list.find((item) => item.kind === 'assign')
  if (!action) {
    toast.danger('Bu o‘tishni hozir bajarib bo‘lmaydi (ruxsat yoki tayinlash kerak).')
    return
  }
  if (action.kind === 'assign') {
    openOrder(order.id)
    return
  }
  startListAction(action, order)
}

function confirmConfig(action: WorkshopOrderListAction, order: OrderSummary) {
  if (action.kind === 'approve') {
    return {
      title: 'Buyurtmani tasdiqlash',
      message: `${order.order_number} tasdiqlanadi va ishlab chiqarishga tayyorlanadi.`,
      confirmLabel: 'Tasdiqlash',
    }
  }
  if (action.kind === 'start_cutting') {
    return {
      title: 'Kesish boshlansinmi?',
      message: `${order.order_number} kesish bosqichiga o'tadi — usta ishni boshlagan bo'lishi kerak.`,
      confirmLabel: 'Boshlash',
    }
  }
  if (action.kind === 'start_banding') {
    return {
      title: 'Kromka boshlansinmi?',
      message: `${order.order_number} uchun kromka ishi boshlanganini belgilaysiz.`,
      confirmLabel: 'Boshlash',
    }
  }
  if (action.kind === 'complete_cutting') {
    return {
      title: 'Kesish tugadimi?',
      message: `${order.order_number} kesish bosqichi yakunlanadi va ombor zaxirasi yangilanadi.`,
      confirmLabel: 'Kesish tugadi',
    }
  }
  if (action.kind === 'complete_banding') {
    return {
      title: 'Kromka tugadimi?',
      message: `${order.order_number} kromka bosqichi yakunlanadi va buyurtma tayyor holatga o'tadi.`,
      confirmLabel: 'Kromka tugadi',
    }
  }
  if (action.kind === 'mark_collected') {
    return {
      title: 'Mijoz olib ketdimi?',
      message: `${order.order_number} yakuniy «topshirildi» holatiga o'tadi.`,
      confirmLabel: 'Ha, topshirildi',
    }
  }
  return null
}

function reasonConfig(action: WorkshopOrderListAction, order: OrderSummary) {
  if (action.kind === 'revert') {
    const target = revertTargetLabelForOrder(order)
    return {
      title: 'Buyurtmani qaytarish',
      message: `${order.order_number} ${target} qaytadi. Sababni yozing.`,
      confirmLabel: 'Ha, qaytarilsin',
      danger: true,
    }
  }
  if (action.kind === 'cancel') {
    return {
      title: 'Buyurtmani bekor qilish',
      message: `${order.order_number} yopiladi. Bekor qilish sababini yozing.`,
      confirmLabel: 'Bekor qilish',
      danger: true,
    }
  }
  return null
}

function listActionSuccessMessage(action: WorkshopOrderListAction) {
  if (action.kind === 'approve') return 'Buyurtma tasdiqlandi.'
  if (action.kind === 'start_cutting') return 'Kesish boshlandi.'
  if (action.kind === 'start_banding') return 'Kromka boshlandi.'
  if (action.kind === 'complete_cutting') return 'Kesish yakunlandi.'
  if (action.kind === 'complete_banding') return 'Kromka yakunlandi.'
  if (action.kind === 'mark_collected') return 'Buyurtma topshirildi.'
  if (action.kind === 'revert') return 'Buyurtma qaytarildi.'
  if (action.kind === 'cancel') return 'Buyurtma bekor qilindi.'
  return 'Amal bajarildi.'
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
  if (action.kind === 'approve') {
    ok = await runListMutation(order, () => orders.approve(order.id, order.version))
  } else if (action.kind === 'start_cutting') {
    ok = await runListMutation(order, () => orders.startCutting(order.id, order.version))
  } else if (action.kind === 'start_banding') {
    ok = await runListMutation(order, () => orders.startBanding(order.id, order.version))
  } else if (action.kind === 'complete_cutting') {
    const completedBy = order.assigned_cutter_user_id
    if (!completedBy) {
      listActionError.value = 'Kesishni bajargan xodim topilmadi.'
      listActionTraceId.value = null
      ok = false
    } else {
      ok = await runListMutation(order, () =>
        orders.cuttingDone(order.id, {
          version: order.version,
          completed_by_user_id: completedBy,
        }),
      )
    }
  } else if (action.kind === 'complete_banding') {
    const completedBy = order.assigned_edger_user_id
    if (!completedBy) {
      listActionError.value = 'Kromka ishini bajargan xodim topilmadi.'
      listActionTraceId.value = null
      ok = false
    } else {
      ok = await runListMutation(order, () =>
        orders.bandingDone(order.id, {
          version: order.version,
          completed_by_user_id: completedBy,
        }),
      )
    }
  } else if (action.kind === 'mark_collected') {
    ok = await runListMutation(order, () => orders.markCollected(order.id, order.version))
  }
  if (ok) {
    toast.success(listActionSuccessMessage(action))
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
  () => {
    applyContextBranch()
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
  // board/table.
  if (canViewDrafts.value) void cutting.loadWorkshopDrafts()
})

onBeforeUnmount(() => {
  window.clearTimeout(timer)
})
</script>

<template>
  <section class="flex min-h-full flex-col">
    <div class="page-head">
      <div>
        <h1>Buyurtmalar</h1>
        <p class="sub">Buyurtmalar oqimi.</p>
      </div>
      <div class="tools">
        <RouterLink
          v-if="canViewDrafts"
          :to="rolePath('/workshop/orders/drafts')"
          class="mp-button mp-button-outline min-h-11 px-3 text-xs"
        >
          Chizmalar<span v-if="draftCount > 0" class="ml-1 font-mono font-bold text-ink"
            >· {{ draftCount }}</span
          >
        </RouterLink>
        <!-- Icon-only segmented view switch; each segment carries its accessible
             name (DESIGN.md icon rule) and a hover tooltip. -->
        <div
          class="flex gap-0.5 rounded-lg border border-hairline-strong bg-sunk p-0.5"
          role="group"
          aria-label="Ko'rinish"
        >
          <button
            type="button"
            class="grid size-10 place-items-center rounded-md transition disabled:cursor-not-allowed disabled:opacity-50"
            :class="
              mode === 'board' ? 'bg-accent text-white' : 'text-ink-soft hover:bg-bg hover:text-ink'
            "
            :disabled="terminalStatus"
            :aria-pressed="mode === 'board'"
            aria-label="Doska ko'rinishi"
            :title="
              terminalStatus ? 'Yakunlangan buyurtmalar faqat jadval rejimida' : `Doska ko'rinishi`
            "
            @click="setMode('board')"
          >
            <AppIcon name="board" class="size-5" />
          </button>
          <button
            type="button"
            class="grid size-10 place-items-center rounded-md transition"
            :class="
              mode === 'table' ? 'bg-accent text-white' : 'text-ink-soft hover:bg-bg hover:text-ink'
            "
            :aria-pressed="mode === 'table'"
            aria-label="Jadval ko'rinishi"
            title="Jadval ko'rinishi"
            @click="setMode('table')"
          >
            <AppIcon name="table" class="size-5" />
          </button>
        </div>
      </div>
    </div>

    <div class="mp-filters">
      <ProjectDropdown v-model="status" label="Holat" :options="statusOptions" top-label />
      <DateRangePicker
        v-model:preset="datePreset"
        v-model:date-from="dateFrom"
        v-model:date-to="dateTo"
      />
      <label class="mp-filter-input relative">
        <span>Telefon</span>
        <input
          v-model="phoneFilter"
          class="pr-9!"
          inputmode="tel"
          autocomplete="off"
          placeholder="+998 yoki raqam qismi"
          aria-label="Mijoz telefoni bo'yicha filtrlash"
        />
        <!-- The input is the label's 40px bottom row; bottom-2 centers the 24px
             clear button on it (the CSS skin needs `> input`, so no wrapper). -->
        <button
          v-if="phoneFilter"
          type="button"
          class="absolute right-1.5 bottom-2 grid size-6 place-items-center rounded text-base text-ink-muted transition hover:bg-bg hover:text-ink"
          aria-label="Telefon filtrini tozalash"
          @click.prevent="phoneFilter = ''"
        >
          ×
        </button>
      </label>
      <button v-if="showResetAll" type="button" class="mp-filter-reset" @click="resetFilters">
        Hammasini tozalash
      </button>
      <!-- Primary action lives on the filter line; the `.mp-filters > .mp-button`
           rule aligns it to the control baseline and pushes it to the far end. -->
      <RouterLink
        v-if="canCreateWalkIn"
        :to="rolePath('/workshop/orders/new')"
        class="mp-button mp-button-primary"
      >
        + Yangi buyurtma
      </RouterLink>
      <button
        v-else
        class="mp-button mp-button-outline"
        type="button"
        disabled
        title="Yangi buyurtma yaratish uchun tegishli filialni tanlang (buyurtma boshqaruvi ruxsati bilan)"
      >
        + Yangi buyurtma
      </button>
    </div>

    <!-- The filtered state must announce itself (DESIGN.md UX bar: visible
         feedback) — a silent list swap reads as "nothing happened". -->
    <p
      v-if="hasActiveFilters"
      class="mb-3 -mt-2 text-xs font-bold text-ink-soft"
      role="status"
      aria-live="polite"
    >
      <template v-if="orders.loading">Yangilanmoqda…</template>
      <template v-else>
        Filtr bo'yicha
        <b class="font-mono text-ink"
          >{{ orders.workshopOrders.length }}{{ orders.workshopOrdersHasMore ? '+' : '' }}</b
        >
        ta buyurtma topildi
      </template>
    </p>

    <section
      v-if="orders.loading && orders.workshopOrders.length === 0"
      aria-live="polite"
      aria-busy="true"
    >
      <div v-if="mode === 'board'" class="board">
        <div v-for="state in activeWorkshopStatuses" :key="state" class="board-col">
          <h4>{{ workshopStatusUz[state] }}</h4>
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
                <th>Mijoz</th>
                <th>Filial</th>
                <th>Holat</th>
                <th>Mas'ul</th>
                <th class="right">Summa</th>
                <th>Vaqt</th>
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
      <h3>Buyurtmalarni yuklab bo'lmadi</h3>
      <p>Internet aloqasini tekshirib, qayta urinib ko'ring.</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        :disabled="orders.loading"
        @click="refresh"
      >
        Qayta urinish
      </button>
      <p v-if="orders.traceId" class="mt-3 text-xs text-ink-muted">
        trace_id: {{ orders.traceId }}
      </p>
    </section>

    <section v-else-if="workshop.branches.length === 0" class="st-empty">
      <h3>Filial biriktirilmagan — ustaxona rahbariga murojaat qiling</h3>
      <p>Filial biriktirilgach, buyurtmalar shu yerda ko'rinadi.</p>
    </section>

    <section v-else-if="orders.workshopOrders.length === 0" class="st-empty">
      <h3>Buyurtma mavjud emas</h3>
      <p>Tanlangan filtrlarga mos buyurtma topilmadi</p>
    </section>

    <template v-else>
      <div v-if="orders.error" class="banner danger mb-4" aria-live="polite">
        <div class="grow">
          Buyurtmalarni yuklashda xato yuz berdi · trace_id:
          {{ orders.traceId ?? 'unavailable' }}
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
          :key="column.state"
          class="board-col"
          :class="{ 'drop-target': dragOverState === column.state }"
          @dragover="onColumnDragOver(column.state, $event)"
          @drop.prevent="onColumnDrop(column.state)"
        >
          <h4>
            {{ workshopStatusUz[column.state] }}
            <span class="ct">{{ column.orders.length }}</span>
          </h4>
          <article
            v-for="order in column.orders"
            :key="order.id"
            class="board-card"
            :class="{ 'is-dragging': draggingOrderId === order.id }"
            draggable="true"
            @dragstart="onCardDragStart(order, $event)"
            @dragend="onCardDragEnd"
          >
            <div
              class="block text-inherit no-underline"
              role="link"
              tabindex="0"
              :aria-label="`${order.order_number} — tafsilotlar`"
              @click="openOrder(order.id)"
              @keydown.enter="openOrder(order.id)"
              @keydown.space.prevent="openOrder(order.id)"
            >
              <span class="top">
                <span class="id">{{ order.order_number }}</span>
                <span class="amt">{{ formatTiyin(order.total_tiyin) }}</span>
              </span>
              <span class="who">{{ order.contact_name }}</span>
              <span class="meta">
                <span>{{ order.item_count }} qism</span>
                <span v-if="branchId === 'all'">{{ order.branch_name }}</span>
                <span :title="formatDate(order.created_at)">{{
                  formatRelativeUz(order.created_at)
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
                      ? `zaxira yetishmaydi (${order.stock_warnings.length})`
                      : 'zaxira yetishmaydi'
                  }}
                </span>
              </span>
              <span
                v-if="assignmentChips(order).length > 0 || edgerMissingForOrder(order)"
                class="worker-chips mt-3"
                :aria-label="`${order.order_number} mas'ullari`"
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
                  v-if="edgerMissingForOrder(order)"
                  class="pill p-warn"
                  title="Kromka ustasi tayinlanmagan"
                >
                  <AppIcon name="alert" />
                  kromka ustasi yo'q
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
                <th>Mijoz</th>
                <th>Filial</th>
                <th>Holat</th>
                <th>Mas'ul</th>
                <th class="right">Summa</th>
                <th>Vaqt</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="order in orders.workshopOrders"
                :key="order.id"
                class="clickable"
                tabindex="0"
                :aria-label="`${order.order_number} — ${order.contact_name}`"
                @click="openOrder(order.id)"
                @keydown.enter="openOrder(order.id)"
                @keydown.space.prevent="openOrder(order.id)"
              >
                <td class="id">{{ order.order_number }}</td>
                <td class="nm">
                  {{ order.contact_name }}<small>{{ order.contact_phone }}</small>
                </td>
                <td>{{ order.branch_name }}</td>
                <td>
                  <span :class="orderPillClass(order.status as OrderStatus)">
                    <span class="pd"></span>{{ workshopStatusUz[order.status] }}
                  </span>
                </td>
                <td>
                  <span
                    v-if="assignmentChips(order).length > 0 || edgerMissingForOrder(order)"
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
                      v-if="edgerMissingForOrder(order)"
                      class="pill p-warn"
                      title="Kromka ustasi tayinlanmagan"
                    >
                      <AppIcon name="alert" />
                      kromka ustasi yo'q
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
          {{ orders.loading ? 'Yuklanmoqda' : "Yana ko'rsatish" }}
        </button>
      </div>
    </template>

    <ConfirmDialog
      :open="pendingConfirmAction !== null"
      :title="pendingConfirmAction?.title ?? ''"
      :message="pendingConfirmAction?.message ?? ''"
      :confirm-label="pendingConfirmAction?.confirmLabel ?? 'Tasdiqlash'"
      cancel-label="Orqaga"
      :danger="pendingConfirmAction?.danger ?? false"
      :busy="orders.actionLoading"
      @cancel="pendingConfirmAction = null"
      @confirm="confirmListAction"
    />

    <ConfirmDialog
      :open="pendingReasonAction !== null"
      :title="pendingReasonAction?.title ?? ''"
      :message="pendingReasonAction?.message ?? ''"
      :confirm-label="pendingReasonAction?.confirmLabel ?? 'Tasdiqlash'"
      cancel-label="Yopish"
      :danger="pendingReasonAction?.danger ?? false"
      :busy="orders.actionLoading"
      :confirm-disabled="reasonDraft.trim().length === 0"
      @cancel="pendingReasonAction = null"
      @confirm="confirmReasonAction"
    >
      <label class="field !mb-0">
        <span>Sabab</span>
        <textarea v-model="reasonDraft" class="mp-input min-h-24 resize-y" />
      </label>
    </ConfirmDialog>
  </section>
</template>
