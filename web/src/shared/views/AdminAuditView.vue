<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  adminActorLabel,
  adminDateTime,
  adminEntityLabel,
  adminStatusTransitionLabel,
  dropdownOption,
} from '@/shared/app/adminUi'
import AdminErrorState from '@/shared/components/AdminErrorState.vue'
import AppTabs from '@/shared/components/AppTabs.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import { useAdminStore, type AuditActionQuery, type AuditStatusQuery } from '@/shared/stores/admin'

const admin = useAdminStore()
const tab = ref<'actions' | 'status'>('actions')
const query = ref('')
const workshopFilter = ref('all')
const entityFilter = ref('all')
const timeFilter = ref('all')
const PAGE_SIZE = 50
const MAX_RESULTS = 200
const actionsHasMore = ref(false)
const statusHasMore = ref(false)
const loadingMore = ref(false)
let refreshTimer: number | undefined

const tabOptions = [
  { value: 'actions', label: 'Amallar' },
  { value: 'status', label: "Holat o'zgarishlari" },
]

const workshopName = computed(() => {
  const map = new Map<string, string>()
  for (const workshop of admin.workshops) map.set(workshop.id, workshop.name)
  return map
})
const workshopOptions = computed(() => [
  dropdownOption('all', 'Ustaxona', 'barcha ustaxonalar'),
  ...admin.workshops.map((workshop) => dropdownOption(workshop.id, workshop.name)),
])
const entityOptions = computed(() => [
  dropdownOption('all', 'Obyekt turi', 'barcha turlar'),
  ...Array.from(
    new Set(
      [...admin.auditActions, ...admin.auditStatusChanges]
        .map((row) => row.entity_type)
        .filter((value): value is string => !!value),
    ),
  ).map((entity) => dropdownOption(entity, adminEntityLabel(entity), entity)),
])
const timeOptions = [
  dropdownOption('all', 'Vaqt', 'barcha vaqt'),
  dropdownOption('24h', 'Oxirgi 24 soat', ''),
  dropdownOption('7d', 'Oxirgi 7 kun', ''),
]

function isoDate(value: Date): string {
  return value.toISOString().slice(0, 10)
}

function selectedDateRange(): Pick<AuditActionQuery, 'date_from' | 'date_to'> {
  if (timeFilter.value === 'all') return {}
  const end = new Date()
  const start = new Date(end)
  if (timeFilter.value === '7d') start.setDate(start.getDate() - 6)
  return { date_from: isoDate(start), date_to: isoDate(end) }
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
}

function actorQuery(value: string): string | undefined {
  return ['platform_user', 'workshop_user', 'client', 'system'].some((actor) =>
    actor.startsWith(value),
  )
    ? value
    : undefined
}

function actionQuery(offset: number): AuditActionQuery {
  const needle = query.value.trim()
  const params: AuditActionQuery = { limit: PAGE_SIZE, offset, ...selectedDateRange() }
  if (workshopFilter.value !== 'all') params.workshop_id = workshopFilter.value
  if (entityFilter.value !== 'all') params.entity_type = entityFilter.value
  if (needle) {
    if (isUuid(needle)) params.entity_id = needle
    else {
      const actor = actorQuery(needle)
      if (actor) params.actor = actor
      else params.action_prefix = needle
    }
  }
  return params
}

function statusQuery(offset: number): AuditStatusQuery {
  const needle = query.value.trim()
  const params: AuditStatusQuery = { limit: PAGE_SIZE, offset, ...selectedDateRange() }
  if (workshopFilter.value !== 'all') params.workshop_id = workshopFilter.value
  if (entityFilter.value !== 'all') params.entity_type = entityFilter.value
  if (needle) {
    if (isUuid(needle)) params.entity_id = needle
    else params.actor = needle
  }
  return params
}

const hasMore = computed(() =>
  tab.value === 'actions' ? actionsHasMore.value : statusHasMore.value,
)
const visibleCount = computed(() =>
  tab.value === 'actions' ? admin.auditActions.length : admin.auditStatusChanges.length,
)

function detailsText(value: Record<string, unknown> | null) {
  if (!value) return '-'
  return JSON.stringify(value)
}

function actorText(actorType: string, actorId: string | null | undefined) {
  const label = adminActorLabel(actorType)
  return actorId ? `${label} ${actorId.slice(0, 8)}` : label
}

async function refresh() {
  if (refreshTimer !== undefined) {
    window.clearTimeout(refreshTimer)
    refreshTimer = undefined
  }
  const result = await admin.loadAudit({
    actions: actionQuery(0),
    status: statusQuery(0),
  })
  actionsHasMore.value =
    result.actionsCount === PAGE_SIZE && admin.auditActions.length < MAX_RESULTS
  statusHasMore.value =
    result.statusCount === PAGE_SIZE && admin.auditStatusChanges.length < MAX_RESULTS
}

function queueRefresh() {
  if (refreshTimer !== undefined) window.clearTimeout(refreshTimer)
  refreshTimer = window.setTimeout(() => {
    refreshTimer = undefined
    void refresh()
  }, 200)
}

