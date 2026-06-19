<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import { formatDate, formatStockQuantity, formatTiyin } from '@/shared/formatters'
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
    actionError.value = orders.actionError ?? 'banding_complete_failed'
  }
}

function edgeLine(order: OrderSummary) {
  const entries = Object.entries(order.edge_length_snapshot ?? {})
  if (entries.length === 0) return 'krom rejasi'
  return entries.map(([key, value]) => `${key}: ${formatStockQuantity(value, 'm')}`).join(' · ')
}

onMounted(refresh)
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Krom yopishtirish navbati</h1>
        <p class="sub">Sizga tayinlangan, krom yopishtirilishi kerak bo'lgan buyurtmalar.</p>
      </div>
      <div class="tools">
        <RouterLink
          :to="rolePath('/workshop/orders')"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
        >
          Buyurtmalar
        </RouterLink>
      </div>
    </div>

    <section v-if="orders.loading" class="card p-5" aria-live="polite">
      <div class="grid gap-3">
        <span class="sk-line"></span>
        <span class="sk-line"></span>
        <span class="sk-line"></span>
      </div>
    </section>

    <section v-else-if="orders.error" class="st-error">
      <h3>Krom navbatini yuklab bo'lmadi</h3>
      <p>trace_id: {{ orders.traceId ?? 'unavailable' }}</p>
    </section>

    <section v-else-if="queueOrders.length === 0" class="st-empty">
      <h3>Sizga tayinlangan krom ishi yo'q</h3>
      <p>Kesish tugagan va sizga biriktirilgan buyurtmalar shu yerda paydo bo'ladi.</p>
    </section>

    <template v-else>
      <div v-if="actionError" class="banner danger">
        <div class="grow">
          {{ actionError }} · trace {{ orders.actionTraceId ?? 'unavailable' }}
        </div>
      </div>

      <div class="queue-grid">
        <section class="queue-col">
          <h2>
            Krom kutmoqda
            <span class="ct">{{ queueOrders.length }}</span>
          </h2>
          <article v-for="order in queueOrders" :key="order.id" class="q-card">
            <div class="top">
              <div>
                <h4>{{ order.order_number }}</h4>
                <div class="meta">
                  {{ order.contact_name }} · <b>{{ edgeLine(order) }}</b> ·
                  {{ formatDate(order.created_at) }} · {{ formatTiyin(order.total_tiyin) }}
                </div>
              </div>
              <span class="assigned-tag">Sizga</span>
            </div>
            <div class="act">
              <button
                type="button"
                class="mp-button mp-button-primary min-h-9 px-3 text-xs"
                :disabled="orders.actionLoading"
                @click="complete(order)"
              >
                Krom tugadi
              </button>
              <RouterLink
                :to="rolePath(`/workshop/orders/${order.id}`)"
                class="mp-button mp-button-outline min-h-9 px-3 text-xs"
              >
                Tafsilotlar
              </RouterLink>
              <button
                type="button"
                class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                @click="orders.downloadWorkshopPdf(order.id)"
              >
                PDF
              </button>
            </div>
          </article>
        </section>
      </div>
    </template>
  </section>
</template>
