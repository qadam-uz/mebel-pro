<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  adminDate,
  adminDateTime,
  errorStatusLabel,
  errorStatusTone,
  workshopStatusLabel,
} from '@/shared/app/adminUi'
import { useRolePath } from '@/shared/app/paths'
import AdminErrorState from '@/shared/components/AdminErrorState.vue'
import { useToast } from '@/shared/composables/useToast'
import { useAdminStore } from '@/shared/stores/admin'

const admin = useAdminStore()
const rolePath = useRolePath()
const toast = useToast()

const today = adminDate(new Date().toISOString())
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
  try {
    const run = await admin.runJob(name)
    if (run.status === 'skipped') toast.warn("Job allaqachon ishlamoqda — o'tkazib yuborildi")
    else toast.success('Ish qayta ishga tushirildi')
  } catch {
    toast.danger('Ish ishga tushmadi')
  } finally {
    running.value = false
  }
}

onMounted(loadAll)
</script>

<template>
  <section>
    <div class="admin-page-head">
      <div>
        <h1>Platforma asosiy</h1>
        <p class="date">
          Loyiha kuni . <b>{{ today }}</b> . platforma sog'ligi va insidentlar
        </p>
      </div>
      <button type="button" class="mp-button mp-button-outline" @click="admin.loadOverview">
        Yangilash
      </button>
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
      title="Platforma ma'lumotlari yuklanmadi"
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
            <span>{{ failedJobs[0]?.definition.name ?? 'hammasi ok' }}</span>
            <span>ko'rish →</span>
          </div>
        </RouterLink>
      </div>

      <div class="admin-grid-two">
        <section class="admin-card">
          <div class="admin-card-h">
            <h2>So'nggi ustaxonalar</h2>
            <RouterLink :to="rolePath('/admin/workshops')" class="admin-more">hammasi →</RouterLink>
          </div>
          <div class="admin-card-b flush">
            <div v-if="recentWorkshops.length === 0" class="admin-empty m-5">
              <h3>Ustaxona yo'q</h3>
              <p>Yangi ustaxona provisioning qilingandan keyin shu yerda ko'rinadi.</p>
            </div>
            <div v-else class="admin-table-wrap">
              <table class="admin-table">
                <thead>
                  <tr>
                    <th>Ustaxona</th>
                    <th>Egasi</th>
                    <th>Filiallar</th>
                    <th>Yaratildi</th>
                    <th>Holat</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="workshop in recentWorkshops" :key="workshop.id">
                    <td class="nm">
                      {{ workshop.name }}
                      <small>{{ workshop.code }}</small>
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
                <p>Scheduler oxirgi natijalari normal.</p>
              </div>
              <article
                v-for="job in failedJobs"
                v-else
                :key="job.definition.id"
                class="admin-row-item"
              >
                <span class="admin-pill admin-pill-danger">Muvaffaqiyatsiz</span>
                <span>
                  <b>{{ job.definition.name }}</b>
                  <small class="block text-ink-muted">
                    {{ adminDateTime(job.definition.last_run_at) }}
                  </small>
                </span>
                <button
                  type="button"
                  class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                  :disabled="running"
                  @click="rerun(job.definition.name)"
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
          <h2>Platforma resurslari</h2>
          <span class="sub">katalog va operatorlik yuzalari</span>
        </div>
        <div class="admin-card-b grid gap-3 md:grid-cols-3">
          <RouterLink
            :to="rolePath('/admin/catalog/manufacturers')"
            class="mp-button mp-button-outline"
          >
            Ishlab chiqaruvchilar
          </RouterLink>
          <RouterLink
            :to="rolePath('/admin/catalog/materials')"
            class="mp-button mp-button-outline"
          >
            Materiallar
          </RouterLink>
          <RouterLink :to="rolePath('/admin/platform/users')" class="mp-button mp-button-outline">
            Operatorlar . {{ overview?.platform_users_active ?? 0 }}
          </RouterLink>
        </div>
      </section>
    </template>
  </section>
</template>
