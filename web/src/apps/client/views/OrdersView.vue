<script setup lang="ts">
// My orders — filter chips + number search + cards. Mirrors prototype orders.html.
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { ErrorState, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtTiyin } from '@/shared/format'
import * as clientApi from '../api'
import type { OrderCard, OrderScope } from '../api/types'
import { relativeTime } from '../lib/cutting'

const router = useRouter()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const orders = ref<OrderCard[]>([])
const scope = ref<OrderScope>('all')
const search = ref('')

const FILTERS: { id: OrderScope; key: string }[] = [
  { id: 'all', key: 'client.filterAll' },
  { id: 'active', key: 'client.filterActive' },
  { id: 'completed', key: 'client.filterCompleted' },
  { id: 'cancelled', key: 'client.filterCancelled' },
]

let searchTimer: ReturnType<typeof setTimeout> | null = null

async function load() {
  loading.value = true
  error.value = null
  try {
    const list = await clientApi.listOrders(scope.value, search.value.trim() || undefined)
    orders.value = list.orders
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

function setScope(s: OrderScope) {
  scope.value = s
}

watch(scope, load)
watch(search, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(load, 350)
})

const emptyBody = computed(() =>
  scope.value === 'all' && !search.value.trim()
    ? t('client.noOrdersBody')
    : t('client.noOrdersFiltered'),
)

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>{{ t('client.ordersTitle') }}</h1>
        <p class="sub">{{ t('client.ordersSub') }}</p>
      </div>
      <div class="tools">
        <RouterLink class="btn btn-acc" to="/c/cutting/drafts">{{
          t('client.newCutting')
        }}</RouterLink>
      </div>
    </div>

    <div class="filters">
      <div class="chips">
        <button
          v-for="f in FILTERS"
          :key="f.id"
          class="chip"
          :class="{ on: scope === f.id }"
          type="button"
          @click="setScope(f.id)"
        >
          {{ t(f.key) }}
        </button>
      </div>
      <div class="input">
        <input v-model="search" :placeholder="t('client.searchOrderNumber')" />
      </div>
    </div>

    <div v-if="loading">
      <div v-for="n in 4" :key="n" class="ord-card">
        <div class="sk sk-line" style="width: 30%" />
        <div class="sk sk-line" style="width: 55%; margin-top: 10px; height: 18px" />
        <div class="sk sk-line" style="width: 38%; margin-top: 18px" />
      </div>
    </div>

    <ErrorState v-else-if="error" :error="error" :retry="load" />

    <div v-else-if="orders.length === 0" class="st-empty">
      <div class="ic">∅</div>
      <h3>{{ t('client.noOrders') }}</h3>
      <p>{{ emptyBody }}</p>
      <RouterLink class="btn btn-acc" to="/c/cutting/drafts">{{
        t('client.newCutting')
      }}</RouterLink>
    </div>

    <article
      v-for="o in orders"
      v-else
      :key="o.id"
      class="ord-card"
      @click="router.push(`/c/orders/${o.id}`)"
    >
      <div class="top">
        <div>
          <div class="id">{{ o.order_number }}</div>
          <h3>{{ o.item_count }} {{ t('client.itemsUnit') }}</h3>
          <div class="meta">{{ relativeTime(o.created_at) }}</div>
        </div>
        <StatusBadge :state="o.status" client-phase />
      </div>
      <div class="foot">
        <div class="total">
          {{ fmtTiyin(o.total_tiyin) }} <small>{{ t('client.totalPrice') }}</small>
        </div>
        <button
          class="btn btn-acc btn-sm"
          type="button"
          @click.stop="router.push(`/c/orders/${o.id}`)"
        >
          {{ o.status === 'ready' ? t('client.readyToPickup') : t('client.track') }}
        </button>
      </div>
    </article>
  </div>
</template>

<style scoped>
.ord-card {
  background: var(--elev);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 18px 20px;
  margin-bottom: 12px;
  cursor: pointer;
  transition:
    border-color 0.12s,
    transform 0.12s;
}
.ord-card:hover {
  border-color: var(--ink-12);
  transform: translateY(-1px);
}
.ord-card .top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
}
.ord-card .id {
  font: 500 11.5px var(--f-mono);
  color: var(--ink-6);
  letter-spacing: 0.04em;
}
.ord-card h3 {
  font: 600 17px var(--f-display);
  margin: 4px 0 0;
  color: var(--ink-12);
}
.ord-card .meta {
  font: 400 12.5px var(--f-ui);
  color: var(--ink-7);
  margin-top: 3px;
}
.ord-card .foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-top: 14px;
  margin-top: 14px;
  border-top: 1px solid var(--line);
}
.ord-card .total {
  font: 600 14.5px var(--f-mono);
  color: var(--ink-12);
}
.ord-card .total small {
  font: 500 11px var(--f-ui);
  color: var(--ink-6);
}
.filters .input input {
  background: var(--elev);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 9px 14px;
  font-size: 14px;
  outline: 0;
}
.filters .input input:focus {
  border-color: var(--ink-12);
}
</style>
