<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { adminDateTime, jobStatusTone, statusLabel } from '@/shared/app/adminUi'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { useFocusTrap } from '@/shared/composables/useFocusTrap'
import { useToast } from '@/shared/composables/useToast'
import { useAdminStore, type PlatformJobSummary } from '@/shared/stores/admin'

const admin = useAdminStore()
const toast = useToast()
const runningJob = ref<string | null>(null)
const runError = ref<string | null>(null)
const selectedJobName = ref<string | null>(null)
const confirmJob = ref<{ name: string; retry: boolean } | null>(null)

const selectedJob = computed(() =>
  selectedJobName.value
    ? admin.jobs.find((job) => job.definition.name === selectedJobName.value)
    : null,
)

const logPanel = ref<HTMLElement | null>(null)
const logOpen = computed(() => selectedJobName.value !== null)
const logTrap = useFocusTrap(logPanel, logOpen, () => (selectedJobName.value = null))

function askRun(job: PlatformJobSummary) {
  confirmJob.value = {
    name: job.definition.name,
    retry: job.definition.last_result === 'failed',
  }
}

async function confirmRun() {
  const target = confirmJob.value
  if (!target) return
  confirmJob.value = null
  runningJob.value = target.name
  runError.value = null
  try {
    await admin.runJob(target.name)
    toast.success('Ish ishga tushirildi')
  } catch {
    runError.value = 'job_run_failed'
    toast.danger('Ish ishga tushmadi')
  } finally {
    runningJob.value = null
  }
}

function openLog(job: PlatformJobSummary) {
  selectedJobName.value = job.definition.name
}

onMounted(admin.loadJobs)
</script>

<template>
  <section>
    <div class="admin-page-head">
      <div>
        <h1>Background ish . scheduler</h1>
        <p class="sub">In-process scheduler holati, oxirgi natija va manual trigger.</p>
      </div>
      <button type="button" class="mp-button mp-button-outline" @click="admin.loadJobs">
        Yangilash
      </button>
    </div>

    <section v-if="admin.opsLoading" class="admin-card p-5">
      <div class="admin-skeleton-line w-3/5"></div>
      <div class="admin-skeleton-line w-4/5"></div>
      <div class="admin-skeleton-line w-2/5"></div>
    </section>

    <section v-else-if="admin.opsError" class="admin-error">
      <h3>Background ish yuklanmadi</h3>
      <p>
        Scheduler endpoint javob bermadi.
        <span v-if="admin.opsTraceId" class="admin-mono">trace {{ admin.opsTraceId }}</span>
      </p>
    </section>

    <section v-else-if="admin.jobs.length === 0" class="admin-empty">
      <h3>Registered job yo'q</h3>
      <p>Default scheduler jobs bootstrap qilingandan keyin ko'rinadi.</p>
    </section>

    <section v-else class="admin-card">
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>Ish nomi</th>
              <th>Jadval</th>
              <th>Oxirgi ishlashi</th>
              <th>Natija</th>
              <th>Xulosa</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="job in admin.jobs"
              :key="job.definition.id"
              :class="{ 'bg-danger-soft': job.definition.last_result === 'failed' }"
            >
              <td class="nm">
                {{ job.definition.name }}
                <small>{{ job.definition.enabled ? 'enabled' : 'disabled' }}</small>
              </td>
              <td class="admin-mono text-ink-muted">{{ job.definition.schedule }}</td>
              <td class="admin-mono text-ink-muted">
                {{ adminDateTime(job.definition.last_run_at) }}
              </td>
              <td>
                <span class="admin-pill" :class="jobStatusTone(job.definition.last_result)">
                  {{ statusLabel(job.definition.last_result) }}
                </span>
              </td>
              <td class="max-w-[360px] truncate">
                {{
                  job.recent_runs[0]?.brief_log ??
                  job.recent_runs[0]?.error_message ??
                  'Jurnal hali yoq'
                }}
              </td>
              <td class="admin-right">
                <div class="flex justify-end gap-2">
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    @click="openLog(job)"
                  >
                    Jurnalni ko'rish
                  </button>
                  <button
                    type="button"
                    class="mp-button mp-button-primary min-h-9 px-3 text-xs"
                    :disabled="runningJob === job.definition.name || job.definition.running"
                    @click="askRun(job)"
                  >
                    {{
                      runningJob === job.definition.name
                        ? 'Ishlamoqda'
                        : job.definition.last_result === 'failed'
                          ? 'Qayta urinish (failed)'
                          : 'Hozir ishga tushirish'
                    }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <p
      v-if="runError"
      class="mt-4 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
    >
      Job ishga tushmadi.
    </p>

    <template v-if="selectedJob">
      <div class="admin-modal-scrim" aria-hidden="true" @click="selectedJobName = null"></div>
      <section
        ref="logPanel"
        class="admin-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="job-log-title"
        tabindex="-1"
        @keydown="logTrap.onKeydown"
      >
        <div class="admin-modal-h">
          <h3 id="job-log-title">Ish jurnali</h3>
          <button
            type="button"
            class="admin-icon-button"
            aria-label="Yopish"
            @click="selectedJobName = null"
          >
            x
          </button>
        </div>
        <div class="admin-modal-b">
          <p class="mb-4 font-mono text-sm font-bold text-ink">{{ selectedJob.definition.name }}</p>
          <div v-if="selectedJob.recent_runs.length === 0" class="admin-empty">
            <h3>Run yo'q</h3>
            <p>Job hali ishga tushmagan.</p>
          </div>
          <article
            v-for="run in selectedJob.recent_runs"
            v-else
            :key="run.id"
            class="mb-3 rounded-md border border-hairline bg-sunk p-4"
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <span class="admin-pill" :class="jobStatusTone(run.status)">
                {{ statusLabel(run.status) }}
              </span>
              <span class="admin-mono text-ink-muted">{{ adminDateTime(run.started_at) }}</span>
            </div>
            <p class="mt-3 text-sm text-ink">
              {{ run.brief_log ?? run.error_message ?? 'No log' }}
            </p>
            <p v-if="run.trace_id" class="mt-2 admin-mono text-ink-muted">
              trace {{ run.trace_id }}
            </p>
          </article>
        </div>
        <div class="admin-modal-f">
          <button type="button" class="mp-button mp-button-outline" @click="selectedJobName = null">
            Yopish
          </button>
        </div>
      </section>
    </template>

    <ConfirmDialog
      :open="confirmJob !== null"
      :title="confirmJob?.retry ? 'Ishni qayta urinish' : 'Ishni hozir ishga tushirish'"
      :message="
        confirmJob?.retry
          ? `${confirmJob?.name} muvaffaqiyatsiz tugagan edi — uni qo'lda qayta ishga tushirasizmi?`
          : `${confirmJob?.name} rejadan tashqari hozir ishga tushiriladi.`
      "
      confirm-label="Ishga tushirish"
      busy-label="Ishlamoqda"
      cancel-label="Bekor qilish"
      @confirm="confirmRun"
      @cancel="confirmJob = null"
    />
  </section>
</template>
