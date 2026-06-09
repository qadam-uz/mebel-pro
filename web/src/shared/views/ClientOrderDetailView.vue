<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import {
  clientPhaseIndex,
  clientPhaseLabels,
  clientStatusLabel,
  clientStatusPillClass,
  formatPercent,
  formatRelativeDate,
} from '@/shared/app/clientUi'
import { useRolePath } from '@/shared/app/paths'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import { formatDate, formatTiyin } from '@/shared/formatters'
import {
  metres,
  type CuttingPanel,
  type CuttingPlacement,
  type CuttingResult,
} from '@/shared/stores/cutting'
import { useOrdersStore, type OrderStatus } from '@/shared/stores/orders'

type DetailTab = 'overview' | 'cutting' | 'finance' | 'timeline'

const route = useRoute()
const rolePath = useRolePath()
const orders = useOrdersStore()
const orderId = computed(() => String(route.params.order_id))
const isNew = computed(() => route.query.new === '1')
const activeTab = ref<DetailTab>('overview')
const activePanelId = ref<string | null>(null)
const activePlacementId = ref<string | null>(null)
const actionError = ref<string | null>(null)
const cancelDialogOpen = ref(false)
const cancelReason = ref('Mijoz buyurtmani tasdiqlashdan oldin bekor qildi')

const order = computed(() => orders.currentOrder)
const result = computed(() => order.value?.cutting_result ?? null)
const activePanel = computed(() => {
  const current = result.value
  if (!current) return null
  return (
    current.panels.find((panel) => panel.id === activePanelId.value) ?? current.panels[0] ?? null
  )
})
const totalPanels = computed(() =>
  result.value
    ? Object.values(result.value.panels_used_by_material).reduce((sum, count) => sum + count, 0)
    : 0,
)
const totalEdge = computed(() => {
  const current = result.value
  if (!current) return 0
  const consumed =
    Object.values(current.edge_consumed_shop_by_material).reduce((sum, value) => sum + value, 0) +
    Object.values(current.edge_consumed_own_by_material).reduce((sum, value) => sum + value, 0)
  return consumed || current.total_edge_length_mm
})
const financeOpen = computed(
  () =>
    Boolean(order.value?.settlement) && ['ready', 'completed'].includes(order.value?.status ?? ''),
)

function statusSubtext(status: OrderStatus) {
  if (status === 'cutting') return 'Kesilmoqda'
  if (status === 'edge_banding') return 'Krom yopishtirilmoqda'
  if (status === 'ready') return 'Olib ketishga tayyor'
  if (status === 'cancelled') return 'Bekor qilingan'
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

function materialName(snapshot: Record<string, unknown>) {
  return String(snapshot.name ?? snapshot.decor_code ?? 'Material')
}

function panelTitle(current: CuttingResult, panel: CuttingPanel) {
  const snapshot = current.material_snapshots[panel.material_id]
  return `${String(snapshot?.name ?? 'Panel')} · ${panel.panel_index}`
}

function selectPlacement(placement: CuttingPlacement) {
  activePlacementId.value = placement.id
}

function requestCancelOrder() {
  cancelReason.value = 'Mijoz buyurtmani tasdiqlashdan oldin bekor qildi'
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
  } catch {
    actionError.value = orders.error ?? 'order_cancel_failed'
  }
}

