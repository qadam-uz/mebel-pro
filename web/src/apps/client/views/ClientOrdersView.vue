<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRouter } from 'vue-router'

import {
  clientErrorLabel,
  clientStatusLabel,
  clientStatusPillClass,
  formatFullDate,
} from '@/shared/app/clientUi'
import { SEARCH_DEBOUNCE_MS } from '@/shared/app/constants'
import { traceSuffix } from '@/shared/app/errorTrace'
import Icon from '@/shared/components/AppIcon.vue'
import ClientErrorState from '@/shared/components/ClientErrorState.vue'
import { useRolePath } from '@/shared/app/paths'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import { formatOrderNumber, formatTiyin } from '@/shared/formatters'
import { useOrdersStore, type OrderSummary } from '@/shared/stores/orders'

const { t } = useI18n()
const orders = useOrdersStore()
const rolePath = useRolePath()
const router = useRouter()
const status = ref('all')
const search = ref('')
const orderPendingCancel = ref<OrderSummary | null>(null)
const cancelReason = ref(t('client.orders.cancelReasonDefault'))
const actionError = ref<string | null>(null)

// Computed, not a plain array: the option labels are copy and must follow a
// language switch made while the page is open.
const statusOptions = computed(() => [
  { value: 'all', label: t('client.orders.statusAll'), meta: t('client.orders.statusAllMeta') },
  {
    value: 'active',
    label: t('client.orders.statusActive'),
    meta: t('client.orders.statusActiveMeta'),
  },
  {
    value: 'completed',
    label: t('client.orders.statusCompleted'),
    meta: t('client.orders.statusCompletedMeta'),
  },
  {
    value: 'cancelled',
    label: t('client.orders.statusCancelled'),
    meta: t('client.orders.statusCancelledMeta'),
  },
])

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
  if (order.status === 'new') return t('client.common.cancel')
  if (order.status === 'ready') return t('client.common.readyForPickup')
  if (order.status === 'completed') return t('client.common.detail')
  return t('client.common.track')
}

function openOrder(order: OrderSummary) {
  void router.push(rolePath(`/c/orders/${order.id}`))
}

