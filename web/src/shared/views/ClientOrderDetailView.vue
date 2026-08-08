<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute } from 'vue-router'

import {
  clientErrorLabel,
  clientPhaseIndex,
  clientPhaseLabels,
  clientStatusLabel,
  clientStatusPillClass,
  formatRelativeDate,
} from '@/shared/app/clientUi'
import { traceSuffix } from '@/shared/app/errorTrace'
import { ownMaterialRows } from '@/shared/app/ownMaterial'
import Icon from '@/shared/components/AppIcon.vue'
import ClientErrorState from '@/shared/components/ClientErrorState.vue'
import { useToast } from '@/shared/composables/useToast'
import { useRolePath } from '@/shared/app/paths'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import CuttingPartsByMaterial from '@/shared/components/CuttingPartsByMaterial.vue'
import BranchContact from '@/shared/components/BranchContact.vue'
import CuttingResultOverview from '@/shared/components/CuttingResultOverview.vue'
import { formatDate, formatTiyin } from '@/shared/formatters'
import { metres } from '@/shared/stores/cutting'
import { useOrdersStore, type OrderStatus } from '@/shared/stores/orders'

type DetailTab = 'overview' | 'parts' | 'cutting' | 'finance' | 'timeline'

const { t } = useI18n()
const route = useRoute()
const rolePath = useRolePath()
const orders = useOrdersStore()
const toast = useToast()
const orderId = computed(() => String(route.params.order_id))
const isNew = computed(() => route.query.new === '1')
const activeTab = ref<DetailTab>('overview')
const activePanelId = ref<string | null>(null)
const activePlacementId = ref<string | null>(null)
const actionError = ref<string | null>(null)
const cancelDialogOpen = ref(false)
const cancelReason = ref(t('client.orders.cancelReasonDefault'))

const order = computed(() => orders.currentOrder)
const cancelledReason = computed(
  () => order.value?.events.find((event) => event.to_status === 'cancelled')?.reason ?? null,
)
const result = computed(() => order.value?.cutting_result ?? null)
// Header summary only — the grouped table itself is CuttingPartsByMaterial's job.
const materialCount = computed(
  () => new Set((result.value?.parts_snapshot ?? []).map((part) => part.material_id)).size,
)
const totalEdge = computed(() => {
  const current = result.value
  if (!current) return 0
  // The consumed sum (edge_length + overhang, per banded side) is the
  // client-facing figure, matching the editor's metres. The geometric
  // total_edge_length_mm fallback was unreachable (both sums share the same
  // banded sides, so consumed === 0 ⟺ total === 0) — dropped (CB-56).
  return (
    Object.values(current.edge_consumed_shop_by_material).reduce((sum, value) => sum + value, 0) +
    Object.values(current.edge_consumed_own_by_material).reduce((sum, value) => sum + value, 0)
  )
})
// What this order still expects the client to hand over.
const ownRows = computed(() => ownMaterialRows(order.value?.price_lines ?? []))
const edgeCostSplit = computed(() => {
  // No backend material/service split yet — use a 45/55 materials/service fallback.
  const total = order.value?.subtotal_edge_banding_tiyin ?? 0
  const materials = Math.round(total * 0.45)
  return { total, materials, service: total - materials }
})
const financeOpen = computed(
  () =>
    Boolean(order.value?.settlement) && ['ready', 'completed'].includes(order.value?.status ?? ''),
)

function statusSubtext(status: OrderStatus) {
  if (status === 'cutting') return t('client.orderDetail.statusCutting')
  if (status === 'edge_banding') return t('client.orderDetail.statusEdgeBanding')
  if (status === 'ready') return t('client.orderDetail.statusReady')
  if (status === 'cancelled') return t('client.status.cancelled')
  return ''
}

function phaseNodeClass(index: number) {
  if (!order.value) return ''
  const current = clientPhaseIndex(order.value.status)
  if (current < 0) return ''
  if (index < current) return 'done'
  if (index === current) return 'now'
  return ''
}

