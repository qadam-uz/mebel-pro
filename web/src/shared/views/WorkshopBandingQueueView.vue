<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import { resolveProductionCreditUser, workshopQueueEdgeLine } from '@/shared/app/workshopProduction'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import { workshopErrorMessage } from '@/shared/app/workshopUi'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { formatDate, formatTiyin } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { useOrdersStore, type OrderSummary } from '@/shared/stores/orders'

const auth = useAuthStore()
const rolePath = useRolePath()
const orders = useOrdersStore()
const toast = useToast()
const permissions = useWorkshopPermissions()
const actionError = ref<string | null>(null)
const completedByDraft = ref<Record<string, string>>({})
const workerOptionsByBranch = ref<Record<string, ChoiceOption[]>>({})
const pendingComplete = ref<OrderSummary | null>(null)

const queueOrders = computed(() =>
  orders.workshopOrders.filter((order) => {
    if (order.status !== 'edge_banding') return false
    if (!order.assigned_edger_user_id) return false
    if (auth.me?.is_owner) return true
    return order.assigned_edger_user_id === auth.me?.principal_id
  }),
)
const canProcessAny = computed(() => permissions.canAny([p.processProduction]))

function canProcessOrder(order: OrderSummary) {
  return permissions.canOnBranch(p.processProduction, order.branch_id)
}

function workerOptionsFor(branchId: string) {
  return workerOptionsByBranch.value[branchId] ?? []
}

async function loadWorkerOptionsFor(branchIds: string[]) {
  if (!auth.me?.is_owner) return
  for (const branchId of new Set(branchIds)) {
    if (workerOptionsByBranch.value[branchId]) continue
    await orders.loadWorkers(branchId).catch(() => undefined)
    workerOptionsByBranch.value = {
      ...workerOptionsByBranch.value,
      [branchId]: orders.workerOptions.map((worker) => ({
        value: worker.id,
        label: worker.full_name,
        meta: worker.is_owner ? 'owner' : 'production',
      })),
    }
  }
}

// Corner tag on a queue card: an usta only ever sees their own jobs, so
// "Sizga" is honest for them; the owner sees ALL workers' jobs, so the tag
// must name the actual assignee instead (or stay empty until options load).
function assigneeLabel(order: OrderSummary) {
  if (!auth.me?.is_owner) return 'Sizga'
  return (
    workerOptionsFor(order.branch_id).find(
      (option) => option.value === order.assigned_edger_user_id,
    )?.label ?? null
  )
}

function seedCompletedByDrafts() {
  const next = { ...completedByDraft.value }
  for (const order of queueOrders.value) {
    if (!next[order.id] && order.assigned_edger_user_id)
      next[order.id] = order.assigned_edger_user_id
  }
  completedByDraft.value = next
}

async function refresh() {
  await orders.loadWorkshopOrders({
    status: 'edge_banding',
    assigned_edger_user_id: auth.me?.is_owner ? null : auth.me?.principal_id,
    limit: 100,
  })
  await loadWorkerOptionsFor(queueOrders.value.map((order) => order.branch_id))
  seedCompletedByDrafts()
}

// "Krom tugadi" advances a live order irreversibly (only a manager can revert),
// so gate the mutation behind a confirm dialog: requestComplete validates the
// credited worker first and only then arms the dialog, complete() runs on confirm.
function resolveCompletion(order: OrderSummary): string | null {
  if (!canProcessOrder(order)) {
    actionError.value = "Bu filialda ishlab chiqarishni yakunlash ruxsatingiz yo'q."
    return null
  }
  const completedBy = resolveProductionCreditUser(
    order.assigned_edger_user_id,
    completedByDraft.value[order.id],
    auth.me?.is_owner === true,
  )
  if (!completedBy) {
    actionError.value = 'Krom ishini bajargan xodimni tanlang.'
    return null
  }
  return completedBy
}

function requestComplete(order: OrderSummary) {
  actionError.value = null
  if (resolveCompletion(order)) pendingComplete.value = order
}

async function complete(order: OrderSummary) {
  actionError.value = null
  const completedBy = resolveCompletion(order)
  if (!completedBy) return false
  try {
    await orders.bandingDone(order.id, {
      version: order.version,
      completed_by_user_id: completedBy,
    })
    toast.success('Krom yakunlandi.')
    return true
  } catch {
    actionError.value = workshopErrorMessage(orders.actionError ?? 'banding_complete_failed')
    return false
  }
}

async function confirmComplete() {
  const order = pendingComplete.value
  if (!order) return
  if (await complete(order)) {
    pendingComplete.value = null
    return
  }
  // On failure the store may have refetched the order (version conflict): re-arm
  // the dialog with the fresh row so a retry carries the current version; if the
  // order left the queue (someone else advanced it), close the moot dialog.
  pendingComplete.value = queueOrders.value.find((row) => row.id === order.id) ?? null
}