function switchTab(tab: DetailTab) {
  activeTab.value = tab
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
    <RouterLink :to="rolePath('/c/orders')" class="client-back">← Buyurtmalar</RouterLink>

    <div v-if="isNew && order" class="client-banner success">
      <span class="font-bold">✓</span>
      <span>Buyurtma berildi — ustaxona ko'rib chiqib siz bilan bog'lanadi.</span>
    </div>

    <div v-if="orders.loading" class="client-card p-5" aria-live="polite">
      <div class="client-skeleton h-4 w-1/4"></div>
      <div class="client-skeleton mt-3 h-8 w-1/2"></div>
      <div class="client-skeleton mt-5 h-20 w-full"></div>
    </div>

    <div v-else-if="orders.error" class="client-error">
      <div class="client-error-icon">!</div>
      <h3>Buyurtmani yuklab bo'lmadi</h3>
      <p>Ulanishda xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.</p>
      <p class="client-trace">trace_id: {{ orders.traceId ?? 'unavailable' }}</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4"
        @click="orders.loadClientOrder(orderId)"
      >
        Qayta urinish
      </button>
    </div>

    <div v-else-if="!order" class="client-empty">
      <div class="client-empty-icon">B</div>
      <h3>Buyurtma topilmadi</h3>
      <p>Bunday raqamli buyurtma yo'q yoki sizga tegishli emas.</p>
      <RouterLink :to="rolePath('/c/orders')" class="mp-button mp-button-primary mt-4">
        Buyurtmalarim
      </RouterLink>
    </div>

    <template v-else>
      <section class="client-card mb-5 p-5">
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 class="m-0 font-serif text-[28px] font-semibold leading-tight text-ink">
              {{ order.order_number }}
            </h1>
            <p class="mt-2 text-sm text-ink-soft">
              {{ order.branch_name }} · {{ formatRelativeDate(order.created_at) }} · ustaxonadan
              olib ketish
            </p>
          </div>
          <div class="text-left sm:text-right">
            <span :class="clientStatusPillClass(order.status)">
              {{ clientStatusLabel[order.status] }}
            </span>
            <div class="mt-2 font-mono text-xl font-bold text-ink">
              {{ formatTiyin(order.total_tiyin) }}
            </div>
            <div class="text-xs font-semibold text-ink-muted">jami narx (qat'iy)</div>
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
            Bekor qilish
          </button>
          <button
            v-else-if="order.status !== 'cancelled'"
            type="button"
            class="mp-button mp-button-outline min-h-8 px-3 text-xs"
            @click="switchTab('timeline')"
          >
            Holatni kuzatish
          </button>
          <button
            v-if="result"
            type="button"
            class="mp-button mp-button-outline min-h-8 px-3 text-xs"
            @click="orders.downloadClientPdf(order.id)"
          >
            Chizmani PDF olish
          </button>
        </div>
      </section>

      <div v-if="order.status === 'cancelled'" class="client-banner warn">
        <span class="font-bold">!</span>
        <span>
          Buyurtma bekor qilindi<span v-if="order.cancelled_at">
            · {{ formatDate(order.cancelled_at) }}</span
          >.
        </span>
      </div>

      <div class="client-tabs" role="tablist" aria-label="Buyurtma tafsilotlari">
        <button
          type="button"
          class="client-tab"
          :class="{ active: activeTab === 'overview' }"
          @click="switchTab('overview')"
        >
          Umumiy
        </button>
        <button
          type="button"
          class="client-tab"
          :class="{ active: activeTab === 'cutting' }"
          @click="switchTab('cutting')"
        >
          Chizma
        </button>
        <button
          type="button"
          class="client-tab"
          :class="{ active: activeTab === 'finance' }"
          @click="switchTab('finance')"
        >
          To'lov
        </button>
        <button
          type="button"
          class="client-tab"
          :class="{ active: activeTab === 'timeline' }"
          @click="switchTab('timeline')"
        >
          Tarix
        </button>
      </div>

      <div class="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.85fr)]">
        <div class="min-w-0">
          <section v-if="activeTab === 'overview'" class="grid gap-4">
            <div class="client-card">
              <div class="client-card-h"><h2>Buyurtma tarkibi</h2></div>
              <div class="client-card-b">
                <div class="client-row-item">
                  <div>
                    <div class="client-row-name">Kesish xizmati</div>
                    <div class="text-sm text-ink-muted">
                      chizma {{ order.cutting_result_id.slice(0, 8) }}
                    </div>
                  </div>
                  <div class="client-row-meta">{{ formatTiyin(order.subtotal_cutting_tiyin) }}</div>
                </div>
                <div class="client-row-item">
                  <div>
                    <div class="client-row-name">Material</div>
                    <div class="text-sm text-ink-muted">ustaxona materiali</div>
                  </div>
                  <div class="client-row-meta">
                    {{ formatTiyin(order.subtotal_materials_tiyin) }}
                  </div>
                </div>
                <div v-if="order.subtotal_edge_banding_tiyin > 0" class="client-row-item">
                  <div>
                    <div class="client-row-name">Krom</div>
                    <div class="text-sm text-ink-muted">material + xizmat</div>
                  </div>
                  <div class="client-row-meta">
                    {{ formatTiyin(order.subtotal_edge_banding_tiyin) }}
                  </div>
                </div>
                <div v-if="order.discount_tiyin > 0" class="client-row-item">
                  <div>
                    <div class="client-row-name">Chegirma</div>
                    <div class="text-sm text-ink-muted">{{ order.discount_reason ?? '' }}</div>
                  </div>
                  <div class="client-row-meta text-success">
                    - {{ formatTiyin(order.discount_tiyin) }}
                  </div>
                </div>
              </div>
            </div>

            <div class="client-card">
              <div class="client-card-h"><h2>Narx</h2></div>
              <div class="client-card-b">
                <div class="rounded-lg border border-hairline bg-sunk p-4 text-sm">
                  <div class="flex justify-between py-1 text-ink-soft">
                    <span>Kesish xizmati</span
                    ><span class="font-mono text-ink">{{
                      formatTiyin(order.subtotal_cutting_tiyin)
                    }}</span>
                  </div>
                  <div class="flex justify-between py-1 text-ink-soft">
                    <span>Material</span
                    ><span class="font-mono text-ink">{{
                      formatTiyin(order.subtotal_materials_tiyin)
                    }}</span>
                  </div>
                  <div
                    v-if="order.subtotal_edge_banding_tiyin > 0"
                    class="flex justify-between py-1 text-ink-soft"
                  >
                    <span>Krom</span
                    ><span class="font-mono text-ink">{{
                      formatTiyin(order.subtotal_edge_banding_tiyin)
                    }}</span>
                  </div>
                  <div
                    v-if="order.discount_tiyin > 0"
                    class="flex justify-between py-1 text-success"
                  >
                    <span>Chegirma</span
                    ><span class="font-mono">- {{ formatTiyin(order.discount_tiyin) }}</span>
                  </div>
                  <div
                    class="mt-2 flex justify-between border-t border-ink pt-3 font-bold text-ink"
                  >
                    <span>Jami</span
                    ><span class="font-serif text-2xl">{{ formatTiyin(order.total_tiyin) }}</span>
                  </div>
                </div>
                <p class="mt-3 text-sm text-ink-muted">
                  Narx buyurtma berilganda qat'iy belgilangan — keyin o'zgarmaydi.
                </p>
              </div>
            </div>

            <div class="client-card">
              <div class="client-card-h"><h2>Olib ketish</h2></div>
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
                  <div class="client-row-name">Aloqa</div>
                  <div class="client-row-meta">
                    {{ order.contact_name }} · {{ order.contact_phone }}
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section v-else-if="activeTab === 'cutting'" class="client-card">
            <div class="client-card-h">
              <h2>Chizma</h2>
              <button
                v-if="result"
                type="button"
                class="text-sm font-bold text-accent"
                @click="orders.downloadClientPdf(order.id)"
              >
                PDF olish →
              </button>
            </div>
            <div class="client-card-b">
              <div v-if="!result" class="text-sm text-ink-muted">Chizma natijasi topilmadi.</div>
              <template v-else>
                <div class="mb-4 grid gap-3 sm:grid-cols-3">
                  <div class="rounded-md bg-sunk p-3">
                    <div class="text-xs font-bold uppercase text-ink-muted">Panellar</div>
                    <div class="mt-1 text-xl font-bold text-ink">{{ totalPanels }}</div>
                  </div>
                  <div class="rounded-md bg-sunk p-3">
                    <div class="text-xs font-bold uppercase text-ink-muted">Krom</div>
                    <div class="mt-1 text-xl font-bold text-ink">{{ metres(totalEdge) }}</div>
                  </div>
                  <div class="rounded-md bg-sunk p-3">
                    <div class="text-xs font-bold uppercase text-ink-muted">Chiqim</div>
                    <div class="mt-1 text-xl font-bold text-ink">
                      {{ formatPercent(result.waste_percentage) }}
                    </div>
                  </div>
                </div>

                <div class="mb-4 flex flex-wrap gap-2">
                  <button
                    v-for="panel in result.panels"
                    :key="panel.id"
                    type="button"
                    class="mp-chip"
                    :class="panel.id === activePanel?.id ? 'bg-accent-soft text-accent' : ''"
                    @click="activePanelId = panel.id"
                  >
                    {{ panelTitle(result, panel) }}
                  </button>
                </div>

                <div class="grid gap-5 xl:grid-cols-[minmax(0,1fr)_220px]">
                  <CuttingPanelSvg
                    v-if="activePanel"
                    :result="result"
                    :panel="activePanel"
                    :active-placement-id="activePlacementId"
                    @select-placement="selectPlacement"
                  />
                  <aside v-if="activePanel">
                    <h3 class="mb-3 text-xs font-bold uppercase text-ink-muted">Qismlar</h3>
                    <div class="grid gap-2">
                      <button
                        v-for="placement in activePanel.placements"
                        :key="placement.id"
                        type="button"
                        class="rounded-md border border-hairline bg-sunk px-3 py-2 text-left font-mono text-xs text-ink"
                        :class="
                          placement.id === activePlacementId ? 'border-accent text-accent' : ''
                        "
                        @click="selectPlacement(placement)"
                      >
                        {{ placement.part_ref }} #{{ placement.part_quantity_index }}
                        <span v-if="placement.rotated" class="font-bold">R</span>
                      </button>
                    </div>
                  </aside>
                </div>
              </template>
            </div>
          </section>

          <section v-else-if="activeTab === 'finance'" class="client-card">
            <div class="client-card-h"><h2>To'lov</h2></div>
            <div class="client-card-b">
              <template v-if="financeOpen && order.settlement">
                <div class="rounded-lg border border-hairline bg-sunk p-4 text-sm">
                  <div class="flex justify-between py-1 text-ink-soft">
                    <span>Jami</span
                    ><span class="font-mono text-ink">{{
                      formatTiyin(order.settlement.total_tiyin)
                    }}</span>
                  </div>
                  <div class="flex justify-between py-1 text-ink-soft">
                    <span>To'langan</span
                    ><span class="font-mono text-success"
                      >- {{ formatTiyin(order.settlement.recorded_tiyin) }}</span
                    >
                  </div>
                  <div
                    class="mt-2 flex justify-between border-t border-ink pt-3 font-bold text-ink"
                  >
                    <span>Qoldiq</span
                    ><span class="font-serif text-2xl">{{
                      formatTiyin(order.settlement.balance_tiyin)
                    }}</span>
                  </div>
                </div>
                <p class="mt-3 text-sm text-ink-muted">
                  To'lov ustaxonada qabul qilinadi. Agar to'lov bo'yicha nomuvofiqlik bo'lsa —
                  to'lov bo'yicha ustaxonaga murojaat qiling.
                </p>
              </template>
              <div v-else class="client-empty border-0 !p-8">
                <div class="client-empty-icon">L</div>
                <h3>To'lov ma'lumotlari hali yopiq</h3>
                <p>To'lov ma'lumotlari buyurtma tayyor bo'lganda ochiladi.</p>
              </div>
            </div>
          </section>

          <section v-else class="client-card">
            <div class="client-card-h"><h2>Holatlar tarixi</h2></div>
            <div class="client-card-b">
              <ol class="relative ml-4 grid gap-4 border-l-2 border-hairline pl-5">
                <li v-for="event in order.events" :key="event.id" class="relative">
                  <span class="absolute -left-[27px] top-1 size-3 rounded-full bg-accent"></span>
                  <div class="font-bold text-ink">
                    {{ event.from_status ? clientStatusLabel[event.from_status] : 'Yaratildi' }}
                    →
                    {{ clientStatusLabel[event.to_status] }}
                  </div>
                  <p v-if="event.reason" class="mt-1 text-sm text-ink-soft">{{ event.reason }}</p>
                  <div class="mt-1 font-mono text-xs text-ink-muted">
                    {{ formatRelativeDate(event.changed_at) }}
                  </div>
                </li>
              </ol>
            </div>
          </section>
        </div>

        <aside class="grid gap-4 self-start">
          <section class="client-card">
            <div class="client-card-h"><h2 class="!text-base">Holat</h2></div>
            <div class="client-card-b">
              <div class="grid gap-3">
                <div
                  v-for="(label, index) in clientPhaseLabels"
                  :key="label"
                  class="flex items-center gap-3"
                >
                  <span
                    class="size-3 rounded-full border-2"
                    :class="
                      phaseNodeClass(index) === 'done'
                        ? 'border-accent bg-accent'
                        : phaseNodeClass(index) === 'now'
                          ? 'border-accent bg-elevated shadow-[0_0_0_4px_rgb(15_118_110_/_28%)]'
                          : 'border-hairline bg-elevated'
                    "
                  ></span>
                  <span class="text-sm font-bold text-ink">{{ label }}</span>
                </div>
              </div>
              <p v-if="statusSubtext(order.status)" class="mt-4 text-sm font-bold text-accent">
                {{ statusSubtext(order.status) }}
              </p>
            </div>
          </section>

          <section class="client-card">
            <div class="client-card-h"><h2 class="!text-base">Ustaxonaga aloqa</h2></div>
            <div class="client-card-b">
              <div class="client-row-item">
                <div class="client-row-name">{{ order.workshop_name }}</div>
                <div class="client-row-meta">{{ order.branch_phone }}</div>
              </div>
              <div class="client-row-item">
                <div>
                  <div class="client-row-name">{{ order.branch_name }}</div>
                  <div class="text-sm text-ink-muted">{{ order.branch_address }}</div>
                </div>
              </div>
            </div>
          </section>

          <section class="client-card">
            <div class="client-card-h"><h2 class="!text-base">Qismlar</h2></div>
            <div class="client-card-b">
              <div v-for="item in order.items" :key="item.id" class="client-row-item">
                <div>
                  <div class="client-row-name">{{ item.part_ref }}</div>
                  <div class="text-sm text-ink-muted">
                    {{ materialName(item.material_snapshot) }} · {{ item.length_mm }}x{{
                      item.width_mm
                    }}
                    mm · {{ item.quantity }} dona
                  </div>
                </div>
                <div class="client-row-meta">{{ formatTiyin(item.line_total_tiyin) }}</div>
              </div>
            </div>
          </section>

          <p v-if="actionError" class="rounded-md bg-danger-soft p-3 text-sm font-bold text-danger">
            {{ actionError }} · trace {{ orders.traceId ?? 'unavailable' }}
          </p>
        </aside>
      </div>
    </template>

    <ConfirmDialog
      :open="cancelDialogOpen"
      title="Buyurtmani bekor qilish"
      message="Buyurtma bekor qilinadi. Bu amal qaytarilmaydi."
      confirm-label="Bekor qilish"
      danger
      :busy="orders.actionLoading"
      :confirm-disabled="cancelReason.trim().length === 0"
      @cancel="cancelDialogOpen = false"
      @confirm="cancelOrder"
    >
      <label class="grid gap-1 text-sm font-bold text-ink">
        Sabab
        <textarea v-model="cancelReason" class="mp-input min-h-24 resize-y" />
      </label>
    </ConfirmDialog>
  </section>
</template>
