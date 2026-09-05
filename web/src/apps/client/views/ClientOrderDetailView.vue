<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute } from 'vue-router'

import {
  clientErrorLabel,
  clientStatusLabel,
  clientStatusPillClass,
  formatPhone,
} from '@/shared/app/clientUi'
import { traceSuffix } from '@/shared/app/errorTrace'
import { useRolePath } from '@/shared/app/paths'
import { yandexMapUrl } from '@/shared/app/yandexMapLink'
import Icon from '@/shared/components/AppIcon.vue'
import ClientErrorState from '@/shared/components/ClientErrorState.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import CuttingPartsByMaterial from '@/shared/components/CuttingPartsByMaterial.vue'
import CuttingResultOverview from '@/shared/components/CuttingResultOverview.vue'
import SegmentedControl from '@/shared/components/SegmentedControl.vue'
import { useToast } from '@/shared/composables/useToast'
import { formatOrderNumber, formatTiyin } from '@/shared/formatters'
import { metres } from '@/shared/stores/cutting'
import { useOrdersStore } from '@/shared/stores/orders'

/**
 * One order (spec §5, decision 10).
 *
 * Header card, the Ustaxona card, the Narx receipt, then the parts — and on
 * desktop the drawing beside them under a two-tab control. Deliberately gone:
 * the four-phase track (the pill says the same thing in one word), the history
 * tab, the To'lov tab — its two figures moved into the receipt, where the
 * client already reads the total — and every date.
 */
const { t } = useI18n()
const route = useRoute()
const rolePath = useRolePath()
const orders = useOrdersStore()
const toast = useToast()

const orderId = computed(() => String(route.params.order_id))
const isNew = computed(() => route.query.new === '1')

type DetailTab = 'parts' | 'cutting'
/** Phones render the parts table alone; the control that reaches the drawing
 *  exists only at `md` and up, which is what keeps this at `parts` there. */
const activeTab = ref<DetailTab>('parts')
const activePanelId = ref<string | null>(null)
const actionError = ref<string | null>(null)
const cancelDialogOpen = ref(false)
const cancelReason = ref(t('client.orders.cancelReasonDefault'))

const order = computed(() => orders.currentOrder)
const result = computed(() => order.value?.cutting_result ?? null)
const isCancelled = computed(() => order.value?.status === 'cancelled')
const cancelledReason = computed(
  () => order.value?.events.find((event) => event.to_status === 'cancelled')?.reason ?? null,
)
const materialCount = computed(
  () => new Set((result.value?.parts_snapshot ?? []).map((part) => part.material_id)).size,
)

/** Decision 23, in the card's own shape: the workshop stays the title and the
 *  branch becomes a second line only where there is more than one to tell
 *  apart. The count is the payload's, so the card and the orders list can
 *  never disagree about what this workshop is called. */
const showBranchName = computed(
  () => (order.value?.workshop_branch_count ?? 0) > 1 && Boolean(order.value?.branch_name),
)
const mapUrl = computed(() =>
  yandexMapUrl(order.value?.branch_latitude, order.value?.branch_longitude),
)

const tabOptions = computed(() => [
  { value: 'parts', label: t('client.orderDetail.tabParts') },
  { value: 'cutting', label: t('client.orderDetail.tabCutting') },
])

/** Every banded millimetre this order carries — the editor's own figure. */
const totalEdge = computed(() => {
  const current = result.value
  if (!current) return 0
  return (
    Object.values(current.edge_consumed_shop_by_material).reduce((sum, value) => sum + value, 0) +
    Object.values(current.edge_consumed_own_by_material).reduce((sum, value) => sum + value, 0)
  )
})

/**
 * The tapes behind the «Kromka» row — «{tape} · {metres}», one line each (§5).
 *
 * The row keeps ONE money figure because `subtotal_edge_banding_tiyin` is one:
 * it is material *plus* the per-metre banding service, and that service is not
 * split per tape anywhere. So the tapes are named in the row's sub-lines rather
 * than given rows of their own — which is what the receipt owes the client,
 * since «Kromka · 3.72 m» alone never says which colour was banded on.
 */
const edgeRows = computed(() =>
  (order.value?.price_lines ?? [])
    .filter((line) => line.kind === 'edge' && (line.consumed_mm ?? 0) > 0)
    .map((line) => ({
      id: line.material_id,
      label: `${line.material_name} · ${metres(line.consumed_mm ?? 0)}`,
    })),
)

/**
 * One receipt row per material the workshop supplied, rather than a single
 * lumped «Material» line: with two boards on an order the lump is a number the
 * client cannot check against anything. The rows still sum to
 * `subtotal_materials_tiyin`.
 */
