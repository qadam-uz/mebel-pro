<script setup lang="ts">
// Client home — KPI strip, "New cutting" CTA, active orders with the 5-phase
// stepper, recent drafts. Mirrors prototype client/home.html.
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { ErrorState, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtTiyin } from '@/shared/format'
import * as clientApi from '../api'
import type { Draft, Material, OrderCard } from '../api/types'
import { isActive, phaseIndex, relativeTime, summariseDraft } from '../lib/cutting'
import { useToast } from '@/shared/composables/useToast'

const router = useRouter()
const toast = useToast()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const orders = ref<OrderCard[]>([])
const drafts = ref<Draft[]>([])
const materials = ref<Material[]>([])
const creating = ref(false)

const activeOrders = computed(() => orders.value.filter((o) => isActive(o.status)))
const inProduction = computed(
  () => orders.value.filter((o) => o.status === 'cutting' || o.status === 'edge_banding').length,
)
const ready = computed(() => orders.value.filter((o) => o.status === 'ready').length)

const phaseLabels = computed(() => [
  t('clientPhase.new'),
  t('clientPhase.confirmed'),
  t('clientPhase.cutting'),
  t('clientPhase.ready'),
])

async function load() {
  loading.value = true
  error.value = null
  try {
    const [orderList, draftList, mats] = await Promise.all([
      clientApi.listOrders('all'),
      clientApi.listDrafts(),
      clientApi.listMaterials(),
    ])
    orders.value = orderList.orders
    // unbound drafts only (chosen drafts that became orders are filtered server-side)
    drafts.value = draftList
    materials.value = mats
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

async function newCutting() {
  if (creating.value) return
  creating.value = true
  try {
    const draft = await clientApi.createDraft()
    router.push(`/c/cutting/${draft.id}`)
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    creating.value = false
  }
}

function draftLabel(d: Draft) {
  return summariseDraft(d, materials.value, null)
}

onMounted(load)
</script>

<template>
  <div>
    <!-- KPI strip -->
    <div v-if="loading" class="kpis">
      <div v-for="n in 4" :key="n" class="kpi">
        <div class="sk sk-line" style="width: 40px; height: 24px" />
        <div class="sk sk-line" style="width: 70%; margin-top: 10px" />
      </div>
    </div>
    <div v-else class="kpis">
      <RouterLink class="kpi" to="/c/orders">
        <div class="v">
          {{ activeOrders.length }}<small>{{ t('client.countUnit') }}</small>
        </div>
        <div class="lbl">{{ t('client.kpiActive') }}</div>
      </RouterLink>
      <RouterLink class="kpi" to="/c/orders">
        <div class="v">
          {{ inProduction }}<small>{{ t('client.countUnit') }}</small>
        </div>
        <div class="lbl">{{ t('client.kpiProduction') }}</div>
      </RouterLink>
      <RouterLink class="kpi" :class="{ warn: ready > 0 }" to="/c/orders">
        <div class="v">
          {{ ready }}<small>{{ t('client.countUnit') }}</small>
        </div>
        <div class="lbl">{{ t('client.kpiReady') }}</div>
      </RouterLink>
      <RouterLink class="kpi" to="/c/cutting/drafts">
        <div class="v">
          {{ drafts.length }}<small>{{ t('client.countUnit') }}</small>
        </div>
        <div class="lbl">{{ t('client.kpiDrafts') }}</div>
      </RouterLink>
    </div>

    <!-- New cutting CTA -->
    <div class="new-cta">
      <div>
        <div class="t">{{ t('client.newCuttingTitle') }}</div>
        <div class="s">{{ t('client.newCuttingSub') }}</div>
      </div>
      <button class="btn" type="button" :disabled="creating" @click="newCutting">
        {{ t('client.newCutting') }}
      </button>
    </div>

    <ErrorState v-if="error" :error="error" :retry="load" />

    <template v-else>
      <!-- Active orders -->
      <div class="sec-hd">
        <h2>{{ t('client.activeOrders') }}</h2>
        <RouterLink to="/c/orders">{{ t('client.allOrders') }}</RouterLink>
      </div>

      <div v-if="loading">
        <div v-for="n in 2" :key="n" class="ao">
          <div class="sk sk-line" style="width: 30%" />
          <div class="sk sk-line" style="width: 55%; margin-top: 10px; height: 18px" />
          <div class="sk sk-line" style="width: 100%; margin-top: 18px; height: 32px" />
        </div>
      </div>
      <div v-else-if="activeOrders.length === 0" class="st-empty">
        <div class="ic">∅</div>
        <h3>{{ t('client.noActiveOrders') }}</h3>
        <p>{{ t('client.noActiveOrdersBody') }}</p>
        <button class="btn btn-acc" type="button" :disabled="creating" @click="newCutting">
          {{ t('client.newCutting') }}
        </button>
      </div>
      <article
        v-for="o in activeOrders"
        v-else
        :key="o.id"
        class="ao"
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
        <div class="step">
          <template v-for="(lb, i) in phaseLabels" :key="lb">
            <div
              class="node"
              :class="{
                done: i < phaseIndex(o.status),
                cur: i === phaseIndex(o.status),
              }"
            >
              <span class="dot" />
              <span class="cap">{{ lb }}</span>
            </div>
            <span
              v-if="i < phaseLabels.length - 1"
              class="bar"
              :class="{ done: i < phaseIndex(o.status) }"
            />
          </template>
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

      <!-- Recent drafts -->
      <div class="sec-hd">
        <h2>{{ t('client.recentDrafts') }}</h2>
        <RouterLink to="/c/cutting/drafts">{{ t('client.allDrafts') }}</RouterLink>
      </div>

      <div v-if="loading">
        <div v-for="n in 2" :key="n" class="dr">
          <div>
            <div class="sk sk-line" style="width: 50%" />
            <div class="sk sk-line" style="width: 70%; margin-top: 8px" />
          </div>
        </div>
      </div>
      <div v-else-if="drafts.length === 0" class="st-empty">
        <div class="ic">∅</div>
        <h3>{{ t('client.noDrafts') }}</h3>
        <p>{{ t('client.noDraftsBody') }}</p>
        <button class="btn btn-acc" type="button" :disabled="creating" @click="newCutting">
          {{ t('client.newCutting') }}
        </button>
      </div>
      <article
        v-for="d in drafts.slice(0, 3)"
        v-else
        :key="d.id"
        class="dr"
        @click="router.push(`/c/cutting/${d.id}`)"
      >
        <div>
          <div class="nm">{{ draftLabel(d).dominantLabel || t('client.noMaterial') }}</div>
          <div class="st">
            <span
              ><b>{{ draftLabel(d).totalParts }}</b> {{ t('client.partsUnit') }}</span
            >
            <span style="color: var(--ink-6)">{{ relativeTime(d.updated_at) }}</span>
          </div>
        </div>
        <span class="open-aff">
          {{ t('client.open') }}
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M9 6l6 6-6 6" />
          </svg>
        </span>
      </article>
    </template>
  </div>
</template>

<style scoped>
.kpi {
  text-decoration: none;
}
.kpi .v {
  font-family: var(--f-mono);
  font-size: 24px;
  font-weight: 700;
  color: var(--ink-12);
  line-height: 1;
}
.kpi .v small {
  font: 600 12px var(--f-ui);
  color: var(--ink-6);
  margin-left: 2px;
}
.kpi .lbl {
  font: 500 12px var(--f-ui);
  color: var(--ink-7);
  margin-top: 7px;
  text-transform: none;
  letter-spacing: 0;
}
.kpi.warn .v {
  color: var(--accent);
}

.sec-hd {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 0 0 12px;
  border-bottom: 1px solid var(--line);
  margin: 26px 0 16px;
}
.sec-hd h2 {
  font: 600 18px var(--f-display);
  margin: 0;
  color: var(--ink-12);
}
.sec-hd a {
  font: 500 13px var(--f-ui);
  color: var(--ink-8);
  text-decoration: none;
}

.new-cta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  background: var(--ink-12);
  color: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  margin: 28px 0 16px;
}
.new-cta .t {
  font: 600 17px var(--f-display);
}
.new-cta .s {
  font: 400 13px var(--f-ui);
  opacity: 0.8;
  margin-top: 3px;
}
.new-cta .btn {
  background: #fff;
  color: var(--ink-12);
  border: 0;
  font-weight: 600;
}