onMounted(refresh)
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Krom yopishtirish navbati</h1>
      </div>
      <div class="tools">
        <button
          type="button"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
          :disabled="orders.loading"
          @click="refresh"
        >
          {{ orders.loading ? 'Yuklanmoqda' : 'Yangilash' }}
        </button>
        <RouterLink
          :to="rolePath('/workshop/orders')"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
        >
          Buyurtmalar
        </RouterLink>
      </div>
    </div>

    <section v-if="orders.loading" class="card p-5" aria-live="polite">
      <div class="grid gap-3">
        <span class="sk-line"></span>
        <span class="sk-line"></span>
        <span class="sk-line"></span>
      </div>
    </section>

    <section v-else-if="orders.error" class="st-error" role="alert">
      <h3>Krom navbatini yuklab bo'lmadi</h3>
      <p>Internet aloqasini tekshirib, qayta urinib ko'ring.</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        :disabled="orders.loading"
        @click="refresh"
      >
        Qayta urinish
      </button>
      <p v-if="orders.traceId" class="mt-3 text-xs text-ink-muted">
        trace_id: {{ orders.traceId }}
      </p>
    </section>

    <section v-else-if="!canProcessAny" class="st-empty">
      <h3>Ishlab chiqarish ruxsati yo'q</h3>
      <p>Krom navbatini bajarish uchun filial bo'yicha ishlab chiqarish ruxsati kerak.</p>
    </section>

    <section v-else-if="queueOrders.length === 0" class="st-empty">
      <h3>{{ auth.me?.is_owner ? "Krom navbati bo'sh" : "Sizga tayinlangan krom ishi yo'q" }}</h3>
      <p v-if="auth.me?.is_owner">
        Kesish tugagan buyurtma ustaga tayinlangach, u shu navbatda ko'rinadi.
      </p>
      <p v-else>
        Kesish tugagan buyurtmani rahbar sizga tayinlagach, u shu navbatda ko'rinadi. Agar krom ishi
        kutayotgan bo'lsa, rahbardan tayinlashni so'rang.
      </p>
    </section>

    <template v-else>
      <div v-if="actionError" class="banner danger">
        <div class="grow">
          {{ actionError }}
          <span v-if="orders.actionTraceId"> · trace {{ orders.actionTraceId }}</span>
        </div>
      </div>
      <div v-if="orders.downloadError" class="banner danger">
        <div class="grow">
          {{ orders.downloadError }} · trace_id: {{ orders.downloadTraceId ?? 'unavailable' }}
        </div>
      </div>

      <div class="max-w-2xl">
        <section class="queue-col">
          <h2>
            Krom kutmoqda
            <span class="ct">{{ queueOrders.length }}</span>
          </h2>
          <article v-for="order in queueOrders" :key="order.id" class="q-card">
            <div class="top">
              <div>
                <h4>{{ order.order_number }}</h4>
                <div class="meta">
                  {{ order.contact_name }} ·
                  <b>{{ workshopQueueEdgeLine(order.planned_edge_lines) }}</b> ·
                  {{ formatDate(order.created_at) }} · {{ formatTiyin(order.total_tiyin) }}
                </div>
              </div>
              <span v-if="assigneeLabel(order)" class="assigned-tag">{{
                assigneeLabel(order)
              }}</span>
            </div>
            <div class="act">
              <FormSelect
                v-if="auth.me?.is_owner"
                v-model="completedByDraft[order.id]"
                label="Kim bajardi"
                :options="workerOptionsFor(order.branch_id)"
                :disabled="workerOptionsFor(order.branch_id).length === 0"
              />
              <button
                type="button"
                class="mp-button mp-button-primary min-h-9 px-3 text-xs"
                :disabled="orders.actionLoading || !canProcessOrder(order)"
                @click="requestComplete(order)"
              >
                Krom tugadi
              </button>
              <RouterLink
                :to="rolePath(`/workshop/orders/${order.id}`)"
                class="mp-button mp-button-outline min-h-9 px-3 text-xs"
              >
                Tafsilotlar
              </RouterLink>
              <button
                type="button"
                class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                :disabled="orders.downloadingId === order.id"
                @click="orders.downloadWorkshopPdf(order.id)"
              >
                {{ orders.downloadingId === order.id ? 'Yuklanmoqda' : 'PDF' }}
              </button>
            </div>
          </article>
        </section>
      </div>
    </template>

    <ConfirmDialog
      :open="pendingComplete !== null"
      :title="pendingComplete?.order_number ?? ''"
      :message="`${pendingComplete?.order_number ?? ''} buyurtma uchun krom tugadimi? Buni faqat rahbar orqaga qaytara oladi.`"
      confirm-label="Ha, tugadi"
      cancel-label="Yopish"
      busy-label="Bajarilmoqda"
      danger
      :busy="orders.actionLoading"
      @cancel="pendingComplete = null"
      @confirm="confirmComplete"
    >
      <!-- Failures must surface above the scrim — the page banner sits under it. -->
      <p v-if="actionError" class="text-sm font-bold text-danger">{{ actionError }}</p>
    </ConfirmDialog>
  </section>
</template>