function phaseTimestamp(index: number): string | null {
  if (!order.value) return null
  const statusForPhase: OrderStatus[][] = [
    ['new'],
    ['confirmed'],
    ['cutting', 'edge_banding'],
    ['ready'],
    ['completed'],
  ]
  const statuses = statusForPhase[index] ?? []
  const event = order.value.events.find((entry) => statuses.includes(entry.to_status))
  if (event) return formatRelativeDate(event.changed_at)
  if (index === 0) return formatRelativeDate(order.value.created_at)
  return null
}

function requestCancelOrder() {
  cancelReason.value = t('client.orders.cancelReasonDefault')
  actionError.value = null
  cancelDialogOpen.value = true
}

async function cancelOrder() {
  const current = order.value
  if (!current) return
  const reason = cancelReason.value.trim()
  if (!reason) return
  actionError.value = null
  try {
    await orders.cancelClientOrder(current.id, current.version, reason)
    cancelDialogOpen.value = false
    toast.success(t('client.orderDetail.cancelledToast'))
  } catch {
    actionError.value = orders.actionError ?? 'order_cancel_failed'
  }
}

function switchTab(tab: DetailTab) {
  activeTab.value = tab
}

const detailTabs: DetailTab[] = ['overview', 'parts', 'cutting', 'finance', 'timeline']
function onTabKeydown(event: KeyboardEvent) {
  const current = detailTabs.indexOf(activeTab.value)
  let nextIndex = current
  if (event.key === 'ArrowRight') nextIndex = (current + 1) % detailTabs.length
  else if (event.key === 'ArrowLeft')
    nextIndex = (current - 1 + detailTabs.length) % detailTabs.length
  else if (event.key === 'Home') nextIndex = 0
  else if (event.key === 'End') nextIndex = detailTabs.length - 1
  else return
  event.preventDefault()
  const nextTab = detailTabs[nextIndex]
  if (!nextTab) return
  switchTab(nextTab)
  void nextTick(() => document.getElementById(`tab-${nextTab}`)?.focus())
}

watch(
  result,
  (value) => {
    if (!value) {
      activePanelId.value = null
      activePlacementId.value = null
      return
    }
    if (!value.panels.some((panel) => panel.id === activePanelId.value)) {
      activePanelId.value = value.panels[0]?.id ?? null
      activePlacementId.value = null
    }
  },
  { immediate: true },
)

onMounted(() => {
  void orders.loadClientOrder(orderId.value)
})
</script>

