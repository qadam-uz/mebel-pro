<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import {
  groupProductionJobsByAssignee,
  partitionProductionJobs,
  productionJobAssignee,
  productionJobMetaLine,
} from '@/shared/app/workshopProduction'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import { workshopErrorMessage } from '@/shared/app/workshopUi'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { formatRelativeUz } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { useOrdersStore } from '@/shared/stores/orders'
import {
  useProductionStore,
  type ProductionJobCard,
  type ProductionStation,
} from '@/shared/stores/production'
import { useWorkshopStore } from '@/shared/stores/workshop'

const POLL_INTERVAL_MS = 15_000

// The station comes from the route (/workshop/cutting, /workshop/banding) —
// a tablet pinned to its station page always wakes on its own queue.
const props = defineProps<{ station: ProductionStation }>()

const auth = useAuthStore()
const router = useRouter()
const rolePath = useRolePath()
const orders = useOrdersStore()
const production = useProductionStore()
const workshop = useWorkshopStore()
const toast = useToast()
const permissions = useWorkshopPermissions()

const actionError = ref<string | null>(null)
const pendingJobId = ref<string | null>(null)
const pendingComplete = ref<ProductionJobCard | null>(null)

const station = computed(() => props.station)
const stationTitle = computed(() => (station.value === 'cutting' ? 'Kesish' : 'Krom'))

const queue = computed(() => production.queues[station.value] ?? null)
const isManagerView = computed(
  () => auth.me?.is_owner === true || permissions.canAny([p.manageOrders]),
)
const canProcessAny = computed(() => permissions.canAny([p.processProduction, p.manageOrders]))
const multiBranch = computed(() => workshop.branches.length > 1)

const partitioned = computed(() => partitionProductionJobs(queue.value?.jobs ?? [], station.value))
const currentJobs = computed(() => partitioned.value.current)
const queuedJobs = computed(() => partitioned.value.queued)
const completedToday = computed(() => queue.value?.completed_today ?? [])
const queuedGroups = computed(() =>
  isManagerView.value ? groupProductionJobsByAssignee(queuedJobs.value, station.value) : null,
)

function jobMeta(job: ProductionJobCard) {
  return productionJobMetaLine(job, station.value)
}

function assigneeName(job: ProductionJobCard) {
  return productionJobAssignee(job, station.value)?.full_name ?? null
}

function isMine(job: ProductionJobCard) {
  return productionJobAssignee(job, station.value)?.id === auth.me?.principal_id
}

function canActOn(job: ProductionJobCard) {
  return isMine(job) || permissions.canOnBranch(p.manageOrders, job.branch_id)
}

function startedLabel(job: ProductionJobCard) {
  const at = station.value === 'cutting' ? job.cutting_started_at : job.banding_started_at
  return at ? `boshlangan: ${formatRelativeUz(at)}` : 'boshlangan'
}

function queuedLabel(job: ProductionJobCard) {
  const at = station.value === 'cutting' ? job.cutter_assigned_at : job.edger_assigned_at
  return at
    ? `tayinlangan: ${formatRelativeUz(at)}`
    : `yaratilgan: ${formatRelativeUz(job.created_at)}`
}

function completedLabel(job: ProductionJobCard) {
  const at = station.value === 'cutting' ? job.cut_completed_at : job.edge_completed_at
  return at ? formatRelativeUz(at) : ''
}

async function refresh() {
  await production.loadQueues(['cutting', 'banding'])
}

// The queue stays fresh on its own: a slow poll plus an immediate refresh when
// the tablet wakes up. No manual refresh button — the master shouldn't babysit
// the screen.
let pollTimer: ReturnType<typeof setInterval> | null = null

function onVisibilityChange() {
  if (!document.hidden) void refresh()
}

async function startJob(job: ProductionJobCard) {
  if (!canActOn(job)) return
  actionError.value = null
  pendingJobId.value = job.id
  try {
    if (station.value === 'cutting') await orders.startCutting(job.id, job.version)
    else await orders.startBanding(job.id, job.version)
    toast.success(station.value === 'cutting' ? 'Kesish boshlandi.' : 'Krom boshlandi.')
    // One tap: the job starts and the master lands on its drawing.
    void router.push(rolePath(`/workshop/production/${job.id}`))
  } catch {
    actionError.value = workshopErrorMessage(orders.actionError ?? 'order_action_failed')
  } finally {
    pendingJobId.value = null
    await refresh()
  }
}

function requestComplete(job: ProductionJobCard) {
  if (!canActOn(job)) return
  actionError.value = null
  pendingComplete.value = job
}

