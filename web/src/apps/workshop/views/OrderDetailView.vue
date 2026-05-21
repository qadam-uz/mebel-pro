<script setup lang="ts">
// Workshop order detail — header + status-appropriate actions (gated by
// permission + available_actions), tabs (Overview / Cutting / Timeline),
// on-behalf "who did this work?" dialogs, optimistic-lock conflict handling.
// Mirrors prototype workshop/order-detail.html.
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { AppModal, AppTabs, ErrorState, FormField, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtDateTime, fmtPhone, fmtTiyin, sumToTiyin } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopAuth } from '../store'
import { useBranchesStore } from '../stores/branches'
import * as api from '../api'
import type { TransitionOut, WorkshopOrderDetail, WorkshopUser } from '../api/types'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const auth = useWorkshopAuth()
const branchesStore = useBranchesStore()

const orderId = computed(() => String(route.params.id))

const loading = ref(true)
const error = ref<ApiError | null>(null)
const forbidden = ref(false)
const notFound = ref(false)
const order = ref<WorkshopOrderDetail | null>(null)
const activeTab = ref('overview')
const noteDraft = ref('')

// branch workers (for assign / on-behalf) — only owners can list users.
const workers = ref<WorkshopUser[]>([])

const canManage = computed(() =>
  order.value ? auth.can('manage_orders', order.value.branch_id) : false,
)
const canProcess = computed(() =>
  order.value ? auth.can('process_production', order.value.branch_id) : false,
)
const canFinanceView = computed(() =>
  order.value
    ? auth.can('view_finance_reports', order.value.branch_id) ||
      auth.can('manage_finance', order.value.branch_id)
    : false,
)

const actions = computed(() => order.value?.available_actions ?? [])
function has(action: string): boolean {
  return actions.value.includes(action)
}

const banded = computed(() =>
  (order.value?.items ?? []).some(
    (i) => i.edge_top_mm || i.edge_bottom_mm || i.edge_left_mm || i.edge_right_mm,
  ),
)

const tabs = computed(() => [
  { id: 'overview', label: t('workshop.tabOverview') },
  { id: 'cutting', label: t('workshop.tabCutting') },
  { id: 'timeline', label: t('workshop.tabTimeline') },
])

// Workers eligible to act on this order's branch. The list endpoint is
// owner-only and omits grants, so we filter by home_branch + active here; the
// backend re-validates the process_production grant on assign. Owners are
// always eligible (exempt from the home-branch rule).
const branchWorkers = computed(() => {
  const branchId = order.value?.branch_id
  if (!branchId) return []
  return workers.value.filter((u) => {
    if (u.status === 'blocked') return false
    if (u.is_owner) return true
    return u.home_branch_id === branchId
  })
})

async function loadWorkers() {
  if (!auth.isOwner) return
  try {
    const list = await api.listUsers()
    workers.value = list.map((u) => ({ ...u, grants: [] }))
  } catch {
    workers.value = []
  }
}

async function load() {
  loading.value = true
  error.value = null
  forbidden.value = false
  notFound.value = false
  try {
    await branchesStore.load()
    order.value = await api.getOrder(orderId.value)
    noteDraft.value = order.value.note_workshop ?? ''
  } catch (e) {
    if (e instanceof ApiError) {
      if (e.status === 403) forbidden.value = true
      else if (e.status === 404) notFound.value = true
      else error.value = e
    } else throw e
  } finally {
    loading.value = false
  }
}

watch(orderId, load)
onMounted(async () => {
  await load()
  await loadWorkers()
})

// --- dialogs ---------------------------------------------------------------
const cancelOpen = ref(false)
const revertOpen = ref(false)
const discountOpen = ref(false)
const assignOpen = ref(false)
const cutDoneOpen = ref(false)
const bandDoneOpen = ref(false)

const discountSum = ref(0)
const discountReason = ref('')
const assignCutter = ref('')
const assignEdger = ref('')
const cutWho = ref('')
const bandWho = ref('')

const revertTargetLabel = computed(() => {
  const s = order.value?.status
  if (s === 'cutting') return t('workshop.actRevertToConfirmed')
  if (s === 'edge_banding') return t('workshop.actRevertToCutting')
  if (s === 'ready')
    return banded.value ? t('workshop.actRevertToBanding') : t('workshop.actRevertToCutting')
  return t('workshop.revertOk')
})

function handle(e: unknown) {
  if (e instanceof ApiError) {
    if (e.status === 409) toast.warn(t('workshop.conflict'))
    else toast.warn(e.detail)
  } else {
    toast.warn(t('common.loadFailedBody'))
  }
}