const materialRows = computed(() =>
  (order.value?.price_lines ?? [])
    .filter((line) => line.kind === 'panel' && (line.panels_used ?? 0) > 0)
    .map((line) => ({
      id: line.material_id,
      name: line.material_name,
      sheets: line.panels_used ?? 0,
      total: line.line_total_tiyin,
    })),
)

/** «To'langan» / «Qoldiq» open at `ready` — before that there is nothing to pay. */
const settlement = computed(() => {
  const current = order.value
  if (!current?.settlement) return null
  return ['ready', 'completed'].includes(current.status) ? current.settlement : null
})

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

watch(
  result,
  (value) => {
    if (!value) {
      activePanelId.value = null
      return
    }
    if (!value.panels.some((panel) => panel.id === activePanelId.value)) {
      activePanelId.value = value.panels[0]?.id ?? null
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
    <RouterLink :to="rolePath('/c/orders')" class="client-back">
      ← {{ $t('client.orderDetail.back') }}
    </RouterLink>

    <div v-if="isNew && order" class="client-banner success">
      <span class="font-bold">✓</span>
      <span>{{ $t('client.orderDetail.placedBanner') }}</span>
    </div>

    <!-- `detailLoading`, not `loading`: the latter is shared with the orders
         list, whose in-flight page used to switch this skeleton off and flash
         the not-found state. Re-opening an order the store still holds paints
         it at once and revalidates underneath (client audit 2026-09-03). -->
    <div v-if="orders.detailLoading && !order" class="client-card p-5" aria-live="polite">
      <span class="sr-only">{{ $t('client.common.loading') }}</span>
      <div class="client-skeleton h-7 w-1/2"></div>
      <div class="client-skeleton mt-3 h-4 w-1/4"></div>
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
      <!-- HEADER — identity and money, and the one action a `new` order has.
           No dates, no phase text, no track. -->
      <section class="client-card mb-3.5 p-4 md:mb-5 md:p-5">
        <div class="flex flex-wrap items-start justify-between gap-3.5 md:gap-4">
          <div class="flex min-w-0 flex-wrap items-baseline gap-x-3.5 gap-y-2">
            <h1
              class="m-0 font-display text-[26px] font-semibold leading-[1.15] tracking-[-0.02em] text-ink md:text-[28px]"
            >
              {{ formatOrderNumber(order.order_number) }}
            </h1>
            <p
              v-if="order.draft_name"
              class="m-0 min-w-0 truncate text-[13.5px] text-ink-soft md:text-[15px]"
            >
              {{ order.draft_name }}
            </p>
            <span :class="clientStatusPillClass(order.status)" class="hidden md:inline-flex">
              {{ clientStatusLabel(order.status) }}
            </span>
          </div>
          <div class="shrink-0 text-right">
            <span
              class="block font-display text-[19px] font-bold leading-[1.2] text-ink md:text-[22px]"
            >
              {{ formatTiyin(order.total_tiyin) }}
            </span>
            <span class="mt-0.5 block text-[12.5px] font-semibold text-ink-muted">
              {{ $t('client.orderDetail.fixedTotal') }}
            </span>
          </div>
        </div>
        <span :class="clientStatusPillClass(order.status)" class="mt-3 md:hidden">
          {{ clientStatusLabel(order.status) }}
        </span>

        <!-- The only place the client cancels from, and only while the order is
             still `new` — after that the workshop has committed material. -->
        <button
          v-if="order.status === 'new'"
          type="button"
          class="mp-button mp-button-outline mt-4 w-full text-danger md:w-auto"
          :disabled="orders.actionLoading"
          @click="requestCancelOrder"
        >
          {{ $t('client.common.cancel') }}
        </button>
        <p
          v-if="actionError"
          class="mt-3 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          role="alert"
        >
          {{ clientErrorLabel(actionError) }}{{ traceSuffix(orders.actionTraceId) }}
        </p>
      </section>

      <div v-if="isCancelled" class="client-banner warn">
        <span class="font-bold">!</span>
        <span>
          {{ $t('client.orderDetail.cancelledBanner')
          }}<template v-if="cancelledReason"
            >. {{ $t('client.orderDetail.reasonLabel') }} <b>{{ cancelledReason }}</b></template
          >
        </span>
      </div>

      <!-- Phones: the drawing is unreadable at 358px, so the PDF is the way to
           it and sits directly under the header. Desktop keeps «PDF ochish →»
           in the Chizma tab head. -->
      <button
        v-if="result"
        type="button"
        class="mp-button mp-button-outline mb-3.5 min-h-12 w-full md:hidden"
        :disabled="orders.downloadingId === order.id"
        @click="orders.openClientPdf(order.id)"
      >
        <Icon name="upload" class="size-[18px]" />
        {{
          orders.downloadingId === order.id
            ? $t('client.orderDetail.opening')
            : $t('client.orderDetail.openPdf')
        }}
      </button>
      <p
        v-if="orders.downloadError"
        class="mb-3.5 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
        role="alert"
      >
        {{ orders.downloadError }}
        <span v-if="orders.downloadTraceId" class="block text-xs font-normal opacity-80">
          trace {{ orders.downloadTraceId }}
        </span>
      </p>

      <!-- One DOM order for both layouts. Stacked on a phone it reads
           Ustaxona → Narx → Detallar; at `md` the two-column grid's auto
           placement puts Ustaxona and the tabs in the left column and Narx
           beside them, with no element rendered twice. -->
      <div class="md:grid md:grid-cols-[minmax(0,1fr)_400px] md:items-start md:gap-5">
        <!-- USTAXONA — what the old page said twice («Olib ketish» +
             «Ustaxonaga aloqa»), once. A cancelled order has no pickup, so it
             carries the banner above and no card here. -->
        <section v-if="!isCancelled" class="client-card mb-3.5 md:col-start-1 md:mb-0">
          <div class="client-card-h">
            <h2>{{ $t('client.orderDetail.workshopTitle') }}</h2>
          </div>
          <div class="px-4 py-3.5 md:px-5 md:py-[18px]">
            <div class="text-[15px] font-semibold text-ink">{{ order.workshop_name }}</div>
            <!-- The branch is a second line only when the workshop has more
                 than one counter (decision 23). To a one-branch workshop's
                 client the branch name is noise — the workshop *is* the
                 counter — and a repeated line under the name read as a
                 second, different place. -->
            <div v-if="showBranchName" class="mt-0.5 text-sm font-semibold text-ink-soft">
              {{ order.branch_name }}
            </div>
            <p class="mt-[5px] text-[13px] leading-[1.45] text-ink-muted">
              {{ order.branch_address }}
            </p>
            <div class="flex flex-wrap items-center gap-x-4">
              <!-- Only when the branch actually carries coordinates. -->
              <a
                v-if="mapUrl"
                class="inline-flex min-h-11 items-center text-[13px] font-bold text-accent-deep underline underline-offset-2"
                :href="mapUrl"
                target="_blank"
                rel="noopener noreferrer"
              >
                {{ $t('client.workshop.viewOnMap') }}
              </a>
              <a
                class="inline-flex min-h-11 items-center text-[13px] font-bold text-accent-deep underline underline-offset-2"
                :href="`tel:${order.branch_phone}`"
              >
                {{ formatPhone(order.branch_phone) }}
              </a>
            </div>
          </div>
        </section>

        <!-- NARX — one receipt, replacing «Buyurtma tarkibi» + «Narx», which
             were the same three lines twice. -->
        <!-- Spans both rows so the left column's tabs start directly under the
             Ustaxona card rather than under the taller receipt beside it. -->
        <section class="client-card mb-3.5 md:col-start-2 md:row-span-2 md:row-start-1 md:mb-0">
          <div class="client-card-h">
            <h2>{{ $t('client.orderDetail.price') }}</h2>
          </div>
          <div class="px-4 py-3.5 md:px-5 md:py-[18px]">
            <div class="client-row-item">
              <div>
                <div class="client-row-name">{{ $t('client.common.cuttingService') }}</div>
                <div class="text-[13px] text-ink-muted">
                  {{ $t('client.unit.parts', order.item_count) }} ·
                  {{ $t('client.unit.sheets', order.planned_panels) }}
                </div>
              </div>
              <div class="text-[13.5px] text-ink">
                {{ formatTiyin(order.subtotal_cutting_tiyin) }}
              </div>
            </div>
            <div v-for="row in materialRows" :key="row.id" class="client-row-item">
              <div class="min-w-0">
                <div class="client-row-name">{{ $t('client.common.material') }}</div>
                <div class="truncate text-[13px] text-ink-muted">
                  {{ row.name }} · {{ $t('client.unit.sheets', row.sheets) }}
                </div>
              </div>
              <div class="text-[13.5px] text-ink">{{ formatTiyin(row.total) }}</div>
            </div>
            <div v-if="order.subtotal_edge_banding_tiyin > 0" class="client-row-item">
              <div class="min-w-0">
                <div class="client-row-name">{{ $t('client.orderDetail.edge') }}</div>
                <!-- Legacy orders carry no edge price lines; the total metres
                     stand in so the row is never left without its quantity. -->
                <div
                  v-for="row in edgeRows"
                  :key="row.id"
                  class="truncate text-[13px] text-ink-muted"
                >
                  {{ row.label }}
                </div>
                <div v-if="edgeRows.length === 0" class="text-[13px] text-ink-muted">
                  {{ metres(totalEdge) }}
                </div>
                <div class="text-[13px] text-ink-muted">
                  {{ $t('client.orderDetail.edgeMaterialAndService') }}
                </div>
              </div>
              <div class="text-[13.5px] text-ink">
                {{ formatTiyin(order.subtotal_edge_banding_tiyin) }}
              </div>
            </div>
            <div v-if="order.surcharge_tiyin > 0" class="client-row-item">
              <div>
                <div class="client-row-name">{{ $t('client.orderDetail.surcharge') }}</div>
                <div class="text-[13px] text-ink-muted">{{ order.surcharge_reason ?? '' }}</div>
              </div>
              <div class="text-[13.5px] text-ink">+ {{ formatTiyin(order.surcharge_tiyin) }}</div>
            </div>
            <div v-if="order.discount_tiyin > 0" class="client-row-item">
              <div>
                <div class="client-row-name">{{ $t('client.orderDetail.discount') }}</div>
                <div class="text-[13px] text-ink-muted">{{ order.discount_reason ?? '' }}</div>
              </div>
              <div class="text-[13.5px] text-success">
                − {{ formatTiyin(order.discount_tiyin) }}
              </div>
            </div>

            <!-- At ready / completed the client's question is what is left to
                 pay at the counter, so QOLDIQ is the display figure and Jami
                 steps down to a plain row (UX review 2026-09-05). -->
            <div
              class="mt-2.5 flex items-baseline justify-between gap-3 border-t border-hairline pt-2.5 text-sm text-ink-soft"
            >
              <span>{{ $t('client.common.total') }}</span>
              <span class="font-semibold text-ink">{{ formatTiyin(order.total_tiyin) }}</span>
            </div>
            <template v-if="settlement">
              <div class="mt-[5px] flex items-baseline justify-between gap-3 text-sm text-ink-soft">
                <span>{{ $t('client.orderDetail.paid') }}</span>
                <span class="text-success">− {{ formatTiyin(settlement.recorded_tiyin) }}</span>
              </div>
              <div
                class="mt-2.5 flex items-baseline justify-between gap-3 border-t border-ink pt-3 font-bold text-ink"
              >
                <span class="text-base">{{ $t('client.orderDetail.balance') }}</span>
                <span class="font-display text-[27px] leading-[1.1] md:text-3xl">
                  {{ formatTiyin(settlement.balance_tiyin) }}
                </span>
              </div>
            </template>
            <p class="mt-3 text-[13px] leading-[1.5] text-ink-muted">
              {{ $t('client.orderDetail.priceNote') }}
            </p>
          </div>
        </section>

        <div class="md:col-start-1">
          <SegmentedControl
            v-if="result"
            v-model="activeTab"
            class="mb-4 hidden max-w-[320px] md:block"
            :label="$t('client.orderDetail.tabsLabel')"
            hide-label
            :options="tabOptions"
          />

          <section v-show="activeTab === 'parts'" class="client-card">
            <div class="client-card-h">
              <h2>{{ $t('client.orderDetail.tabParts') }}</h2>
              <span class="text-[13.5px] text-ink-muted">
                {{ $t('client.unit.parts', order.item_count) }} ·
                {{ $t('client.unit.materials', materialCount) }}
              </span>
            </div>
            <div class="px-4 py-3.5 md:px-5 md:py-[18px]">
              <CuttingPartsByMaterial v-if="result" :result="result" />
              <div v-else class="text-sm text-ink-muted">
                {{ $t('client.orderDetail.partsEmpty') }}
              </div>
            </div>
          </section>

          <!-- Reached only from the desktop tab control: the drawing needs a
               width where its labels can be read. `v-show` keeps the SVG
               mounted across tab switches. -->
          <section v-if="result" v-show="activeTab === 'cutting'" class="client-card">
            <div class="client-card-h">
              <h2>{{ $t('client.orderDetail.tabCutting') }}</h2>
              <button
                type="button"
                class="text-[13.5px] font-bold text-accent-deep"
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
            <div class="px-4 py-3.5 md:px-5 md:py-[18px]">
              <CuttingResultOverview v-model:active-panel-id="activePanelId" :result="result" />
            </div>
          </section>
        </div>
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
