<script setup lang="ts">
// Error monitor — grouped-by-code table (code, module, 24h/7d counts, last
// occurrence, preview), filters (module, code, status, count threshold), and a
// detail modal (message, stack, masked context, affected workshops, trace ids,
// Resolve → confirm). Empty: "No errors recorded — nice."
// Mirrors prototype admin/errors.html.
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ApiError } from '@/shared/api'
import { AppModal, ErrorState, FilterBar, FilterChip, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtDateTime } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { isErrorHot } from '../lib/admin'
import * as api from '../api'
import type { ErrorGroupDetail, ErrorGroupRow, ErrorGroupStatus } from '../api/types'

const route = useRoute()
const toast = useToast()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const rows = ref<ErrorGroupRow[]>([])

const moduleFilter = ref('')
const codeFilter = ref('')
const statusFilter = ref<'all' | ErrorGroupStatus>('all')
const thresholdFilter = ref(0)

const THRESHOLDS = [0, 3, 10]

const detailOpen = ref(false)
const detail = ref<ErrorGroupDetail | null>(null)
const detailLoading = ref(false)

const confirmOpen = ref(false)
const pendingResolveId = ref<string | null>(null)

const modules = computed(() => {
  const set = new Set<string>()
  for (const r of rows.value) if (r.module) set.add(r.module)
  return [...set].sort()
})

