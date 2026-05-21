<script setup lang="ts">
// Worker production report — period + branch scope, table per worker, with a
// "record salary expense" shortcut that prefills the expense form.
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { ErrorState, FormField } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { useWorkshopAuth } from '../../store'
import * as api from '../../api'
import type { WorkerProductionRow } from '../../api/types'

const props = defineProps<{ canMutate: boolean }>()
const router = useRouter()
const auth = useWorkshopAuth()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const rows = ref<WorkerProductionRow[]>([])

function defaultRange() {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 30)
  const fmt = (d: Date) => d.toISOString().slice(0, 10)
  return { start: fmt(start), end: fmt(end) }
}
const range = ref(defaultRange())

async function load() {
  loading.value = true
  error.value = null
  try {
    const branchId = auth.branchScope
    rows.value = await api.workerProduction({
      period_start: range.value.start,
      period_end: range.value.end,
      branchIds: branchId ? [branchId] : undefined,
    })
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

function metresLine(row: WorkerProductionRow): string {
  const parts = Object.entries(row.metres_by_thickness).map(([thk, m]) => `${thk}mm: ${m}m`)
  return parts.length ? parts.join(' · ') : '—'
}

function recordSalary(row: WorkerProductionRow) {
  router.push({ name: 'finance-expenses', query: { expense: 'salary', worker: row.user_id } })
}

watch(() => auth.branchScope, load)
watch(range, load, { deep: true })
onMounted(load)
</script>

<template>
  <div style="margin-top: 16px">
    <div class="filters" style="margin-bottom: 14px">
      <FormField v-model="range.start" type="date" :label="t('workshop.periodFrom')" />
      <FormField v-model="range.end" type="date" :label="t('workshop.periodTo')" />
    </div>

    <ErrorState v-if="error" :error="error" :retry="load" />
    <div v-else-if="loading" class="card">
      <div class="card-b"><div class="sk sk-line" style="width: 60%" /></div>
    </div>
    <div v-else-if="rows.length === 0" class="st-empty">
      <div class="ic">∅</div>
      <h3>{{ t('workshop.productionEmpty') }}</h3>
    </div>
    <div v-else class="card">
      <table class="tbl">
        <thead>
          <tr>
            <th>{{ t('workshop.workerColName') }}</th>
            <th class="right">{{ t('workshop.sheetsCut') }}</th>
            <th class="right">{{ t('workshop.cutCount') }}</th>
            <th class="right">{{ t('workshop.ordersBanded') }}</th>
            <th>{{ t('workshop.metres') }}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.user_id">
            <td class="id">{{ r.user_id }}</td>
            <td class="amt">{{ r.sheets_cut }}</td>
            <td class="amt">{{ r.cut_count }}</td>
            <td class="amt">{{ r.orders_banded }}</td>
            <td style="font-size: 12px; color: var(--ink-7)">{{ metresLine(r) }}</td>
            <td>
              <button
                v-if="props.canMutate"
                class="btn btn-ghost btn-sm"
                type="button"
                @click="recordSalary(r)"
              >
                {{ t('workshop.recordSalary') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