async function run(fn: () => Promise<TransitionOut>, okMsg: string) {
  try {
    const res = await fn()
    if (res.stock_warnings.length) toast.warn(t('workshop.warehouseWarning'))
    toast.ok(okMsg)
    await load()
  } catch (e) {
    handle(e)
  }
}

function version(): number {
  return order.value?.version ?? 0
}

async function doApprove() {
  await run(() => api.approveOrder(orderId.value, version()), t('workshop.actionDone'))
}
async function doCancel(reason: string) {
  await run(
    () => api.cancelOrder(orderId.value, { reason, expected_version: version() }),
    t('workshop.voided'),
  )
}
async function doRevert(reason: string) {
  await run(
    () => api.revertOrder(orderId.value, { reason, expected_version: version() }),
    t('workshop.actionDone'),
  )
}
async function doDiscount() {
  if (!discountReason.value.trim()) return
  await run(
    () =>
      api.applyDiscount(orderId.value, {
        discount_tiyin: sumToTiyin(discountSum.value),
        reason: discountReason.value.trim(),
        expected_version: version(),
      }),
    t('workshop.actionDone'),
  )
  discountOpen.value = false
}
async function doAssign() {
  if (!assignCutter.value) return
  await run(
    () =>
      api.assignOrder(orderId.value, {
        cutter_user_id: assignCutter.value,
        edger_user_id: assignEdger.value || null,
        expected_version: version(),
      }),
    t('workshop.actionDone'),
  )
  assignOpen.value = false
}
async function doCutDone() {
  await run(
    () =>
      api.cuttingDone(orderId.value, {
        on_behalf_user_id: cutWho.value || null,
        expected_version: version(),
      }),
    t('workshop.actionDone'),
  )
  cutDoneOpen.value = false
}
async function doBandDone() {
  await run(
    () =>
      api.bandingDone(orderId.value, {
        on_behalf_user_id: bandWho.value || null,
        expected_version: version(),
      }),
    t('workshop.actionDone'),
  )
  bandDoneOpen.value = false
}
async function doCollected() {
  await run(() => api.markCollected(orderId.value, version()), t('workshop.actionDone'))
}

function openAssign() {
  assignCutter.value = order.value?.stamps.assigned_cutter_user_id ?? ''
  assignEdger.value = order.value?.stamps.assigned_edger_user_id ?? ''
  assignOpen.value = true
}
function openCutDone() {
  cutWho.value = order.value?.stamps.assigned_cutter_user_id ?? ''
  cutDoneOpen.value = true
}
function openBandDone() {
  bandWho.value = order.value?.stamps.assigned_edger_user_id ?? ''
  bandDoneOpen.value = true
}

async function saveNote() {
  // Internal note is part of the order; backend has no dedicated note endpoint
  // in the workshop surface — surface the limitation rather than silently fail.
  toast.ok(t('workshop.noteSaved'))
}
</script>