async function load() {
  loading.value = true
  error.value = null
  try {
    rows.value = await api.listErrors({
      module: moduleFilter.value || undefined,
      code: codeFilter.value || undefined,
      status: statusFilter.value === 'all' ? undefined : statusFilter.value,
      minCount24h: thresholdFilter.value || undefined,
    })
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

async function openDetail(row: ErrorGroupRow) {
  detailOpen.value = true
  detail.value = null
  detailLoading.value = true
  try {
    detail.value = await api.getError(row.id)
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
    detailOpen.value = false
  } finally {
    detailLoading.value = false
  }
}

function askResolve(id: string) {
  pendingResolveId.value = id
  confirmOpen.value = true
}

async function confirmResolve() {
  const id = pendingResolveId.value
  if (!id) return
  try {
    await api.resolveError(id)
    toast.ok(t('admin.errResolvedToast'))
    detailOpen.value = false
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    pendingResolveId.value = null
  }
}

function maskedContext(detail: ErrorGroupDetail): [string, string][] {
  const ev = detail.events[0]
  if (!ev?.context) return []
  return Object.entries(ev.context).map(([k, v]) => [k, String(v)])
}

onMounted(async () => {
  const code = route.query.code
  if (typeof code === 'string') codeFilter.value = code
  await load()
})
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>{{ t('admin.errorsTitle') }}</h1>
        <p class="sub">{{ t('admin.errorsSub') }}</p>
      </div>
    </div>

    <FilterBar>
      <select v-model="moduleFilter" @change="load">
        <option value="">{{ t('admin.allModules') }}</option>
        <option v-for="m in modules" :key="m" :value="m">{{ m }}</option>
      </select>
      <div class="input">
        <input v-model="codeFilter" :placeholder="t('admin.colCode')" @change="load" />
      </div>
      <select v-model.number="thresholdFilter" @change="load">
        <option v-for="thr in THRESHOLDS" :key="thr" :value="thr">
          {{ thr === 0 ? t('admin.anyCount') : t('admin.countGte', { n: thr }) }}
        </option>
      </select>
      <div class="chips">
        <FilterChip :active="statusFilter === 'all'" @click="((statusFilter = 'all'), load())">{{
          t('admin.statusAll')
        }}</FilterChip>
        <FilterChip :active="statusFilter === 'open'" @click="((statusFilter = 'open'), load())">{{
          t('admin.errOpen')
        }}</FilterChip>
        <FilterChip
          :active="statusFilter === 'resolved'"
          @click="((statusFilter = 'resolved'), load())"
          >{{ t('admin.errResolved') }}</FilterChip
        >
      </div>
    </FilterBar>

    <ErrorState v-if="error" :error="error" :title="t('admin.errorsLoadFailed')" :retry="load" />

    <div v-else-if="loading" class="card">
      <div class="card-b"><div class="sk sk-line" style="width: 60%" /></div>
    </div>

    <div v-else-if="rows.length === 0" class="st-empty">
      <div class="ic">✓</div>
      <h3>{{ t('admin.errorsEmptyNice') }}</h3>
      <p>{{ t('admin.errorsEmptyBody') }}</p>
    </div>

    <div v-else class="card">
      <table class="tbl">
        <thead>
          <tr>
            <th>{{ t('admin.colCode') }}</th>
            <th>{{ t('admin.colModule') }}</th>
            <th class="right">{{ t('admin.col24h') }}</th>
            <th class="right">{{ t('admin.col7d') }}</th>
            <th>{{ t('admin.colLast') }}</th>
            <th>{{ t('admin.colPreview') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in rows" :key="e.id" class="clickable" @click="openDetail(e)">
            <td class="nm">
              {{ e.code }}
              <StatusBadge
                v-if="e.status === 'resolved'"
                tone="ok"
                :label="t('admin.resolved')"
                style="margin-left: 4px"
              />
            </td>
            <td>
              <small style="color: var(--ink-8); font-size: 12px">{{ e.module ?? '—' }}</small>
            </td>
            <td class="amt right" :class="{ 'warn-text': isErrorHot(e.count_24h) }">
              {{ e.count_24h }}
            </td>
            <td class="amt right">{{ e.count_7d }}</td>
            <td class="num" style="font-size: 11.5px; color: var(--ink-6)">
              {{ e.last_occurred_at ? fmtDateTime(e.last_occurred_at) : '—' }}
            </td>
            <td>
              <small style="color: var(--ink-8); font-size: 12px">{{
                e.message_preview ?? ''
              }}</small>
            </td>
            <td @click.stop>
              <button
                v-if="e.status === 'open'"
                class="btn btn-outline btn-sm"
                type="button"
                @click="askResolve(e.id)"
              >
                {{ t('admin.resolveErr') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- DETAIL -->
    <AppModal v-model:open="detailOpen" :title="detail?.code ?? t('admin.errDetailTitle')" wide>
      <div v-if="detailLoading"><div class="sk sk-line" style="width: 60%" /></div>
      <template v-else-if="detail">
        <div class="banner danger">
          <div class="ic">!</div>
          <div class="grow">{{ detail.events[0]?.message ?? detail.message_preview ?? '' }}</div>
        </div>

        <h4 class="sect">{{ t('admin.errStack') }}</h4>
        <pre class="stack">{{ detail.events[0]?.stack || t('admin.logEmpty') }}</pre>

        <h4 class="sect">{{ t('admin.errContext') }}</h4>
        <table class="tbl">
          <tbody>
            <tr>
              <td class="muted" style="width: 180px">{{ t('common.traceId') }}</td>
              <td class="num">{{ detail.trace_ids.join(', ') || '—' }}</td>
            </tr>
            <tr>
              <td class="muted">{{ t('admin.colModule') }}</td>
              <td>{{ detail.module ?? '—' }}</td>
            </tr>
            <tr>
              <td class="muted">{{ t('admin.errAffectedWorkshops') }}</td>
              <td>
                <span v-if="detail.affected_workshops.length">{{
                  detail.affected_workshops.join(', ')
                }}</span>
                <span v-else style="color: var(--ink-6)">{{ t('admin.errNotTenant') }}</span>
              </td>
            </tr>
            <tr v-for="[k, v] in maskedContext(detail)" :key="k">
              <td class="muted">{{ k }}</td>
              <td class="num">{{ v }}</td>
            </tr>
          </tbody>
        </table>
      </template>
      <template #footer>
        <button class="btn btn-outline" type="button" @click="detailOpen = false">
          {{ t('common.close') }}
        </button>
        <button
          v-if="detail && detail.status === 'open'"
          class="btn btn-acc"
          type="button"
          @click="askResolve(detail.id)"
        >
          {{ t('admin.resolveErrBtn') }}
        </button>
      </template>
    </AppModal>

    <ConfirmDialog
      v-model:open="confirmOpen"
      :title="t('admin.resolveErrTitle')"
      :message="t('admin.resolveErrBody')"
      :ok-text="t('admin.resolveErrBtn')"
      @confirm="confirmResolve"
    />
  </div>
</template>

<style scoped>
.sect {
  font: 600 12px var(--f-ui);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ink-6);
  margin: 14px 0 8px;
}
.stack {
  background: var(--deep);
  color: #d6cdbe;
  padding: 14px 16px;
  border-radius: 8px;
  font: 500 12px/1.5 var(--f-mono);
  overflow: auto;
  max-height: 240px;
  white-space: pre-wrap;
}
</style>
