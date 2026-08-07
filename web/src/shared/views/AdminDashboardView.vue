<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  adminCount,
  adminDate,
  adminDateTime,
  adminErrorMessage,
  adminJobNameLabel,
  errorStatusLabel,
  errorStatusTone,
  workshopStatusLabel,
} from '@/shared/app/adminUi'
import { apiErrorCode } from '@/shared/api/client'
import { useRolePath } from '@/shared/app/paths'
import AdminErrorState from '@/shared/components/AdminErrorState.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import TrendSparkline from '@/shared/components/TrendSparkline.vue'
import { useToast } from '@/shared/composables/useToast'
import { useAdminStore, type SignupMetrics } from '@/shared/stores/admin'

const admin = useAdminStore()
const rolePath = useRolePath()
const toast = useToast()

const failedJobs = computed(() =>
  admin.jobs.filter((job) => job.definition.last_result === 'failed').slice(0, 2),
)
const openErrors = computed(() => admin.errors.filter((error) => error.status === 'open'))
const recentErrors = computed(() => admin.errors.slice(0, 4))
const recentWorkshops = computed(() => admin.workshops.slice(0, 5))
const overview = computed(() => admin.overview)
const isLoading = computed(
  () => admin.loading && !overview.value && admin.workshops.length === 0 && admin.jobs.length === 0,
)
const hasError = computed(() => admin.error && !overview.value)
const partialFailure = ref(false)
const running = ref(false)
const confirmJob = ref<string | null>(null)

// AB-119: the KPI row above answers "how big is the platform"; this grid answers
// "how is it moving". Every calendar period is on screen at once — a period
// switcher would hide two thirds of the data behind a click for no gain, and
// registrations genuinely have no weekly column to switch to.
interface TrendCell {
  value: number
  spark: number[]
}

interface TrendRow {
  key: string
  label: string
  cells: (TrendCell | null)[]
}

const trendColumns = [
  { key: 'daily', label: 'Kunlik', window: "so'nggi 14 kun" },
  { key: 'weekly', label: 'Haftalik', window: "so'nggi 12 hafta" },
  { key: 'monthly', label: 'Oylik', window: "so'nggi 12 oy" },
  { key: 'yearly', label: 'Yillik', window: "so'nggi 5 yil" },
]

function signupCells(metrics: SignupMetrics): (TrendCell | null)[] {
  return [
    { value: metrics.daily, spark: metrics.spark.daily },
    null,
    { value: metrics.monthly, spark: metrics.spark.monthly },
    { value: metrics.yearly, spark: metrics.spark.yearly },
  ]
}

const trendRows = computed<TrendRow[]>(() => {
  const data = overview.value
  if (!data) return []
  return [
    {
      key: 'orders',
      label: 'Buyurtmalar',
      cells: [
        { value: data.orders.daily, spark: data.orders.spark.daily },
        { value: data.orders.weekly, spark: data.orders.spark.weekly },
        { value: data.orders.monthly, spark: data.orders.spark.monthly },
        { value: data.orders.yearly, spark: data.orders.spark.yearly },
      ],
    },
    {
      key: 'workshop_signups',
      label: 'Ustaxona registratsiyalari',
      cells: signupCells(data.workshop_signups),
    },
    {
      key: 'client_signups',
      label: 'Mijoz registratsiyalari',
      cells: signupCells(data.client_signups),
    },
  ]
})

// AB-14 / AB-46: the dashboard only needs overview + workshops + jobs + errors
// (the operator count comes from `overview`, so the full catalog/operator lists
// are no longer pre-pulled here). Run the loads sequentially and snapshot each
// result so a single failed sub-load surfaces a non-fatal banner instead of
// being lost to the shared loading/error refs (no concurrent clobber).
async function loadAll() {
  partialFailure.value = false
  await admin.loadOverview()
  if (admin.error) partialFailure.value = true
  await admin.loadWorkshops()
  if (admin.error) partialFailure.value = true
  await admin.loadJobs()
  if (admin.opsError) partialFailure.value = true
  await admin.loadErrors()
  if (admin.opsError) partialFailure.value = true
}

async function rerun(name: string) {
  running.value = true
  confirmJob.value = null
  try {
    const run = await admin.runJob(name)
    if (run.status === 'skipped')
      toast.warn("Fon vazifa allaqachon ishlamoqda — o'tkazib yuborildi")
    else toast.success('Fon vazifa qayta ishga tushirildi')
  } catch (error) {
    toast.danger(adminErrorMessage(apiErrorCode(error), 'Fon vazifa ishga tushmadi.'))
  } finally {
    running.value = false
  }
}

function requestRerun(name: string) {
  confirmJob.value = name
}

onMounted(loadAll)
</script>

