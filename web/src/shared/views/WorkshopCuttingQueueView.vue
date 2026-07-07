<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import {
  resolveProductionCreditUser,
  workshopQueuePartsLine,
} from '@/shared/app/workshopProduction'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import { workshopErrorMessage } from '@/shared/app/workshopUi'
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

const queueOrders = computed(() =>
  orders.workshopOrders.filter((order) => {
    if (!['confirmed', 'cutting'].includes(order.status)) return false
    if (!order.assigned_cutter_user_id) return false
    if (auth.me?.is_owner) return true
    return order.assigned_cutter_user_id === auth.me?.principal_id
  }),
)
const awaiting = computed(() => queueOrders.value.filter((order) => order.status === 'confirmed'))
const inProgress = computed(() => queueOrders.value.filter((order) => order.status === 'cutting'))
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
      (option) => option.value === order.assigned_cutter_user_id,
    )?.label ?? null
  )
}

function seedCompletedByDrafts() {
  const next = { ...completedByDraft.value }
  for (const order of queueOrders.value) {
    if (!next[order.id] && order.assigned_cutter_user_id)
      next[order.id] = order.assigned_cutter_user_id
  }
  completedByDraft.value = next
}

async function refresh() {
  await orders.loadWorkshopOrders({
    status: 'active',
    assigned_cutter_user_id: auth.me?.is_owner ? null : auth.me?.principal_id,
    limit: 100,
  })
  await loadWorkerOptionsFor(queueOrders.value.map((order) => order.branch_id))
  seedCompletedByDrafts()
}

async function complete(order: OrderSummary) {
  actionError.value = null
  if (!canProcessOrder(order)) {
    actionError.value = "Bu filialda ishlab chiqarishni yakunlash ruxsatingiz yo'q."
    return
  }
  const completedBy = resolveProductionCreditUser(
    order.assigned_cutter_user_id,
    completedByDraft.value[order.id],
    auth.me?.is_owner === true,
  )
  if (!completedBy) {
    actionError.value = 'Kesishni bajargan xodimni tanlang.'
    return
  }
  try {
    await orders.cuttingDone(order.id, {
      version: order.version,
      completed_by_user_id: completedBy,
    })
    toast.success('Kesish yakunlandi.')
  } catch {
    actionError.value = workshopErrorMessage(orders.actionError ?? 'cutting_complete_failed')
  }
}

onMounted(refresh)
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Kesish navbati</h1>
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

    <section v-else-if="orders.error" class="st-error">
      <h3>Kesish navbatini yuklab bo'lmadi</h3>
      <p>trace_id: {{ orders.traceId ?? 'unavailable' }}</p>
    </section>

    <section v-else-if="!canProcessAny" class="st-empty">
      <h3>Ishlab chiqarish ruxsati yo'q</h3>
      <p>Kesish navbatini bajarish uchun filial bo'yicha ishlab chiqarish ruxsati kerak.</p>
    </section>

    <section v-else-if="queueOrders.length === 0" class="st-empty">
      <h3>
        {{ auth.me?.is_owner ? "Kesish navbati bo'sh" : "Sizga tayinlangan kesish ishi yo'q" }}
      </h3>
      <p v-if="auth.me?.is_owner">
        Buyurtma tasdiqlanib ustaga tayinlangach, u shu navbatda ko'rinadi.
      </p>
      <p v-else>
        Rahbar tasdiqlangan buyurtmani sizga tayinlagach, u shu navbatda ko'rinadi. Agar ustaxonada
        ish kutayotgan bo'lsa, rahbardan tayinlashni so'rang.
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

      <div class="queue-grid">
        <section class="queue-col">
          <h2>
            Kesishni kutmoqda
            <span class="ct">{{ awaiting.length }}</span>
          </h2>
          <div v-if="awaiting.length === 0" class="st-empty !px-4 !py-8">
            <h3>Kesishni kutayotgan ish yo'q</h3>
            <p>Yangi ish rahbar tayinlagandan keyin shu ustunda chiqadi.</p>
          </div>
          <article v-for="order in awaiting" v-else :key="order.id" class="q-card">
            <div class="top">
              <div>
                <h4>{{ order.order_number }}</h4>
                <div class="meta">
                  {{ order.contact_name }} · <b>{{ workshopQueuePartsLine(order) }}</b> ·
                  {{ formatDate(order.created_at) }}
                </div>
              </div>
              <span v-if="assigneeLabel(order)" class="assigned-tag">{{
                assigneeLabel(order)
              }}</span>
            </div>
            <div class="act">
              <RouterLink
                :to="rolePath(`/workshop/orders/${order.id}`)"
                class="mp-button mp-button-primary min-h-9 px-3 text-xs"
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

        <section class="queue-col">
          <h2>
            Kesilmoqda
            <span class="ct">{{ inProgress.length }}</span>
          </h2>
          <div v-if="inProgress.length === 0" class="st-empty !px-4 !py-8">
            <h3>Hozir kesilayotgan ish yo'q</h3>
            <p>Boshlangan kesish ishlari shu yerda ko'rinadi.</p>
          </div>
          <article v-for="order in inProgress" v-else :key="order.id" class="q-card">
            <div class="top">
              <div>
                <h4>{{ order.order_number }}</h4>
                <div class="meta">
                  {{ order.contact_name }} · <b>{{ workshopQueuePartsLine(order) }}</b> ·
                  {{ formatTiyin(order.total_tiyin) }}
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
                @click="complete(order)"
              >
                Kesish tugadi
              </button>
              <RouterLink
                :to="rolePath(`/workshop/orders/${order.id}`)"
                class="mp-button mp-button-outline min-h-9 px-3 text-xs"
              >
                Chizmani ko'rish
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
  </section>
</template>
