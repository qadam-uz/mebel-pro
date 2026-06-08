<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { formatDate, formatTiyin } from '@/shared/formatters'
import {
  useOrdersStore,
  workshopStatusLabel,
  type OrderStatus,
  type OrderStockWarning,
} from '@/shared/stores/orders'
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
const actionError = ref<string | null>(null)
const activePanelId = ref<string | null>(null)
const activePlacementId = ref<string | null>(null)
const reasonDialogAction = ref<'revert' | 'cancel' | null>(null)
const reasonDraft = ref('')

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

function statusTone(status: OrderStatus) {
  if (status === 'completed') return 'bg-success-soft text-success'
  if (status === 'cancelled') return 'bg-danger-soft text-danger'
  if (status === 'ready') return 'bg-info-soft text-info'
  if (status === 'cutting' || status === 'edge_banding') return 'bg-accent-soft text-accent'
  return 'bg-warning-soft text-warning'
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
    actionError.value = orders.error ?? 'order_action_failed'
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
  await run(() => orders.markCollected(current.id, current.version))
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
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <RouterLink :to="rolePath('/workshop/orders')" class="text-sm font-bold text-accent">
          Orders
        </RouterLink>
        <h1 class="mt-2 font-serif text-3xl font-semibold text-ink">Order detail</h1>
        <p v-if="order" class="mt-2 text-base text-ink-soft">
          {{ order.order_number }} · {{ order.contact_name }} · {{ order.branch_name }}
        </p>
      </div>
      <div v-if="order" class="flex flex-wrap gap-2">
        <RouterLink
          v-if="order.status === 'cutting'"
          :to="rolePath('/workshop/cutting')"
          class="mp-button mp-button-outline"
        >
          Cutting queue
        </RouterLink>
        <RouterLink
          v-if="order.status === 'edge_banding'"
          :to="rolePath('/workshop/banding')"
          class="mp-button mp-button-outline"
        >
          Banding queue
        </RouterLink>
        <button
          type="button"
          class="mp-button mp-button-primary"
          @click="orders.downloadWorkshopPdf(order.id)"
        >
          Download PDF
        </button>
      </div>
    </div>

    <section v-if="orders.loading" class="mp-surface p-5" aria-live="polite">Loading order</section>
    <section v-else-if="orders.error" class="mp-surface p-5 text-danger">
      Order could not be loaded. trace {{ orders.traceId ?? 'unavailable' }}
    </section>
    <section v-else-if="!order" class="mp-surface p-5">
      <div class="rounded-lg border border-dashed border-hairline-strong bg-sunk p-5">
        <h2 class="font-serif text-2xl font-semibold text-ink">Order not found</h2>
        <p class="mt-2 text-sm text-ink-soft">Open the order list and try again.</p>
      </div>
    </section>

    <template v-else>
      <section class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div class="space-y-4">
          <section class="mp-surface p-5">
            <div class="flex flex-wrap items-start justify-between gap-4">
              <div>
                <span class="mp-chip" :class="statusTone(order.status)">
                  <span class="mp-dot" aria-hidden="true"></span>
                  {{ workshopStatusLabel[order.status] }}
                </span>
                <h2 class="mt-4 font-serif text-xl font-semibold text-ink">
                  {{ order.order_number }}
                </h2>
                <p class="mt-1 text-sm text-ink-soft">
                  Created {{ formatDate(order.created_at) }} · version {{ order.version }}
                </p>
              </div>
              <div class="text-right">
                <div class="font-mono text-2xl font-extrabold text-accent">
                  {{ formatTiyin(order.total_tiyin) }}
                </div>
                <div v-if="order.discount_tiyin > 0" class="mt-1 text-sm font-bold text-success">
                  discount {{ formatTiyin(order.discount_tiyin) }}
                </div>
              </div>
            </div>
          </section>

          <section class="mp-surface overflow-hidden">
            <div class="border-b border-hairline px-5 py-4">
              <h2 class="font-serif text-xl font-semibold text-ink">Production</h2>
              <p class="mt-1 text-sm text-ink-soft">
                Assignments, credited workers, and stock-sensitive transitions.
              </p>
            </div>
            <div class="grid gap-3 p-5 md:grid-cols-2">
              <div class="rounded-md bg-sunk p-4">
                <div class="text-xs font-bold uppercase text-ink-muted">Cutter</div>
                <div class="mt-1 font-bold text-ink">
                  {{ workerName(order.assigned_cutter_user_id) }}
                </div>
                <p class="mt-1 text-sm text-ink-soft">
                  {{
                    order.cut_completed_at
                      ? `done ${formatDate(order.cut_completed_at)}`
                      : 'not done'
                  }}
                </p>
              </div>
              <div class="rounded-md bg-sunk p-4">
                <div class="text-xs font-bold uppercase text-ink-muted">Edge bander</div>
                <div class="mt-1 font-bold text-ink">
                  {{
                    order.has_banding ? workerName(order.assigned_edger_user_id) : 'Not required'
                  }}
                </div>
                <p class="mt-1 text-sm text-ink-soft">
                  {{
                    order.edge_completed_at
                      ? `done ${formatDate(order.edge_completed_at)}`
                      : order.has_banding
                        ? 'not done'
                        : 'no edge step'
                  }}
                </p>
              </div>
            </div>
          </section>

          <section v-if="order.stock_warnings.length > 0" class="mp-surface overflow-hidden">
            <div class="border-b border-hairline px-5 py-4">
              <h2 class="font-serif text-xl font-semibold text-ink">Stock warnings</h2>
            </div>
            <div class="divide-y divide-hairline">
              <article
                v-for="warning in order.stock_warnings"
                :key="`${warning.material_id}-${warning.kind}`"
                class="grid gap-3 px-5 py-4 md:grid-cols-[1fr_auto]"
              >
                <div>
                  <div class="font-bold text-warning">{{ warning.material_name }}</div>
                  <p class="mt-1 text-sm text-ink-soft">
                    Required {{ warningQuantity(warning, 'required') }} · on hand
                    {{ warningQuantity(warning, 'on_hand') }}
                  </p>
                </div>
                <div class="font-mono text-sm font-bold text-warning">
                  after {{ warningQuantity(warning, 'projected_after') }}
                </div>
              </article>
            </div>
          </section>

          <section class="mp-surface overflow-hidden">
            <div class="border-b border-hairline px-5 py-4">
              <h2 class="font-serif text-xl font-semibold text-ink">Cutting result</h2>
            </div>
            <div v-if="!result" class="p-5 text-sm text-ink-soft">
              Cutting result is unavailable.
            </div>
            <div v-else class="grid gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_300px]">
              <div class="min-w-0 space-y-4">
                <div class="grid gap-3 sm:grid-cols-4">
                  <div class="rounded-md bg-sunk p-3">
                    <div class="text-xs font-bold uppercase text-ink-muted">Panels</div>
                    <div class="mt-1 text-xl font-extrabold text-ink">{{ totalPanels }}</div>
                  </div>
                  <div class="rounded-md bg-sunk p-3">
                    <div class="text-xs font-bold uppercase text-ink-muted">Cut length</div>
                    <div class="mt-1 text-xl font-extrabold text-ink">
                      {{ metres(result.total_cut_length_mm) }}
                    </div>
                  </div>
                  <div class="rounded-md bg-sunk p-3">
                    <div class="text-xs font-bold uppercase text-ink-muted">Edge</div>
                    <div class="mt-1 text-xl font-extrabold text-ink">
                      {{ metres(result.total_edge_length_mm) }}
                    </div>
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
              <h2 class="font-serif text-xl font-semibold text-ink">Status events</h2>
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
                    {{ event.from_status ? workshopStatusLabel[event.from_status] : 'Created' }}
                    <span class="text-ink-muted">→</span>
                    {{ workshopStatusLabel[event.to_status] }}
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
            <h2 class="font-serif text-xl font-semibold text-ink">Actions</h2>
            <div class="mt-4 space-y-3">
              <template v-if="order.status === 'new'">
                <button
                  type="button"
                  class="mp-button mp-button-primary w-full"
                  :disabled="orders.actionLoading"
                  @click="approve"
                >
                  Approve
                </button>
              </template>

              <template v-else-if="order.status === 'confirmed'">
                <FormSelect
                  v-model="cutterId"
                  label="Cutter"
                  :options="workerOptions"
                  :disabled="workerOptions.length === 0"
                />
                <FormSelect
                  v-if="order.has_banding"
                  v-model="edgerId"
                  label="Edge bander"
                  :options="workerOptions"
                  :disabled="workerOptions.length === 0"
                />
                <button
                  type="button"
                  class="mp-button mp-button-primary w-full"
                  :disabled="orders.actionLoading || !cutterId || (order.has_banding && !edgerId)"
                  @click="assignWorkers"
                >
                  Assign and start
                </button>
              </template>

              <template v-else-if="order.status === 'cutting'">
                <FormSelect
                  v-if="workerOptions.length > 0"
                  v-model="completedById"
                  label="Credited cutter"
                  :options="workerOptions"
                />
                <button
                  type="button"
                  class="mp-button mp-button-primary w-full"
                  :disabled="orders.actionLoading"
                  @click="completeCutting"
                >
                  Mark cutting done
                </button>
              </template>

              <template v-else-if="order.status === 'edge_banding'">
                <FormSelect
                  v-if="workerOptions.length > 0"
                  v-model="completedById"
                  label="Credited bander"
                  :options="workerOptions"
                />
                <button
                  type="button"
                  class="mp-button mp-button-primary w-full"
                  :disabled="orders.actionLoading"
                  @click="completeBanding"
                >
                  Mark banding done
                </button>
              </template>

              <template v-else-if="order.status === 'ready'">
                <button
                  type="button"
                  class="mp-button mp-button-primary w-full"
                  :disabled="orders.actionLoading"
                  @click="markCollected"
                >
                  Mark collected
                </button>
              </template>

              <p
                v-if="order.status === 'completed' || order.status === 'cancelled'"
                class="rounded-md bg-sunk p-3 text-sm text-ink-soft"
              >
                No further production actions are available.
              </p>

              <div
                v-if="['cutting', 'edge_banding', 'ready'].includes(order.status)"
                class="grid gap-2"
              >
                <button
                  type="button"
                  class="mp-button mp-button-outline w-full"
                  :disabled="orders.actionLoading"
                  @click="requestRevertOrder"
                >
                  Revert one step
                </button>
              </div>

              <button
                v-if="!['completed', 'cancelled'].includes(order.status)"
                type="button"
                class="mp-button mp-button-outline w-full text-danger"
                :disabled="orders.actionLoading"
                @click="requestCancelOrder"
              >
                Cancel order
              </button>
            </div>
            <p v-if="actionError" class="mt-4 rounded-md bg-danger-soft p-3 text-sm text-danger">
              {{ actionError }} · trace {{ orders.traceId ?? 'unavailable' }}
            </p>
          </section>

          <section
            v-if="order.status === 'new' || order.status === 'confirmed'"
            class="mp-surface p-5"
          >
            <h2 class="font-serif text-xl font-semibold text-ink">Discount</h2>
            <div class="mt-4 grid gap-3">
              <FormSelect v-model="discountKind" label="Kind" :options="discountOptions" />
              <label class="grid gap-1 text-sm font-bold text-ink">
                Value
                <input v-model="discountValue" class="mp-input" inputmode="numeric" />
              </label>
              <label class="grid gap-1 text-sm font-bold text-ink">
                Reason
                <input v-model="discountReason" class="mp-input" />
              </label>
              <button
                type="button"
                class="mp-button mp-button-outline"
                :disabled="orders.actionLoading"
                @click="applyDiscount"
              >
                Apply discount
              </button>
            </div>
          </section>

          <section class="mp-surface p-5">
            <h2 class="font-serif text-xl font-semibold text-ink">Contact</h2>
            <div class="mt-4 grid gap-2 text-sm">
              <div class="flex justify-between gap-3">
                <span class="text-ink-soft">Client</span>
                <span class="font-bold text-ink">{{ order.client_name }}</span>
              </div>
              <div class="flex justify-between gap-3">
                <span class="text-ink-soft">Order contact</span>
                <span class="font-bold text-ink">{{ order.contact_name }}</span>
              </div>
              <div class="flex justify-between gap-3">
                <span class="text-ink-soft">Phone</span>
                <span class="font-mono font-bold text-ink">{{ order.contact_phone }}</span>
              </div>
            </div>
          </section>

          <section class="mp-surface p-5">
            <h2 class="font-serif text-xl font-semibold text-ink">Internal note</h2>
            <label class="mt-4 grid gap-1 text-sm font-bold text-ink">
              Note
              <textarea v-model="noteDraft" class="mp-input min-h-28 resize-y" />
            </label>
            <button
              type="button"
              class="mp-button mp-button-outline mt-3 w-full"
              :disabled="orders.actionLoading"
              @click="saveNote"
            >
              Save note
            </button>
          </section>
        </aside>
      </section>
    </template>

    <ConfirmDialog
      :open="reasonDialogAction !== null"
      :title="reasonDialogAction === 'revert' ? 'Revert order' : 'Cancel order'"
      :message="
        reasonDialogAction === 'revert'
          ? 'Record the correction reason before moving this order back one step.'
          : 'Record the cancellation reason before closing this order.'
      "
      :confirm-label="reasonDialogAction === 'revert' ? 'Revert one step' : 'Cancel order'"
      :danger="reasonDialogAction === 'cancel'"
      :busy="orders.actionLoading"
      :confirm-disabled="reasonDraft.trim().length === 0"
      @cancel="reasonDialogAction = null"
      @confirm="confirmReasonedAction"
    >
      <label class="grid gap-1 text-sm font-bold text-ink">
        Reason
        <textarea v-model="reasonDraft" class="mp-input min-h-24 resize-y" />
      </label>
    </ConfirmDialog>
  </section>
</template>
