<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import { formatDate, formatTiyin } from '@/shared/formatters'
import { clientStatusLabel, useOrdersStore, type OrderStatus } from '@/shared/stores/orders'
import {
  metres,
  type CuttingPanel,
  type CuttingPlacement,
  type CuttingResult,
} from '@/shared/stores/cutting'

const route = useRoute()
const orders = useOrdersStore()
const orderId = computed(() => String(route.params.order_id))
const isNew = computed(() => route.query.new === '1')
const activePanelId = ref<string | null>(null)
const activePlacementId = ref<string | null>(null)
const actionError = ref<string | null>(null)

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
const totalEdge = computed(() => result.value?.total_edge_length_mm ?? 0)

const phases = [
  { key: 'new', label: 'Placed' },
  { key: 'confirmed', label: 'Confirmed' },
  { key: 'production', label: 'Production' },
  { key: 'ready', label: 'Ready' },
  { key: 'completed', label: 'Collected' },
] as const
const phaseIndex: Record<OrderStatus, number> = {
  new: 0,
  confirmed: 1,
  cutting: 2,
  edge_banding: 2,
  ready: 3,
  completed: 4,
  cancelled: -1,
}

function statusTone(status: OrderStatus) {
  if (status === 'completed') return 'bg-success-soft text-success'
  if (status === 'cancelled') return 'bg-danger-soft text-danger'
  if (status === 'ready') return 'bg-info-soft text-info'
  return 'bg-warning-soft text-warning'
}

