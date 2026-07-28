<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import {
  clientErrorLabel,
  clientStatusLabel,
  clientStatusPillClass,
  formatRelativeDate,
} from '@/shared/app/clientUi'
import { SEARCH_DEBOUNCE_MS } from '@/shared/app/constants'
import { traceSuffix } from '@/shared/app/errorTrace'
import Icon from '@/shared/components/AppIcon.vue'
import ClientErrorState from '@/shared/components/ClientErrorState.vue'
import { useRolePath } from '@/shared/app/paths'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import { formatTiyin } from '@/shared/formatters'
import { useOrdersStore, type OrderSummary } from '@/shared/stores/orders'

const orders = useOrdersStore()
const rolePath = useRolePath()
const router = useRouter()
const status = ref('all')
const search = ref('')
const orderPendingCancel = ref<OrderSummary | null>(null)
const cancelReason = ref('Mijoz buyurtmani tasdiqlashdan oldin bekor qildi')
const actionError = ref<string | null>(null)

const statusOptions = [
  { value: 'all', label: 'Hammasi', meta: 'barcha buyurtmalar' },
  { value: 'active', label: 'Faol', meta: 'ish jarayonida' },
  { value: 'completed', label: 'Tugatilgan', meta: 'topshirilgan' },
  { value: 'cancelled', label: 'Bekor qilingan', meta: "to'xtatilgan" },
]

const visibleOrders = computed(() => orders.clientOrders)

// "True empty" = no orders at all, not merely filtered away. Drives the header
// CTA: hide it in the onboarding empty state (the centred CTA covers it), but
// keep it when the user has orders or just filtered them out.
const noFilter = computed(() => status.value === 'all' && !search.value)
const isTrueEmpty = computed(
  () => !orders.loading && !orders.error && visibleOrders.value.length === 0 && noFilter.value,
)

function clearFilters() {
  status.value = 'all'
  search.value = ''
}

function reloadOrders() {
  void orders.loadClientOrders({ status: status.value, search: search.value })
}

function loadMoreOrders() {
  void orders.loadClientOrders({
    status: status.value,
    search: search.value,
    offset: orders.clientOrders.length,
  })
}

let timer: number | undefined
watch([status, search], () => {
  window.clearTimeout(timer)
  timer = window.setTimeout(reloadOrders, SEARCH_DEBOUNCE_MS)
})

function nextAction(order: OrderSummary) {
  if (order.status === 'new') return 'Bekor qilish'
  if (order.status === 'ready') return 'Olishga tayyor'
  if (order.status === 'completed') return 'Tafsilot'
  return 'Kuzatish'
}

function openOrder(order: OrderSummary) {
  void router.push(rolePath(`/c/orders/${order.id}`))
}

function requestCancel(order: OrderSummary) {
  cancelReason.value = 'Mijoz buyurtmani tasdiqlashdan oldin bekor qildi'
  actionError.value = null
  orderPendingCancel.value = order
}

async function confirmCancel() {
  const order = orderPendingCancel.value
  if (!order) return
  actionError.value = null
  try {
    await orders.cancelClientOrder(order.id, order.version, cancelReason.value.trim())
    orderPendingCancel.value = null
    actionError.value = null
    await orders.loadClientOrders({ status: status.value, search: search.value })
  } catch {
    actionError.value = orders.actionError ?? 'order_cancel_failed'
  }
}

onMounted(() => {
  void orders.loadClientOrders()
})
</script>