<template>
  <section>
    <RouterLink :to="rolePath('/c/orders')" class="client-back"
      >← {{ $t('client.orderDetail.back') }}</RouterLink
    >

    <div v-if="isNew && order" class="client-banner success">
      <span class="font-bold">✓</span>
      <span>{{ $t('client.orderDetail.placedBanner') }}</span>
    </div>

    <div v-if="orders.loading" class="client-card p-5" aria-live="polite">
      <div class="client-skeleton h-4 w-1/4"></div>
      <div class="client-skeleton mt-3 h-8 w-1/2"></div>
      <div class="client-skeleton mt-5 h-20 w-full"></div>
    </div>

    <ClientErrorState
      v-else-if="orders.error"
      :title="$t('client.orderDetail.loadFailed')"
      :trace-id="orders.traceId"
      @retry="orders.loadClientOrder(orderId)"
    />

    <div v-else-if="!order" class="client-empty">
      <div class="client-empty-icon"><Icon name="box" /></div>
      <h3>{{ $t('client.orderDetail.notFoundTitle') }}</h3>
      <p>{{ $t('client.orderDetail.notFoundBody') }}</p>
      <RouterLink :to="rolePath('/c/orders')" class="mp-button mp-button-primary mt-4">
        {{ $t('client.orderDetail.myOrders') }}
      </RouterLink>
    </div>

    <template v-else>
      <section class="client-card mb-5 p-5">
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 class="m-0 font-display text-[28px] font-semibold leading-tight text-ink">
              {{ order.order_number }}
            </h1>
            <p class="mt-2 text-sm text-ink-soft">
              {{ order.branch_name }} · {{ formatRelativeDate(order.created_at) }} ·
              {{ $t('client.orderDetail.pickupAtWorkshop') }}
            </p>
          </div>
          <div class="text-left sm:text-right">
            <span :class="clientStatusPillClass(order.status)">
              {{ clientStatusLabel(order.status) }}
            </span>
            <div class="mt-2 text-xl font-bold text-ink">
              {{ formatTiyin(order.total_tiyin) }}
            </div>
            <div class="text-xs font-semibold text-ink-muted">
              {{ $t('client.orderDetail.fixedTotal') }}
            </div>
          </div>
        </div>
        <div class="mt-4 flex flex-wrap gap-2">
          <button
            v-if="order.status === 'new'"
            type="button"
            class="mp-button mp-button-outline min-h-8 px-3 text-xs text-danger"
            :disabled="orders.actionLoading"
            @click="requestCancelOrder"
          >
            {{ $t('client.common.cancel') }}
          </button>
          <button
            v-else-if="order.status !== 'cancelled'"
            type="button"
            class="mp-button mp-button-outline min-h-8 px-3 text-xs"
            @click="switchTab('timeline')"
          >
            {{ $t('client.orderDetail.track') }}
          </button>
          <button
            v-if="result"
            type="button"
            class="mp-button mp-button-outline min-h-8 px-3 text-xs"
            :disabled="orders.downloadingId === order.id"
            @click="orders.openClientPdf(order.id)"
          >
            {{
              orders.downloadingId === order.id
                ? $t('client.orderDetail.opening')
                : $t('client.orderDetail.openPdf')
            }}
          </button>
        </div>
        <!-- The header PDF button is reachable from every tab, so its failure
             needs a banner here too — the Chizma tab's one isn't on screen. -->
        <p
          v-if="orders.downloadError"
          class="mt-3 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          role="alert"
        >
          {{ orders.downloadError }}
          <span v-if="orders.downloadTraceId" class="block text-xs font-normal opacity-80">
            trace {{ orders.downloadTraceId }}
          </span>
        </p>
      </section>

      <div v-if="order.status === 'cancelled'" class="client-banner warn">
        <span class="font-bold">!</span>
        <span>
          {{ $t('client.orderDetail.cancelledBanner')
          }}<span v-if="order.cancelled_at"> · {{ formatDate(order.cancelled_at) }}</span
          >.<span v-if="cancelledReason">
            {{ $t('client.orderDetail.reasonLabel') }} <b>{{ cancelledReason }}</b></span
          >
        </span>
      </div>

      <!-- Above the tabs, not inside one: this is the only thing on the page
           the client has to act on, and it is unreadable if it is one tab away
           behind a receipt. Drops out entirely on an ordinary order. -->
      <div v-if="ownRows.length > 0" class="client-banner warn">
        <span class="font-bold">!</span>
        <span>
          <b>{{ $t('orders.own.clientTitle') }}</b>
          <span v-for="(row, index) in ownRows" :key="row.materialId">
            <span v-if="index > 0"> · </span>
            {{ row.materialName }} — <b>{{ row.amount }}</b>
          </span>
          <span class="mt-1 block opacity-80">{{ $t('orders.own.clientBody') }}</span>
        </span>
      </div>

      <div
        class="client-tabs"
        role="tablist"
        :aria-label="$t('client.orderDetail.tabsLabel')"
        @keydown="onTabKeydown"
      >
        <button
          id="tab-overview"
          type="button"
          role="tab"
          class="client-tab"
          :class="{ active: activeTab === 'overview' }"
          :aria-selected="activeTab === 'overview'"
          aria-controls="panel-overview"
          :tabindex="activeTab === 'overview' ? 0 : -1"
          @click="switchTab('overview')"
        >
          {{ $t('client.orderDetail.tabOverview') }}
        </button>
        <button
          id="tab-parts"
          type="button"
          role="tab"
          class="client-tab"
          :class="{ active: activeTab === 'parts' }"
          :aria-selected="activeTab === 'parts'"
          aria-controls="panel-parts"
          :tabindex="activeTab === 'parts' ? 0 : -1"
          @click="switchTab('parts')"
        >
          {{ $t('client.orderDetail.tabParts') }}
        </button>
        <button
          id="tab-cutting"
          type="button"
          role="tab"
          class="client-tab"
          :class="{ active: activeTab === 'cutting' }"
          :aria-selected="activeTab === 'cutting'"
          aria-controls="panel-cutting"
          :tabindex="activeTab === 'cutting' ? 0 : -1"
          @click="switchTab('cutting')"
        >
          {{ $t('client.orderDetail.tabCutting') }}
        </button>
        <button
          id="tab-finance"
          type="button"
          role="tab"
          class="client-tab"
          :class="{ active: activeTab === 'finance' }"
          :aria-selected="activeTab === 'finance'"
          aria-controls="panel-finance"
          :tabindex="activeTab === 'finance' ? 0 : -1"
          @click="switchTab('finance')"
        >
          {{ $t('client.orderDetail.tabPayment') }}
        </button>
        <button
          id="tab-timeline"
          type="button"
          role="tab"
          class="client-tab"
          :class="{ active: activeTab === 'timeline' }"
          :aria-selected="activeTab === 'timeline'"
          aria-controls="panel-timeline"
          :tabindex="activeTab === 'timeline' ? 0 : -1"
          @click="switchTab('timeline')"
        >
          {{ $t('client.orderDetail.tabHistory') }}
        </button>
      </div>

      <div class="min-w-0">
        <section
          v-if="activeTab === 'overview'"
          id="panel-overview"
          role="tabpanel"
          aria-labelledby="tab-overview"
          tabindex="0"
          class="grid gap-4"
        >
          <div class="client-card">
            <div class="client-card-h">
              <h2>{{ $t('client.orderDetail.composition') }}</h2>
            </div>
            <div class="client-card-b">
              <div class="client-row-item">
                <div>
                  <div class="client-row-name">{{ $t('client.common.cuttingService') }}</div>
                  <div class="text-sm text-ink-muted">
                    {{
                      $t('client.orderDetail.cuttingDraftRef', {
                        id: order.cutting_result_id.slice(0, 8),
                      })
                    }}
                  </div>
                </div>
                <div class="client-row-meta">{{ formatTiyin(order.subtotal_cutting_tiyin) }}</div>
              </div>
              <div class="client-row-item">
                <div>
                  <div class="client-row-name">{{ $t('client.common.material') }}</div>
                  <div class="text-sm text-ink-muted">
                    {{ $t('client.orderDetail.workshopMaterial') }}
                  </div>
                </div>
                <div class="client-row-meta">
                  {{ formatTiyin(order.subtotal_materials_tiyin) }}
                </div>
              </div>
              <template v-if="order.subtotal_edge_banding_tiyin > 0">
                <div class="client-row-item">
                  <div>
                    <div class="client-row-name">{{ $t('client.orderDetail.edge') }}</div>
                    <div class="text-sm text-ink-muted">
                      {{ metres(totalEdge) }} ·
                      {{ $t('client.orderDetail.edgeMaterialAndService') }}
                    </div>
                  </div>
                  <div class="client-row-meta">
                    {{ formatTiyin(order.subtotal_edge_banding_tiyin) }}
                  </div>
                </div>
                <div class="client-row-item">
                  <div>
                    <div class="client-row-name">{{ $t('client.orderDetail.edgeMaterial') }}</div>
                    <div class="text-sm text-ink-muted">
                      {{ $t('client.orderDetail.edgeTapePrice') }}
                    </div>
                  </div>
                  <div class="client-row-meta">{{ formatTiyin(edgeCostSplit.materials) }}</div>
                </div>
                <div class="client-row-item">
                  <div>
                    <div class="client-row-name">{{ $t('client.orderDetail.edgeService') }}</div>
                    <div class="text-sm text-ink-muted">
                      {{ $t('client.orderDetail.edgeServiceDetail') }}
                    </div>
                  </div>
                  <div class="client-row-meta">{{ formatTiyin(edgeCostSplit.service) }}</div>
                </div>
              </template>
              <div v-if="order.surcharge_tiyin > 0" class="client-row-item">
                <div>
                  <div class="client-row-name">{{ $t('client.orderDetail.surcharge') }}</div>
                  <div class="text-sm text-ink-muted">{{ order.surcharge_reason ?? '' }}</div>
                </div>
                <div class="client-row-meta">+ {{ formatTiyin(order.surcharge_tiyin) }}</div>
              </div>
              <div v-if="order.discount_tiyin > 0" class="client-row-item">
                <div>
                  <div class="client-row-name">{{ $t('client.orderDetail.discount') }}</div>
                  <div class="text-sm text-ink-muted">{{ order.discount_reason ?? '' }}</div>
                </div>
                <div class="client-row-meta text-success">
                  - {{ formatTiyin(order.discount_tiyin) }}
                </div>
              </div>
            </div>
          </div>

          <div class="client-card">
            <div class="client-card-h">
              <h2>{{ $t('client.orderDetail.price') }}</h2>
            </div>
            <div class="client-card-b">
              <div class="rounded-lg border border-hairline bg-sunk p-4 text-sm">
                <div class="flex justify-between py-1 text-ink-soft">
                  <span>{{ $t('client.common.cuttingService') }}</span
                  ><span class="text-ink">{{ formatTiyin(order.subtotal_cutting_tiyin) }}</span>
                </div>
                <div class="flex justify-between py-1 text-ink-soft">
                  <span>{{ $t('client.common.material') }}</span
                  ><span class="text-ink">{{ formatTiyin(order.subtotal_materials_tiyin) }}</span>
                </div>
                <template v-if="order.subtotal_edge_banding_tiyin > 0">
                  <div class="flex justify-between py-1 text-ink-soft">
                    <span>{{ $t('client.orderDetail.edgeMaterial') }}</span
                    ><span class="text-ink">{{ formatTiyin(edgeCostSplit.materials) }}</span>
                  </div>
                  <div class="flex justify-between py-1 text-ink-soft">
                    <span>{{ $t('client.orderDetail.edgeService') }}</span
                    ><span class="text-ink">{{ formatTiyin(edgeCostSplit.service) }}</span>
                  </div>
                </template>
                <div
                  v-if="order.surcharge_tiyin > 0"
                  class="flex justify-between py-1 text-ink-soft"
                >
                  <span>{{ $t('client.orderDetail.surcharge') }}</span
                  ><span class="text-ink">+ {{ formatTiyin(order.surcharge_tiyin) }}</span>
                </div>
                <div v-if="order.discount_tiyin > 0" class="flex justify-between py-1 text-success">
                  <span>{{ $t('client.orderDetail.discount') }}</span
                  ><span>- {{ formatTiyin(order.discount_tiyin) }}</span>
                </div>
                <div class="mt-2 flex justify-between border-t border-ink pt-3 font-bold text-ink">
                  <span>{{ $t('client.common.total') }}</span
                  ><span class="font-display text-2xl">{{ formatTiyin(order.total_tiyin) }}</span>
                </div>
              </div>
              <p class="mt-3 text-sm text-ink-muted">
                {{ $t('client.orderDetail.priceFixedNote') }}
              </p>
            </div>
          </div>

          <div class="client-card">
            <div class="client-card-h">
              <h2>{{ $t('client.orderDetail.pickup') }}</h2>
            </div>
            <div class="client-card-b">
              <div class="client-row-item">
                <div>
                  <div class="client-row-name">
                    {{ order.workshop_name }} · {{ order.branch_name }}
                  </div>
                  <div class="text-sm text-ink-muted">{{ order.branch_address }}</div>
                </div>
                <div class="client-row-meta">{{ order.branch_phone }}</div>
              </div>
              <div class="client-row-item">
                <div class="client-row-name">{{ $t('client.orderDetail.contact') }}</div>
                <div class="client-row-meta">
                  {{ order.contact_name }} · {{ order.contact_phone }}
                </div>
              </div>
            </div>
          </div>

          <div v-if="order.note_workshop || order.note_client" class="client-card">
            <div class="client-card-h">
              <h2>{{ $t('client.orderDetail.note') }}</h2>
            </div>
            <div class="client-card-b space-y-3">
              <div v-if="order.note_workshop">
                <div class="text-[12.5px] font-semibold text-ink-muted">
                  {{ $t('client.orderDetail.noteWorkshop') }}
                </div>
                <p class="mt-1 text-sm text-ink">{{ order.note_workshop }}</p>
              </div>
              <div v-if="order.note_client">
                <div class="text-[12.5px] font-semibold text-ink-muted">
                  {{ $t('client.orderDetail.noteClient') }}
                </div>
                <p class="mt-1 text-sm text-ink">{{ order.note_client }}</p>
              </div>
            </div>
          </div>
          <section class="client-card">
            <div class="client-card-h">
              <h2 class="!text-base">{{ $t('client.orderDetail.statusCard') }}</h2>
            </div>
            <div class="client-card-b">
              <div class="grid gap-3">
                <div
                  v-for="(label, index) in clientPhaseLabels()"
                  :key="label"
                  class="flex items-center gap-3"
                >
                  <span
                    class="size-3 rounded-full border-2"
                    :class="
                      phaseNodeClass(index) === 'done'
                        ? 'border-accent bg-accent'
                        : phaseNodeClass(index) === 'now'
                          ? 'border-signal bg-elevated shadow-[0_0_0_4px_color-mix(in_srgb,var(--color-signal)_28%,transparent)]'
                          : 'border-hairline bg-elevated'
                    "
                  ></span>
                  <span class="text-sm font-bold text-ink">{{ label }}</span>
                </div>
              </div>
              <p v-if="statusSubtext(order.status)" class="mt-4 text-sm font-bold text-ink">
                {{ statusSubtext(order.status) }}
              </p>
            </div>
          </section>

          <section class="client-card">
            <div class="client-card-h">
              <h2 class="!text-base">{{ $t('client.orderDetail.workshopContact') }}</h2>
            </div>
            <div class="client-card-b">
              <div class="client-row-item">
                <div class="client-row-name">{{ order.workshop_name }}</div>
                <div class="client-row-meta">{{ order.branch_phone }}</div>
              </div>
              <div class="client-row-item">
                <div class="min-w-0">
                  <div class="client-row-name">{{ order.branch_name }}</div>
                  <BranchContact
                    class="mt-1"
                    :address="order.branch_address"
                    :phone="order.branch_phone"
                    :additional-phones="order.branch_additional_phones"
                    :latitude="order.branch_latitude"
                    :longitude="order.branch_longitude"
                  />
                </div>
              </div>
            </div>
          </section>

          <p v-if="actionError" class="rounded-md bg-danger-soft p-3 text-sm font-bold text-danger">
            {{ clientErrorLabel(actionError) }}{{ traceSuffix(orders.actionTraceId) }}
          </p>
        </section>

        <section
          v-else-if="activeTab === 'parts'"
          id="panel-parts"
          role="tabpanel"
          aria-labelledby="tab-parts"
          tabindex="0"
          class="client-card"
        >
          <div class="client-card-h">
            <h2>{{ $t('client.common.parts') }}</h2>
            <span class="text-sm text-ink-muted">
              {{ $t('client.unit.parts', order.item_count) }} ·
              {{ $t('client.unit.materials', materialCount) }}
            </span>
          </div>
          <div class="client-card-b">
            <CuttingPartsByMaterial v-if="result" :result="result" />
            <div v-else class="text-sm text-ink-muted">
              {{ $t('client.orderDetail.partsEmpty') }}
            </div>
          </div>
        </section>

        <section
          v-else-if="activeTab === 'cutting'"
          id="panel-cutting"
          role="tabpanel"
          aria-labelledby="tab-cutting"
          tabindex="0"
          class="client-card"
        >
          <div class="client-card-h">
            <h2>{{ $t('client.orderDetail.tabCutting') }}</h2>
            <button
              v-if="result"
              type="button"
              class="text-sm font-bold text-accent-deep"
              :disabled="orders.downloadingId === order.id"
              @click="orders.openClientPdf(order.id)"
            >
              {{
                orders.downloadingId === order.id
                  ? $t('client.orderDetail.opening')
                  : `${$t('client.orderDetail.openPdfShort')} →`
              }}
            </button>
          </div>
          <div class="client-card-b">
            <p
              v-if="orders.downloadError"
              class="mb-3 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
              role="alert"
            >
              {{ orders.downloadError }}
              <span v-if="orders.downloadTraceId" class="block text-xs font-normal opacity-80">
                trace {{ orders.downloadTraceId }}
              </span>
            </p>
            <div v-if="!result" class="text-sm text-ink-muted">
              {{ $t('client.orderDetail.resultMissing') }}
            </div>
            <!-- The same component the cutting-result page renders — material
                 and edge tally, sheet strip, drawing, per-sheet rail — so a
                 placed order's drawing is not a second, thinner version of the
                 screen the client already saw before ordering. -->
            <CuttingResultOverview
              v-else
              v-model:active-panel-id="activePanelId"
              :result="result"
            />
          </div>
        </section>

        <section
          v-else-if="activeTab === 'finance'"
          id="panel-finance"
          role="tabpanel"
          aria-labelledby="tab-finance"
          tabindex="0"
          class="client-card"
        >
          <div class="client-card-h">
            <h2>{{ $t('client.orderDetail.tabPayment') }}</h2>
          </div>
          <div class="client-card-b">
            <template v-if="financeOpen && order.settlement">
              <div class="rounded-lg border border-hairline bg-sunk p-4 text-sm">
                <div class="flex justify-between py-1 text-ink-soft">
                  <span>{{ $t('client.common.total') }}</span
                  ><span class="text-ink">{{ formatTiyin(order.settlement.total_tiyin) }}</span>
                </div>
                <div class="flex justify-between py-1 text-ink-soft">
                  <span>{{ $t('client.orderDetail.paid') }}</span
                  ><span class="text-success"
                    >- {{ formatTiyin(order.settlement.recorded_tiyin) }}</span
                  >
                </div>
                <div class="mt-2 flex justify-between border-t border-ink pt-3 font-bold text-ink">
                  <span>{{ $t('client.orderDetail.balance') }}</span
                  ><span class="font-display text-2xl">{{
                    formatTiyin(order.settlement.balance_tiyin)
                  }}</span>
                </div>
              </div>
              <p class="mt-3 text-sm text-ink-muted">
                {{ $t('client.orderDetail.paymentNote') }}
              </p>
            </template>
            <div v-else class="client-empty border-0 !p-8">
              <div class="client-empty-icon"><Icon name="layers" /></div>
              <h3>{{ $t('client.orderDetail.paymentLockedTitle') }}</h3>
              <p>{{ $t('client.orderDetail.paymentLockedBody') }}</p>
            </div>
          </div>
        </section>

        <section
          v-else
          id="panel-timeline"
          role="tabpanel"
          aria-labelledby="tab-timeline"
          tabindex="0"
          class="client-card"
        >
          <div class="client-card-h">
            <h2>{{ $t('client.orderDetail.history') }}</h2>
          </div>
          <div class="client-card-b">
            <ol v-if="order.status === 'cancelled'" class="tl">
              <li class="step done">
                <span class="when">{{ formatRelativeDate(order.created_at) }}</span>
                {{ $t('client.status.new') }}
              </li>
              <li class="step bad">
                <span v-if="order.cancelled_at" class="when">{{
                  formatRelativeDate(order.cancelled_at)
                }}</span>
                {{ $t('client.status.cancelled') }}
                <p v-if="cancelledReason" class="mt-1 text-sm text-ink-soft">
                  {{ cancelledReason }}
                </p>
              </li>
            </ol>
            <ol v-else class="tl">
              <li
                v-for="(label, index) in clientPhaseLabels()"
                :key="label"
                class="step"
                :class="phaseNodeClass(index)"
              >
                <span v-if="phaseTimestamp(index)" class="when">{{ phaseTimestamp(index) }}</span>
                {{ label }}
              </li>
            </ol>
          </div>
        </section>
      </div>
    </template>

    <ConfirmDialog
      :open="cancelDialogOpen"
      :title="$t('client.orders.cancelTitle')"
      :message="$t('client.orders.cancelMessage')"
      :confirm-label="$t('client.common.cancel')"
      :cancel-label="$t('client.common.back')"
      :busy-label="$t('client.common.busy')"
      danger
      :busy="orders.actionLoading"
      :confirm-disabled="cancelReason.trim().length === 0"
      @cancel="cancelDialogOpen = false"
      @confirm="cancelOrder"
    >
      <label class="grid gap-1 text-sm font-bold text-ink">
        {{ $t('client.common.reason') }}
        <textarea v-model="cancelReason" class="mp-input min-h-24 resize-y" />
      </label>
    </ConfirmDialog>
  </section>
</template>