.ao {
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
.ao:hover {
  border-color: var(--ink-12);
  transform: translateY(-1px);
}
.ao .top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
}
.ao .id {
  font: 500 11.5px var(--f-mono);
  color: var(--ink-6);
  letter-spacing: 0.04em;
}
.ao h3 {
  font: 600 17px var(--f-display);
  margin: 4px 0 0;
  color: var(--ink-12);
}
.ao .meta {
  font: 400 12.5px var(--f-ui);
  color: var(--ink-7);
  margin-top: 3px;
}
.ao .foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}
.ao .total {
  font: 600 14.5px var(--f-mono);
  color: var(--ink-12);
}
.ao .total small {
  font: 500 11px var(--f-ui);
  color: var(--ink-6);
}

.step {
  display: flex;
  align-items: center;
  gap: 0;
  margin: 16px 0 14px;
}
.step .node {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
}
.step .dot {
  width: 13px;
  height: 13px;
  border-radius: 50%;
  border: 2px solid var(--line);
  background: var(--elev);
  box-sizing: border-box;
}
.step .node.done .dot {
  background: var(--ink-12);
  border-color: var(--ink-12);
}
.step .node.cur .dot {
  border-color: var(--ink-12);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--ink-12) 14%, transparent);
}
.step .node .cap {
  font: 500 10.5px var(--f-ui);
  color: var(--ink-6);
  white-space: nowrap;
}
.step .node.done .cap,
.step .node.cur .cap {
  color: var(--ink-12);
  font-weight: 600;
}
.step .bar {
  flex: 1 1 auto;
  height: 2px;
  background: var(--line);
  margin: 0 6px 22px;
}
.step .bar.done {
  background: var(--ink-12);
}

.dr {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: center;
  padding: 14px 16px;
  background: var(--elev);
  border: 1px solid var(--line);
  border-radius: 10px;
  margin-bottom: 10px;
  cursor: pointer;
  transition:
    border-color 0.12s,
    transform 0.12s;
}
.dr:hover {
  border-color: var(--ink-10);
  transform: translateY(-1px);
}
.dr .nm {
  font: 500 14px var(--f-ui);
  color: var(--ink-12);
}
.dr .st {
  font: 400 12px var(--f-mono);
  color: var(--ink-6);
  margin-top: 4px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.dr .st b {
  color: var(--ink-12);
  font-weight: 600;
}
.open-aff {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font: 600 12.5px var(--f-ui);
  color: var(--accent);
  white-space: nowrap;
}
.open-aff svg {
  width: 14px;
  height: 14px;
}

@media (max-width: 720px) {
  .step .node .cap {
    display: none;
  }
  .step .bar {
    margin-bottom: 0;
  }
}
</style>
