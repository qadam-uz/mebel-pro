<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import { formatDate, formatTiyin } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { useOrdersStore, type OrderSummary } from '@/shared/stores/orders'

const auth = useAuthStore()
const rolePath = useRolePath()
const orders = useOrdersStore()
const actionError = ref<string | null>(null)

const queueOrders = computed(() =>
  orders.workshopOrders.filter((order) => {
    if (order.status !== 'edge_banding') return false
    if (!order.assigned_edger_user_id) return false
    if (auth.me?.is_owner) return true
    return order.assigned_edger_user_id === auth.me?.principal_id
  }),
)

async function refresh() {
  await orders.loadWorkshopOrders({ status: 'edge_banding' })
}

async function complete(order: OrderSummary) {
  actionError.value = null
  try {
    await orders.bandingDone(order.id, {
      version: order.version,
      completed_by_user_id: order.assigned_edger_user_id,
    })
    await refresh()
  } catch {
    actionError.value = orders.error ?? 'banding_complete_failed'
  }
}

onMounted(refresh)
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold text-ink">Banding queue</h1>
        <p class="mt-2 max-w-2xl text-base text-ink-soft">
          Edge-banding work assigned to the current bander.
        </p>
      </div>
      <RouterLink :to="rolePath('/workshop/orders')" class="mp-button mp-button-outline">
        Orders
      </RouterLink>
    </div>

    <section v-if="orders.loading" class="mp-surface p-5" aria-live="polite">
      Loading banding queue
    </section>
    <section v-else-if="orders.error" class="mp-surface p-5 text-danger">
      Banding queue could not be loaded. trace {{ orders.traceId ?? 'unavailable' }}
    </section>
    <section v-else-if="queueOrders.length === 0" class="mp-surface p-5">
      <div class="rounded-lg border border-dashed border-hairline-strong bg-sunk p-6">
        <h2 class="font-serif text-2xl font-semibold text-ink">No assigned banding jobs</h2>
        <p class="mt-2 text-sm text-ink-soft">Orders enter this queue after cutting is done.</p>
      </div>
    </section>

    <template v-else>
      <p v-if="actionError" class="rounded-md bg-danger-soft p-3 text-sm text-danger">
        {{ actionError }} · trace {{ orders.traceId ?? 'unavailable' }}
      </p>

      <section class="mp-surface overflow-hidden">
        <div class="border-b border-hairline px-5 py-4">
          <h2 class="font-serif text-xl font-semibold text-ink">Edge banding</h2>
        </div>
        <div class="divide-y divide-hairline">
          <article v-for="order in queueOrders" :key="order.id" class="px-5 py-4">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div class="font-mono text-sm font-extrabold text-ink">
                  {{ order.order_number }}
                </div>
                <p class="mt-1 text-sm text-ink-soft">
                  {{ order.contact_name }} · {{ order.item_count }} parts ·
                  {{ formatDate(order.created_at) }}
                </p>
                <p class="mt-2 font-mono text-sm font-bold text-accent">
                  {{ formatTiyin(order.total_tiyin) }}
                </p>
              </div>
              <span class="mp-chip bg-accent-soft text-accent">
                <span class="mp-dot" aria-hidden="true"></span>
                Assigned
              </span>
            </div>
            <div class="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                class="mp-button mp-button-primary"
                :disabled="orders.actionLoading"
                @click="complete(order)"
              >
                Mark banding done
              </button>
              <button
                type="button"
                class="mp-button mp-button-outline"
                @click="orders.downloadWorkshopPdf(order.id)"
              >
                PDF
              </button>
              <RouterLink
                :to="rolePath(`/workshop/orders/${order.id}`)"
                class="mp-button mp-button-outline"
              >
                Detail
              </RouterLink>
            </div>
          </article>
        </div>
      </section>
    </template>
  </section>
</template>