async function loadMore() {
  loadingMore.value = true
  try {
    const result = await admin.loadAudit({
      actions: actionQuery(admin.auditActions.length),
      status: statusQuery(admin.auditStatusChanges.length),
      appendActions: true,
      appendStatus: true,
    })
    actionsHasMore.value =
      result.actionsCount === PAGE_SIZE && admin.auditActions.length < MAX_RESULTS
    statusHasMore.value =
      result.statusCount === PAGE_SIZE && admin.auditStatusChanges.length < MAX_RESULTS
  } finally {
    loadingMore.value = false
  }
}

function csvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`
}

function exportCsv() {
  const rows =
    tab.value === 'actions'
      ? [
          ['Vaqt', 'Ustaxona', 'Obyekt turi', 'Amal', 'Aktor', 'Tafsilot'],
          ...admin.auditActions.map((row) => [
            adminDateTime(row.created_at),
            row.workshop_id ? (workshopName.value.get(row.workshop_id) ?? row.workshop_id) : '-',
            adminEntityLabel(row.entity_type),
            row.action,
            actorText(row.actor_type, row.actor_user_id),
            detailsText(row.details),
          ]),
        ]
      : [
          ['Vaqt', 'Obyekt', 'Obyekt ID', "O'tish", 'Aktor', 'Sabab'],
          ...admin.auditStatusChanges.map((row) => [
            adminDateTime(row.changed_at),
            adminEntityLabel(row.entity_type),
            row.entity_id,
            adminStatusTransitionLabel(row.from_status, row.to_status),
            actorText(row.actor_type, row.actor_user_id),
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

onBeforeUnmount(() => {
  if (refreshTimer !== undefined) window.clearTimeout(refreshTimer)
})

watch([query, workshopFilter, entityFilter, timeFilter], queueRefresh)
</script>

<template>
  <section>
    <div class="admin-page-head">
      <div>
        <h1>Audit logi</h1>
      </div>
    </div>

    <div class="admin-filters">
      <label class="admin-filter-input">
        <span>Qidiruv</span>
        <input v-model="query" placeholder="Obyekt ID, amal yoki aktor" />
      </label>
      <FormSelect
        v-model="workshopFilter"
        class="admin-filter-select"
        label="Ustaxona"
        :options="workshopOptions"
      />
      <FormSelect
        v-model="entityFilter"
        class="admin-filter-select"
        label="Obyekt turi"
        :options="entityOptions"
      />
      <FormSelect
        v-model="timeFilter"
        class="admin-filter-select"
        label="Vaqt"
        :options="timeOptions"
      />
      <button type="button" class="mp-button mp-button-outline" @click="exportCsv">CSV</button>
    </div>

    <AppTabs
      v-model="tab"
      :tabs="tabOptions"
      id-prefix="audit"
      label="Audit turi"
      variant="admin"
    />

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
      id="audit-actions-panel"
      role="tabpanel"
      aria-labelledby="audit-actions-tab"
      class="admin-card"
    >
      <div v-if="admin.auditActions.length === 0" class="admin-empty m-5">
        <h3>Amallar logi bo'sh</h3>
        <p>O'zgartiruvchi platforma amallari shu yerda ko'rinadi.</p>
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
            <tr v-for="row in admin.auditActions" :key="row.id">
              <td class="admin-mono text-ink-muted">{{ adminDateTime(row.created_at) }}</td>
              <td class="text-ink-muted">
                {{
                  row.workshop_id
                    ? (workshopName.get(row.workshop_id) ?? row.workshop_id.slice(0, 8))
                    : '-'
                }}
              </td>
              <td>{{ adminEntityLabel(row.entity_type) }}</td>
              <td class="nm">
                {{ row.action }}
                <small>{{ row.summary ?? "Izoh yo'q" }}</small>
              </td>
              <td class="admin-mono text-ink-muted">
                {{ actorText(row.actor_type, row.actor_user_id) }}
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
      id="audit-status-panel"
      role="tabpanel"
      aria-labelledby="audit-status-tab"
      class="admin-card"
    >
      <div v-if="admin.auditStatusChanges.length === 0" class="admin-empty m-5">
        <h3>Holat logi bo'sh</h3>
        <p>Holat o'zgarishlari shu yerda ko'rinadi.</p>
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
            <tr v-for="row in admin.auditStatusChanges" :key="row.id">
              <td class="admin-mono text-ink-muted">{{ adminDateTime(row.changed_at) }}</td>
              <td class="nm">
                {{ adminEntityLabel(row.entity_type) }}
                <small>{{ row.entity_id }}</small>
              </td>
              <td class="admin-mono">
                {{ adminStatusTransitionLabel(row.from_status, row.to_status) }}
              </td>
              <td class="admin-mono text-ink-muted">
                {{ actorText(row.actor_type, row.actor_user_id) }}
              </td>
              <td>{{ row.reason ?? '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="!admin.opsLoading && !admin.opsError" class="mt-4 flex items-center gap-3">
      <button
        v-if="hasMore"
        type="button"
        class="mp-button mp-button-outline"
        :disabled="loadingMore"
        @click="loadMore"
      >
        {{ loadingMore ? 'Yuklanmoqda' : "Ko'proq yuklash" }}
      </button>
      <span class="text-xs text-ink-muted">
        {{ visibleCount }} ta yozuv · serverda filtrlangan
      </span>
    </div>
  </section>
</template>