<template>
  <section>
    <div class="admin-page-head">
      <div>
        <h1>Asosiy</h1>
      </div>
    </div>

    <section v-if="isLoading" class="admin-kpis" aria-live="polite">
      <div v-for="index in 4" :key="index" class="admin-card p-5">
        <div class="admin-skeleton-line w-3/5"></div>
        <div class="admin-skeleton-line h-8 w-2/3"></div>
        <div class="admin-skeleton-line w-4/5"></div>
      </div>
    </section>

    <AdminErrorState
      v-else-if="hasError"
      :code="admin.error"
      :trace-id="admin.traceId"
      title="Ma'lumotlar yuklanmadi"
      @retry="loadAll"
    />

    <template v-else>
      <p
        v-if="partialFailure"
        class="mb-4 rounded-md bg-warning-soft px-4 py-3 text-sm font-bold text-warning"
        role="alert"
      >
        Ba'zi bo'limlarni yangilab bo'lmadi — ko'rsatilgan ma'lumotlar to'liq bo'lmasligi mumkin.
        <button type="button" class="ml-2 underline" @click="loadAll">Qayta urinish</button>
      </p>

      <div class="admin-kpis">
        <RouterLink :to="rolePath('/admin/workshops')" class="admin-kpi">
          <div class="admin-kpi-label">Faol ustaxonalar</div>
          <div class="admin-kpi-value">
            {{ overview?.workshops_active ?? 0 }}
            <small>/ {{ overview?.workshops_total ?? admin.workshops.length }}</small>
          </div>
          <div class="admin-kpi-detail">
            <span>{{ overview?.workshops_blocked ?? 0 }} bloklangan</span>
            <span>ro'yxat →</span>
          </div>
        </RouterLink>

        <RouterLink :to="rolePath('/admin/workshops')" class="admin-kpi">
          <div class="admin-kpi-label">Filiallar . mijozlar</div>
          <div class="admin-kpi-value">
            {{ overview?.branches_total ?? 0 }}
            <small>filial</small>
          </div>
          <div class="admin-kpi-detail">
            <span>{{ overview?.clients_total ?? 0 }} mijoz platformada</span>
          </div>
        </RouterLink>

        <RouterLink
          :to="rolePath('/admin/platform/errors')"
          class="admin-kpi"
          :class="{ warning: openErrors.length > 0 }"
        >
          <div class="admin-kpi-label">Xatoliklar . 24 soat</div>
          <div class="admin-kpi-value">
            {{ openErrors.reduce((sum, row) => sum + row.count_24h, 0) }}
          </div>
          <div class="admin-kpi-detail">
            <span>{{ openErrors.length }} ta ochiq kod</span>
            <span>monitor →</span>
          </div>
        </RouterLink>

        <RouterLink
          :to="rolePath('/admin/platform/jobs')"
          class="admin-kpi"
          :class="{ danger: failedJobs.length > 0 }"
        >
          <div class="admin-kpi-label">Fon vazifalar</div>
          <div class="admin-kpi-value">
            {{ failedJobs.length }}
            <small>muvaffaqiyatsiz</small>
          </div>
          <div class="admin-kpi-detail">
            <span>
              {{ failedJobs[0] ? adminJobNameLabel(failedJobs[0].definition.name) : 'hammasi ok' }}
            </span>
            <span>ko'rish →</span>
          </div>
        </RouterLink>
      </div>

      <section class="admin-card mb-5">
        <div class="admin-card-h">
          <h2>Dinamika</h2>
          <span class="text-xs text-ink-muted"> Toshkent vaqti · joriy davr hali tugamagan </span>
        </div>
        <div class="admin-card-b flush">
          <div v-if="trendRows.length === 0" class="admin-empty m-5">
            <h3>Ko'rsatkichlar yuklanmadi</h3>
            <p>Sahifani qayta yuklang — dinamika ma'lumotlari kelmadi.</p>
          </div>
          <div v-else class="admin-table-wrap">
            <table class="admin-table">
              <thead>
                <tr>
                  <th>Ko'rsatkich</th>
                  <th v-for="column in trendColumns" :key="column.key">
                    <span class="admin-trend-head">
                      {{ column.label }}
                      <small>{{ column.window }}</small>
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in trendRows" :key="row.key">
                  <td class="nm">{{ row.label }}</td>
                  <td v-for="(cell, index) in row.cells" :key="trendColumns[index]?.key">
                    <div v-if="cell" class="admin-trend-cell">
                      <span class="admin-trend-value">{{ adminCount(cell.value) }}</span>
                      <TrendSparkline :values="cell.spark" />
                    </div>
                    <span
                      v-else
                      class="admin-trend-void"
                      title="Registratsiyalar haftalik kesimda yuritilmaydi"
                    >
                      —
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <div class="admin-grid-two">
        <section class="admin-card">
          <div class="admin-card-h">
            <h2>So'nggi ustaxonalar</h2>
            <RouterLink :to="rolePath('/admin/workshops')" class="admin-more">hammasi →</RouterLink>
          </div>
          <div class="admin-card-b flush">
            <div v-if="recentWorkshops.length === 0" class="admin-empty m-5">
              <h3>Ustaxona yo'q</h3>
              <p>Yangi ustaxona yaratilgandan keyin shu yerda ko'rinadi.</p>
            </div>
            <div v-else class="admin-table-wrap">
              <table class="admin-table">
                <thead>
                  <tr>
                    <th>Ustaxona</th>
                    <th>Rahbar</th>
                    <th>Filiallar</th>
                    <th>Yaratildi</th>
                    <th>Holat</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="workshop in recentWorkshops" :key="workshop.id">
                    <td class="nm">
                      {{ workshop.name }}
                    </td>
                    <td class="admin-mono text-ink-muted">{{ workshop.owner_login }}</td>
                    <td class="admin-mono text-ink-muted">{{ workshop.branch_count }}</td>
                    <td class="admin-mono text-ink-muted">{{ adminDate(workshop.created_at) }}</td>
                    <td>
                      <span
                        class="admin-pill"
                        :class="
                          workshop.status === 'active' ? 'admin-pill-success' : 'admin-pill-danger'
                        "
                      >
                        {{ workshopStatusLabel(workshop.status) }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <div class="grid gap-5">
          <section class="admin-card">
            <div class="admin-card-h">
              <h2>Muvaffaqiyatsiz vazifalar</h2>
              <RouterLink :to="rolePath('/admin/platform/jobs')" class="admin-more">
                hammasi →
              </RouterLink>
            </div>
            <div class="admin-card-b">
              <div v-if="failedJobs.length === 0" class="admin-empty">
                <h3>Muvaffaqiyatsiz vazifa yo'q</h3>
                <p>Oxirgi ishga tushirishlar xatoliksiz tugagan.</p>
              </div>
              <article
                v-for="job in failedJobs"
                v-else
                :key="job.definition.id"
                class="admin-row-item"
              >
                <span class="admin-pill admin-pill-danger">Muvaffaqiyatsiz</span>
                <span>
                  <b>{{ adminJobNameLabel(job.definition.name) }}</b>
                  <small class="block text-ink-muted">
                    {{ adminDateTime(job.definition.last_run_at) }}
                  </small>
                </span>
                <button
                  type="button"
                  class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                  :disabled="running"
                  :aria-label="`${adminJobNameLabel(job.definition.name)} vazifasini qayta ishga tushirish`"
                  @click="requestRerun(job.definition.name)"
                >
                  Qayta
                </button>
              </article>
            </div>
          </section>

          <section class="admin-card">
            <div class="admin-card-h">
              <h2>So'nggi xatoliklar</h2>
              <RouterLink :to="rolePath('/admin/platform/errors')" class="admin-more">
                monitor →
              </RouterLink>
            </div>
            <div class="admin-card-b">
              <div v-if="recentErrors.length === 0" class="admin-empty">
                <h3>Xatolik yozilmagan</h3>
                <p>Monitor hozircha toza.</p>
              </div>
              <article
                v-for="record in recentErrors"
                v-else
                :key="record.id"
                class="admin-row-item"
              >
                <span class="admin-pill" :class="errorStatusTone(record.status)">
                  {{ errorStatusLabel(record.status) }}
                </span>
                <span class="min-w-0">
                  <b class="block truncate font-mono text-xs">{{ record.code }}</b>
                  <small class="block truncate text-ink-muted">{{ record.module }}</small>
                </span>
                <span class="admin-mono font-bold">{{ record.count_24h }}</span>
              </article>
            </div>
          </section>
        </div>
      </div>

      <section class="admin-card mt-5">
        <div class="admin-card-h">
          <h2>Resurslar</h2>
        </div>
        <div class="admin-card-b grid gap-3 md:grid-cols-3">
          <RouterLink
            :to="rolePath('/admin/catalog/manufacturers')"
            class="mp-button mp-button-outline"
          >
            Ishlab chiqaruvchilar
          </RouterLink>
          <RouterLink :to="rolePath('/admin/catalog/dekorlar')" class="mp-button mp-button-outline">
            Dekorlar
          </RouterLink>
          <RouterLink :to="rolePath('/admin/platform/users')" class="mp-button mp-button-outline">
            Adminlar . {{ overview?.platform_users_active ?? 0 }}
          </RouterLink>
        </div>
      </section>
    </template>

    <ConfirmDialog
      :open="confirmJob !== null"
      title="Ishni qayta urinish"
      :message="`${adminJobNameLabel(confirmJob)} muvaffaqiyatsiz tugagan edi — uni qo'lda qayta ishga tushirasizmi?`"
      confirm-label="Ishga tushirish"
      busy-label="Ishlamoqda"
      cancel-label="Bekor qilish"
      :busy="running"
      @confirm="confirmJob && rerun(confirmJob)"
      @cancel="confirmJob = null"
    />
  </section>
</template>