function requestCancel(order: OrderSummary) {
  cancelReason.value = t('client.orders.cancelReasonDefault')
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
        <h1>{{ $t('client.orders.title') }}</h1>
      </div>
      <!-- The onboarding empty state carries a centred CTA, so this would be
           redundant there; it shows once the user has orders (or has merely
           filtered them away). -->
      <RouterLink
        v-if="!isTrueEmpty"
        :to="rolePath('/c/cutting/drafts')"
        class="mp-button mp-button-primary"
      >
        {{ $t('client.common.newOrder') }}
      </RouterLink>
    </div>

    <div class="mb-5 grid gap-3 md:grid-cols-[220px_minmax(0,1fr)]">
      <FormSelect v-model="status" :label="$t('client.common.status')" :options="statusOptions" />
      <label class="grid gap-1 text-sm font-bold text-ink">
        {{ $t('client.common.search') }}
        <!-- Names both fields the search reaches rather than showing one sample
             number: the drawing name is the card's headline, and an example of
             only one of the two accepted inputs hides the other. -->
        <input
          v-model="search"
          class="mp-input"
          :placeholder="$t('client.orders.searchPlaceholder')"
        />
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
      :title="$t('client.orders.loadFailed')"
      :trace-id="orders.traceId"
      @retry="reloadOrders"
    />

    <div v-else-if="visibleOrders.length === 0" class="client-empty">
      <div class="client-empty-icon"><Icon name="box" /></div>
      <h3>{{ $t('client.orders.emptyTitle') }}</h3>
      <template v-if="noFilter">
        <p>{{ $t('client.orders.emptyBody') }}</p>
        <RouterLink :to="rolePath('/c/cutting/drafts')" class="mp-button mp-button-primary mt-4">
          {{ $t('client.common.newOrder') }}
        </RouterLink>
      </template>
      <template v-else>
        <p>{{ $t('client.orders.emptyFilteredBody') }}</p>
        <button type="button" class="mp-button mp-button-outline mt-4" @click="clearFilters">
          {{ $t('client.orders.clearFilters') }}
        </button>
      </template>
    </div>

    <div v-else class="grid gap-3">
      <article
        v-for="order in visibleOrders"
        :key="order.id"
        class="client-card client-card-link p-5 focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
        role="link"
        tabindex="0"
        :aria-label="`${formatOrderNumber(order.order_number)} — ${order.branch_name}`"
        @click="openOrder(order)"
        @keydown.enter="openOrder(order)"
      >
        <!-- The drawing's name leads because it is the only field that differs
             from card to card: a client usually orders from one branch, so the
             branch name was the largest type on every card and identical on all
             of them. It stays, demoted to the identifier line. -->
        <div class="mb-4 flex items-start justify-between gap-4">
          <div class="min-w-0">
            <!-- Weight + ink against the soft sans rest of the line, no chip: the
                 status pill already occupies this row on the right, and a second
                 boxed element would read as a second status. -->
            <p class="truncate text-sm text-ink-soft">
              <span class="text-[15px] font-bold text-ink">{{
                formatOrderNumber(order.order_number)
              }}</span>
              · {{ order.workshop_name }} · {{ order.branch_name }}
            </p>
            <div class="mt-1 flex flex-wrap items-center gap-2">
              <h2
                class="font-display text-lg font-semibold"
                :class="order.draft_name ? 'text-ink' : 'text-ink-muted'"
              >
                {{ order.draft_name || $t('client.draft.untitled') }}
              </h2>
              <!-- Staff-minted drawings stay hidden from the client's own list
                   until the order exists, so this is the first time they see it. -->
              <span v-if="order.created_via_workshop" class="client-pill client-pill-info">
                {{ $t('client.orders.createdByWorkshop') }}
              </span>
            </div>
            <p class="mt-1 text-sm text-ink-soft">
              <b class="font-semibold text-ink">{{ order.item_count }}</b>
              {{ $t('client.unit.part', order.item_count) }} ·
              <b class="font-semibold text-ink">{{ order.planned_panels || '—' }}</b>
              {{ $t('client.unit.sheet', order.planned_panels) }} ·
              <span>{{ formatFullDate(order.created_at) }}</span>
            </p>
          </div>
          <span :class="clientStatusPillClass(order.status)">
            {{ clientStatusLabel(order.status) }}
          </span>
        </div>

        <div
          class="flex flex-wrap items-center justify-between gap-3 border-t border-hairline pt-4"
        >
          <div class="text-base font-bold text-ink">
            {{ formatTiyin(order.total_tiyin) }}
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
        {{ $t('client.orders.loadMore') }}
      </button>
    </div>

    <ConfirmDialog
      :open="Boolean(orderPendingCancel)"
      :title="$t('client.orders.cancelTitle')"
      :message="$t('client.orders.cancelMessage')"
      :confirm-label="$t('client.common.cancel')"
      :cancel-label="$t('client.common.back')"
      :busy-label="$t('client.common.busy')"
      danger
      :busy="orders.actionLoading"
      :confirm-disabled="cancelReason.trim().length === 0"
      @cancel="orderPendingCancel = null"
      @confirm="confirmCancel"
    >
      <label class="grid gap-1 text-sm font-bold text-ink">
        {{ $t('client.common.reason') }}
        <textarea v-model="cancelReason" class="mp-input min-h-24 resize-y" />
      </label>
      <p v-if="actionError" class="mt-3 text-sm font-bold text-danger">
        {{ clientErrorLabel(actionError) }}{{ traceSuffix(orders.actionTraceId) }}
      </p>
    </ConfirmDialog>
  </section>
</template>
