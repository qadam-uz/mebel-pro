<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { sanitizeMoneyInput } from '@/shared/app/inputSanitizers'
import { useRolePath } from '@/shared/app/paths'
import {
  discountDraftFromOrder,
  orderPhaseSteps,
  orderReworkCount,
  parseDiscountDraft,
  productionTimelineDetails,
  type WorkshopDiscountKind,
} from '@/shared/app/workshopOrderDetail'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import { workshopErrorMessage, workshopStatusUz } from '@/shared/app/workshopUi'
import AppTabs from '@/shared/components/AppTabs.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { formatDate, formatTiyin } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import {
  useOrdersStore,
  type OrderDetail,
  type OrderEvent,
  type OrderItem,
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
const auth = useAuthStore()
const permissions = useWorkshopPermissions()
const toast = useToast()
const orders = useOrdersStore()
const orderId = computed(() => String(route.params.order_id))
const cutterId = ref<string | null>(null)
const edgerId = ref<string | null>(null)
const completedById = ref<string | null>(null)
const noteDraft = ref('')
const loadedOrderId = ref<string | null>(null)
const discountKind = ref<WorkshopDiscountKind>('fixed')
const discountValue = ref('')
const discountReason = ref('')
const activeTab = ref<'overview' | 'cutting' | 'timeline'>('overview')
const actionError = ref<string | null>(null)
const actionTraceId = ref<string | null>(null)
// Which single button is mid-request, so only the clicked one shows a busy
// label while orders.actionLoading still locks the rest (QAD-77).
const pendingAction = ref<string | null>(null)
const activePanelId = ref<string | null>(null)
const activePlacementId = ref<string | null>(null)
const reasonDialogAction = ref<'revert' | 'cancel' | null>(null)
const reasonDraft = ref('')
const markCollectedOpen = ref(false)
const actionPanel = ref<HTMLElement | null>(null)
const discountPanel = ref<HTMLElement | null>(null)
const discountValueInput = ref<HTMLInputElement | null>(null)
const discountError = ref<string | null>(null)

// Type-time sanitization (PhoneInput precedent) — the money charset covers both
// discount kinds (a percent is digits with an optional decimal separator).
watch(discountValue, (value) => {
  const clean = sanitizeMoneyInput(value)
  if (clean !== value) discountValue.value = clean
})

const order = computed(() => orders.currentOrder)
const result = computed(() => order.value?.cutting_result ?? null)
const canManageOrders = computed(() =>
  permissions.canOnBranch(p.manageOrders, order.value?.branch_id),
)
const canProcessProduction = computed(() =>
  permissions.canOnBranch(p.processProduction, order.value?.branch_id),
)
const canCompleteCutting = computed(() => {
  const current = order.value
  if (!current) return false
  return (
    canManageOrders.value ||
    (canProcessProduction.value && current.assigned_cutter_user_id === auth.me?.principal_id)
  )
})
const canCompleteBanding = computed(() => {
  const current = order.value
  if (!current) return false
  return (
    canManageOrders.value ||
    (canProcessProduction.value && current.assigned_edger_user_id === auth.me?.principal_id)
  )
})
const canViewSettlement = computed(() =>
  permissions.canAnyOnBranch([p.manageFinance, p.viewFinanceReports], order.value?.branch_id),
)
const hasLifecycleAction = computed(() => {
  const current = order.value
  if (!current) return false
  if (['new', 'confirmed', 'ready'].includes(current.status)) return canManageOrders.value
  if (current.status === 'cutting') return canManageOrders.value || canCompleteCutting.value
  if (current.status === 'edge_banding') return canManageOrders.value || canCompleteBanding.value
  return false
})
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
  { value: 'fixed', label: "So'm", meta: "aniq chegirma so'mda" },
  { value: 'percent', label: 'Foiz', meta: '0-100 foiz' },
]
const orderTabs: ChoiceOption[] = [
  { value: 'overview', label: 'Umumiy' },
  { value: 'cutting', label: 'Chizma' },
  { value: 'timeline', label: 'Tarix' },
]
const phaseSteps = computed(() => (order.value ? orderPhaseSteps(order.value) : []))
const reworkCount = computed(() => orderReworkCount(order.value?.events ?? []))
const isCancelled = computed(() => order.value?.status === 'cancelled')
const discountButtonLabel = computed(() =>
  order.value?.discount_tiyin ? 'Chegirmani yangilash' : "Chegirma qo'shish",
)
const noteDirty = computed(() => noteDraft.value.trim() !== (order.value?.note_workshop ?? ''))
// Cutting would oversell stock (projected balance below zero), not just dip low —
// escalate the warning banner to danger and reword it (QAD-82).
const hasShortfall = computed(
  () => order.value?.stock_warnings.some((warning) => warning.projected_after < 0) ?? false,
)
const revertTargetLabel = computed(() => {
  const current = order.value
  if (!current) return ''
  if (current.status === 'cutting') return 'tasdiqlangan holatiga'
  if (current.status === 'edge_banding') return 'kesishga'
  if (current.status === 'ready') return current.has_banding ? 'kromga' : 'kesishga'
  return ''
})
const revertButtonLabel = computed(() => {
  if (!revertTargetLabel.value) return 'Bir qadam orqaga'
  const label = `${revertTargetLabel.value} qaytarish`
  return label.charAt(0).toUpperCase() + label.slice(1)
})
const canSubmitCuttingCompletion = computed(() => {
  const current = order.value
  if (!current || !canCompleteCutting.value) return false
  return Boolean(completedById.value || current.assigned_cutter_user_id)
})
const canSubmitBandingCompletion = computed(() => {
  const current = order.value
  if (!current || !canCompleteBanding.value) return false
  return Boolean(completedById.value || current.assigned_edger_user_id)
})

