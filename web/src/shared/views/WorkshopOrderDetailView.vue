<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import { orderPillClass, workshopStatusUz } from '@/shared/app/workshopUi'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { formatDate, formatTiyin } from '@/shared/formatters'
import { useOrdersStore, type OrderItem, type OrderStockWarning } from '@/shared/stores/orders'
import {
  metres,
  type CuttingPanel,
  type CuttingPlacement,
  type CuttingResult,
} from '@/shared/stores/cutting'

const route = useRoute()
const rolePath = useRolePath()
const orders = useOrdersStore()
const orderId = computed(() => String(route.params.order_id))
const cutterId = ref<string | null>(null)
const edgerId = ref<string | null>(null)
const completedById = ref<string | null>(null)
const noteDraft = ref('')
const discountKind = ref('fixed')
const discountValue = ref('')
const discountReason = ref('')
const activeTab = ref<'overview' | 'cutting' | 'timeline'>('overview')
const actionError = ref<string | null>(null)
const activePanelId = ref<string | null>(null)
const activePlacementId = ref<string | null>(null)
const reasonDialogAction = ref<'revert' | 'cancel' | null>(null)
const reasonDraft = ref('')
const markCollectedOpen = ref(false)

const order = computed(() => orders.currentOrder)
const result = computed(() => order.value?.cutting_result ?? null)
const workerOptions = computed<ChoiceOption[]>(() =>
  orders.workerOptions.map((worker) => ({
    value: worker.id,
    label: worker.full_name,
    meta: worker.is_owner ? 'owner' : 'production',
  })),
)
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
const discountOptions: ChoiceOption[] = [
  { value: 'fixed', label: 'Fixed', meta: 'value in tiyin' },
  { value: 'percent', label: 'Percent', meta: '0-100 percent' },
]

function snapshotName(item: OrderItem) {
  const value = item.material_snapshot.name
  return typeof value === 'string' ? value : item.material_id.slice(0, 8)
}

function edgeSummary(item: OrderItem) {
  const sides = [
    ['T', item.edge_top],
    ['B', item.edge_bottom],
    ['L', item.edge_left],
    ['R', item.edge_right],
  ]
    .filter(([, edge]) => edge)
    .map(([side, edge]) => {
      const data = edge as Record<string, unknown>
      const source = data.source === 'own' ? ' · mijoz' : ''
      return `${side}${source}`
    })
  return sides.length > 0 ? `Krom · ${sides.join(' · ')}` : 'krom yoq'
}

function workerName(id: string | null) {
  if (!id) return 'Unassigned'
  return (
    orders.workerOptions.find((worker) => worker.id === id)?.full_name ?? `user ${id.slice(0, 8)}`
  )
}

function warningQuantity(
  warning: OrderStockWarning,
  key: 'on_hand' | 'required' | 'projected_after',
) {
  const value = warning[key]
  return warning.kind === 'edge' ? metres(value) : `${value} pcs`
}

function panelTitle(current: CuttingResult, panel: CuttingPanel) {
  const snapshot = current.material_snapshots[panel.material_id]
  return `${String(snapshot?.name ?? 'Panel')} · ${panel.panel_index}`
}

function selectPlacement(placement: CuttingPlacement) {
  activePlacementId.value = placement.id
}

async function loadDetail() {
  await orders.loadWorkshopOrder(orderId.value)
  const current = orders.currentOrder
  if (current) await orders.loadWorkers(current.branch_id).catch(() => undefined)
}

async function run(action: () => Promise<unknown>) {
  actionError.value = null
  try {
    await action()
    return true
  } catch {
    actionError.value = orders.actionError ?? 'order_action_failed'
    return false
  }
}

async function approve() {
  const current = order.value
  if (!current) return
  await run(() => orders.approve(current.id, current.version))
}

async function assignWorkers() {
  const current = order.value
  if (!current) return
  if (!cutterId.value) {
    actionError.value = 'Choose a cutter.'
    return
  }
  if (current.has_banding && !edgerId.value) {
    actionError.value = 'Choose an edge bander.'
    return
  }
  await run(() =>
    orders.assign(current.id, {
      version: current.version,
      cutter_user_id: cutterId.value,
      edger_user_id: current.has_banding ? edgerId.value : null,
    }),
  )
}

