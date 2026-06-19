<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { adminDateTime } from '@/shared/app/adminUi'
import AdminErrorState from '@/shared/components/AdminErrorState.vue'
import { useAdminStore } from '@/shared/stores/admin'

const admin = useAdminStore()
const tab = ref<'actions' | 'status'>('actions')
const query = ref('')

const filteredActions = computed(() => {
  const needle = query.value.trim().toLowerCase()
  if (!needle) return admin.auditActions
  return admin.auditActions.filter((row) =>
    [row.action, row.entity_type ?? '', row.entity_id ?? '', row.summary ?? '', row.trace_id]
      .join(' ')
      .toLowerCase()
      .includes(needle),
  )
})
const filteredStatus = computed(() => {
  const needle = query.value.trim().toLowerCase()
  if (!needle) return admin.auditStatusChanges
  return admin.auditStatusChanges.filter((row) =>
    [row.entity_type, row.entity_id, row.from_status ?? '', row.to_status, row.reason ?? '']
      .join(' ')
      .toLowerCase()
      .includes(needle),
  )
})

function detailsText(value: Record<string, unknown> | null) {
  if (!value) return '-'
  return JSON.stringify(value)
}

onMounted(admin.loadAudit)
</script>

<template>
  <section>
    <div class="admin-page-head">
      <div>
        <h1>Audit log . platforma</h1>
        <p class="sub">Mutating use cases va status transitions append-only loglari.</p>
      </div>
      <button type="button" class="mp-button mp-button-outline" @click="admin.loadAudit">
        Yangilash
      </button>
    </div>

    <div class="admin-filters">
      <label class="admin-filter-input">
        <span class="sr-only">Obyekt ID yoki action</span>
        <input v-model="query" placeholder="Obyekt ID yoki action" />
      </label>
      <button type="button" class="mp-button mp-button-outline">CSV</button>
    </div>

    <div class="admin-tabs" role="tablist" aria-label="Audit turi">
      <button
        type="button"
        class="admin-tab"
        :class="{ on: tab === 'actions' }"
        @click="tab = 'actions'"
      >
        Amallar (Action log)
      </button>
      <button
        type="button"
        class="admin-tab"
        :class="{ on: tab === 'status' }"
        @click="tab = 'status'"
      >
        Holat o'zgarishlari (Status changes)
      </button>
    </div>

    <section v-if="admin.opsLoading" class="admin-card p-5" aria-live="polite">
      <div class="admin-skeleton-line w-3/5"></div>
      <div class="admin-skeleton-line w-4/5"></div>
      <div class="admin-skeleton-line w-2/5"></div>
    </section>

    <AdminErrorState
      v-else-if="admin.opsError"
      :code="admin.opsError"
      :trace-id="admin.opsTraceId"
      title="Audit log yuklanmadi"
      @retry="admin.loadAudit"
    />

    <section v-else-if="tab === 'actions'" class="admin-card">
      <div v-if="filteredActions.length === 0" class="admin-empty m-5">
        <h3>Action log bo'sh</h3>
        <p>Mutating platform amallari shu yerda ko'rinadi.</p>
      </div>
      <div v-else class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>Vaqt</th>
              <th>Ustaxona</th>
              <th>Modul</th>
              <th>Amal</th>
              <th>Aktor</th>
              <th>Tafsilot</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredActions" :key="row.id">
              <td class="admin-mono text-ink-muted">{{ adminDateTime(row.created_at) }}</td>
              <td class="admin-mono text-ink-muted">{{ row.workshop_id?.slice(0, 8) ?? '-' }}</td>
              <td>{{ row.entity_type ?? '-' }}</td>
              <td class="nm">
                {{ row.action }}
                <small>{{ row.summary ?? 'No summary' }}</small>
              </td>
              <td class="admin-mono text-ink-muted">
                {{ row.actor_type }} {{ row.actor_user_id?.slice(0, 8) ?? '' }}
              </td>
              <td class="max-w-[320px] truncate admin-mono text-ink-muted">
                {{ detailsText(row.details) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-else class="admin-card">
      <div v-if="filteredStatus.length === 0" class="admin-empty m-5">
        <h3>Status log bo'sh</h3>
        <p>Status transitions shu yerda ko'rinadi.</p>
      </div>
      <div v-else class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>Vaqt</th>
              <th>Entity</th>
              <th>Change</th>
              <th>Aktor</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredStatus" :key="row.id">
              <td class="admin-mono text-ink-muted">{{ adminDateTime(row.changed_at) }}</td>
              <td class="nm">
                {{ row.entity_type }}
                <small>{{ row.entity_id }}</small>
              </td>
              <td class="admin-mono">{{ row.from_status ?? '-' }} -> {{ row.to_status }}</td>
              <td class="admin-mono text-ink-muted">
                {{ row.actor_type }} {{ row.actor_user_id?.slice(0, 8) ?? '' }}
              </td>
              <td>{{ row.reason ?? '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>
