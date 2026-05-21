<script setup lang="ts">
// Order detail at /c/orders/:id — header (number, 5-phase status), tabs
// (Overview / Cutting / Finance[gated] / Timeline), cancel while new.
// Mirrors prototype client/order-detail.html.
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { AppTabs, ErrorState, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtDateTime, fmtTiyin } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import * as clientApi from '../api'
import type { OrderDetail, OrderStatus } from '../api/types'
import { financeOpen as financeOpenFor } from '../lib/cutting'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const route = useRoute()
const router = useRouter()
const toast = useToast()

const orderId = computed(() => String(route.params.id))
const justPlaced = computed(() => route.query.placed === '1')

const loading = ref(true)
const error = ref<ApiError | null>(null)
const notFound = ref(false)
const order = ref<OrderDetail | null>(null)
const activeTab = ref('overview')
const cancelOpen = ref(false)

const tabs = computed(() => [
  { id: 'overview', label: t('client.tabOverview') },
  { id: 'cutting', label: t('client.tabCutting') },
  { id: 'finance', label: t('client.tabFinance') },
  { id: 'timeline', label: t('client.tabTimeline') },
])

const phaseLabels = computed(() => [
  t('clientPhase.new'),
  t('clientPhase.confirmed'),
  t('clientPhase.cutting'),
  t('clientPhase.ready'),
  t('clientPhase.completed'),
])

const finOpen = computed(() => (order.value ? financeOpenFor(order.value.status) : false))
const banded = computed(() =>
  (order.value?.items ?? []).some(
    (i) => i.edge_top_mm || i.edge_bottom_mm || i.edge_left_mm || i.edge_right_mm,
  ),
)

const priceRows = computed(() => {
  const p = order.value?.price
  if (!p) return []
  const rows: { label: string; value: string; discount?: boolean }[] = []
  rows.push({ label: t('client.cuttingService'), value: fmtTiyin(p.subtotal_cutting_tiyin) })
  if (p.subtotal_materials_tiyin > 0)
    rows.push({ label: t('client.materialsLine'), value: fmtTiyin(p.subtotal_materials_tiyin) })
  if (p.subtotal_edge_banding_tiyin > 0)
    rows.push({ label: t('client.edgeBanding'), value: fmtTiyin(p.subtotal_edge_banding_tiyin) })
  if (p.discount_tiyin > 0)
    rows.push({
      label: t('client.discount'),
      value: `− ${fmtTiyin(p.discount_tiyin)}`,
      discount: true,
    })
  return rows
})

// timeline as the 5-phase progress (cancelled is special-cased).
function phaseFor(status: OrderStatus): number {
  switch (status) {
    case 'new':
      return 0
    case 'confirmed':
      return 1
    case 'cutting':
    case 'edge_banding':
      return 2
    case 'ready':
      return 3
    case 'completed':
      return 4
    default:
      return 0
  }
}

async function load() {
  loading.value = true
  error.value = null
  notFound.value = false
  try {
    order.value = await clientApi.getOrder(orderId.value)
  } catch (e) {
    if (e instanceof ApiError) {
      if (e.status === 404 || e.status === 403) notFound.value = true
      else error.value = e
    } else throw e
  } finally {
    loading.value = false
  }
}

function onFinanceTab() {
  if (!finOpen.value) toast.warn(t('client.financeLockedBody'))
}

async function doCancel(reason: string) {
  try {
    await clientApi.cancelOrder(orderId.value, reason)
    toast.ok(t('client.orderCancelled'))
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  }
}

async function downloadPdf() {
  if (!order.value) return
  toast.ok(t('client.pdfPreparing'))
  try {
    const url = await clientApi.openResultPdf(order.value.cutting_result_id)
    window.open(url, '_blank')
  } catch {
    toast.warn(t('common.loadFailedBody'))
  }
}

onMounted(load)
</script>

