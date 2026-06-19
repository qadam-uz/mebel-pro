<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { adminDateTime, dropdownOption } from '@/shared/app/adminUi'
import AdminErrorState from '@/shared/components/AdminErrorState.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { useAdminStore } from '@/shared/stores/admin'

const admin = useAdminStore()
const tab = ref<'actions' | 'status'>('actions')
const query = ref('')
const workshopFilter = ref('all')
const entityFilter = ref('all')
const timeFilter = ref('all')
const limit = ref(50)
const MAX_LIMIT = 200

const workshopName = computed(() => {
  const map = new Map<string, string>()
  for (const workshop of admin.workshops) map.set(workshop.id, workshop.name)
  return map
})
const workshopOptions = computed(() => [
  dropdownOption('all', 'Ustaxona', 'barcha ustaxonalar'),
  ...admin.workshops.map((workshop) => dropdownOption(workshop.id, workshop.name, workshop.code)),
])
const entityOptions = computed(() => [
  dropdownOption('all', 'Obyekt turi', 'barcha turlar'),
  ...Array.from(
    new Set(
      [...admin.auditActions, ...admin.auditStatusChanges]
        .map((row) => row.entity_type)
        .filter((value): value is string => !!value),
    ),
  ).map((entity) => dropdownOption(entity, entity, '')),
])
const timeOptions = [
  dropdownOption('all', 'Vaqt', 'barcha vaqt'),
  dropdownOption('24h', 'Oxirgi 24 soat', ''),
  dropdownOption('7d', 'Oxirgi 7 kun', ''),
]

function withinWindow(timestamp: string): boolean {
  if (timeFilter.value === 'all') return true
  const windowMs = timeFilter.value === '24h' ? 86_400_000 : 604_800_000
  return Date.now() - new Date(timestamp).getTime() <= windowMs
}

const filteredActions = computed(() => {
  const needle = query.value.trim().toLowerCase()
  return admin.auditActions.filter((row) => {
    if (workshopFilter.value !== 'all' && row.workshop_id !== workshopFilter.value) return false
    if (entityFilter.value !== 'all' && row.entity_type !== entityFilter.value) return false
    if (!withinWindow(row.created_at)) return false
    if (!needle) return true
    return [row.action, row.entity_type ?? '', row.entity_id ?? '', row.summary ?? '', row.trace_id]
      .join(' ')
      .toLowerCase()
      .includes(needle)
  })
})
const filteredStatus = computed(() => {
  const needle = query.value.trim().toLowerCase()
  return admin.auditStatusChanges.filter((row) => {
    if (workshopFilter.value !== 'all' && row.workshop_id !== workshopFilter.value) return false
    if (entityFilter.value !== 'all' && row.entity_type !== entityFilter.value) return false
    if (!withinWindow(row.changed_at)) return false
    if (!needle) return true
    return [row.entity_type, row.entity_id, row.from_status ?? '', row.to_status, row.reason ?? '']
      .join(' ')
      .toLowerCase()
      .includes(needle)
  })
})

// A full page back means there may be more rows server-side (the 50-row default
// is the silent cap AB-17 makes visible/extendable).
const hasMore = computed(
  () =>
    limit.value < MAX_LIMIT &&
    (admin.auditActions.length >= limit.value || admin.auditStatusChanges.length >= limit.value),
)

function detailsText(value: Record<string, unknown> | null) {
  if (!value) return '-'
  return JSON.stringify(value)
}

function refresh() {
  void admin.loadAudit(limit.value)
}

function loadMore() {
  limit.value = Math.min(MAX_LIMIT, limit.value + 50)
  refresh()
}

function csvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`
}

function exportCsv() {
  const rows =
    tab.value === 'actions'
      ? [
          ['Vaqt', 'Ustaxona', 'Obyekt turi', 'Amal', 'Aktor', 'Tafsilot'],
          ...filteredActions.value.map((row) => [
            adminDateTime(row.created_at),
            row.workshop_id ? (workshopName.value.get(row.workshop_id) ?? row.workshop_id) : '-',
            row.entity_type ?? '-',
            row.action,
            `${row.actor_type} ${row.actor_user_id ?? ''}`.trim(),
            detailsText(row.details),
          ]),
        ]
      : [
          ['Vaqt', 'Obyekt', 'Obyekt ID', "O'tish", 'Aktor', 'Sabab'],
          ...filteredStatus.value.map((row) => [
            adminDateTime(row.changed_at),
            row.entity_type,
            row.entity_id,
            `${row.from_status ?? '-'} -> ${row.to_status}`,
            `${row.actor_type} ${row.actor_user_id ?? ''}`.trim(),
            row.reason ?? '-',
          ]),
        ]
  const csv = rows.map((cells) => cells.map((cell) => csvCell(String(cell))).join(',')).join('\n')
  const blob = new Blob([`﻿${csv}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `audit-${tab.value}.csv`
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

