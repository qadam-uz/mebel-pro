<script setup lang="ts">
import { onMounted } from 'vue'

import { useAdminStore } from '@/shared/stores/admin'

const admin = useAdminStore()

function formatDate(value: string) {
  return new Intl.DateTimeFormat('en', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function detailsText(value: Record<string, unknown> | null) {
  if (!value) return 'No details'
  return JSON.stringify(value)
}

onMounted(admin.loadAudit)
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold text-ink">Audit</h1>
        <p class="mt-2 max-w-2xl text-base text-ink-soft">
          Cross-workshop action history and status changes for platform review.
        </p>
      </div>
      <button type="button" class="mp-button mp-button-outline" @click="admin.loadAudit">
        Refresh
      </button>
    </div>

    <section v-if="admin.opsLoading" class="mp-surface p-5 text-sm font-bold text-ink-soft">
      Loading audit logs
    </section>
    <section v-else-if="admin.opsError" class="mp-surface p-5 text-sm font-bold text-danger">
      Audit logs could not be loaded.
      <span v-if="admin.opsTraceId" class="font-mono">trace {{ admin.opsTraceId }}</span>
    </section>
    <section v-else class="grid gap-5 xl:grid-cols-2">
      <div class="mp-surface overflow-hidden">
        <div class="border-b border-hairline px-5 py-4">
          <h2 class="font-serif text-xl font-semibold text-ink">Actions</h2>
          <p class="mt-1 text-sm text-ink-soft">Append-only mutating use cases.</p>
        </div>
        <div v-if="admin.auditActions.length === 0" class="px-5 py-6 text-sm text-ink-soft">
          No action logs yet.
        </div>
        <div v-else class="overflow-x-auto">
          <table class="min-w-full text-left text-sm">
            <thead class="bg-sunk text-xs uppercase text-ink-muted">
              <tr>
                <th class="px-5 py-3">When</th>
                <th class="px-5 py-3">Action</th>
                <th class="px-5 py-3">Actor</th>
                <th class="px-5 py-3">Entity</th>
                <th class="px-5 py-3">Details</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-hairline">
              <tr v-for="row in admin.auditActions" :key="row.id">
                <td class="px-5 py-3 font-mono text-xs text-ink-soft">
                  {{ formatDate(row.created_at) }}
                </td>
                <td class="px-5 py-3">
                  <div class="font-mono text-xs font-bold text-ink">{{ row.action }}</div>
                  <div class="mt-1 text-xs text-ink-soft">{{ row.summary ?? 'No summary' }}</div>
                </td>
                <td class="px-5 py-3 font-mono text-xs text-ink-soft">
                  {{ row.actor_type }}
                </td>
                <td class="px-5 py-3 font-mono text-xs text-ink-soft">
                  {{ row.entity_type ?? 'none' }}
                </td>
                <td class="max-w-[280px] truncate px-5 py-3 font-mono text-xs text-ink-soft">
                  {{ detailsText(row.details) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="mp-surface overflow-hidden">
        <div class="border-b border-hairline px-5 py-4">
          <h2 class="font-serif text-xl font-semibold text-ink">Status changes</h2>
          <p class="mt-1 text-sm text-ink-soft">State transitions written with the action.</p>
        </div>
        <div v-if="admin.auditStatusChanges.length === 0" class="px-5 py-6 text-sm text-ink-soft">
          No status changes yet.
        </div>
        <div v-else class="overflow-x-auto">
          <table class="min-w-full text-left text-sm">
            <thead class="bg-sunk text-xs uppercase text-ink-muted">
              <tr>
                <th class="px-5 py-3">When</th>
                <th class="px-5 py-3">Entity</th>
                <th class="px-5 py-3">Change</th>
                <th class="px-5 py-3">Actor</th>
                <th class="px-5 py-3">Reason</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-hairline">
              <tr v-for="row in admin.auditStatusChanges" :key="row.id">
                <td class="px-5 py-3 font-mono text-xs text-ink-soft">
                  {{ formatDate(row.changed_at) }}
                </td>
                <td class="px-5 py-3 font-mono text-xs font-bold text-ink">
                  {{ row.entity_type }}
                </td>
                <td class="px-5 py-3 font-mono text-xs text-ink-soft">
                  {{ row.from_status ?? 'new' }} -> {{ row.to_status }}
                </td>
                <td class="px-5 py-3 font-mono text-xs text-ink-soft">
                  {{ row.actor_type }}
                </td>
                <td class="px-5 py-3 text-sm text-ink-soft">
                  {{ row.reason ?? 'No reason' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </section>
</template>