async function completeCutting() {
  const current = order.value
  if (!current) return
  await run(() =>
    orders.cuttingDone(current.id, {
      version: current.version,
      completed_by_user_id: completedById.value || current.assigned_cutter_user_id,
    }),
  )
}

async function completeBanding() {
  const current = order.value
  if (!current) return
  await run(() =>
    orders.bandingDone(current.id, {
      version: current.version,
      completed_by_user_id: completedById.value || current.assigned_edger_user_id,
    }),
  )
}

async function markCollected() {
  const current = order.value
  if (!current) return
  const ok = await run(() => orders.markCollected(current.id, current.version))
  if (ok) markCollectedOpen.value = false
}

function requestRevertOrder() {
  reasonDraft.value = 'Production correction'
  reasonDialogAction.value = 'revert'
}

function requestCancelOrder() {
  reasonDraft.value = 'Workshop cancelled by request'
  reasonDialogAction.value = 'cancel'
}

async function confirmReasonedAction() {
  const current = order.value
  if (!current) return
  const action = reasonDialogAction.value
  const reason = reasonDraft.value.trim()
  if (!action || !reason) return
  const ok =
    action === 'revert'
      ? await run(() => orders.revert(current.id, current.version, reason))
      : await run(() => orders.cancelWorkshopOrder(current.id, current.version, reason))
  if (ok) reasonDialogAction.value = null
}

async function applyDiscount() {
  const current = order.value
  if (!current) return
  const value = Number(discountValue.value)
  if (!Number.isInteger(value) || value < 0) {
    actionError.value = 'Enter a non-negative integer discount value.'
    return
  }
  if (!discountReason.value.trim()) {
    actionError.value = 'Enter a discount reason.'
    return
  }
  await run(() =>
    orders.discount(current.id, {
      version: current.version,
      kind: discountKind.value === 'percent' ? 'percent' : 'fixed',
      value,
      reason: discountReason.value,
    }),
  )
}

async function saveNote() {
  const current = order.value
  if (!current) return
  await run(() => orders.updateNote(current.id, noteDraft.value.trim() || null))
}

watch(
  order,
  (value) => {
    if (!value) return
    cutterId.value = value.assigned_cutter_user_id
    edgerId.value = value.assigned_edger_user_id
    completedById.value =
      value.status === 'edge_banding' ? value.assigned_edger_user_id : value.assigned_cutter_user_id
    noteDraft.value = value.note_workshop ?? ''
    if (value.discount_tiyin > 0) discountValue.value = String(value.discount_tiyin)
  },
  { immediate: true },
)

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

onMounted(loadDetail)
</script>