const completeDialogTitle = computed(() =>
  station.value === 'cutting' ? 'Kesish tugadimi?' : 'Krom tugadimi?',
)
const completeDialogMessage = computed(() => {
  const job = pendingComplete.value
  if (!job) return ''
  const intro = `${job.order_number} · ${jobMeta(job)}`
  if (station.value === 'banding') return `${intro}. Keyin buyurtma tayyor holatga o'tadi.`
  if (!job.has_banding) return `${intro}. Keyin buyurtma tayyor holatga o'tadi.`
  const edger = job.assigned_edger ? ` (${job.assigned_edger.full_name} navbatiga)` : ''
  return `${intro}. Keyin buyurtma krom bosqichiga o'tadi${edger}.`
})

async function confirmComplete() {
  const job = pendingComplete.value
  if (!job) return
  actionError.value = null
  // Completion always credits the assignee; a manager who needs a different
  // credit uses the office order page, which keeps its own "who did this" flow.
  const completedBy = productionJobAssignee(job, station.value)?.id ?? null
  if (!completedBy) {
    actionError.value = 'Buyurtmaga usta tayinlanmagan.'
    return
  }
  try {
    const payload = { version: job.version, completed_by_user_id: completedBy }
    if (station.value === 'cutting') await orders.cuttingDone(job.id, payload)
    else await orders.bandingDone(job.id, payload)
    pendingComplete.value = null
    const next = queuedJobs.value.find((row) => row.id !== job.id)
    toast.success(`${job.order_number} yakunlandi.${next ? ` Keyingi: ${next.order_number}` : ''}`)
    await refresh()
  } catch {
    actionError.value = workshopErrorMessage(orders.actionError ?? 'order_action_failed')
    await refresh()
    // Re-arm with the fresh row (a version conflict means someone else moved
    // it); if the job left the queue entirely, the dialog is moot — close it.
    pendingComplete.value = (queue.value?.jobs ?? []).find((row) => row.id === job.id) ?? null
  }
}

onMounted(async () => {
  await refresh()
  pollTimer = setInterval(() => {
    if (!document.hidden && !orders.actionLoading) void refresh()
  }, POLL_INTERVAL_MS)
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
  document.removeEventListener('visibilitychange', onVisibilityChange)
})