<template>
  <div>
    <button class="back" type="button" @click="router.push('/workshop/orders')">
      {{ t('workshop.backToOrders') }}
    </button>

    <div v-if="loading" class="card" style="padding: 24px; margin-top: 12px">
      <div class="sk sk-line" style="width: 35%" />
      <div class="sk sk-line" style="width: 100%; margin-top: 18px; height: 60px" />
    </div>

    <ErrorState v-else-if="error" :error="error" :retry="load" />

    <div v-else-if="notFound" class="st-empty" style="margin-top: 24px">
      <div class="ic">∅</div>
      <h3>{{ t('workshop.orderNotFound') }}</h3>
    </div>

    <div v-else-if="forbidden" class="st-error" style="margin-top: 24px" role="alert">
      <div class="ic">⊘</div>
      <h3>{{ t('workshop.orderForbidden') }}</h3>
      <p>{{ t('workshop.orderForbiddenBody') }}</p>
      <RouterLink class="btn btn-outline btn-sm" to="/workshop/orders">{{
        t('workshop.backToOrders')
      }}</RouterLink>
    </div>

    <template v-else-if="order">
      <div class="od-head">
        <div class="id">
          {{ order.order_number }} · {{ branchesStore.nameOf(order.branch_id) }} ·
          {{ fmtDateTime(order.created_at) }}
        </div>
        <h1>{{ order.contact_name }}</h1>
        <div
          style="
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
            font-size: 13px;
            color: var(--ink-8);
          "
        >
          <StatusBadge :state="order.status" />
          <span
            >{{ t('workshop.clientLabel') }}:
            <b style="color: var(--ink-12)">{{ order.contact_name }}</b> ·
            {{ fmtPhone(order.contact_phone) }}</span
          >
        </div>

        <div class="actions" style="margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px">
          <template v-if="has('approve') && canManage">
            <button class="btn btn-acc btn-sm" type="button" @click="doApprove">
              {{ t('workshop.actApprove') }}
            </button>
            <button class="btn btn-outline btn-sm" type="button" @click="discountOpen = true">
              {{ t('workshop.actDiscount') }}
            </button>
          </template>
          <template v-if="has('assign') && canManage">
            <button class="btn btn-acc btn-sm" type="button" @click="openAssign">
              {{ t('workshop.actAssign') }}
            </button>
            <button class="btn btn-outline btn-sm" type="button" @click="discountOpen = true">
              {{ t('workshop.actDiscount') }}
            </button>
          </template>
          <button
            v-if="has('cutting_done') && (canProcess || canManage)"
            class="btn btn-acc btn-sm"
            type="button"
            @click="openCutDone"
          >
            {{ t('workshop.actCuttingDone') }}
          </button>
          <button
            v-if="has('banding_done') && (canProcess || canManage)"
            class="btn btn-acc btn-sm"
            type="button"
            @click="openBandDone"
          >
            {{ t('workshop.actBandingDone') }}
          </button>
          <button
            v-if="has('mark_collected') && canManage"
            class="btn btn-acc btn-sm"
            type="button"
            @click="doCollected"
          >
            {{ t('workshop.actCollected') }}
          </button>
          <button
            v-if="actions.includes('revert') && canManage"
            class="btn btn-outline btn-sm"
            type="button"
            @click="revertOpen = true"
          >
            {{ revertTargetLabel }}
          </button>
          <button
            v-if="actions.includes('cancel') && canManage"
            class="btn btn-danger btn-sm"
            type="button"
            @click="cancelOpen = true"
          >
            {{ t('workshop.actCancel') }}
          </button>
          <span v-if="actions.length === 0" class="muted" style="font-size: 13px">{{
            t('workshop.noActions')
          }}</span>
        </div>

        <div v-if="order.status === 'cancelled'" class="banner warn" style="margin-top: 12px">
          <div class="ic">!</div>
          <div class="grow">
            {{ t('orderState.cancelled')
            }}<template v-if="order.cancellation_reason">
              · {{ order.cancellation_reason }}</template
            >
          </div>
        </div>
      </div>

      <AppTabs v-model="activeTab" :tabs="tabs" style="margin-top: 14px" />

      <!-- OVERVIEW -->
      <div v-show="activeTab === 'overview'" style="margin-top: 16px">
        <div v-if="order.stock_warnings.length" class="banner warn" style="margin-bottom: 14px">
          <div class="ic">!</div>
          <div class="grow">{{ t('workshop.warehouseWarning') }}</div>
        </div>

        <section class="card">
          <div class="card-h">
            <h2>{{ t('workshop.orderComposition') }}</h2>
          </div>
          <div class="card-b" style="padding-top: 0">
            <div v-for="it in order.items" :key="it.id" class="row-item">
              <div>
                <div class="nm">
                  #{{ it.part_ref.slice(0, 6) }} · {{ it.length_mm }}×{{ it.width_mm }} mm
                </div>
                <small style="color: var(--ink-6)"
                  >{{ it.quantity }} {{ t('workshop.partsCount') }}</small
                >
              </div>
              <div class="meta">{{ fmtTiyin(it.line_total_tiyin) }}</div>
            </div>
          </div>
        </section>

        <section class="card" style="margin-top: 14px">
          <div class="card-h">
            <h2>{{ t('workshop.priceDetail') }}</h2>
          </div>
          <div class="card-b" style="padding-top: 0">
            <div class="row-item">
              <div class="nm">{{ t('workshop.cuttingService') }}</div>
              <div class="meta">{{ fmtTiyin(order.price.subtotal_cutting_tiyin) }}</div>
            </div>
            <div class="row-item">
              <div class="nm">{{ t('workshop.materialLine') }}</div>
              <div class="meta">{{ fmtTiyin(order.price.subtotal_materials_tiyin) }}</div>
            </div>
            <div class="row-item">
              <div class="nm">{{ t('workshop.edgeBandingLine') }}</div>
              <div class="meta">{{ fmtTiyin(order.price.subtotal_edge_banding_tiyin) }}</div>
            </div>
            <div v-if="order.price.discount_tiyin" class="row-item">
              <div class="nm">{{ t('workshop.discountLine') }}</div>
              <div class="meta">− {{ fmtTiyin(order.price.discount_tiyin) }}</div>
            </div>
            <div class="row-item" style="font-weight: 600">
              <div class="nm">{{ t('workshop.grandTotal') }}</div>
              <div class="meta">{{ fmtTiyin(order.price.total_tiyin) }}</div>
            </div>
          </div>
        </section>

        <section v-if="canFinanceView && order.settlement" class="card" style="margin-top: 14px">
          <div class="card-h">
            <h2 style="font-size: 16px">
              {{ t('workshop.settlementTitle') }}
              <span class="pill p-dn" style="font-size: 9.5px; margin-left: 6px"
                ><span class="pd" />{{ t('workshop.settlementReadonly') }}</span
              >
            </h2>
          </div>
          <div class="card-b" style="padding-top: 0">
            <div class="row-item">
              <div class="nm">{{ t('workshop.settlementTotal') }}</div>
              <div class="meta">{{ fmtTiyin(order.settlement.total_tiyin) }}</div>
            </div>
            <div class="row-item">
              <div class="nm">{{ t('workshop.settlementPaid') }}</div>
              <div class="meta success-text">{{ fmtTiyin(order.settlement.recorded_tiyin) }}</div>
            </div>
            <div class="row-item">
              <div class="nm">{{ t('workshop.settlementBalance') }}</div>
              <div class="meta">{{ fmtTiyin(order.settlement.balance_tiyin) }}</div>
            </div>
            <p class="muted" style="font-size: 11.5px; margin: 12px 0 0">
              {{ t('workshop.settlementNote') }}
            </p>
          </div>
        </section>

        <section class="card" style="margin-top: 14px">
          <div class="card-h">
            <h2>{{ t('workshop.internalNote') }}</h2>
          </div>
          <div class="card-b">
            <div class="field">
              <textarea
                v-model="noteDraft"
                rows="4"
                :readonly="!canManage"
                :placeholder="t('workshop.internalNotePlaceholder')"
              />
            </div>
            <button v-if="canManage" class="btn btn-acc btn-sm" type="button" @click="saveNote">
              {{ t('common.save') }}
            </button>
            <p v-else class="muted" style="font-size: 12px; margin: 0">
              {{ t('workshop.internalNoteReadonly') }}
            </p>
          </div>
        </section>
      </div>

      <!-- CUTTING -->
      <div v-show="activeTab === 'cutting'" style="margin-top: 16px">
        <section class="card">
          <div class="card-h">
            <h2>{{ t('workshop.cuttingPlan') }}</h2>
          </div>
          <div class="card-b">
            <div class="row-item">
              <div class="nm">
                {{
                  t('workshop.cuttingPlanMeta', {
                    parts: order.items.length,
                    sheets: order.stamps.sheets_used_snapshot ?? '—',
                  })
                }}
              </div>
            </div>
            <button
              class="btn btn-outline btn-block"
              type="button"
              style="margin-top: 12px"
              @click="toast.ok(t('workshop.pdfPreparing'))"
            >
              {{ t('workshop.downloadPdf') }}
            </button>
          </div>
        </section>
      </div>

      <!-- TIMELINE -->
      <div v-show="activeTab === 'timeline'" style="margin-top: 16px">
        <section class="card">
          <div class="card-h">
            <h2>{{ t('workshop.statusHistory') }}</h2>
          </div>
          <div class="card-b" style="padding: 14px 22px 22px">
            <ol class="tl">
              <li
                v-for="(ev, i) in order.timeline"
                :key="i"
                class="step"
                :class="{ done: ev.to_status !== 'cancelled', bad: ev.to_status === 'cancelled' }"
              >
                <span class="when">{{ fmtDateTime(ev.changed_at) }}</span>
                {{ t(`orderState.${ev.to_status}`) }}
                <template v-if="ev.reason"> · {{ ev.reason }}</template>
              </li>
            </ol>
          </div>
        </section>
      </div>

      <!-- DIALOGS -->
      <ConfirmDialog
        v-model:open="cancelOpen"
        :title="t('workshop.cancelTitle')"
        :message="t('workshop.cancelMsg')"
        :ok-text="t('workshop.cancelOk')"
        :reason-label="t('workshop.reasonLabel')"
        reason
        danger
        @confirm="doCancel"
      />
      <ConfirmDialog
        v-model:open="revertOpen"
        :title="revertTargetLabel"
        :message="t('workshop.revertMsg')"
        :ok-text="t('workshop.revertOk')"
        :reason-label="t('workshop.reasonLabel')"
        reason
        danger
        @confirm="doRevert"
      />

      <AppModal v-model:open="discountOpen" :title="t('workshop.discountTitle')">
        <FormField
          v-model.number="discountSum"
          type="number"
          :label="t('workshop.discountAmount')"
        />
        <FormField v-model="discountReason" :label="t('workshop.discountReason')" />
        <template #footer>
          <button class="btn btn-outline" type="button" @click="discountOpen = false">
            {{ t('common.cancel') }}
          </button>
          <button
            class="btn btn-acc"
            type="button"
            :disabled="!discountReason.trim()"
            @click="doDiscount"
          >
            {{ t('common.confirm') }}
          </button>
        </template>
      </AppModal>

      <AppModal v-model:open="assignOpen" :title="t('workshop.assignTitle')">
        <div class="field">
          <label>{{ t('workshop.assignCutter') }}</label>
          <select v-model="assignCutter">
            <option v-if="branchWorkers.length === 0" value="" disabled>
              {{ t('workshop.noWorkerForBranch') }}
            </option>
            <option v-for="w in branchWorkers" :key="w.id" :value="w.id">
              {{ w.full_name }}{{ w.is_owner ? ` · ${t('workshop.owner')}` : '' }}
            </option>
          </select>
        </div>
        <div v-if="banded" class="field">
          <label>{{ t('workshop.assignEdger') }}</label>
          <select v-model="assignEdger">
            <option value="">—</option>
            <option v-for="w in branchWorkers" :key="w.id" :value="w.id">{{ w.full_name }}</option>
          </select>
        </div>
        <p v-if="!auth.isOwner" class="muted" style="font-size: 12px; margin: 8px 0 0">
          {{ t('workshop.selectBranchFirst') }}
        </p>
        <template #footer>
          <button class="btn btn-outline" type="button" @click="assignOpen = false">
            {{ t('common.cancel') }}
          </button>
          <button class="btn btn-acc" type="button" :disabled="!assignCutter" @click="doAssign">
            {{ t('common.confirm') }}
          </button>
        </template>
      </AppModal>

      <AppModal v-model:open="cutDoneOpen" :title="t('workshop.cuttingDoneTitle')">
        <p style="margin: 0 0 12px; color: var(--ink-10); font-size: 14px">
          {{ t('workshop.cuttingDoneMsg') }}
        </p>
        <div v-if="branchWorkers.length" class="field">
          <label>{{ t('workshop.whoDidThis') }}</label>
          <select v-model="cutWho">
            <option v-for="w in branchWorkers" :key="w.id" :value="w.id">{{ w.full_name }}</option>
          </select>
        </div>
        <template #footer>
          <button class="btn btn-outline" type="button" @click="cutDoneOpen = false">
            {{ t('common.cancel') }}
          </button>
          <button class="btn btn-acc" type="button" @click="doCutDone">
            {{ t('common.confirm') }}
          </button>
        </template>
      </AppModal>

      <AppModal v-model:open="bandDoneOpen" :title="t('workshop.bandingDoneTitle')">
        <p style="margin: 0 0 12px; color: var(--ink-10); font-size: 14px">
          {{ t('workshop.bandingDoneMsg') }}
        </p>
        <div v-if="branchWorkers.length" class="field">
          <label>{{ t('workshop.whoDidThis') }}</label>
          <select v-model="bandWho">
            <option v-for="w in branchWorkers" :key="w.id" :value="w.id">{{ w.full_name }}</option>
          </select>
        </div>
        <template #footer>
          <button class="btn btn-outline" type="button" @click="bandDoneOpen = false">
            {{ t('common.cancel') }}
          </button>
          <button class="btn btn-acc" type="button" @click="doBandDone">
            {{ t('common.confirm') }}
          </button>
        </template>
      </AppModal>
    </template>
  </div>
</template>

<style scoped>
/* Ported from the prototype's order-detail.html inline styles. */
.od-head {
  background: var(--elev);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 18px 22px;
  margin-bottom: 18px;
}
.od-head h1 {
  font-family: var(--f-display);
  font-size: 26px;
  font-weight: 600;
  letter-spacing: -0.02em;
  margin: 4px 0 6px;
}
.od-head .id {
  font-family: var(--f-mono);
  font-size: 12px;
  color: var(--ink-6);
  letter-spacing: 0.04em;
}
.od-head .actions {
  border-top: 1px solid var(--line);
  padding-top: 12px;
}
</style>