<template>
  <section>
    <RouterLink :to="rolePath('/workshop/orders')" class="back">← Buyurtmalar</RouterLink>

    <section v-if="orders.loading" class="card p-5" aria-live="polite">
      <div class="grid gap-3">
        <span class="sk-line"></span>
        <span class="sk-line"></span>
        <span class="sk-line"></span>
      </div>
    </section>
    <section v-else-if="orders.error" class="st-error">
      <h3>Buyurtmani yuklab bo'lmadi</h3>
      <p>trace_id: {{ orders.traceId ?? 'unavailable' }}</p>
    </section>
    <section v-else-if="!order" class="st-empty">
      <h3>Buyurtma topilmadi</h3>
      <p>Buyurtmalar ro'yxatidan qayta ochib ko'ring.</p>
    </section>

    <template v-else>
      <div class="od-head">
        <h1>{{ order.order_number }}</h1>
        <div class="id">
          {{ order.branch_name }} · {{ formatDate(order.created_at) }} · v{{ order.version }}
        </div>
        <div class="mt-3 flex flex-wrap items-center gap-3 text-sm text-ink-soft">
          <span :class="orderPillClass(order.status)">
            <span class="pd"></span>{{ workshopStatusUz[order.status] }}
          </span>
          <span
            >Mijoz: <b class="text-ink">{{ order.contact_name }}</b> ·
            {{ order.contact_phone }}</span
          >
          <span class="font-mono text-ink-muted">{{ formatTiyin(order.total_tiyin) }}</span>
        </div>
        <div class="actions">
          <RouterLink
            v-if="order.status === 'cutting'"
            :to="rolePath('/workshop/cutting')"
            class="mp-button mp-button-outline min-h-9 px-3 text-xs"
          >
            Kesish navbati
          </RouterLink>
          <RouterLink
            v-if="order.status === 'edge_banding'"
            :to="rolePath('/workshop/banding')"
            class="mp-button mp-button-outline min-h-9 px-3 text-xs"
          >
            Krom navbati
          </RouterLink>
          <button
            type="button"
            class="mp-button mp-button-outline min-h-9 px-3 text-xs"
            @click="orders.downloadWorkshopPdf(order.id)"
          >
            Chizma PDF
          </button>
        </div>
      </div>

      <div class="tabs">
        <button
          class="tab"
          :class="{ on: activeTab === 'overview' }"
          type="button"
          @click="activeTab = 'overview'"
        >
          Umumiy
        </button>
        <button
          class="tab"
          :class="{ on: activeTab === 'cutting' }"
          type="button"
          @click="activeTab = 'cutting'"
        >
          Chizma
        </button>
        <button
          class="tab"
          :class="{ on: activeTab === 'timeline' }"
          type="button"
          @click="activeTab = 'timeline'"
        >
          Tarix
        </button>
      </div>

      <div class="od-grid">
        <main class="min-w-0">
          <section v-if="activeTab === 'overview'" class="grid gap-4">
            <div v-if="order.stock_warnings.length > 0" class="banner warn">
              <div class="grow">
                Kesishdan keyin past zaxira:
                <b>
                  {{
                    order.stock_warnings
                      .map(
                        (warning) =>
                          `${warning.material_name} → ${warningQuantity(warning, 'projected_after')}`,
                      )
                      .join(' · ')
                  }}
                </b>
              </div>
            </div>

            <section class="card">
              <div class="card-h"><h2>Buyurtma tarkibi</h2></div>
              <div class="card-b">
                <div v-for="item in order.items" :key="item.id" class="row-item">
                  <div>
                    <div class="nm">
                      {{ snapshotName(item) }} · {{ item.length_mm }}x{{ item.width_mm }}
                    </div>
                    <small class="text-ink-muted"
                      >{{ item.material_source === 'own' ? 'mijoz paneli' : 'ustaxona paneli' }} ·
                      {{ edgeSummary(item) }}</small
                    >
                  </div>
                  <div class="meta">{{ item.quantity }} dona</div>
                </div>
                <div v-if="order.items.length === 0" class="st-empty !border-0 !py-8">
                  <h3>Chizma qismi yo'q</h3>
                </div>
              </div>
            </section>

            <section class="card">
              <div class="card-h"><h2>Narx tafsiloti</h2></div>
              <div class="card-b">
                <div class="row-item">
                  <div><div class="nm">Kesish xizmati</div></div>
                  <div class="meta">{{ formatTiyin(order.subtotal_cutting_tiyin) }}</div>
                </div>
                <div class="row-item">
                  <div><div class="nm">Material</div></div>
                  <div class="meta">{{ formatTiyin(order.subtotal_materials_tiyin) }}</div>
                </div>
                <div class="row-item">
                  <div>
                    <div class="nm">Krom</div>
                    <small class="text-ink-muted">{{
                      order.subtotal_edge_banding_tiyin > 0
                        ? 'material + xizmat'
                        : "bu buyurtmada krom yo'q"
                    }}</small>
                  </div>
                  <div class="meta">
                    {{
                      order.subtotal_edge_banding_tiyin > 0
                        ? formatTiyin(order.subtotal_edge_banding_tiyin)
                        : '—'
                    }}
                  </div>
                </div>
                <div v-if="order.discount_tiyin > 0" class="row-item">
                  <div>
                    <div class="nm">Chegirma</div>
                    <small class="text-ink-muted">{{ order.discount_reason }}</small>
                  </div>
                  <div class="meta">- {{ formatTiyin(order.discount_tiyin) }}</div>
                </div>
                <div class="row-item font-extrabold">
                  <div><div class="nm">Jami</div></div>
                  <div class="meta">{{ formatTiyin(order.total_tiyin) }}</div>
                </div>
              </div>
            </section>

            <section v-if="order.settlement" class="card">
              <div class="card-h">
                <h2>To'lov holati <span class="pill p-dn ml-1">faqat o'qish</span></h2>
              </div>
              <div class="card-b">
                <div class="ro-figure">
                  <span>Jami summa</span
                  ><span class="v">{{ formatTiyin(order.settlement.total_tiyin) }}</span>
                </div>
                <div class="ro-figure">
                  <span>Yozilgan to'lov</span
                  ><span class="v success-text">{{
                    formatTiyin(order.settlement.recorded_tiyin)
                  }}</span>
                </div>
                <div class="ro-figure">
                  <span>Qoldiq</span
                  ><span class="v">{{ formatTiyin(order.settlement.balance_tiyin) }}</span>
                </div>
              </div>
            </section>

            <section class="card">
              <div class="card-h"><h2>Ishlab chiqarish</h2></div>
              <div class="card-b">
                <div class="row-item">
                  <div>
                    <div class="nm">Kesuvchi</div>
                    <small class="text-ink-muted">{{
                      order.cut_completed_at
                        ? `Bajardi · ${formatDate(order.cut_completed_at)}`
                        : order.assigned_cutter_user_id
                          ? 'tayinlangan'
                          : 'tayinlanmagan'
                    }}</small>
                  </div>
                  <div class="meta">
                    {{ workerName(order.cutter_user_id ?? order.assigned_cutter_user_id) }}
                  </div>
                </div>
                <div
                  v-if="order.cut_count_snapshot !== null || order.panels_used_snapshot !== null"
                  class="row-item"
                >
                  <div><div class="nm">Kesilgan</div></div>
                  <div class="meta">
                    {{ order.cut_count_snapshot ?? 0 }} ta ·
                    {{ order.panels_used_snapshot ?? 0 }} panel
                  </div>
                </div>
                <div class="row-item">
                  <div>
                    <div class="nm">Krom yopishtiruvchi</div>
                    <small class="text-ink-muted">{{
                      order.has_banding
                        ? order.edge_completed_at
                          ? `Bajardi · ${formatDate(order.edge_completed_at)}`
                          : order.assigned_edger_user_id
                            ? 'tayinlangan'
                            : 'tayinlanmagan'
                        : "bu buyurtmada krom yo'q"
                    }}</small>
                  </div>
                  <div class="meta">
                    {{
                      order.has_banding
                        ? workerName(order.edger_user_id ?? order.assigned_edger_user_id)
                        : '—'
                    }}
                  </div>
                </div>
              </div>
            </section>

            <section class="card">
              <div class="card-h"><h2>Ichki izoh</h2></div>
              <div class="card-b">
                <textarea
                  v-model="noteDraft"
                  class="mp-input min-h-28 resize-y"
                  placeholder="Faqat ustaxona xodimlari ko'radi"
                ></textarea>
                <button
                  type="button"
                  class="mp-button mp-button-outline mt-3 min-h-9 px-3 text-xs"
                  :disabled="orders.actionLoading"
                  @click="saveNote"
                >
                  Saqlash
                </button>
              </div>
            </section>
          </section>

          <section v-else-if="activeTab === 'cutting'" class="card">
            <div class="card-h"><h2>Chizma rejasi</h2></div>
            <div v-if="!result" class="card-b">
              <div class="st-empty !border-0 !py-8"><h3>Chizma biriktirilmagan</h3></div>
            </div>
            <div v-else class="card-b grid gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
              <div class="min-w-0 space-y-4">
                <div class="grid gap-3 sm:grid-cols-4">
                  <div class="rounded-md bg-sunk p-3">
                    <div class="filter-label">Panel</div>
                    <div class="mt-1 text-xl font-extrabold">{{ totalPanels }}</div>
                  </div>
                  <div class="rounded-md bg-sunk p-3">
                    <div class="filter-label">Kesim</div>
                    <div class="mt-1 text-xl font-extrabold">
                      {{ metres(result.total_cut_length_mm) }}
                    </div>
                  </div>
                  <div class="rounded-md bg-sunk p-3">
                    <div class="filter-label">Krom</div>
                    <div class="mt-1 text-xl font-extrabold">
                      {{ metres(result.total_edge_length_mm) }}
                    </div>
                  </div>
                  <div class="rounded-md bg-sunk p-3">
                    <div class="filter-label">Qoldiq</div>
                    <div class="mt-1 text-xl font-extrabold">
                      {{ (Number(result.waste_percentage) * 100).toFixed(2) }}%
                    </div>
                  </div>
                </div>
                <div class="flex flex-wrap gap-2">
                  <button
                    v-for="panel in result.panels"
                    :key="panel.id"
                    type="button"
                    class="pill"
                    :class="panel.id === activePanel?.id ? 'p-cut' : 'p-dn'"
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
                <button
                  type="button"
                  class="mp-button mp-button-outline w-full"
                  @click="orders.downloadWorkshopPdf(order.id)"
                >
                  Chizma (PDF)
                </button>
              </div>
              <aside v-if="activePanel" class="rounded-lg border border-hairline bg-sunk p-4">
                <h3 class="text-sm font-extrabold text-ink">Qismlar</h3>
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

          <section v-else class="card">
            <div class="card-h"><h2>Holat tarixi</h2></div>
            <div class="card-b">
              <div v-if="order.events.length === 0" class="st-empty !border-0 !py-8">
                <h3>Holat tarixi hali yo'q</h3>
              </div>
              <ol v-else class="tl">
                <li
                  v-for="event in order.events"
                  :key="event.id"
                  class="step"
                  :class="event.to_status === 'cancelled' ? 'bad' : 'done'"
                >
                  <span class="when">{{ formatDate(event.changed_at) }}</span>
                  {{ event.from_status ? workshopStatusUz[event.from_status] : 'Yaratildi' }}
                  <span class="text-ink-muted">→</span>
                  {{ workshopStatusUz[event.to_status] }}
                  <span v-if="event.reason" class="block text-ink-soft">{{ event.reason }}</span>
                </li>
              </ol>
            </div>
          </section>
        </main>

        <aside class="grid content-start gap-4">
          <section class="totals">
            <div class="r">
              <span>Kesish xizmati</span
              ><span class="num">{{ formatTiyin(order.subtotal_cutting_tiyin) }}</span>
            </div>
            <div class="r">
              <span>Material</span
              ><span class="num">{{ formatTiyin(order.subtotal_materials_tiyin) }}</span>
            </div>
            <div class="r">
              <span>Krom</span
              ><span class="num">{{ formatTiyin(order.subtotal_edge_banding_tiyin) }}</span>
            </div>
            <div v-if="order.discount_tiyin > 0" class="r">
              <span>Chegirma</span
              ><span class="num">- {{ formatTiyin(order.discount_tiyin) }}</span>
            </div>
            <div class="r grand">
              <span>Jami</span><span class="num">{{ formatTiyin(order.total_tiyin) }}</span>
            </div>
          </section>

          <section class="card">
            <div class="card-h"><h2>Amallar</h2></div>
            <div class="card-b grid gap-3">
              <button
                v-if="order.status === 'new'"
                type="button"
                class="mp-button mp-button-primary w-full"
                :disabled="orders.actionLoading"
                @click="approve"
              >
                Tasdiqlash
              </button>

              <template v-else-if="order.status === 'confirmed'">
                <FormSelect
                  v-model="cutterId"
                  label="Kesuvchi"
                  :options="workerOptions"
                  :disabled="workerOptions.length === 0"
                />
                <FormSelect
                  v-if="order.has_banding"
                  v-model="edgerId"
                  label="Krom yopishtiruvchi"
                  :options="workerOptions"
                  :disabled="workerOptions.length === 0"
                />
                <button
                  type="button"
                  class="mp-button mp-button-primary w-full"
                  :disabled="orders.actionLoading || !cutterId || (order.has_banding && !edgerId)"
                  @click="assignWorkers"
                >
                  Tayinlash va boshlash
                </button>
              </template>

              <template v-else-if="order.status === 'cutting'">
                <FormSelect
                  v-if="workerOptions.length > 0"
                  v-model="completedById"
                  label="Kim bajardi"
                  :options="workerOptions"
                />
                <button
                  type="button"
                  class="mp-button mp-button-primary w-full"
                  :disabled="orders.actionLoading"
                  @click="completeCutting"
                >
                  Kesish tugadi
                </button>
              </template>

              <template v-else-if="order.status === 'edge_banding'">
                <FormSelect
                  v-if="workerOptions.length > 0"
                  v-model="completedById"
                  label="Kim bajardi"
                  :options="workerOptions"
                />
                <button
                  type="button"
                  class="mp-button mp-button-primary w-full"
                  :disabled="orders.actionLoading"
                  @click="completeBanding"
                >
                  Krom tugadi
                </button>
              </template>

              <button
                v-else-if="order.status === 'ready'"
                type="button"
                class="mp-button mp-button-primary w-full"
                :disabled="orders.actionLoading"
                @click="markCollectedOpen = true"
              >
                Mijoz olib ketdi
              </button>

              <p
                v-if="order.status === 'completed' || order.status === 'cancelled'"
                class="rounded-md bg-sunk p-3 text-sm text-ink-soft"
              >
                Bu holatda ishlab chiqarish amali yo'q.
              </p>

              <button
                v-if="['cutting', 'edge_banding', 'ready'].includes(order.status)"
                type="button"
                class="mp-button mp-button-outline w-full"
                :disabled="orders.actionLoading"
                @click="requestRevertOrder"
              >
                Bir qadam orqaga
              </button>
              <button
                v-if="!['completed', 'cancelled'].includes(order.status)"
                type="button"
                class="mp-button mp-button-outline w-full text-danger"
                :disabled="orders.actionLoading"
                @click="requestCancelOrder"
              >
                Buyurtmani bekor qilish
              </button>
              <p v-if="actionError" class="rounded-md bg-danger-soft p-3 text-sm text-danger">
                {{ actionError }} · trace {{ orders.actionTraceId ?? 'unavailable' }}
              </p>
            </div>
          </section>

          <section v-if="order.status === 'new' || order.status === 'confirmed'" class="card">
            <div class="card-h"><h2>Chegirma</h2></div>
            <div class="card-b grid gap-3">
              <FormSelect v-model="discountKind" label="Turi" :options="discountOptions" />
              <label class="field !mb-0"
                ><span>Qiymat</span
                ><input v-model="discountValue" class="mp-input" inputmode="numeric"
              /></label>
              <label class="field !mb-0"
                ><span>Sabab</span><input v-model="discountReason" class="mp-input"
              /></label>
              <button
                type="button"
                class="mp-button mp-button-outline"
                :disabled="orders.actionLoading"
                @click="applyDiscount"
              >
                Chegirma qo'shish
              </button>
            </div>
          </section>

          <section class="card">
            <div class="card-h"><h2>Mijoz</h2></div>
            <div class="card-b">
              <div class="row-item">
                <div>
                  <div class="nm">{{ order.client_name }}</div>
                </div>
                <div></div>
              </div>
              <div class="row-item">
                <div><div class="nm">Aloqa</div></div>
                <div class="meta">{{ order.contact_name }}</div>
              </div>
              <div class="row-item">
                <div><div class="nm">Telefon</div></div>
                <div class="meta">{{ order.contact_phone }}</div>
              </div>
            </div>
          </section>
        </aside>
      </div>
    </template>

    <ConfirmDialog
      :open="reasonDialogAction !== null"
      :title="reasonDialogAction === 'revert' ? 'Buyurtmani qaytarish' : 'Buyurtmani bekor qilish'"
      :message="
        reasonDialogAction === 'revert'
          ? 'Buyurtma bir qadam orqaga qaytadi. Sababni yozing.'
          : 'Buyurtma yopiladi. Bekor qilish sababini yozing.'
      "
      :confirm-label="reasonDialogAction === 'revert' ? 'Qaytarish' : 'Bekor qilish'"
      :danger="reasonDialogAction === 'cancel'"
      :busy="orders.actionLoading"
      :confirm-disabled="reasonDraft.trim().length === 0"
      @cancel="reasonDialogAction = null"
      @confirm="confirmReasonedAction"
    >
      <label class="field !mb-0">
        <span>Sabab</span>
        <textarea v-model="reasonDraft" class="mp-input min-h-24 resize-y" />
      </label>
    </ConfirmDialog>

    <ConfirmDialog
      :open="markCollectedOpen"
      title="Mijoz olib ketdimi?"
      message="Buyurtma yakuniy «topshirildi» holatiga o'tadi va ortga qaytarib bo'lmaydi."
      confirm-label="Ha, topshirildi"
      :busy="orders.actionLoading"
      @cancel="markCollectedOpen = false"
      @confirm="markCollected"
    />
  </section>
</template>