watch(station, () => {
  actionError.value = null
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>{{ stationTitle }}</h1>
      </div>
      <div class="tools">
        <RouterLink
          v-if="isManagerView"
          :to="rolePath('/workshop/orders')"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
        >
          Buyurtmalar
        </RouterLink>
      </div>
    </div>

    <section v-if="production.loading && !queue" class="card mt-4 p-5" aria-live="polite">
      <div class="grid gap-3">
        <span class="sk-line"></span>
        <span class="sk-line"></span>
        <span class="sk-line"></span>
      </div>
    </section>

    <section v-else-if="production.error" class="st-error mt-4" role="alert">
      <h3>Ish navbatini yuklab bo'lmadi</h3>
      <p>Internet aloqasini tekshirib, qayta urinib ko'ring.</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        :disabled="production.loading"
        @click="refresh"
      >
        Qayta urinish
      </button>
      <p v-if="production.traceId" class="mt-3 text-xs text-ink-muted">
        trace_id: {{ production.traceId }}
      </p>
    </section>

    <section v-else-if="!canProcessAny" class="st-empty mt-4">
      <h3>Ishlab chiqarish ruxsati yo'q</h3>
      <p>Bu sahifa uchun filial bo'yicha ishlab chiqarish ruxsati kerak.</p>
    </section>

    <template v-else>
      <div v-if="actionError" class="banner danger mt-4" role="alert">
        <div class="grow">
          {{ actionError }}
          <span v-if="orders.actionTraceId"> · trace {{ orders.actionTraceId }}</span>
        </div>
      </div>

      <section v-if="currentJobs.length === 0 && queuedJobs.length === 0" class="st-empty mt-4">
        <h3>
          {{ isManagerView ? "Bu stanokda ish yo'q" : "Sizga tayinlangan ish yo'q" }}
        </h3>
        <p v-if="isManagerView">Buyurtma tasdiqlanib ustaga tayinlangach, u shu yerda ko'rinadi.</p>
        <p v-else>
          Rahbar buyurtmani sizga tayinlagach, u shu yerda ko'rinadi — sahifa o'zi yangilanib
          turadi.
        </p>
      </section>

      <template v-else>
        <!-- The running job(s): pinned, loud, one primary action. -->
        <div v-if="currentJobs.length > 0" class="mt-6">
          <article v-for="job in currentJobs" :key="job.id" class="prod-hero">
            <span class="prod-hero-eyebrow">Hozirgi ish</span>
            <div class="flex items-baseline justify-between gap-3">
              <h4>{{ job.order_number }}</h4>
              <span class="text-xs text-ink-muted">{{ startedLabel(job) }}</span>
            </div>
            <div class="meta">
              {{ jobMeta(job) }} · {{ job.client_first_name }} uchun
              <template v-if="isManagerView && assigneeName(job)">
                · {{ assigneeName(job) }}</template
              >
              <template v-if="isManagerView && multiBranch"> · {{ job.branch_name }}</template>
            </div>
            <div class="mt-4 flex flex-wrap gap-2">
              <button
                v-if="canActOn(job)"
                type="button"
                class="mp-button mp-button-primary min-h-12 grow px-5 text-[15px]"
                :disabled="orders.actionLoading"
                @click="requestComplete(job)"
              >
                ✓ Tugatdim
              </button>
              <RouterLink
                :to="rolePath(`/workshop/production/${job.id}`)"
                class="mp-button mp-button-outline min-h-12 px-5 text-[15px]"
              >
                Chizma
              </RouterLink>
            </div>
          </article>
        </div>

        <!-- The queue, FIFO by assignment. Managers see it grouped by master. -->
        <div class="prod-sec-h">
          <span>Navbatda</span>
          <span>{{ queuedJobs.length }} ta</span>
        </div>
        <div v-if="queuedJobs.length === 0" class="st-empty !px-4 !py-6">
          <h3>Navbatda ish yo'q</h3>
          <p>Yangi tayinlangan ishlar shu yerda chiqadi.</p>
        </div>
        <template v-else-if="queuedGroups">
          <div v-for="group in queuedGroups" :key="group.worker?.id ?? 'unassigned'">
            <div class="prod-group-h">{{ group.worker?.full_name ?? 'Tayinlanmagan' }}</div>
            <article v-for="job in group.jobs" :key="job.id" class="prod-card">
              <div class="flex items-baseline justify-between gap-3">
                <h4>{{ job.order_number }}</h4>
                <span class="text-xs text-ink-muted">{{ queuedLabel(job) }}</span>
              </div>
              <div class="meta">
                {{ jobMeta(job) }} · {{ job.client_first_name }} uchun
                <template v-if="multiBranch"> · {{ job.branch_name }}</template>
              </div>
              <div class="mt-3 flex flex-wrap gap-2">
                <button
                  v-if="canActOn(job)"
                  type="button"
                  class="mp-button mp-button-primary min-h-11 px-4"
                  :disabled="orders.actionLoading || pendingJobId === job.id"
                  @click="startJob(job)"
                >
                  {{ pendingJobId === job.id ? 'Boshlanmoqda…' : 'Boshlash' }}
                </button>
                <RouterLink
                  :to="rolePath(`/workshop/production/${job.id}`)"
                  class="mp-button mp-button-outline min-h-11 px-4"
                >
                  Chizma
                </RouterLink>
              </div>
            </article>
          </div>
        </template>
        <template v-else>
          <article v-for="job in queuedJobs" :key="job.id" class="prod-card">
            <div class="flex items-baseline justify-between gap-3">
              <h4>{{ job.order_number }}</h4>
              <span class="text-xs text-ink-muted">{{ queuedLabel(job) }}</span>
            </div>
            <div class="meta">{{ jobMeta(job) }} · {{ job.client_first_name }} uchun</div>
            <div class="mt-3 flex flex-wrap gap-2">
              <button
                v-if="canActOn(job)"
                type="button"
                class="mp-button mp-button-primary min-h-11 px-4"
                :disabled="orders.actionLoading || pendingJobId === job.id"
                @click="startJob(job)"
              >
                {{ pendingJobId === job.id ? 'Boshlanmoqda…' : 'Boshlash' }}
              </button>
              <RouterLink
                :to="rolePath(`/workshop/production/${job.id}`)"
                class="mp-button mp-button-outline min-h-11 px-4"
              >
                Chizma
              </RouterLink>
            </div>
          </article>
        </template>
      </template>

      <!-- Today's finished work: the master's own tally, straight from the
           production stamps the labor report reads. Rendered outside the
           empty-state fork — finishing the last job must not erase the day. -->
      <template v-if="completedToday.length > 0">
        <div class="prod-sec-h">
          <span>Bugun tugatildi</span>
          <span>{{ completedToday.length }} ta</span>
        </div>
        <div class="card p-3">
          <div v-for="job in completedToday" :key="job.id" class="prod-done-row">
            <span class="font-extrabold text-accent" aria-hidden="true">✓</span>
            <span class="font-mono text-[13px] font-bold text-ink">{{ job.order_number }}</span>
            <span class="truncate">{{ jobMeta(job) }}</span>
            <span class="when">{{ completedLabel(job) }}</span>
          </div>
        </div>
      </template>
    </template>

    <ConfirmDialog
      :open="pendingComplete !== null"
      :title="completeDialogTitle"
      :message="completeDialogMessage"
      confirm-label="✓ Ha, tugatdim"
      cancel-label="Bekor qilish"
      busy-label="Bajarilmoqda"
      :busy="orders.actionLoading"
      @cancel="pendingComplete = null"
      @confirm="confirmComplete"
    >
      <p class="mt-2 text-xs text-ink-muted">
        Xatolik bo'lsa, rahbar bir qadam orqaga qaytara oladi.
      </p>
      <p v-if="actionError" class="mt-2 text-sm font-bold text-danger">{{ actionError }}</p>
    </ConfirmDialog>
  </section>
</template>
