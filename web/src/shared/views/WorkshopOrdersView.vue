<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import { branchOptions, orderPillClass, workshopStatusUz } from '@/shared/app/workshopUi'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { formatDate, formatTiyin } from '@/shared/formatters'
import {
  activeWorkshopStatuses,
  useOrdersStore,
  type OrderStatus,
  type OrderSummary,
} from '@/shared/stores/orders'
import { useWorkshopStore } from '@/shared/stores/workshop'

const orders = useOrdersStore()
const workshop = useWorkshopStore()
const rolePath = useRolePath()
const mode = ref<'board' | 'table'>('board')
const branchId = ref('all')
const status = ref('active')
const search = ref('')
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
const boardColumns = computed(() =>
  activeWorkshopStatuses.map((state) => ({
    state,
    orders: orders.workshopOrders.filter((order) => order.status === state),
  })),
)
const terminalStatus = computed(() => ['completed', 'cancelled'].includes(status.value))

function assignedText(order: OrderSummary) {
  if (order.status === 'cutting')
    return order.assigned_cutter_user_id ? 'kesuvchi tayinlangan' : 'kesuvchi yo‘q'
  if (order.status === 'edge_banding')
    return order.assigned_edger_user_id ? 'kromchi tayinlangan' : 'kromchi yo‘q'
  if (order.status === 'confirmed') return 'tayinlash kerak'
  return `${order.item_count} qism`
}

function setMode(next: 'board' | 'table') {
  mode.value = terminalStatus.value && next === 'board' ? 'table' : next
}

async function refresh() {
  await orders.loadWorkshopOrders({
    branch_id: branchId.value === 'all' ? null : branchId.value,
    status: status.value,
    search: search.value,
  })
}

watch(status, () => {
  if (terminalStatus.value) mode.value = 'table'
})

watch([branchId, status, search], () => {
  window.clearTimeout(timer)
  timer = window.setTimeout(() => void refresh(), 250)
})

onMounted(async () => {
  await workshop.loadBranchContext().catch(() => undefined)
  await refresh()
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
      </div>
    </div>

    <div class="filters">
      <ProjectDropdown v-model="status" label="Holat" :options="statusOptions" />
      <label class="grid gap-1">
        <span class="filter-label">Qidirish</span>
        <input v-model="search" class="mp-input min-w-64" placeholder="ID yoki mijoz nomi..." />
      </label>
      <ProjectDropdown v-model="branchId" label="Filial" :options="branchFilterOptions" />
    </div>

    <section v-if="orders.loading" class="card p-5" aria-live="polite">
      <div class="grid gap-3">
        <span class="sk-line"></span>
        <span class="sk-line"></span>
        <span class="sk-line"></span>
      </div>
    </section>

    <section v-else-if="orders.error" class="st-error">
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
      <section v-if="mode === 'board'" class="board">
        <div v-for="column in boardColumns" :key="column.state" class="board-col">
          <h4>
            {{ workshopStatusUz[column.state] }}
            <span class="ct">{{ column.orders.length }}</span>
          </h4>
          <RouterLink
            v-for="order in column.orders"
            :key="order.id"
            :to="rolePath(`/workshop/orders/${order.id}`)"
            class="board-card"
          >
            <span class="top">
              <span class="id">{{ order.order_number }}</span>
              <span class="amt">{{ formatTiyin(order.total_tiyin) }}</span>
            </span>
            <span class="who">{{ order.contact_name }}</span>
            <span class="meta">
              <span>{{ order.item_count }} qism</span>
              <span>{{ formatDate(order.created_at) }}</span>
              <span>{{ assignedText(order) }}</span>
            </span>
          </RouterLink>
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
                  <small class="text-ink-soft">{{ assignedText(order) }}</small>
                </td>
                <td class="amt">{{ formatTiyin(order.total_tiyin) }}</td>
                <td class="num text-[11px] text-ink-muted">{{ formatDate(order.created_at) }}</td>
                <td class="right">
                  <RouterLink
                    :to="rolePath(`/workshop/orders/${order.id}`)"
                    class="mp-button mp-button-primary min-h-8 px-2 text-xs"
                  >
                    Tafsilotlar
                  </RouterLink>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </section>
</template>