function phaseTone(index: number) {
  const current = order.value ? phaseIndex[order.value.status] : -1
  if (current < 0) return 'bg-sunk text-ink-muted'
  return index <= current ? 'bg-accent-soft text-accent' : 'bg-sunk text-ink-muted'
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

async function cancelOrder() {
  const current = order.value
  if (!current) return
  const reason = window.prompt('Cancellation reason', 'Client cancelled before confirmation')
  if (!reason?.trim()) return
  actionError.value = null
  try {
    await orders.cancelClientOrder(current.id, current.version, reason)
  } catch {
    actionError.value = orders.error ?? 'order_cancel_failed'
  }
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
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <RouterLink to="/c/orders" class="text-sm font-bold text-accent"> My orders </RouterLink>
        <h1 class="mt-2 font-serif text-3xl font-semibold text-ink">Order tracking</h1>
        <p v-if="order" class="mt-2 text-base text-ink-soft">
          {{ order.order_number }} · {{ order.branch_name }}
        </p>
      </div>
      <div v-if="order" class="flex flex-wrap gap-2">
        <button
          type="button"
          class="mp-button mp-button-outline"
          @click="orders.downloadClientPdf(order.id)"
        >
          Download PDF
        </button>
        <button
          v-if="order.status === 'new'"
          type="button"
          class="mp-button mp-button-outline text-danger"
          :disabled="orders.actionLoading"
          @click="cancelOrder"
        >
          Cancel order
        </button>
      </div>
    </div>

    <section v-if="isNew && order" class="rounded-lg bg-success-soft p-4 text-success">
      <div class="font-extrabold">Order placed</div>
      <p class="mt-1 text-sm">The workshop now has the frozen cutting plan and contact snapshot.</p>
    </section>

    <section v-if="orders.loading" class="mp-surface p-5" aria-live="polite">Loading order</section>
    <section v-else-if="orders.error" class="mp-surface p-5 text-danger">
      Order could not be loaded. trace {{ orders.traceId ?? 'unavailable' }}
    </section>
    <section v-else-if="!order" class="mp-surface p-5">
      <div class="rounded-lg border border-dashed border-hairline-strong bg-sunk p-5">
        <h2 class="font-serif text-2xl font-semibold text-ink">Order not found</h2>
        <p class="mt-2 text-sm text-ink-soft">Open your order list and try again.</p>
      </div>
    </section>

    <template v-else>
      <section class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div class="space-y-4">
          <section class="mp-surface p-5">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 class="font-serif text-xl font-semibold text-ink">Status</h2>
                <p class="mt-1 text-sm text-ink-soft">Current workshop stage for this order.</p>
              </div>
              <span class="mp-chip" :class="statusTone(order.status)">
                <span class="mp-dot" aria-hidden="true"></span>
                {{ clientStatusLabel[order.status] }}
              </span>
            </div>
            <div class="mt-5 grid gap-2 sm:grid-cols-5">
              <div
                v-for="(phase, index) in phases"
                :key="phase.key"
                class="rounded-md border border-hairline p-3"
                :class="phaseTone(index)"
              >
                <div class="font-mono text-xs font-extrabold">{{ index + 1 }}</div>
                <div class="mt-1 text-sm font-extrabold">{{ phase.label }}</div>
              </div>
            </div>
            <p v-if="order.status === 'cancelled'" class="mt-4 text-sm font-bold text-danger">
              This order was cancelled.
            </p>
          </section>

          <section class="mp-surface overflow-hidden">
            <div class="border-b border-hairline px-5 py-4">
              <h2 class="font-serif text-xl font-semibold text-ink">Cutting result</h2>
              <p class="mt-1 text-sm text-ink-soft">Order-bound result frozen at placement.</p>
            </div>
            <div v-if="!result" class="p-5 text-sm text-ink-soft">
              Cutting result is unavailable.
            </div>
            <div v-else class="grid gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_300px]">
              <div class="min-w-0 space-y-4">
                <div class="grid gap-3 sm:grid-cols-3">
                  <div class="rounded-md bg-sunk p-3">
                    <div class="text-xs font-bold uppercase text-ink-muted">Panels</div>
                    <div class="mt-1 text-xl font-extrabold text-ink">{{ totalPanels }}</div>
                  </div>
                  <div class="rounded-md bg-sunk p-3">
                    <div class="text-xs font-bold uppercase text-ink-muted">Edge</div>
                    <div class="mt-1 text-xl font-extrabold text-ink">{{ metres(totalEdge) }}</div>
                  </div>
                  <div class="rounded-md bg-sunk p-3">
                    <div class="text-xs font-bold uppercase text-ink-muted">Waste</div>
                    <div class="mt-1 text-xl font-extrabold text-ink">
                      {{ (Number(result.waste_percentage) * 100).toFixed(2) }}%
                    </div>
                  </div>
                </div>

                <div class="flex flex-wrap gap-2">
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

                <CuttingPanelSvg
                  v-if="activePanel"
                  :result="result"
                  :panel="activePanel"
                  :active-placement-id="activePlacementId"
                  @select-placement="selectPlacement"
                />
              </div>

              <aside v-if="activePanel" class="rounded-lg border border-hairline bg-sunk p-4">
                <h3 class="text-sm font-extrabold text-ink">Placements</h3>
                <div class="mt-3 grid gap-2">
                  <button
                    v-for="placement in activePanel.placements"
                    :key="placement.id"
                    type="button"
                    class="rounded-md border border-hairline bg-elevated px-3 py-2 text-left text-sm"
                    :class="
                      placement.id === activePlacementId ? 'border-accent text-accent' : 'text-ink'
                    "
                    @click="selectPlacement(placement)"
                  >
                    {{ placement.part_ref }} #{{ placement.part_quantity_index }}
                    <span v-if="placement.rotated" class="font-bold">R</span>
                  </button>
                </div>
              </aside>
            </div>
          </section>

          <section class="mp-surface overflow-hidden">
            <div class="border-b border-hairline px-5 py-4">
              <h2 class="font-serif text-xl font-semibold text-ink">Timeline</h2>
            </div>
            <div v-if="order.events.length === 0" class="p-5 text-sm text-ink-soft">
              No status events yet.
            </div>
            <div v-else class="divide-y divide-hairline">
              <article
                v-for="event in order.events"
                :key="event.id"
                class="grid gap-2 px-5 py-4 md:grid-cols-[1fr_auto]"
              >
                <div>
                  <div class="font-bold text-ink">
                    {{ event.from_status ? clientStatusLabel[event.from_status] : 'Created' }}
                    <span class="text-ink-muted">→</span>
                    {{ clientStatusLabel[event.to_status] }}
                  </div>
                  <p v-if="event.reason" class="mt-1 text-sm text-ink-soft">
                    {{ event.reason }}
                  </p>
                </div>
                <div class="font-mono text-xs text-ink-muted">
                  {{ formatDate(event.changed_at) }}
                </div>
              </article>
            </div>
          </section>
        </div>

        <aside class="space-y-4">
          <section class="mp-surface p-5">
            <h2 class="font-serif text-xl font-semibold text-ink">Price</h2>
            <div class="mt-4 grid gap-3 text-sm">
              <div class="flex justify-between gap-3">
                <span class="text-ink-soft">Cutting</span>
                <span class="font-mono font-bold">{{
                  formatTiyin(order.subtotal_cutting_tiyin)
                }}</span>
              </div>
              <div class="flex justify-between gap-3">
                <span class="text-ink-soft">Materials</span>
                <span class="font-mono font-bold">{{
                  formatTiyin(order.subtotal_materials_tiyin)
                }}</span>
              </div>
              <div class="flex justify-between gap-3">
                <span class="text-ink-soft">Edge banding</span>
                <span class="font-mono font-bold">
                  {{ formatTiyin(order.subtotal_edge_banding_tiyin) }}
                </span>
              </div>
              <div v-if="order.discount_tiyin > 0" class="flex justify-between gap-3">
                <span class="text-success">Discount</span>
                <span class="font-mono font-bold text-success">
                  - {{ formatTiyin(order.discount_tiyin) }}
                </span>
              </div>
              <div class="flex justify-between gap-3 border-t border-hairline pt-3">
                <span class="font-extrabold text-ink">Frozen total</span>
                <span class="font-mono text-lg font-extrabold text-accent">
                  {{ formatTiyin(order.total_tiyin) }}
                </span>
              </div>
            </div>
          </section>

          <section class="mp-surface p-5">
            <h2 class="font-serif text-xl font-semibold text-ink">Contact</h2>
            <div class="mt-4 grid gap-2 text-sm">
              <div class="flex justify-between gap-3">
                <span class="text-ink-soft">Name</span>
                <span class="font-bold text-ink">{{ order.contact_name }}</span>
              </div>
              <div class="flex justify-between gap-3">
                <span class="text-ink-soft">Phone</span>
                <span class="font-mono font-bold text-ink">{{ order.contact_phone }}</span>
              </div>
              <div class="flex justify-between gap-3">
                <span class="text-ink-soft">Branch</span>
                <span class="font-bold text-ink">{{ order.branch_name }}</span>
              </div>
            </div>
          </section>

          <section class="mp-surface overflow-hidden">
            <div class="border-b border-hairline px-5 py-4">
              <h2 class="font-serif text-xl font-semibold text-ink">Items</h2>
            </div>
            <div class="divide-y divide-hairline">
              <article v-for="item in order.items" :key="item.id" class="px-5 py-4">
                <div class="font-bold text-ink">{{ item.part_ref }}</div>
                <p class="mt-1 text-sm text-ink-soft">
                  {{ materialName(item.material_snapshot) }} · {{ item.length_mm }}x{{
                    item.width_mm
                  }}
                  mm · qty {{ item.quantity }}
                </p>
                <p class="mt-2 font-mono text-sm font-bold text-ink">
                  {{ formatTiyin(item.line_total_tiyin) }}
                </p>
              </article>
            </div>
          </section>

          <p v-if="actionError" class="rounded-md bg-danger-soft p-3 text-sm text-danger">
            {{ actionError }} · trace {{ orders.traceId ?? 'unavailable' }}
          </p>
        </aside>
      </section>
    </template>
  </section>
</template>
