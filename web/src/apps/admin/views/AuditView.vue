<script setup lang="ts">
// Audit viewer — two tabs: Action log (action/family, module, actor, entity
// type+id, date range, workshop) and Status changes (entity type+id, from→to,
// actor, date range, workshop). Read-only, paginated, JSON details preview.
// Mirrors prototype admin/audit.html.
import { computed, onMounted, ref, watch } from 'vue'
import { ApiError } from '@/shared/api'
import { AppPagination, AppTabs, ErrorState, FilterBar, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtDateTime } from '@/shared/format'
import * as api from '../api'
import type { ActionLogRow, StatusChangeRow } from '../api/types'

const PAGE_SIZE = 50

const tab = ref('actions')
const tabs = computed(() => [
  { id: 'actions', label: t('admin.tabActions') },
  { id: 'statusChanges', label: t('admin.tabStatusChanges') },
])

const loading = ref(true)
const error = ref<ApiError | null>(null)
const actions = ref<ActionLogRow[]>([])
const statusChanges = ref<StatusChangeRow[]>([])
const page = ref(1)

// Shared filters
const fAction = ref('')
const fFamily = ref('')
const fModule = ref('')
const fActor = ref('')
const fEntityType = ref('')
const fEntityId = ref('')
const fDateFrom = ref('')
const fDateTo = ref('')
// Status-change-only
const fFromStatus = ref('')
const fToStatus = ref('')

const expanded = ref<Set<string>>(new Set())

// A full page came back ⇒ there may be more.
const hasMore = computed(() =>
  tab.value === 'actions'
    ? actions.value.length === PAGE_SIZE
    : statusChanges.value.length === PAGE_SIZE,
)
const pageCount = computed(() => (hasMore.value ? page.value + 1 : page.value))

