<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import FormSelect from '@/shared/components/FormSelect.vue'
import { formatDate, formatTiyin } from '@/shared/formatters'
import { clientStatusLabel, useOrdersStore, type OrderSummary } from '@/shared/stores/orders'

const orders = useOrdersStore()
const rolePath = useRolePath()
const status = ref('all')
const search = ref('')

const statusOptions = [
  { value: 'all', label: 'All', meta: 'all orders' },
  { value: 'active', label: 'Active', meta: 'open production' },
  { value: 'completed', label: 'Completed', meta: 'collected' },
  { value: 'cancelled', label: 'Cancelled', meta: 'stopped' },
]

const filtered = computed(() => orders.clientOrders)

let timer: number | undefined
watch([status, search], () => {
  window.clearTimeout(timer)
  timer = window.setTimeout(() => {
    void orders.loadClientOrders({ status: status.value, search: search.value })
  }, 250)
})

function statusClass(order: OrderSummary) {
  if (order.status === 'completed') return 'bg-success-soft text-success'
  if (order.status === 'cancelled') return 'bg-danger-soft text-danger'
  if (order.status === 'ready') return 'bg-info-soft text-info'
  return 'bg-warning-soft text-warning'
}

onMounted(() => {
  void orders.loadClientOrders()
})
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold text-ink">My orders</h1>
        <p class="mt-2 max-w-2xl text-base text-ink-soft">
          Track active orders and review completed pickups.
        </p>
      </div>
      <RouterLink :to="rolePath('/c/cutting/drafts')" class="mp-button mp-button-primary">
        New cutting
      </RouterLink>
    </div>

    <section class="mp-surface p-4">
      <div class="grid gap-3 md:grid-cols-[220px_1fr]">
        <FormSelect v-model="status" label="Status" :options="statusOptions" />
        <label class="grid gap-1 text-sm font-bold text-ink">
          Search
          <input v-model="search" class="mp-input" placeholder="Order number" />
        </label>
      </div>
    </section>

    <section class="mp-surface overflow-hidden">
      <div v-if="orders.loading" class="space-y-3 p-5" aria-live="polite">
        <div class="h-16 animate-pulse rounded bg-sunk"></div>
        <div class="h-16 animate-pulse rounded bg-sunk"></div>
      </div>
      <div v-else-if="orders.error" class="p-5">
        <div class="rounded-md bg-danger-soft p-4 text-danger">
          <div class="font-extrabold">Orders could not be loaded</div>
          <p class="mt-1 text-sm">trace {{ orders.traceId ?? 'unavailable' }}</p>
        </div>
      </div>
      <div
        v-else-if="filtered.length === 0"
        class="rounded-lg border border-dashed border-hairline-strong bg-sunk p-6"
      >
        <h2 class="font-serif text-2xl font-semibold text-ink">No orders</h2>
        <p class="mt-2 text-sm text-ink-soft">Start from a cutting when you are ready.</p>
      </div>
      <div v-else class="divide-y divide-hairline">
        <article
          v-for="order in filtered"
          :key="order.id"
          class="grid gap-4 p-5 md:grid-cols-[1fr_auto]"
        >
          <div>
            <div class="flex flex-wrap items-center gap-2">
              <h2 class="font-mono text-base font-extrabold text-ink">
                {{ order.order_number }}
              </h2>
              <span class="mp-chip" :class="statusClass(order)">
                <span class="mp-dot" aria-hidden="true"></span>
                {{ clientStatusLabel[order.status] }}
              </span>
            </div>
            <p class="mt-2 text-sm text-ink-soft">
              {{ order.branch_name }} · {{ formatDate(order.created_at) }} ·
              {{ order.item_count }} parts
            </p>
            <p class="mt-2 font-mono text-sm font-bold text-ink">
              {{ formatTiyin(order.total_tiyin) }} frozen total
            </p>
          </div>
          <RouterLink :to="rolePath(`/c/orders/${order.id}`)" class="mp-button mp-button-primary">
            Track
          </RouterLink>
        </article>
      </div>
    </section>
  </section>
</template>
