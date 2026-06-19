<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { apiTraceId } from '@/shared/api/client'
import { ORDERS_PAGE_LIMIT } from '@/shared/app/constants'
import { useRolePath } from '@/shared/app/paths'
import { assignmentChipsForOrder } from '@/shared/app/workshopAssignments'
import {
  revertTargetLabelForOrder,
  workshopOrderListActions,
  type WorkshopOrderListAction,
} from '@/shared/app/workshopOrderDetail'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import {
  branchOptions,
  orderPillClass,
  workshopErrorMessage,
  workshopStatusUz,
} from '@/shared/app/workshopUi'
import AppIcon from '@/shared/components/AppIcon.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { formatDate, formatTiyin } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
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
const toast = useToast()
const rolePath = useRolePath()
const route = useRoute()
const mode = ref<'board' | 'table'>('board')
const branchId = ref('all')
const status = ref('active')
const search = ref('')
const dateFilter = ref<'all' | 'today' | 'week' | 'month'>('all')
const openActionMenuId = ref<string | null>(null)
const listActionError = ref<string | null>(null)
const listActionTraceId = ref<string | null>(null)
const csvDownloading = ref(false)
const csvError = ref<string | null>(null)
const csvTraceId = ref<string | null>(null)
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

const branchFilterOptions = computed(() => branchOptions(workshop.branches))
const statusOptions = [
  { value: 'all', label: 'Hammasi', meta: 'barcha holatlar', status: 'active' as const },
  { value: 'active', label: 'Faol', meta: 'terminal emas', status: 'active' as const },
  { value: 'new', label: 'Yangi', meta: 'tasdiq kerak', status: 'pending' as const },
  {
    value: 'confirmed',
    label: 'Tasdiqlangan',
    meta: 'kesuvchi kutilmoqda',
    status: 'pending' as const,
  },
  { value: 'cutting', label: 'Kesilmoqda', meta: 'arra oldida', status: 'active' as const },
  { value: 'edge_banding', label: 'Kromda', meta: 'krom ishlari', status: 'active' as const },
  { value: 'ready', label: 'Tayyor', meta: 'olib ketishni kutmoqda', status: 'active' as const },
  {
    value: 'completed',
    label: 'Tugatilgan',
    meta: 'mijoz olib ketgan',
    status: 'blocked' as const,
  },
  { value: 'cancelled', label: 'Bekor qilingan', meta: 'to‘xtatilgan', status: 'blocked' as const },
]
const dateOptions = [
  { value: 'all', label: 'Barcha sanalar', meta: 'cheklanmagan', status: 'active' as const },
  { value: 'today', label: 'Bugun', meta: 'joriy kun', status: 'active' as const },
  { value: 'week', label: 'Oxirgi 7 kun', meta: 'bugundan orqaga', status: 'pending' as const },
  { value: 'month', label: 'Joriy oy', meta: 'oy boshidan', status: 'pending' as const },
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

function isoDate(value: Date) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function dateRange() {
  const now = new Date()
  if (dateFilter.value === 'today') {
    const today = isoDate(now)
    return { date_from: today, date_to: today }
  }
  if (dateFilter.value === 'week') {
    const start = new Date(now)
    start.setDate(now.getDate() - 6)
    return { date_from: isoDate(start), date_to: isoDate(now) }
  }
  if (dateFilter.value === 'month') {
    return {
      date_from: isoDate(new Date(now.getFullYear(), now.getMonth(), 1)),
      date_to: isoDate(now),
    }
  }
  return { date_from: null, date_to: null }
}

function listFilters() {
  const range = dateRange()
  return {
    branch_id: branchId.value === 'all' ? null : branchId.value,
    status: status.value,
    search: search.value,
    date_from: range.date_from,
    date_to: range.date_to,
  }
}

function assignedText(order: OrderSummary) {
  if (order.status === 'cutting')
    return order.assigned_cutter_user_id ? 'kesuvchi tayinlangan' : 'kesuvchi yo‘q'
  if (order.status === 'edge_banding')
    return order.assigned_edger_user_id ? 'kromchi tayinlangan' : 'kromchi yo‘q'
  if (order.status === 'confirmed') return 'tayinlash kerak'
  return `${order.item_count} qism`
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

function toggleActionMenu(orderId: string) {
  openActionMenuId.value = openActionMenuId.value === orderId ? null : orderId
}

function closeActionMenu() {
  openActionMenuId.value = null
}

function confirmConfig(action: WorkshopOrderListAction, order: OrderSummary) {
  if (action.kind === 'approve') {
    return {
      title: 'Buyurtmani tasdiqlash',
      message: `${order.order_number} tasdiqlanadi va ishlab chiqarishga tayyorlanadi.`,
      confirmLabel: 'Tasdiqlash',
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
      title: 'Krom tugadimi?',
      message: `${order.order_number} krom bosqichi yakunlanadi va buyurtma tayyor holatga o'tadi.`,
      confirmLabel: 'Krom tugadi',
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
      confirmLabel: 'Qaytarish',
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
  if (action.kind === 'complete_cutting') return 'Kesish yakunlandi.'
  if (action.kind === 'complete_banding') return 'Krom yakunlandi.'
  if (action.kind === 'mark_collected') return 'Buyurtma topshirildi.'
  if (action.kind === 'revert') return 'Buyurtma qaytarildi.'
  if (action.kind === 'cancel') return 'Buyurtma bekor qilindi.'
  return 'Amal bajarildi.'
}

function startListAction(action: WorkshopOrderListAction, order: OrderSummary) {
  closeActionMenu()
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
    reasonDraft.value = action.kind === 'revert' ? 'Ishlab chiqarish tuzatishi' : ''
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
      listActionError.value = 'Krom ishini bajargan xodim topilmadi.'
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

async function exportCsv() {
  csvDownloading.value = true
  csvError.value = null
  csvTraceId.value = null
  try {
    await orders.downloadWorkshopOrdersCsv(
      listFilters(),
      `workshop-orders-${isoDate(new Date())}.csv`,
    )
    toast.success('CSV yuklandi.')
  } catch (caught) {
    csvError.value = "CSV yuklab bo'lmadi. Qayta urinib ko'ring."
    csvTraceId.value = apiTraceId(caught)
  } finally {
    csvDownloading.value = false
  }
}

function onDocumentClick(event: MouseEvent) {
  if (!(event.target instanceof Element)) return
  if (!event.target.closest('[data-order-action-menu]')) closeActionMenu()
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

watch([branchId, status, search, dateFilter], () => {
  window.clearTimeout(timer)
  timer = window.setTimeout(() => void refresh(), 250)
})

onMounted(async () => {
  document.addEventListener('click', onDocumentClick)
  applyRouteSearch()
  await workshop.loadBranchContext().catch(() => undefined)
  if (!applyRouteBranch()) applyContextBranch()
  window.clearTimeout(timer)
  await refresh()
})

onBeforeUnmount(() => {
  window.clearTimeout(timer)
  document.removeEventListener('click', onDocumentClick)
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Buyurtmalar</h1>
        <p class="sub">Barcha filiallar bo'yicha buyurtmalar oqimi.</p>
      </div>
      <div class="tools">
        <button
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
          :class="{ 'bg-accent-soft text-accent': mode === 'board' }"
          type="button"
          @click="setMode('board')"
        >
          Taxta
        </button>
        <button
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
          :class="{ 'bg-accent-soft text-accent': mode === 'table' }"
          type="button"
          @click="setMode('table')"
        >
          Jadval
        </button>
        <RouterLink
          :to="rolePath('/workshop/cutting')"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
        >
          Kesish navbati
        </RouterLink>
        <button
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
          type="button"
          :disabled="csvDownloading"
          @click="exportCsv"
        >
          {{ csvDownloading ? 'CSV...' : 'CSV' }}
        </button>
      </div>
    </div>

    <div class="filters">
      <ProjectDropdown v-model="status" label="Holat" :options="statusOptions" />
      <label class="grid gap-1">
        <span class="filter-label">Qidirish</span>
        <input v-model="search" class="mp-input min-w-64" placeholder="ID yoki mijoz nomi..." />
      </label>
      <ProjectDropdown v-model="dateFilter" label="Sana" :options="dateOptions" />
      <ProjectDropdown v-model="branchId" label="Filial" :options="branchFilterOptions" />
    </div>

    <section
      v-if="orders.loading && orders.workshopOrders.length === 0"
      class="card p-5"
      aria-live="polite"
    >
      <div class="grid gap-3">
        <span class="sk-line"></span>
        <span class="sk-line"></span>
        <span class="sk-line"></span>
      </div>
    </section>

    <section v-else-if="orders.error && orders.workshopOrders.length === 0" class="st-error">
      <h3>Buyurtmalarni yuklab bo'lmadi</h3>
      <p>trace_id: {{ orders.traceId ?? 'unavailable' }}</p>
    </section>

    <section v-else-if="workshop.branches.length === 0" class="st-empty">
      <h3>Filial biriktirilmagan — ustaxona egasiga murojaat qiling</h3>
      <p>Filial biriktirilgach, buyurtmalar shu yerda ko'rinadi.</p>
    </section>

    <section v-else-if="orders.workshopOrders.length === 0" class="st-empty">
      <h3>Filial(lar)ingizda buyurtma yo'q</h3>
      <p>Tanlangan filtrga mos buyurtma yo'q.</p>
    </section>

    <template v-else>
      <div v-if="orders.error" class="banner danger mb-4">
        <div class="grow">
          Buyurtmalarni yuklashda xato yuz berdi · trace_id:
          {{ orders.traceId ?? 'unavailable' }}
        </div>
      </div>

      <div v-if="listActionError" class="banner danger mb-4">
        <div class="grow">
          {{ listActionError }}
          <span v-if="listActionTraceId"> · trace_id: {{ listActionTraceId }}</span>
        </div>
      </div>

      <div v-if="csvError" class="banner danger mb-4">
        <div class="grow">
          {{ csvError }}
          <span v-if="csvTraceId"> · trace_id: {{ csvTraceId }}</span>
        </div>
      </div>

      <section v-if="mode === 'board'" class="board">
        <div v-for="column in boardColumns" :key="column.state" class="board-col">
          <h4>
            {{ workshopStatusUz[column.state] }}
            <span class="ct">{{ column.orders.length }}</span>
          </h4>
          <article v-for="order in column.orders" :key="order.id" class="board-card">
            <RouterLink
              :to="rolePath(`/workshop/orders/${order.id}`)"
              class="block text-inherit no-underline"
            >
              <span class="top">
                <span class="id">{{ order.order_number }}</span>
                <span class="amt">{{ formatTiyin(order.total_tiyin) }}</span>
              </span>
              <span class="who">{{ order.contact_name }}</span>
              <span class="meta">
                <span>{{ order.item_count }} qism</span>
                <span>{{ formatDate(order.created_at) }}</span>
                <span v-if="assignmentChips(order).length === 0">{{ assignedText(order) }}</span>
              </span>
              <span
                v-if="assignmentChips(order).length > 0"
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
              </span>
            </RouterLink>
            <div
              class="mp-action-menu-wrap mt-3 ml-auto block w-fit"
              data-order-action-menu
              @click.stop
              @keydown.esc.stop.prevent="closeActionMenu"
            >
              <button
                type="button"
                class="mp-action-menu-button"
                :aria-expanded="openActionMenuId === order.id"
                :aria-controls="`order-actions-${order.id}`"
                :aria-label="`${order.order_number} holat amallari`"
                @click="toggleActionMenu(order.id)"
              >
                Holat <span aria-hidden="true">...</span>
              </button>
              <div
                v-if="openActionMenuId === order.id"
                :id="`order-actions-${order.id}`"
                class="mp-action-menu"
                role="menu"
              >
                <template
                  v-for="(action, index) in actionsFor(order)"
                  :key="`${order.id}-${action.kind}`"
                >
                  <div
                    v-if="action.kind === 'detail' && index > 0"
                    class="mp-action-menu-sep"
                    aria-hidden="true"
                  ></div>
                  <RouterLink
                    v-if="action.kind === 'detail' || action.kind === 'assign'"
                    :to="rolePath(`/workshop/orders/${order.id}`)"
                    class="mp-action-menu-item"
                    :class="{ danger: action.danger }"
                    role="menuitem"
                    @click="closeActionMenu"
                  >
                    {{ action.label }}
                  </RouterLink>
                  <button
                    v-else
                    type="button"
                    class="mp-action-menu-item"
                    :class="{ danger: action.danger }"
                    role="menuitem"
                    :disabled="orders.actionLoading"
                    @click="startListAction(action, order)"
                  >
                    {{ action.label }}
                  </button>
                </template>
              </div>
            </div>
          </article>
          <div v-if="column.orders.length === 0" class="py-4 text-center text-xs text-ink-muted">
            bo'sh
          </div>
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
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="order in orders.workshopOrders" :key="order.id" class="clickable">
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
                  <span v-if="assignmentChips(order).length > 0" class="worker-chips">
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
                  </span>
                  <small v-else class="text-ink-soft">{{ assignedText(order) }}</small>
                </td>
                <td class="amt">{{ formatTiyin(order.total_tiyin) }}</td>
                <td class="num text-[11px] text-ink-muted">{{ formatDate(order.created_at) }}</td>
                <td class="right" @click.stop>
                  <div
                    class="mp-action-menu-wrap"
                    data-order-action-menu
                    @keydown.esc.stop.prevent="closeActionMenu"
                  >
                    <button
                      type="button"
                      class="mp-action-icon-button"
                      :aria-expanded="openActionMenuId === order.id"
                      :aria-controls="`order-actions-table-${order.id}`"
                      :aria-label="`${order.order_number} amallari`"
                      @click="toggleActionMenu(order.id)"
                    >
                      <span aria-hidden="true">...</span>
                    </button>
                    <div
                      v-if="openActionMenuId === order.id"
                      :id="`order-actions-table-${order.id}`"
                      class="mp-action-menu"
                      role="menu"
                    >
                      <template
                        v-for="(action, index) in actionsFor(order)"
                        :key="`${order.id}-${action.kind}`"
                      >
                        <div
                          v-if="action.kind === 'detail' && index > 0"
                          class="mp-action-menu-sep"
                          aria-hidden="true"
                        ></div>
                        <RouterLink
                          v-if="action.kind === 'detail' || action.kind === 'assign'"
                          :to="rolePath(`/workshop/orders/${order.id}`)"
                          class="mp-action-menu-item"
                          :class="{ danger: action.danger }"
                          role="menuitem"
                          @click="closeActionMenu"
                        >
                          {{ action.label }}
                        </RouterLink>
                        <button
                          v-else
                          type="button"
                          class="mp-action-menu-item"
                          :class="{ danger: action.danger }"
                          role="menuitem"
                          :disabled="orders.actionLoading"
                          @click="startListAction(action, order)"
                        >
                          {{ action.label }}
                        </button>
                      </template>
                    </div>
                  </div>
                </td>
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
