<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { formatDate, formatTiyin } from '@/shared/formatters'
import {
  activeWorkshopStatuses,
  useOrdersStore,
  workshopStatusLabel,
  type OrderStatus,
  type OrderSummary,
} from '@/shared/stores/orders'
import { useWorkshopStore } from '@/shared/stores/workshop'

const orders = useOrdersStore()
const workshop = useWorkshopStore()
const branchId = ref('all')
const status = ref('active')
const search = ref('')
let timer: number | undefined

const branchOptions = computed<ChoiceOption[]>(() => [
  { value: 'all', label: 'All branches', meta: 'accessible orders' },
  ...workshop.branches.map((branch) => ({
    value: branch.id,
    label: branch.name,
    meta: branch.status === 'temporarily_closed' ? 'temporarily closed' : branch.address,
  })),
])
const statusOptions: ChoiceOption[] = [
  { value: 'all', label: 'All', meta: 'every status' },
  { value: 'active', label: 'Active', meta: 'not completed' },
  { value: 'new', label: 'New', meta: 'needs approval' },
  { value: 'confirmed', label: 'Confirmed', meta: 'needs assignment' },
  { value: 'cutting', label: 'Cutting', meta: 'panels in production' },
  { value: 'edge_banding', label: 'Edge banding', meta: 'edge tape work' },
  { value: 'ready', label: 'Ready', meta: 'waiting pickup' },
  { value: 'completed', label: 'Completed', meta: 'collected' },
  { value: 'cancelled', label: 'Cancelled', meta: 'stopped' },
]
const boardColumns = computed(() =>
  activeWorkshopStatuses.map((state) => ({
    state,
    orders: orders.workshopOrders.filter((order) => order.status === state),
  })),
)

function statusTone(state: OrderStatus) {
  if (state === 'completed') return 'bg-success-soft text-success'
  if (state === 'cancelled') return 'bg-danger-soft text-danger'
  if (state === 'ready') return 'bg-info-soft text-info'
  if (state === 'cutting' || state === 'edge_banding') return 'bg-accent-soft text-accent'
  return 'bg-warning-soft text-warning'
}

function assignedText(order: OrderSummary) {
  if (order.status === 'cutting') {
    return order.assigned_cutter_user_id ? 'cutter assigned' : 'no cutter'
  }
  if (order.status === 'edge_banding') {
    return order.assigned_edger_user_id ? 'bander assigned' : 'no bander'
  }
  if (order.status === 'confirmed') return 'assignment needed'
  return `${order.item_count} parts`
}

async function refresh() {
  await orders.loadWorkshopOrders({
    branch_id: branchId.value === 'all' ? null : branchId.value,
    status: status.value,
    search: search.value,
  })
}

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
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold text-ink">Orders</h1>
        <p class="mt-2 max-w-2xl text-base text-ink-soft">
          Branch-scoped order board and production handoff.
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <RouterLink to="/workshop/cutting" class="mp-button mp-button-outline">
          Cutting queue
        </RouterLink>
        <RouterLink to="/workshop/banding" class="mp-button mp-button-primary">
          Banding queue
        </RouterLink>
      </div>
    </div>

    <section class="mp-surface p-4">
      <div class="grid gap-3 md:grid-cols-[220px_220px_1fr]">
        <FormSelect v-model="branchId" label="Branch" :options="branchOptions" />
        <FormSelect v-model="status" label="Status" :options="statusOptions" />
        <label class="grid gap-1 text-sm font-bold text-ink">
          Search
          <input v-model="search" class="mp-input" placeholder="Order number or contact" />
        </label>
      </div>
    </section>

    <section v-if="orders.loading" class="mp-surface p-5" aria-live="polite">
      <div class="space-y-3">
        <div class="h-16 animate-pulse rounded bg-sunk"></div>
        <div class="h-16 animate-pulse rounded bg-sunk"></div>
      </div>
    </section>
    <section v-else-if="orders.error" class="mp-surface p-5">
      <div class="rounded-md bg-danger-soft p-4 text-danger">
        <div class="font-extrabold">Orders could not be loaded</div>
        <p class="mt-1 text-sm">trace {{ orders.traceId ?? 'unavailable' }}</p>
      </div>
    </section>
    <section v-else-if="orders.workshopOrders.length === 0" class="mp-surface p-5">
      <div class="rounded-lg border border-dashed border-hairline-strong bg-sunk p-6">
        <h2 class="font-serif text-2xl font-semibold text-ink">No orders</h2>
        <p class="mt-2 text-sm text-ink-soft">Orders appear here after clients place them.</p>
      </div>
    </section>

    <template v-else>
      <section class="grid gap-3 xl:grid-cols-5">
        <article
          v-for="column in boardColumns"
          :key="column.state"
          class="mp-surface min-h-36 overflow-hidden"
        >
          <div class="border-b border-hairline px-4 py-3">
            <div class="flex items-center justify-between gap-2">
              <h2 class="text-sm font-extrabold text-ink">
                {{ workshopStatusLabel[column.state] }}
              </h2>
              <span class="mp-chip" :class="statusTone(column.state)">
                {{ column.orders.length }}
              </span>
            </div>
          </div>
          <div v-if="column.orders.length === 0" class="p-4 text-sm text-ink-soft">
            No orders in this stage.
          </div>
          <div v-else class="divide-y divide-hairline">
            <RouterLink
              v-for="order in column.orders.slice(0, 4)"
              :key="order.id"
              :to="`/workshop/orders/${order.id}`"
              class="block px-4 py-3 no-underline transition hover:bg-sunk"
            >
              <span class="block font-mono text-xs font-extrabold text-ink">
                {{ order.order_number }}
              </span>
              <span class="mt-1 block truncate text-sm text-ink-soft">
                {{ order.contact_name }} · {{ assignedText(order) }}
              </span>
              <span class="mt-2 block font-mono text-xs font-bold text-accent">
                {{ formatTiyin(order.total_tiyin) }}
              </span>
            </RouterLink>
          </div>
        </article>
      </section>

      <section class="mp-surface overflow-hidden">
        <div class="border-b border-hairline px-5 py-4">
          <h2 class="font-serif text-xl font-semibold text-ink">Order list</h2>
        </div>
        <div class="divide-y divide-hairline">
          <article
            v-for="order in orders.workshopOrders"
            :key="order.id"
            class="grid gap-4 p-5 lg:grid-cols-[1fr_180px_auto]"
          >
            <div>
              <div class="flex flex-wrap items-center gap-2">
                <h3 class="font-mono text-base font-extrabold text-ink">
                  {{ order.order_number }}
                </h3>
                <span class="mp-chip" :class="statusTone(order.status)">
                  <span class="mp-dot" aria-hidden="true"></span>
                  {{ workshopStatusLabel[order.status] }}
                </span>
              </div>
              <p class="mt-2 text-sm text-ink-soft">
                {{ order.contact_name }} · {{ order.contact_phone }} · {{ order.branch_name }}
              </p>
              <p class="mt-1 text-sm text-ink-soft">
                {{ formatDate(order.created_at) }} · {{ assignedText(order) }}
              </p>
            </div>
            <div class="font-mono text-sm font-extrabold text-ink lg:text-right">
              {{ formatTiyin(order.total_tiyin) }}
            </div>
            <RouterLink :to="`/workshop/orders/${order.id}`" class="mp-button mp-button-primary">
              Open
            </RouterLink>
          </article>
        </div>
      </section>
    </template>
  </section>
</template>