<template>
  <section>
    <div class="client-page-head">
      <div>
        <h1>Mening buyurtmalarim</h1>
        <p class="sub">Faol va tugatilgan buyurtmalaringiz.</p>
      </div>
      <!-- The onboarding empty state carries a centred CTA, so this would be
           redundant there; it shows once the user has orders (or has merely
           filtered them away). -->
      <RouterLink
        v-if="!isTrueEmpty"
        :to="rolePath('/c/cutting/drafts')"
        class="mp-button mp-button-primary"
      >
        + Yangi buyurtma
      </RouterLink>
    </div>

    <div class="mb-5 grid gap-3 md:grid-cols-[220px_minmax(0,1fr)]">
      <FormSelect v-model="status" label="Holat" :options="statusOptions" />
      <label class="grid gap-1 text-sm font-bold text-ink">
        Qidirish
        <input v-model="search" class="mp-input" placeholder="#26-14-0003" />
      </label>
    </div>

    <div v-if="orders.loading" class="grid gap-3" aria-live="polite">
      <div v-for="item in 4" :key="item" class="client-card p-5">
        <div class="client-skeleton h-4 w-1/3"></div>
        <div class="client-skeleton mt-3 h-5 w-1/2"></div>
        <div class="client-skeleton mt-5 h-4 w-2/5"></div>
      </div>
    </div>

    <ClientErrorState
      v-else-if="orders.error"
      title="Buyurtmalarni yuklab bo'lmadi"
      :trace-id="orders.traceId"
      @retry="reloadOrders"
    />

    <div v-else-if="visibleOrders.length === 0" class="client-empty">
      <div class="client-empty-icon"><Icon name="box" /></div>
      <h3>Buyurtma yo'q</h3>
      <template v-if="noFilter">
        <p>Hali buyurtma bermagansiz — chizmadan boshlang.</p>
        <RouterLink :to="rolePath('/c/cutting/drafts')" class="mp-button mp-button-primary mt-4">
          + Yangi buyurtma
        </RouterLink>
      </template>
      <template v-else>
        <p>Bu so'rovga mos buyurtma topilmadi.</p>
        <button type="button" class="mp-button mp-button-outline mt-4" @click="clearFilters">
          Filtrlarni tozalash
        </button>
      </template>
    </div>

    <div v-else class="grid gap-3">
      <article
        v-for="order in visibleOrders"
        :key="order.id"
        class="client-card client-card-link p-5 focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-tint"
        role="link"
        tabindex="0"
        :aria-label="`${order.order_number} — ${order.branch_name}`"
        @click="openOrder(order)"
        @keydown.enter="openOrder(order)"
      >
        <div class="mb-4 flex items-start justify-between gap-4">
          <div class="min-w-0">
            <span
              class="inline-block rounded-md bg-sunk px-2 py-0.5 font-mono text-[11px] uppercase tracking-wide text-ink-soft"
            >
              {{ order.order_number }}
            </span>
            <h2 class="mb-1 mt-2 font-serif text-xl font-semibold text-ink">
              {{ order.branch_name }}
            </h2>
            <p class="text-sm text-ink-soft">
              {{ order.workshop_name }} · {{ formatRelativeDate(order.created_at) }} ·
              <b class="font-semibold text-ink">{{ order.item_count }} detal</b>
            </p>
          </div>
          <span :class="clientStatusPillClass(order.status)">
            {{ clientStatusLabel[order.status] }}
          </span>
        </div>

        <div
          class="flex flex-wrap items-center justify-between gap-3 border-t border-hairline pt-4"
        >
          <div class="font-mono text-base font-bold text-ink">
            {{ formatTiyin(order.total_tiyin) }}
            <small class="font-sans text-xs font-medium text-ink-muted">jami narx</small>
          </div>
          <button
            v-if="order.status === 'new'"
            type="button"
            class="mp-button mp-button-outline min-h-8 px-3 text-xs text-danger"
            @click.stop="requestCancel(order)"
          >
            {{ nextAction(order) }}
          </button>
          <RouterLink
            v-else
            :to="rolePath(`/c/orders/${order.id}`)"
            class="mp-button min-h-8 px-3 text-xs"
            :class="order.status === 'completed' ? 'mp-button-outline' : 'mp-button-primary'"
            @click.stop
          >
            {{ nextAction(order) }}
          </RouterLink>
        </div>
      </article>

      <button
        v-if="orders.ordersHasMore"
        type="button"
        class="mp-button mp-button-outline w-full"
        :disabled="orders.loading"
        @click="loadMoreOrders"
      >
        Yana ko'rsatish
      </button>
    </div>

    <ConfirmDialog
      :open="Boolean(orderPendingCancel)"
      title="Buyurtmani bekor qilish"
      message="Buyurtma bekor qilinadi. Bu amal qaytarilmaydi."
      confirm-label="Bekor qilish"
      cancel-label="Orqaga"
      busy-label="Bajarilmoqda"
      danger
      :busy="orders.actionLoading"
      :confirm-disabled="cancelReason.trim().length === 0"
      @cancel="orderPendingCancel = null"
      @confirm="confirmCancel"
    >
      <label class="grid gap-1 text-sm font-bold text-ink">
        Sabab
        <textarea v-model="cancelReason" class="mp-input min-h-24 resize-y" />
      </label>
      <p v-if="actionError" class="mt-3 text-sm font-bold text-danger">
        {{ clientErrorLabel(actionError) }}{{ traceSuffix(orders.actionTraceId) }}
      </p>
    </ConfirmDialog>
  </section>
</template>
