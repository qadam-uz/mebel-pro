<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { useAdminStore, type ErrorRecord, type ErrorRecordStatus } from '@/shared/stores/admin'

const admin = useAdminStore()
const selectedId = ref<string | null>(null)
const resolvingId = ref<string | null>(null)
const actionError = ref<string | null>(null)

const selectedRecord = computed(() =>
  selectedId.value ? admin.errors.find((row) => row.id === selectedId.value) : null,
)

const statusTone: Record<ErrorRecordStatus, string> = {
  open: 'bg-danger-soft text-danger',
  resolved: 'bg-success-soft text-success',
}

function formatDate(value: string | null) {
  if (!value) return 'Never'
  return new Intl.DateTimeFormat('en', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function contextText(value: Record<string, unknown> | null) {
  if (!value) return 'No context'
  return JSON.stringify(value, null, 2)
}

async function openDetail(record: ErrorRecord) {
  selectedId.value = record.id
  actionError.value = null
  try {
    await admin.loadErrorDetail(record.id)
  } catch {
    actionError.value = 'error_detail_failed'
  }
}

async function resolveSelected() {
  if (!selectedId.value) return
  resolvingId.value = selectedId.value
  actionError.value = null
  try {
    await admin.resolveError(selectedId.value)
  } catch {
    actionError.value = 'error_resolve_failed'
  } finally {
    resolvingId.value = null
  }
}

onMounted(admin.loadErrors)
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold text-ink">Application errors</h1>
        <p class="mt-2 max-w-2xl text-base text-ink-soft">
          Grouped backend errors with occurrence traces and masked context.
        </p>
      </div>
      <button type="button" class="mp-button mp-button-outline" @click="admin.loadErrors">
        Refresh
      </button>
    </div>

    <section v-if="admin.opsLoading" class="mp-surface p-5 text-sm font-bold text-ink-soft">
      Loading errors
    </section>
    <section v-else-if="admin.opsError" class="mp-surface p-5 text-sm font-bold text-danger">
      Errors could not be loaded.
      <span v-if="admin.opsTraceId" class="font-mono">trace {{ admin.opsTraceId }}</span>
    </section>
    <section v-else-if="admin.errors.length === 0" class="mp-surface p-5 text-sm text-ink-soft">
      No errors recorded.
    </section>
    <section v-else class="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
      <div class="mp-surface overflow-hidden">
        <div class="overflow-x-auto">
          <table class="min-w-full text-left text-sm">
            <thead class="bg-sunk text-xs uppercase text-ink-muted">
              <tr>
                <th class="px-5 py-3">Code</th>
                <th class="px-5 py-3">Module</th>
                <th class="px-5 py-3">Counts</th>
                <th class="px-5 py-3">Last occurrence</th>
                <th class="px-5 py-3">Status</th>
                <th class="px-5 py-3">Action</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-hairline">
              <tr
                v-for="record in admin.errors"
                :key="record.id"
                :class="selectedId === record.id ? 'bg-accent-soft' : ''"
              >
                <td class="max-w-[320px] px-5 py-3">
                  <div class="truncate font-mono text-xs font-bold text-ink">
                    {{ record.code }}
                  </div>
                  <div class="mt-1 truncate text-xs text-ink-soft">
                    {{ record.preview_message ?? 'No preview' }}
                  </div>
                </td>
                <td class="px-5 py-3 font-mono text-xs text-ink-soft">{{ record.module }}</td>
                <td class="px-5 py-3 font-mono text-xs">
                  {{ record.count_24h }} / 24 h · {{ record.count_7d }} / 7 d
                </td>
                <td class="px-5 py-3 font-mono text-xs text-ink-soft">
                  {{ formatDate(record.last_occurred_at) }}
                </td>
                <td class="px-5 py-3">
                  <span class="mp-chip" :class="statusTone[record.status]">
                    <span class="mp-dot" aria-hidden="true"></span>
                    {{ record.status }}
                  </span>
                </td>
                <td class="px-5 py-3">
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    @click="openDetail(record)"
                  >
                    Inspect
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <aside class="mp-surface overflow-hidden">
        <div class="border-b border-hairline px-5 py-4">
          <h2 class="font-serif text-xl font-semibold text-ink">Error detail</h2>
          <p class="mt-1 text-sm text-ink-soft">
            {{ selectedRecord?.code ?? 'Select a row to inspect occurrences.' }}
          </p>
        </div>
        <div v-if="!admin.errorDetail || admin.errorDetail.record.id !== selectedId" class="p-5">
          <p class="text-sm text-ink-soft">No error selected.</p>
        </div>
        <div v-else class="space-y-4 p-5">
          <button
            type="button"
            class="mp-button mp-button-primary w-full"
            :disabled="admin.errorDetail.record.status === 'resolved' || resolvingId === selectedId"
            @click="resolveSelected"
          >
            {{ resolvingId === selectedId ? 'Resolving' : 'Resolve error code' }}
          </button>

          <article
            v-for="occurrence in admin.errorDetail.occurrences"
            :key="occurrence.id"
            class="rounded-md border border-hairline bg-sunk p-4"
          >
            <div class="font-mono text-xs font-bold text-ink">trace {{ occurrence.trace_id }}</div>
            <p class="mt-2 text-sm text-ink">{{ occurrence.message }}</p>
            <p class="mt-1 font-mono text-xs text-ink-muted">
              {{ formatDate(occurrence.occurred_at) }}
            </p>
            <pre
              class="mt-3 max-h-44 overflow-auto rounded bg-elevated p-3 text-xs text-ink-soft"
              >{{ contextText(occurrence.context) }}</pre
            >
          </article>
        </div>
      </aside>
    </section>

    <p v-if="actionError" class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger">
      Error action could not be completed.
    </p>
  </section>
</template>