function snapshotName(item: OrderItem) {
  const value = item.material_snapshot.name
  return typeof value === 'string' ? value : item.material_id.slice(0, 8)
}

function edgeCountLabel(item: OrderItem) {
  const count = edgeSideDetails(item).length
  return count > 0 ? `Krom · ${count} tomon` : "krom yo'q"
}

function edgeSideDetails(item: OrderItem) {
  return [
    { label: 'Yuqori', edge: item.edge_top, length: item.length_mm },
    { label: 'Past', edge: item.edge_bottom, length: item.length_mm },
    { label: 'Chap', edge: item.edge_left, length: item.width_mm },
    { label: "O'ng", edge: item.edge_right, length: item.width_mm },
  ]
    .filter((side) => side.edge)
    .map((side) => {
      const data = side.edge as Record<string, unknown>
      const snapshot =
        data.snapshot && typeof data.snapshot === 'object'
          ? (data.snapshot as Record<string, unknown>)
          : {}
      const thickness =
        snapshot.thickness_mm || snapshot.thickness || snapshot.size_mm
          ? `${snapshot.thickness_mm ?? snapshot.thickness ?? snapshot.size_mm} mm`
          : 'qalinlik yo‘q'
      const color =
        typeof snapshot.color === 'string' && snapshot.color ? ` · ${snapshot.color}` : ''
      const material =
        typeof snapshot.name === 'string' && snapshot.name ? ` · ${snapshot.name}` : ''
      const source = data.source === 'own' ? ' · mijoz materiali' : ''
      return `${side.label}: ${thickness}${color}${material} · ${metres(side.length * item.quantity)}${source}`
    })
}

function edgeMaterialTotal(current: OrderDetail) {
  return current.items.reduce((sum, item) => sum + item.edge_cost_tiyin, 0)
}

function edgeServiceTotal(current: OrderDetail) {
  return Math.max(current.subtotal_edge_banding_tiyin - edgeMaterialTotal(current), 0)
}

function edgeConsumedTotal(current: OrderDetail) {
  return current.planned_edge_lines.reduce((sum, line) => sum + line.consumed_mm, 0)
}

function orderDueLabel(current: OrderDetail) {
  const dueAt = (current as OrderDetail & { due_at?: string | null }).due_at
  return dueAt ? formatDate(dueAt) : 'belgilanmagan'
}

function workerName(id: string | null) {
  if (!id) return 'Tayinlanmagan'
  return orders.workerOptions.find((worker) => worker.id === id)?.full_name ?? "Noma'lum xodim"
}

function timelineProductionDetails(event: OrderEvent) {
  return productionTimelineDetails(event, (id) => workerName(id))
}

