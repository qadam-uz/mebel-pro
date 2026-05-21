<script setup lang="ts">
// Background jobs console — table (name, schedule, last run, last result,
// menu: Run now → confirm, View log → modal). Failed rows highlighted.
// "Already running" surfaces as the server's conflict toast.
// Mirrors prototype admin/jobs.html.
import { onMounted, ref } from 'vue'
import { ApiError } from '@/shared/api'
import { AppModal, ErrorState, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtDateTime } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import * as api from '../api'
import type { JobOut } from '../api/types'

const toast = useToast()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const rows = ref<JobOut[]>([])

const confirmOpen = ref(false)
const pendingJob = ref<JobOut | null>(null)

const logOpen = ref(false)
const logJob = ref<JobOut | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    rows.value = await api.listJobs()
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

function askRun(job: JobOut) {
  pendingJob.value = job
  confirmOpen.value = true
}

async function confirmRun() {
  const job = pendingJob.value
  if (!job) return
  try {
    await api.runJob(job.name)
    toast.ok(t('admin.jobStarted'))
    await load()
  } catch (e) {
    // 409 "job_already_running" surfaces here.
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    pendingJob.value = null
  }
}

function showLog(job: JobOut) {
  logJob.value = job
  logOpen.value = true
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>{{ t('admin.jobsTitle') }}</h1>
        <p class="sub">{{ t('admin.jobsSub') }}</p>
      </div>
    </div>

    <ErrorState v-if="error" :error="error" :title="t('admin.jobsLoadFailed')" :retry="load" />

    <div v-else-if="loading" class="card">
      <div class="card-b"><div class="sk sk-line" style="width: 60%" /></div>
    </div>

    <div v-else-if="rows.length === 0" class="st-empty">
      <div class="ic">⌥</div>
      <h3>{{ t('admin.jobsEmpty') }}</h3>
      <p>{{ t('admin.jobsEmptyBody') }}</p>
    </div>

    <div v-else class="card">
      <table class="tbl">
        <thead>
          <tr>
            <th>{{ t('admin.colJob') }}</th>
            <th>{{ t('admin.colSchedule') }}</th>
            <th>{{ t('admin.colLastRun') }}</th>
            <th>{{ t('admin.colResult') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="j in rows" :key="j.name" :class="{ 'job-fail': j.last_result === 'failed' }">
            <td class="nm">
              {{ j.name }}
              <span v-if="j.last_result === 'running'" class="pill p-cut" style="font-size: 9.5px"
                ><span class="pd" />{{ t('admin.jobRunning') }}</span
              >
            </td>
            <td>
              <small style="color: var(--ink-8); font: 400 12px var(--f-mono)">
                {{ t('admin.everySeconds', { n: j.interval_seconds }) }}
              </small>
            </td>
            <td class="num" style="font-size: 11.5px; color: var(--ink-6)">
              {{ j.last_finished_at ? fmtDateTime(j.last_finished_at) : '—' }}
            </td>
            <td>
              <StatusBadge
                v-if="j.last_result === 'failed'"
                tone="bad"
                :label="t('admin.jobFailed')"
              />
              <StatusBadge
                v-else-if="j.last_result === 'running'"
                tone="cut"
                :label="t('admin.jobRunning')"
              />
              <StatusBadge v-else-if="j.last_result === 'ok'" tone="ok" :label="t('admin.jobOk')" />
              <span v-else style="color: var(--ink-6)">—</span>
            </td>
            <td>
              <div style="display: flex; gap: 6px; justify-content: flex-end">
                <button class="btn btn-outline btn-sm" type="button" @click="showLog(j)">
                  {{ t('admin.viewLog') }}
                </button>
                <button
                  class="btn btn-acc btn-sm"
                  type="button"
                  :disabled="j.last_result === 'running'"
                  @click="askRun(j)"
                >
                  {{ j.last_result === 'running' ? t('admin.jobRunning') : t('admin.runNow') }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <ConfirmDialog
      v-model:open="confirmOpen"
      :title="t('admin.runNowTitle')"
      :message="t('admin.runNowBody')"
      :ok-text="t('admin.runNowBtn')"
      @confirm="confirmRun"
    />

    <AppModal v-model:open="logOpen" :title="logJob?.name ?? t('admin.logTitle')">
      <pre class="log-body">{{ logJob?.last_log || t('admin.logEmpty') }}</pre>
      <template #footer>
        <button class="btn btn-outline" type="button" @click="logOpen = false">
          {{ t('common.close') }}
        </button>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.job-fail td {
  background: var(--danger-tint);
}
.job-fail td:first-child {
  box-shadow: inset 3px 0 0 var(--danger);
}
.log-body {
  background: var(--deep);
  color: #d6cdbe;
  padding: 14px 16px;
  border-radius: 8px;
  font: 500 12px/1.5 var(--f-mono);
  overflow: auto;
  max-height: 60vh;
  white-space: pre-wrap;
}
</style>