async function load() {
  loading.value = true
  error.value = null
  const offset = (page.value - 1) * PAGE_SIZE
  try {
    if (tab.value === 'actions') {
      actions.value = await api.listAuditActions({
        action: fAction.value || undefined,
        family: fFamily.value || undefined,
        module: fModule.value || undefined,
        actor: fActor.value || undefined,
        entityType: fEntityType.value || undefined,
        entityId: fEntityId.value || undefined,
        dateFrom: fDateFrom.value || undefined,
        dateTo: fDateTo.value || undefined,
        limit: PAGE_SIZE,
        offset,
      })
    } else {
      statusChanges.value = await api.listAuditStatusChanges({
        entityType: fEntityType.value || undefined,
        entityId: fEntityId.value || undefined,
        fromStatus: fFromStatus.value || undefined,
        toStatus: fToStatus.value || undefined,
        actor: fActor.value || undefined,
        dateFrom: fDateFrom.value || undefined,
        dateTo: fDateTo.value || undefined,
        limit: PAGE_SIZE,
        offset,
      })
    }
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  page.value = 1
  load()
}

function clearFilters() {
  fAction.value = ''
  fFamily.value = ''
  fModule.value = ''
  fActor.value = ''
  fEntityType.value = ''
  fEntityId.value = ''
  fDateFrom.value = ''
  fDateTo.value = ''
  fFromStatus.value = ''
  fToStatus.value = ''
  applyFilters()
}

function toggleRow(id: string) {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}

watch(tab, () => {
  page.value = 1
  expanded.value = new Set()
  load()
})
watch(page, load)

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>{{ t('admin.auditTitle') }}</h1>
        <p class="sub">{{ t('admin.auditSub') }}</p>
      </div>
    </div>

    <AppTabs v-model="tab" :tabs="tabs" />

    <FilterBar>
      <template v-if="tab === 'actions'">
        <div class="input">
          <input v-model="fAction" :placeholder="t('admin.auditActionPlaceholder')" />
        </div>
        <div class="input">
          <input v-model="fFamily" :placeholder="t('admin.auditFamilyPlaceholder')" />
        </div>
        <div class="input">
          <input v-model="fModule" :placeholder="t('admin.auditModuleAll')" />
        </div>
      </template>
      <template v-else>
        <div class="input">
          <input v-model="fFromStatus" :placeholder="t('admin.auditFromStatus')" />
        </div>
        <div class="input">
          <input v-model="fToStatus" :placeholder="t('admin.auditToStatus')" />
        </div>
      </template>
      <div class="input">
        <input v-model="fActor" :placeholder="t('admin.auditActorPlaceholder')" />
      </div>
      <div class="input">
        <input v-model="fEntityType" :placeholder="t('admin.auditEntityTypePlaceholder')" />
      </div>
      <div class="input">
        <input v-model="fEntityId" :placeholder="t('admin.auditEntityIdPlaceholder')" />
      </div>
      <input v-model="fDateFrom" type="date" :aria-label="t('admin.auditDateFrom')" />
      <input v-model="fDateTo" type="date" :aria-label="t('admin.auditDateTo')" />
      <button class="btn btn-acc btn-sm" type="button" @click="applyFilters">
        {{ t('admin.apply') }}
      </button>
      <button class="btn btn-ghost btn-sm" type="button" @click="clearFilters">
        {{ t('admin.clearFilters') }}
      </button>
    </FilterBar>

    <ErrorState v-if="error" :error="error" :title="t('admin.auditLoadFailed')" :retry="load" />

    <div v-else-if="loading" class="card">
      <div class="card-b"><div class="sk sk-line" style="width: 60%" /></div>
    </div>

    <!-- ACTIONS -->
    <template v-else-if="tab === 'actions'">
      <div v-if="actions.length === 0" class="st-empty">
        <div class="ic">≡</div>
        <h3>{{ t('admin.actionsEmpty') }}</h3>
        <p>{{ t('admin.actionsEmptyBody') }}</p>
      </div>
      <div v-else class="card">
        <table class="tbl">
          <thead>
            <tr>
              <th>{{ t('admin.colTime') }}</th>
              <th>{{ t('admin.colModule') }}</th>
              <th>{{ t('admin.colAction') }}</th>
              <th>{{ t('admin.colActor') }}</th>
              <th>{{ t('admin.colEntity') }}</th>
              <th>{{ t('admin.colDetail') }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="a in actions" :key="a.id">
              <tr :class="{ clickable: a.details }" @click="a.details && toggleRow(a.id)">
                <td class="num" style="font-size: 11.5px; color: var(--ink-6)">
                  {{ fmtDateTime(a.created_at) }}
                </td>
                <td>
                  <small style="color: var(--ink-8); font-size: 12px">{{
                    a.entity_type ?? '—'
                  }}</small>
                </td>
                <td><StatusBadge tone="conf" :label="a.action" /></td>
                <td>
                  <small style="color: var(--ink-8)">{{ a.actor_type }}</small>
                </td>
                <td>
                  <small class="num" style="color: var(--ink-8); font-size: 11px">{{
                    a.entity_id ?? '—'
                  }}</small>
                </td>
                <td>
                  <small style="color: var(--ink-10); font-size: 12.5px">{{
                    a.summary ?? '—'
                  }}</small>
                  <span v-if="a.details" class="toggle">{{ expanded.has(a.id) ? '▾' : '▸' }}</span>
                </td>
              </tr>
              <tr v-if="a.details && expanded.has(a.id)">
                <td colspan="6">
                  <pre class="json">{{ JSON.stringify(a.details, null, 2) }}</pre>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </template>

    <!-- STATUS CHANGES -->
    <template v-else>
      <div v-if="statusChanges.length === 0" class="st-empty">
        <div class="ic">≡</div>
        <h3>{{ t('admin.statusEmpty') }}</h3>
        <p>{{ t('admin.statusEmptyBody') }}</p>
      </div>
      <div v-else class="card">
        <table class="tbl">
          <thead>
            <tr>
              <th>{{ t('admin.colTime') }}</th>
              <th>{{ t('admin.colEntity') }}</th>
              <th>{{ t('admin.colTransition') }}</th>
              <th>{{ t('admin.colActor') }}</th>
              <th>{{ t('admin.colReason') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in statusChanges" :key="s.id">
              <td class="num" style="font-size: 11.5px; color: var(--ink-6)">
                {{ fmtDateTime(s.changed_at) }}
              </td>
              <td>
                <small style="color: var(--ink-8); font-size: 12px">{{ s.entity_type }}</small>
                <small class="num" style="display: block; color: var(--ink-6); font-size: 11px">{{
                  s.entity_id
                }}</small>
              </td>
              <td>
                <small style="color: var(--ink-10); font-size: 12.5px"
                  >{{ s.from_status ?? '—' }} → <b>{{ s.to_status }}</b></small
                >
              </td>
              <td>
                <small style="color: var(--ink-8)">{{ s.actor_type }}</small>
              </td>
              <td>
                <small style="color: var(--ink-8); font-size: 12px">{{ s.reason ?? '—' }}</small>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <AppPagination
      v-if="!loading && !error && pageCount > 1"
      v-model:page="page"
      :page-count="pageCount"
      style="margin-top: 14px"
    />
  </div>
</template>

<style scoped>
.toggle {
  margin-left: 6px;
  color: var(--ink-6);
}
.json {
  background: var(--sunk);
  border-radius: 8px;
  padding: 12px 14px;
  font: 400 12px/1.5 var(--f-mono);
  color: var(--ink-10);
  overflow: auto;
  max-height: 320px;
  margin: 0;
}
</style>