// Mark the latest event as the live phase (CB-113 ".now" dot) unless the order
// already reached a terminal state, where the final row stays done/cancelled (QAD-80).
function timelineStepClass(event: OrderEvent, index: number) {
  if (event.to_status === 'cancelled') return 'bad'
  const events = order.value?.events ?? []
  const terminal = order.value ? ['completed', 'cancelled'].includes(order.value.status) : true
  return index === events.length - 1 && !terminal ? 'now' : 'done'
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

async function run(action: () => Promise<unknown>, successMessage?: string, key?: string) {
  actionError.value = null
  actionTraceId.value = null
  if (key) pendingAction.value = key
  try {
    await action()
    if (successMessage) toast.success(successMessage)
    return true
  } catch {
    actionError.value = workshopErrorMessage(orders.actionError ?? 'order_action_failed')
    actionTraceId.value = orders.actionTraceId
    return false
  } finally {
    if (key) pendingAction.value = null
  }
}

async function focusFirstField(panel: () => HTMLElement | null) {
  await nextTick()
  const current = panel()
  current?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  const field = current?.querySelector<HTMLElement>(
    'input:not([disabled]), textarea:not([disabled]), button:not([disabled]), [role="combobox"]:not([aria-disabled="true"])',
  )
  field?.focus({ preventScroll: true })
}

async function approve() {
  const current = order.value
  if (!current || !canManageOrders.value) return
  const ok = await run(
    () => orders.approve(current.id, current.version),
    'Buyurtma tasdiqlandi.',
    'approve',
  )
  if (ok) void focusFirstField(() => actionPanel.value)
}

async function assignWorkers() {
  const current = order.value
  if (!current || !canManageOrders.value) return
  if (!cutterId.value) {
    actionError.value = 'Kesuvchini tanlang.'
    actionTraceId.value = null
    void focusFirstField(() => actionPanel.value)
    return
  }
  if (current.has_banding && !edgerId.value) {
    actionError.value = 'Krom yopishtiruvchini tanlang.'
    actionTraceId.value = null
    void focusFirstField(() => actionPanel.value)
    return
  }
  await run(
    () =>
      orders.assign(current.id, {
        version: current.version,
        cutter_user_id: cutterId.value,
        edger_user_id: current.has_banding ? edgerId.value : null,
      }),
    'Xodimlar tayinlandi.',
    'assign',
  )
}

async function assignCutterOnly() {
  const current = order.value
  if (!current || !canManageOrders.value) return
  if (!cutterId.value) {
    actionError.value = 'Kesuvchini tanlang.'
    actionTraceId.value = null
    void focusFirstField(() => actionPanel.value)
    return
  }
  await run(
    () =>
      orders.assign(current.id, {
        version: current.version,
        cutter_user_id: cutterId.value,
        edger_user_id: null,
      }),
    'Kesuvchi saqlandi.',
    'assignCutter',
  )
}

async function assignEdgerOnly() {
  const current = order.value
  if (!current || !canManageOrders.value || !current.has_banding) return
  if (!edgerId.value) {
    actionError.value = 'Krom yopishtiruvchini tanlang.'
    actionTraceId.value = null
    void focusFirstField(() => actionPanel.value)
    return
  }
  await run(
    () =>
      orders.assign(current.id, {
        version: current.version,
        cutter_user_id: null,
        edger_user_id: edgerId.value,
      }),
    'Kromchi saqlandi.',
    'assignEdger',
  )
}

async function completeCutting() {
  const current = order.value
  if (!current || !canCompleteCutting.value) return
  const completedBy = completedById.value || current.assigned_cutter_user_id
  if (!completedBy) {
    actionError.value = 'Kesishni bajargan xodimni tanlang.'
    actionTraceId.value = null
    void focusFirstField(() => actionPanel.value)
    return
  }
  await run(
    () =>
      orders.cuttingDone(current.id, {
        version: current.version,
        completed_by_user_id: completedBy,
      }),
    'Kesish yakunlandi.',
    'completeCutting',
  )
}

async function completeBanding() {
  const current = order.value
  if (!current || !canCompleteBanding.value) return
  const completedBy = completedById.value || current.assigned_edger_user_id
  if (!completedBy) {
    actionError.value = 'Krom ishini bajargan xodimni tanlang.'
    actionTraceId.value = null
    void focusFirstField(() => actionPanel.value)
    return
  }
  await run(
    () =>
      orders.bandingDone(current.id, {
        version: current.version,
        completed_by_user_id: completedBy,
      }),
    'Krom yakunlandi.',
    'completeBanding',
  )
}

async function markCollected() {
  const current = order.value
  if (!current || !canManageOrders.value) return
  const ok = await run(
    () => orders.markCollected(current.id, current.version),
    'Buyurtma topshirildi.',
  )
  if (ok) markCollectedOpen.value = false
}

function requestRevertOrder() {
  if (!canManageOrders.value) return
  // Start the reason blank so the destructive confirm isn't armed the instant the
  // dialog opens — the required-reason guard keeps confirm disabled until typed.
  reasonDraft.value = ''
  reasonDialogAction.value = 'revert'
}

function requestCancelOrder() {
  if (!canManageOrders.value) return
  reasonDraft.value = ''
  reasonDialogAction.value = 'cancel'
}

async function confirmReasonedAction() {
  const current = order.value
  if (!current || !canManageOrders.value) return
  const action = reasonDialogAction.value
  const reason = reasonDraft.value.trim()
  if (!action || !reason) return
  const ok =
    action === 'revert'
      ? await run(() => orders.revert(current.id, current.version, reason), 'Buyurtma qaytarildi.')
      : await run(
          () => orders.cancelWorkshopOrder(current.id, current.version, reason),
          'Buyurtma bekor qilindi.',
        )
  if (ok) reasonDialogAction.value = null
}

async function applyDiscount() {
  const current = order.value
  if (!current || !canManageOrders.value) return
  discountError.value = null
  const parsed = parseDiscountDraft(discountKind.value, discountValue.value, discountReason.value)
  if (!parsed.ok) {
    // Surface the validation error inside the Chegirma card, beside the field
    // the manager pressed — not in the distant Amallar error region (QAD-75).
    discountError.value = parsed.message
    void nextTick(() => {
      discountPanel.value?.scrollIntoView({ block: 'start', behavior: 'smooth' })
      discountValueInput.value?.focus({ preventScroll: true })
    })
    return
  }
  const ok = await run(
    () =>
      orders.discount(current.id, {
        version: current.version,
        ...parsed.payload,
      }),
    'Chegirma saqlandi.',
    'discount',
  )
  if (ok) discountError.value = null
}

async function removeDiscount() {
  const current = order.value
  if (!current || !canManageOrders.value || current.discount_tiyin <= 0) return
  discountError.value = null
  await run(
    () =>
      orders.discount(current.id, {
        version: current.version,
        kind: 'fixed',
        value: 0,
        reason: 'Chegirma olib tashlandi',
      }),
    'Chegirma olib tashlandi.',
    'removeDiscount',
  )
}

async function saveNote() {
  const current = order.value
  if (!current) return
  await run(
    () => orders.updateNote(current.id, noteDraft.value.trim() || null),
    'Izoh saqlandi.',
    'note',
  )
}

watch(
  order,
  (value) => {
    if (!value) return
    cutterId.value = value.assigned_cutter_user_id
    edgerId.value = value.assigned_edger_user_id
    completedById.value =
      value.status === 'edge_banding' ? value.assigned_edger_user_id : value.assigned_cutter_user_id
    // Don't clobber a half-typed note when an action reassigns the same order;
    // only reset when navigating to a different order or the field is clean (QAD-79).
    if (value.id !== loadedOrderId.value || !noteDirty.value) {
      noteDraft.value = value.note_workshop ?? ''
    }
    loadedOrderId.value = value.id
    const discountDraft = discountDraftFromOrder(value)
    discountKind.value = discountDraft.kind
    discountValue.value = discountDraft.value
    discountReason.value = discountDraft.reason
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

    <section v-if="orders.loading" class="grid gap-4" aria-busy="true" aria-live="polite">
      <div class="od-head">
        <span class="sk-line" style="height: 24px; width: 30%"></span>
        <span class="sk-line mt-3" style="width: 50%"></span>
        <span class="sk-line mt-3" style="width: 72%"></span>
      </div>
      <div class="od-grid">
        <main class="grid gap-4">
          <section class="card">
            <div class="card-h"><span class="sk-line" style="height: 16px; width: 38%"></span></div>
            <div class="card-b grid gap-3">
              <span v-for="n in 4" :key="n" class="sk-line"></span>
            </div>
          </section>
        </main>
        <aside class="grid content-start gap-4">
          <div class="totals grid gap-3">
            <span v-for="n in 4" :key="n" class="sk-line"></span>
          </div>
          <section class="card">
            <div class="card-h"><span class="sk-line" style="height: 16px; width: 45%"></span></div>
            <div class="card-b"><span class="sk-line" style="height: 40px"></span></div>
          </section>
        </aside>
      </div>
    </section>
    <section v-else-if="orders.error" class="st-error" role="alert">
      <h3>Buyurtmani yuklab bo'lmadi</h3>
      <p>Internet aloqasini tekshirib, qayta urinib ko'ring.</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        :disabled="orders.loading"
        @click="loadDetail"
      >
        Qayta urinish
      </button>
      <p class="mt-3 text-xs text-ink-muted">trace_id: {{ orders.traceId ?? 'unavailable' }}</p>
    </section>
    <section v-else-if="!order" class="st-empty">
      <h3>Buyurtma topilmadi</h3>
      <p>Buyurtmalar ro'yxatidan qayta ochib ko'ring.</p>
    </section>

    <template v-else>
      <div class="od-head-row">
        <div class="od-head">
          <h1>{{ order.order_number }}</h1>
          <div class="od-meta">
            <span
              >Mijoz: <b class="text-ink">{{ order.contact_name }}</b> ·
              {{ order.contact_phone }}</span
            >
            <span
              >Muddat: <b class="text-ink">{{ orderDueLabel(order) }}</b></span
            >
            <span
              >Jami:
              <b class="font-mono font-semibold text-ink">{{
                formatTiyin(order.total_tiyin)
              }}</b></span
            >
          </div>

          <div v-if="order.status === 'cutting' || order.status === 'edge_banding'" class="actions">
            <RouterLink
              v-if="order.status === 'cutting'"
              :to="rolePath('/workshop/cutting')"
              class="mp-button mp-button-outline min-h-11 px-3 text-xs"
            >
              Kesish navbati
            </RouterLink>
            <RouterLink
              v-if="order.status === 'edge_banding'"
              :to="rolePath('/workshop/banding')"
              class="mp-button mp-button-outline min-h-11 px-3 text-xs"
            >
              Krom navbati
            </RouterLink>
          </div>
        </div>

        <div class="od-stepper-card">
          <h2 class="od-stepper-title">Buyurtma holati</h2>
          <div class="od-stepper-body">
            <div v-if="isCancelled" class="od-cancelled">Bekor qilingan</div>
            <div v-else class="od-steps" role="list" aria-label="Buyurtma bosqichlari">
              <template v-for="(step, i) in phaseSteps" :key="step.status">
                <div
                  class="od-step"
                  :class="step.state"
                  role="listitem"
                  :aria-current="step.state === 'current' ? 'step' : undefined"
                >
                  <span class="od-dot" aria-hidden="true"></span>
                  <span class="od-lbl">{{ workshopStatusUz[step.status] }}</span>
                </div>
                <span
                  v-if="i < phaseSteps.length - 1"
                  class="od-conn"
                  :class="{ done: step.state === 'done' }"
                  aria-hidden="true"
                ></span>
              </template>
            </div>
            <p v-if="reworkCount > 0 && !isCancelled" class="od-rework">
              ↻ {{ reworkCount }} marta qaytarilgan
            </p>
          </div>
        </div>
      </div>

      <div v-if="orders.downloadError" class="banner danger mb-4" role="alert">
        <div class="grow">
          {{ orders.downloadError }} · trace_id: {{ orders.downloadTraceId ?? 'unavailable' }}
        </div>
      </div>

      <AppTabs
        v-model="activeTab"
        id-prefix="workshop-order"
        label="Buyurtma bo'limlari"
        :tabs="orderTabs"
      />

      <div class="od-grid">
        <main class="min-w-0">
          <section
            v-if="activeTab === 'overview'"
            id="workshop-order-overview-panel"
            class="grid gap-4"
            role="tabpanel"
            aria-labelledby="workshop-order-overview-tab"
            tabindex="0"
          >
            <div
              v-if="order.stock_warnings.length > 0"
              class="banner"
              :class="hasShortfall ? 'danger' : 'warn'"
              role="status"
            >
              <div class="grow">
                {{
                  hasShortfall
                    ? 'Kesishdan keyin zaxira yetishmaydi:'
                    : 'Kesishdan keyin kam qoladi:'
                }}
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

            <details class="card">
              <summary class="collapse-summary">
                <h2>Buyurtma tarkibi</h2>
                <span class="collapse-meta">
                  <span>{{ order.items.length }} panel</span>
                  <svg
                    class="od-chev"
                    viewBox="0 0 20 20"
                    width="16"
                    height="16"
                    aria-hidden="true"
                  >
                    <path
                      d="M5 7.5 10 12.5 15 7.5"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    />
                  </svg>
                </span>
              </summary>
              <div class="card-b">
                <details v-for="item in order.items" :key="item.id" class="bom-item">
                  <summary class="bom-summary">
                    <div class="bom-main">
                      <div class="nm">
                        {{ snapshotName(item) }} · {{ item.length_mm }}x{{ item.width_mm }}
                      </div>
                      <small class="text-ink-muted"
                        >{{ item.material_source === 'own' ? 'mijoz paneli' : 'ustaxona paneli' }} ·
                        {{ edgeCountLabel(item) }}</small
                      >
                    </div>
                    <span class="bom-qty">{{ item.quantity }} dona</span>
                    <svg
                      class="od-chev"
                      viewBox="0 0 20 20"
                      width="16"
                      height="16"
                      aria-hidden="true"
                    >
                      <path
                        d="M5 7.5 10 12.5 15 7.5"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                    </svg>
                  </summary>
                  <div class="bom-body">
                    <ul v-if="edgeSideDetails(item).length > 0" class="grid gap-1">
                      <li
                        v-for="detail in edgeSideDetails(item)"
                        :key="detail"
                        class="text-xs text-ink-muted"
                      >
                        {{ detail }}
                      </li>
                    </ul>
                    <p v-else class="text-xs text-ink-muted">
                      Bu panelda krom yo'q — yaxlit panel.
                    </p>
                  </div>
                </details>
                <div
                  v-if="order.planned_edge_lines.length > 0"
                  class="mt-4 border-t border-hairline pt-4"
                >
                  <div class="mb-2 text-xs font-extrabold uppercase text-ink-muted">Krom sarfi</div>
                  <div
                    v-for="line in order.planned_edge_lines"
                    :key="line.material_id"
                    class="row-item"
                  >
                    <div>
                      <div class="nm">{{ line.material_label }}</div>
                      <small class="text-ink-muted">
                        {{ line.thickness_mm ? `${line.thickness_mm} mm` : 'qalinlik yo‘q' }}
                        <span v-if="line.color"> · {{ line.color }}</span>
                      </small>
                    </div>
                    <div class="meta">{{ metres(line.consumed_mm) }}</div>
                  </div>
                </div>
                <div v-if="order.items.length === 0" class="st-empty !border-0 !py-8">
                  <h3>Chizma qismi yo'q</h3>
                </div>
              </div>
            </details>

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

            <details class="card">
              <summary class="collapse-summary">
                <h2>Ichki izoh</h2>
                <span class="collapse-meta">
                  <span>{{ order.note_workshop ? 'mavjud' : "bo'sh" }}</span>
                  <svg
                    class="od-chev"
                    viewBox="0 0 20 20"
                    width="16"
                    height="16"
                    aria-hidden="true"
                  >
                    <path
                      d="M5 7.5 10 12.5 15 7.5"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    />
                  </svg>
                </span>
              </summary>
              <div class="card-b">
                <textarea
                  v-model="noteDraft"
                  class="mp-input min-h-28 resize-y"
                  placeholder="Faqat ustaxona xodimlari ko'radi"
                ></textarea>
                <button
                  type="button"
                  class="mp-button mp-button-outline mt-3 min-h-11 px-3 text-xs"
                  :disabled="orders.actionLoading || !noteDirty"
                  @click="saveNote"
                >
                  {{
                    pendingAction === 'note' ? 'Saqlanmoqda…' : noteDirty ? 'Saqlash' : 'Saqlangan'
                  }}
                </button>
              </div>
            </details>
          </section>

          <section
            v-else-if="activeTab === 'cutting'"
            id="workshop-order-cutting-panel"
            class="card"
            role="tabpanel"
            aria-labelledby="workshop-order-cutting-tab"
            tabindex="0"
          >
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
                <div class="flex flex-wrap gap-2" role="group" aria-label="Panellar">
                  <button
                    v-for="panel in result.panels"
                    :key="panel.id"
                    type="button"
                    class="pill"
                    :class="panel.id === activePanel?.id ? 'p-cut' : 'p-dn'"
                    :aria-pressed="panel.id === activePanel?.id"
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
                  :disabled="orders.downloadingId === order.id"
                  @click="orders.downloadWorkshopPdf(order.id)"
                >
                  {{ orders.downloadingId === order.id ? 'Yuklanmoqda' : 'Chizma (PDF)' }}
                </button>
              </div>
              <aside v-if="activePanel" class="rounded-lg border border-hairline bg-sunk p-4">
                <h3 class="text-sm font-extrabold text-ink">Qismlar</h3>
                <div class="mt-3 grid gap-2" role="group" aria-label="Qismlar">
                  <button
                    v-for="placement in activePanel.placements"
                    :key="placement.id"
                    type="button"
                    class="rounded-md border border-hairline bg-elevated px-3 py-2 text-left text-sm"
                    :class="
                      placement.id === activePlacementId ? 'border-accent text-accent' : 'text-ink'
                    "
                    :aria-pressed="placement.id === activePlacementId"
                    @click="selectPlacement(placement)"
                  >
                    {{ placement.part_ref }} #{{ placement.part_quantity_index }}
                    <span v-if="placement.rotated" class="font-bold">R</span>
                  </button>
                </div>
              </aside>
            </div>
          </section>

          <section
            v-else
            id="workshop-order-timeline-panel"
            class="card"
            role="tabpanel"
            aria-labelledby="workshop-order-timeline-tab"
            tabindex="0"
          >
            <div class="card-h"><h2>Holat tarixi</h2></div>
            <div class="card-b">
              <div v-if="order.events.length === 0" class="st-empty !border-0 !py-8">
                <h3>Holat tarixi hali yo'q</h3>
              </div>
              <ol v-else class="tl">
                <li
                  v-for="(event, index) in order.events"
                  :key="event.id"
                  class="step"
                  :class="timelineStepClass(event, index)"
                >
                  <span class="when">{{ formatDate(event.changed_at) }}</span>
                  {{ event.from_status ? workshopStatusUz[event.from_status] : 'Yaratildi' }}
                  <span class="text-ink-muted">→</span>
                  {{ workshopStatusUz[event.to_status] }}
                  <span v-if="event.reason" class="block text-ink-soft">{{ event.reason }}</span>
                  <span
                    v-for="detail in timelineProductionDetails(event)"
                    :key="detail"
                    class="block text-ink-soft"
                  >
                    {{ detail }}
                  </span>
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
              <span
                >Krom<small
                  v-if="order.subtotal_edge_banding_tiyin > 0"
                  class="block text-xs text-ink-muted"
                  >{{ metres(edgeConsumedTotal(order)) }} · material + xizmat</small
                ></span
              ><span class="num">{{ formatTiyin(order.subtotal_edge_banding_tiyin) }}</span>
            </div>
            <div v-if="order.subtotal_edge_banding_tiyin > 0" class="r text-xs text-ink-muted">
              <span>Krom materiali</span
              ><span class="num">{{ formatTiyin(edgeMaterialTotal(order)) }}</span>
            </div>
            <div v-if="order.subtotal_edge_banding_tiyin > 0" class="r text-xs text-ink-muted">
              <span>Krom xizmati</span
              ><span class="num">{{ formatTiyin(edgeServiceTotal(order)) }}</span>
            </div>
            <div v-if="order.discount_tiyin > 0" class="r">
              <span
                >Chegirma<small v-if="order.discount_reason" class="block text-xs text-ink-muted">{{
                  order.discount_reason
                }}</small></span
              ><span class="num">- {{ formatTiyin(order.discount_tiyin) }}</span>
            </div>
            <div class="r grand">
              <span>Jami</span><span class="num">{{ formatTiyin(order.total_tiyin) }}</span>
            </div>
            <template v-if="order.settlement && canViewSettlement">
              <div class="r settle">
                <span>To'langan</span
                ><span class="num" :class="{ 'paid-off': order.settlement.recorded_tiyin > 0 }">{{
                  formatTiyin(order.settlement.recorded_tiyin)
                }}</span>
              </div>
              <div class="r">
                <span>Qoldiq</span
                ><span class="num" :class="{ 'paid-off': order.settlement.balance_tiyin === 0 }">{{
                  formatTiyin(order.settlement.balance_tiyin)
                }}</span>
              </div>
            </template>
          </section>

          <section ref="actionPanel" class="card">
            <div class="card-h"><h2>Amallar</h2></div>
            <div class="card-b grid gap-3">
              <button
                v-if="order.status === 'new' && canManageOrders"
                type="button"
                class="mp-button mp-button-primary w-full"
                :disabled="orders.actionLoading"
                @click="approve"
              >
                {{ pendingAction === 'approve' ? 'Tasdiqlanmoqda…' : 'Tasdiqlash' }}
              </button>

              <template v-else-if="order.status === 'confirmed' && canManageOrders">
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
                  v-if="order.has_banding"
                  type="button"
                  class="mp-button mp-button-outline w-full"
                  :disabled="orders.actionLoading || !edgerId"
                  @click="assignEdgerOnly"
                >
                  {{ pendingAction === 'assignEdger' ? 'Saqlanmoqda…' : 'Kromchini saqlash' }}
                </button>
                <!-- Partial saves sit under their own dropdown; the combined start action
                     stays separated below so it can't be mistaken for a per-worker save. -->
                <div :class="{ 'border-t border-hairline pt-3': order.has_banding }">
                  <button
                    type="button"
                    class="mp-button mp-button-primary w-full"
                    :disabled="orders.actionLoading || !cutterId || (order.has_banding && !edgerId)"
                    @click="assignWorkers"
                  >
                    {{ pendingAction === 'assign' ? 'Saqlanmoqda…' : 'Tayinlash va boshlash' }}
                  </button>
                </div>
              </template>

              <template v-else-if="order.status === 'cutting' && canCompleteCutting">
                <template v-if="canManageOrders">
                  <FormSelect
                    v-model="cutterId"
                    label="Kesuvchi"
                    :options="workerOptions"
                    :disabled="workerOptions.length === 0"
                  />
                  <button
                    type="button"
                    class="mp-button mp-button-outline w-full"
                    :disabled="orders.actionLoading || !cutterId"
                    @click="assignCutterOnly"
                  >
                    {{ pendingAction === 'assignCutter' ? 'Saqlanmoqda…' : 'Kesuvchini saqlash' }}
                  </button>
                </template>
                <FormSelect
                  v-if="canManageOrders"
                  v-model="completedById"
                  label="Kim bajardi"
                  :options="workerOptions"
                  :disabled="workerOptions.length === 0"
                />
                <button
                  type="button"
                  class="mp-button mp-button-primary w-full"
                  :disabled="orders.actionLoading || !canSubmitCuttingCompletion"
                  @click="completeCutting"
                >
                  {{ pendingAction === 'completeCutting' ? 'Bajarilmoqda…' : 'Kesish tugadi' }}
                </button>
              </template>

              <template v-else-if="order.status === 'edge_banding' && canCompleteBanding">
                <template v-if="canManageOrders">
                  <FormSelect
                    v-model="edgerId"
                    label="Krom yopishtiruvchi"
                    :options="workerOptions"
                    :disabled="workerOptions.length === 0"
                  />
                  <button
                    type="button"
                    class="mp-button mp-button-outline w-full"
                    :disabled="orders.actionLoading || !edgerId"
                    @click="assignEdgerOnly"
                  >
                    {{ pendingAction === 'assignEdger' ? 'Saqlanmoqda…' : 'Kromchini saqlash' }}
                  </button>
                </template>
                <FormSelect
                  v-if="canManageOrders"
                  v-model="completedById"
                  label="Kim bajardi"
                  :options="workerOptions"
                  :disabled="workerOptions.length === 0"
                />
                <button
                  type="button"
                  class="mp-button mp-button-primary w-full"
                  :disabled="orders.actionLoading || !canSubmitBandingCompletion"
                  @click="completeBanding"
                >
                  {{ pendingAction === 'completeBanding' ? 'Bajarilmoqda…' : 'Krom tugadi' }}
                </button>
              </template>

              <button
                v-else-if="order.status === 'ready' && canManageOrders"
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
              <p
                v-else-if="!hasLifecycleAction"
                class="rounded-md bg-sunk p-3 text-sm text-ink-soft"
              >
                Bu buyurtma siz uchun faqat o'qish holatida.
              </p>

              <button
                v-if="
                  canManageOrders && ['cutting', 'edge_banding', 'ready'].includes(order.status)
                "
                type="button"
                class="mp-button mp-button-outline w-full"
                :disabled="orders.actionLoading"
                @click="requestRevertOrder"
              >
                {{ revertButtonLabel }}
              </button>
              <button
                v-if="canManageOrders && !['completed', 'cancelled'].includes(order.status)"
                type="button"
                class="mp-button mp-button-outline w-full text-danger"
                :disabled="orders.actionLoading"
                @click="requestCancelOrder"
              >
                Buyurtmani bekor qilish
              </button>
              <div v-if="actionError" class="banner danger !mb-0" role="alert">
                <div class="grow">
                  {{ actionError }}
                  <span v-if="actionTraceId"> · trace {{ actionTraceId }}</span>
                </div>
              </div>
            </div>
          </section>

          <section
            v-if="canManageOrders && (order.status === 'new' || order.status === 'confirmed')"
            ref="discountPanel"
            class="card"
          >
            <div class="card-h"><h2>Chegirma</h2></div>
            <div class="card-b grid gap-3">
              <p
                v-if="order.discount_tiyin > 0"
                class="rounded-md bg-sunk p-3 text-sm text-ink-soft"
              >
                Hozirgi chegirma: {{ formatTiyin(order.discount_tiyin) }}. O'zgartirish uchun tur va
                qiymatni qayta kiriting.
              </p>
              <FormSelect v-model="discountKind" label="Turi" :options="discountOptions" />
              <div class="grid gap-1">
                <label class="field !mb-0"
                  ><span>Qiymat</span
                  ><input
                    id="discount-value"
                    ref="discountValueInput"
                    v-model="discountValue"
                    class="mp-input"
                    :class="discountError ? 'border-danger' : ''"
                    inputmode="numeric"
                    :aria-invalid="discountError ? 'true' : undefined"
                    :aria-describedby="discountError ? 'discount-value-error' : undefined"
                /></label>
                <p
                  v-if="discountError"
                  id="discount-value-error"
                  role="alert"
                  class="text-sm font-bold text-danger"
                >
                  {{ discountError }}
                </p>
              </div>
              <label class="field !mb-0"
                ><span>Sabab</span><input v-model="discountReason" class="mp-input"
              /></label>
              <div class="grid gap-2">
                <button
                  type="button"
                  class="mp-button mp-button-outline w-full whitespace-normal text-center leading-tight"
                  :disabled="orders.actionLoading"
                  @click="applyDiscount"
                >
                  {{ pendingAction === 'discount' ? 'Saqlanmoqda…' : discountButtonLabel }}
                </button>
                <button
                  v-if="order.discount_tiyin > 0"
                  type="button"
                  class="mp-button mp-button-outline w-full whitespace-normal text-center leading-tight text-danger"
                  :disabled="orders.actionLoading"
                  @click="removeDiscount"
                >
                  {{
                    pendingAction === 'removeDiscount' ? 'Saqlanmoqda…' : 'Chegirmani olib tashlash'
                  }}
                </button>
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
          ? `Buyurtma ${revertTargetLabel} qaytadi. Sababni yozing.`
          : 'Buyurtma yopiladi. Bekor qilish sababini yozing.'
      "
      :confirm-label="reasonDialogAction === 'revert' ? 'Ha, qaytarilsin' : 'Bekor qilish'"
      cancel-label="Yopish"
      busy-label="Bajarilmoqda"
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
      cancel-label="Orqaga"
      busy-label="Bajarilmoqda"
      :busy="orders.actionLoading"
      @cancel="markCollectedOpen = false"
      @confirm="markCollected"
    />
  </section>
</template>
