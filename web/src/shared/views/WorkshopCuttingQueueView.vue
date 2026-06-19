<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import { orderPillClass, workshopStatusUz } from '@/shared/app/workshopUi'
import { formatDate, formatTiyin } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { useOrdersStore, type OrderSummary } from '@/shared/stores/orders'

const auth = useAuthStore()
const rolePath = useRolePath()
const orders = useOrdersStore()
const actionError = ref<string | null>(null)

const queueOrders = computed(() =>
  orders.workshopOrders.filter((order) => {
    if (!['confirmed', 'cutting'].includes(order.status)) return false
    if (!order.assigned_cutter_user_id) return false
    if (auth.me?.is_owner) return true
    return order.assigned_cutter_user_id === auth.me?.principal_id
  }),
)
const awaiting = computed(() => queueOrders.value.filter((order) => order.status === 'confirmed'))
const inProgress = computed(() => queueOrders.value.filter((order) => order.status === 'cutting'))

async function refresh() {
  await orders.loadWorkshopOrders({ status: 'active' })
}

async function complete(order: OrderSummary) {
  actionError.value = null
  try {
    await orders.cuttingDone(order.id, {
      version: order.version,
      completed_by_user_id: order.assigned_cutter_user_id,
    })
    await refresh()
  } catch {
    actionError.value = orders.actionError ?? 'cutting_complete_failed'
  }
}

function partsLine(order: OrderSummary) {
  return `${order.item_count} qism${order.panels_used_snapshot ? ` · ${order.panels_used_snapshot} panel` : ''}`
}

onMounted(refresh)
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Kesish navbati</h1>
        <p class="sub">Sizga tayinlangan buyurtmalar. Boshqaning ishi bu yerda ko'rinmaydi.</p>
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
      <h3>Kesish navbatini yuklab bo'lmadi</h3>
      <p>trace_id: {{ orders.traceId ?? 'unavailable' }}</p>
    </section>

    <section v-else-if="queueOrders.length === 0" class="st-empty">
      <h3>Sizga tayinlangan kesish ishi yo'q</h3>
      <p>Tasdiqlangan va sizga biriktirilgan buyurtmalar shu yerda paydo bo'ladi.</p>
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
            Kesishni kutmoqda
            <span class="ct">{{ awaiting.length }}</span>
          </h2>
          <div v-if="awaiting.length === 0" class="st-empty !px-4 !py-8">
            <h3>Hozir kesishni kutayotgan ishingiz yo'q</h3>
          </div>
          <article v-for="order in awaiting" v-else :key="order.id" class="q-card">
            <div class="top">
              <div>
                <h4>{{ order.order_number }}</h4>
                <div class="meta">
                  {{ order.contact_name }} · <b>{{ partsLine(order) }}</b> ·
                  {{ formatDate(order.created_at) }}
                </div>
              </div>
              <span class="assigned-tag">Sizga</span>
            </div>
            <div class="act">
              <RouterLink
                :to="rolePath(`/workshop/orders/${order.id}`)"
                class="mp-button mp-button-primary min-h-9 px-3 text-xs"
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

        <section class="queue-col">
          <h2>
            Kesilmoqda
            <span class="ct">{{ inProgress.length }}</span>
          </h2>
          <div v-if="inProgress.length === 0" class="st-empty !px-4 !py-8">
            <h3>Hozir kesilayotgan ishingiz yo'q</h3>
          </div>
          <article v-for="order in inProgress" v-else :key="order.id" class="q-card">
            <div class="top">
              <div>
                <h4>{{ order.order_number }}</h4>
                <div class="meta">
                  {{ order.contact_name }} · <b>{{ partsLine(order) }}</b> ·
                  {{ formatTiyin(order.total_tiyin) }}
                </div>
              </div>
              <span :class="orderPillClass(order.status)">
                <span class="pd"></span>{{ workshopStatusUz[order.status] }}
              </span>
            </div>
            <div class="act">
              <button
                type="button"
                class="mp-button mp-button-primary min-h-9 px-3 text-xs"
                :disabled="orders.actionLoading"
                @click="complete(order)"
              >
                Kesish tugadi
              </button>
              <RouterLink
                :to="rolePath(`/workshop/orders/${order.id}`)"
                class="mp-button mp-button-outline min-h-9 px-3 text-xs"
              >
                Chizmani ko'rish
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
