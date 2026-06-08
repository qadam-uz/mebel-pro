<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { useAdminStore, type JobRunStatus } from '@/shared/stores/admin'

const admin = useAdminStore()
const runningJob = ref<string | null>(null)
const runError = ref<string | null>(null)

const statusTone: Record<JobRunStatus | 'none', string> = {
  running: 'bg-info-soft text-info',
  ok: 'bg-success-soft text-success',
  failed: 'bg-danger-soft text-danger',
  skipped: 'bg-warning-soft text-warning',
  none: 'bg-sunk text-ink-muted',
}

function formatDate(value: string | null) {
  if (!value) return 'Never'
  return new Intl.DateTimeFormat('en', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

async function runJob(name: string) {
  runningJob.value = name
  runError.value = null
  try {
    await admin.runJob(name)
  } catch {
    runError.value = 'job_run_failed'
  } finally {
    runningJob.value = null
  }
}

onMounted(admin.loadJobs)
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold text-ink">Platform jobs</h1>
        <p class="mt-2 max-w-2xl text-base text-ink-soft">
          Scheduled maintenance jobs and manual retry controls.
        </p>
      </div>
      <button type="button" class="mp-button mp-button-outline" @click="admin.loadJobs">
        Refresh
      </button>
    </div>

    <section v-if="admin.opsLoading" class="mp-surface p-5 text-sm font-bold text-ink-soft">
      Loading jobs
    </section>
    <section v-else-if="admin.opsError" class="mp-surface p-5 text-sm font-bold text-danger">
      Jobs could not be loaded.
      <span v-if="admin.opsTraceId" class="font-mono">trace {{ admin.opsTraceId }}</span>
    </section>
    <section v-else-if="admin.jobs.length === 0" class="mp-surface p-5 text-sm text-ink-soft">
      No platform jobs are registered.
    </section>
    <section v-else class="space-y-4">
      <article
        v-for="job in admin.jobs"
        :key="job.definition.id"
        class="mp-surface overflow-hidden"
      >
        <div class="grid gap-4 border-b border-hairline px-5 py-4 lg:grid-cols-[1fr_auto]">
          <div>
            <div class="flex flex-wrap items-center gap-2">
              <h2 class="font-serif text-xl font-semibold text-ink">
                {{ job.definition.name }}
              </h2>
              <span class="mp-chip" :class="statusTone[job.definition.last_result ?? 'none']">
                <span class="mp-dot" aria-hidden="true"></span>
                {{ job.definition.last_result ?? 'no run' }}
              </span>
            </div>
            <p class="mt-1 text-sm text-ink-soft">
              {{ job.definition.schedule }} · last run
              {{ formatDate(job.definition.last_run_at) }}
            </p>
          </div>
          <button
            type="button"
            class="mp-button mp-button-primary"
            :disabled="runningJob === job.definition.name"
            @click="runJob(job.definition.name)"
          >
            {{ runningJob === job.definition.name ? 'Running' : 'Run now' }}
          </button>
        </div>

        <div v-if="job.recent_runs.length === 0" class="px-5 py-4 text-sm text-ink-soft">
          No recorded runs yet.
        </div>
        <div v-else class="overflow-x-auto">
          <table class="min-w-full text-left text-sm">
            <thead class="bg-sunk text-xs uppercase text-ink-muted">
              <tr>
                <th class="px-5 py-3">Started</th>
                <th class="px-5 py-3">Status</th>
                <th class="px-5 py-3">Log</th>
                <th class="px-5 py-3">Trace</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-hairline">
              <tr v-for="run in job.recent_runs" :key="run.id">
                <td class="px-5 py-3 font-mono text-xs text-ink-soft">
                  {{ formatDate(run.started_at) }}
                </td>
                <td class="px-5 py-3">
                  <span class="mp-chip" :class="statusTone[run.status]">
                    <span class="mp-dot" aria-hidden="true"></span>
                    {{ run.status }}
                  </span>
                </td>
                <td class="px-5 py-3 text-ink">
                  {{ run.brief_log ?? run.error_message ?? 'No log' }}
                </td>
                <td class="px-5 py-3 font-mono text-xs text-ink-muted">
                  {{ run.trace_id ?? 'none' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>

    <p v-if="runError" class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger">
      Job could not be run.
    </p>
  </section>
</template>