onMounted(() => {
  refresh()
  if (admin.workshops.length === 0) void admin.loadWorkshops()
})
</script>

<template>
  <section>
    <div class="admin-page-head">
      <div>
        <h1>Audit log . platforma</h1>
        <p class="sub">Mutating use case va status transition append-only loglari.</p>
      </div>
      <button type="button" class="mp-button mp-button-outline" @click="refresh">Yangilash</button>
    </div>

    <div class="admin-filters">
      <label class="admin-filter-input">
        <span class="sr-only">Obyekt ID yoki amal</span>
        <input v-model="query" placeholder="Obyekt ID yoki amal" />
      </label>
      <ProjectDropdown v-model="workshopFilter" label="Ustaxona" :options="workshopOptions" />
      <ProjectDropdown v-model="entityFilter" label="Obyekt turi" :options="entityOptions" />
      <ProjectDropdown v-model="timeFilter" label="Vaqt" :options="timeOptions" />
      <button type="button" class="mp-button mp-button-outline" @click="exportCsv">CSV</button>
    </div>

    <div class="admin-tabs" role="tablist" aria-label="Audit turi">
      <button
        id="audit-tab-actions"
        type="button"
        role="tab"
        :aria-selected="tab === 'actions'"
        aria-controls="audit-panel-actions"
        class="admin-tab"
        :class="{ on: tab === 'actions' }"
        @click="tab = 'actions'"
      >
        Amallar
      </button>
      <button
        id="audit-tab-status"
        type="button"
        role="tab"
        :aria-selected="tab === 'status'"
        aria-controls="audit-panel-status"
        class="admin-tab"
        :class="{ on: tab === 'status' }"
        @click="tab = 'status'"
      >
        Holat o'zgarishlari
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
      @retry="refresh"
    />

    <section
      v-else-if="tab === 'actions'"
      id="audit-panel-actions"
      role="tabpanel"
      aria-labelledby="audit-tab-actions"
      class="admin-card"
    >
      <div v-if="filteredActions.length === 0" class="admin-empty m-5">
        <h3>Action log bo'sh</h3>
        <p>Mutating platform amallari shu yerda ko'rinadi.</p>
      </div>
      <div v-else class="admin-table-wrap">
        <table class="admin-table wide">
          <thead>
            <tr>
              <th>Vaqt</th>
              <th>Ustaxona</th>
              <th>Obyekt turi</th>
              <th>Amal</th>
              <th>Aktor</th>
              <th>Tafsilot</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredActions" :key="row.id">
              <td class="admin-mono text-ink-muted">{{ adminDateTime(row.created_at) }}</td>
              <td class="text-ink-muted">
                {{
                  row.workshop_id
                    ? (workshopName.get(row.workshop_id) ?? row.workshop_id.slice(0, 8))
                    : '-'
                }}
              </td>
              <td>{{ row.entity_type ?? '-' }}</td>
              <td class="nm">
                {{ row.action }}
                <small>{{ row.summary ?? "Izoh yo'q" }}</small>
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

    <section
      v-else
      id="audit-panel-status"
      role="tabpanel"
      aria-labelledby="audit-tab-status"
      class="admin-card"
    >
      <div v-if="filteredStatus.length === 0" class="admin-empty m-5">
        <h3>Status log bo'sh</h3>
        <p>Status transition shu yerda ko'rinadi.</p>
      </div>
      <div v-else class="admin-table-wrap">
        <table class="admin-table wide">
          <thead>
            <tr>
              <th>Vaqt</th>
              <th>Obyekt</th>
              <th>O'zgarish</th>
              <th>Aktor</th>
              <th>Sabab</th>
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

    <div v-if="!admin.opsLoading && !admin.opsError" class="mt-4 flex items-center gap-3">
      <button v-if="hasMore" type="button" class="mp-button mp-button-outline" @click="loadMore">
        Ko'proq yuklash
      </button>
      <span class="text-xs text-ink-muted">
        {{ tab === 'actions' ? filteredActions.length : filteredStatus.length }} ta yozuv · eng
        so'nggi {{ limit }} tagacha
      </span>
    </div>
  </section>
</template>