<template>
  <div>
    <button class="back" type="button" @click="router.push('/c/orders')">
      ← {{ t('common.back') }}
    </button>

    <div v-if="loading" class="card" style="padding: 24px; margin-top: 12px">
      <div class="sk sk-line" style="width: 35%" />
      <div class="sk sk-line" style="width: 100%; margin-top: 18px; height: 60px" />
    </div>

    <ErrorState v-else-if="error" :error="error" :retry="load" />

    <div v-else-if="notFound" class="st-empty" style="margin-top: 24px">
      <div class="ic">∅</div>
      <h3>{{ t('client.orderNotFound') }}</h3>
      <p>{{ t('client.orderNotFoundBody') }}</p>
      <RouterLink class="btn btn-outline" to="/c/orders">{{ t('client.ordersTitle') }}</RouterLink>
    </div>

    <template v-else-if="order">
      <div v-if="justPlaced" class="banner success" style="margin-bottom: 16px">
        <div class="ic">✓</div>
        <div class="grow">{{ t('client.orderPlaced') }}</div>
      </div>

      <div v-if="order.status === 'cancelled'" class="banner warn" style="margin-bottom: 16px">
        <div class="ic">!</div>
        <div class="grow">
          {{ t('clientPhase.cancelled')
          }}<template v-if="order.cancelled_at"> · {{ fmtDateTime(order.cancelled_at) }}</template
          ><template v-if="order.cancellation_reason"> · {{ order.cancellation_reason }}</template>
        </div>
      </div>

      <div class="page-head" style="margin-bottom: 8px">
        <div>
          <h1 style="font-family: var(--f-mono); font-size: 22px">{{ order.order_number }}</h1>
          <p class="sub">{{ fmtDateTime(order.created_at) }}</p>
        </div>
        <div class="tools" style="align-items: center; gap: 10px">
          <StatusBadge :state="order.status" client-phase />
          <button
            v-if="order.status === 'new'"
            class="btn btn-danger btn-sm"
            type="button"
            @click="cancelOpen = true"
          >
            {{ t('client.cancelOrderBtn') }}
          </button>
        </div>
      </div>

      <AppTabs
        v-model="activeTab"
        :tabs="tabs"
        @update:model-value="$event === 'finance' && onFinanceTab()"
      />

      <!-- OVERVIEW -->
      <div v-show="activeTab === 'overview'" style="margin-top: 16px">
        <section class="card">
          <div class="card-h">
            <h2>{{ t('client.orderComposition') }}</h2>
          </div>
          <div class="card-b" style="padding-top: 0">
            <div v-for="it in order.items" :key="it.id" class="row-item">
              <div>
                <div class="nm">
                  #{{ it.part_ref.slice(0, 6) }} · {{ it.length_mm }}×{{ it.width_mm }} mm
                </div>
                <small style="color: var(--ink-6)"
                  >{{ it.quantity }} {{ t('client.itemsUnit') }} ·
                  {{
                    it.material_source === 'own' ? t('client.srcOwn') : t('client.srcShop')
                  }}</small
                >
              </div>
              <div class="meta">{{ fmtTiyin(it.line_total_tiyin) }}</div>
            </div>
          </div>
        </section>

        <section class="card" style="margin-top: 14px">
          <div class="card-h">
            <h2>{{ t('client.grandTotal') }}</h2>
          </div>
          <div class="card-b" style="padding-top: 0">
            <div class="totals">
              <div v-for="r in priceRows" :key="r.label" class="r">
                <span>{{ r.label }}</span>
                <span class="num" :class="{ 'success-text': r.discount }">{{ r.value }}</span>
              </div>
              <div class="r grand">
                <span>{{ t('client.grandTotal') }}</span
                ><span class="num">{{ fmtTiyin(order.price.total_tiyin) }}</span>
              </div>
            </div>
            <p class="muted" style="font-size: 12.5px; margin: 10px 2px 0">
              {{ t('client.priceFrozen') }}
            </p>
          </div>
        </section>

        <section v-if="order.note_client" class="card" style="margin-top: 14px">
          <div class="card-h">
            <h2>{{ t('client.orderNote') }}</h2>
          </div>
          <div class="card-b" style="padding-top: 0">
            <p style="margin: 0; color: var(--ink-10); font-size: 14px">{{ order.note_client }}</p>
          </div>
        </section>
      </div>

      <!-- CUTTING -->
      <div v-show="activeTab === 'cutting'" style="margin-top: 16px">
        <section class="card">
          <div class="card-h">
            <h2>{{ t('client.cuttingTab') }}</h2>
          </div>
          <div class="card-b" style="padding-top: 0">
            <p class="muted" style="font-size: 13px; margin: 0 0 14px">
              {{ t('client.cuttingTab')
              }}<template v-if="banded"> · {{ t('client.bandedNote') }}</template>
            </p>
            <button class="btn btn-outline btn-block" type="button" @click="downloadPdf">
              {{ t('client.downloadCuttingPdf') }}
            </button>
          </div>
        </section>
      </div>

      <!-- FINANCE (gated) -->
      <div v-show="activeTab === 'finance'" style="margin-top: 16px">
        <section v-if="finOpen && order.settlement" class="card">
          <div class="card-h">
            <h2>{{ t('client.tabFinance') }}</h2>
          </div>
          <div class="card-b" style="padding-top: 0">
            <div class="totals">
              <div class="r">
                <span>{{ t('client.financeTotal') }}</span
                ><span class="num">{{ fmtTiyin(order.settlement.total_tiyin) }}</span>
              </div>
              <div class="r">
                <span>{{ t('client.financePaid') }}</span
                ><span class="num success-text"
                  >− {{ fmtTiyin(order.settlement.recorded_tiyin) }}</span
                >
              </div>
              <div class="r grand">
                <span>{{ t('client.financeBalance') }}</span
                ><span class="num">{{ fmtTiyin(order.settlement.balance_tiyin) }}</span>
              </div>
            </div>
            <p class="muted" style="font-size: 12.5px; margin: 12px 2px 0">
              {{ t('client.financeNote') }}
            </p>
          </div>
        </section>
        <section v-else class="card">
          <div class="card-b">
            <div class="st-empty" style="border: 0; padding: 32px 16px">
              <div class="ic">🔒</div>
              <h3>{{ t('client.financeLockedTitle') }}</h3>
              <p>{{ t('client.financeLockedBody') }}</p>
            </div>
          </div>
        </section>
      </div>

      <!-- TIMELINE -->
      <div v-show="activeTab === 'timeline'" style="margin-top: 16px">
        <section class="card">
          <div class="card-h">
            <h2>{{ t('client.timelineTitle') }}</h2>
          </div>
          <div class="card-b" style="padding: 14px 22px 22px">
            <ol v-if="order.status === 'cancelled'" class="tl">
              <li class="step done">
                <span class="when">{{ fmtDateTime(order.created_at) }}</span
                >{{ t('clientPhase.new') }}
              </li>
              <li class="step bad">
                <span class="when">{{ fmtDateTime(order.cancelled_at) }}</span
                >{{ t('clientPhase.cancelled') }}
              </li>
            </ol>
            <ol v-else class="tl">
              <li
                v-for="(label, i) in phaseLabels"
                :key="label"
                class="step"
                :class="{ done: i < phaseFor(order.status), now: i === phaseFor(order.status) }"
              >
                <span class="when">{{
                  i === 0
                    ? fmtDateTime(order.created_at)
                    : i === 1
                      ? fmtDateTime(order.confirmed_at)
                      : i === 4
                        ? fmtDateTime(order.completed_at)
                        : '—'
                }}</span
                >{{ label }}
              </li>
            </ol>
          </div>
        </section>
      </div>

      <ConfirmDialog
        v-model:open="cancelOpen"
        :title="t('client.cancelOrderTitle')"
        :message="t('client.cancelOrderMsg')"
        :ok-text="t('client.cancelOrderOk')"
        :reason-label="t('client.cancelReasonLabel')"
        reason
        danger
        @confirm="doCancel"
      />
    </template>
  </div>
</template>
