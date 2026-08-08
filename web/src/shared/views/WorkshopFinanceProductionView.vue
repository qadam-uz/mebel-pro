<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { presetRange, type DateRangePreset } from '@/shared/app/dateRange'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import DateRangePicker from '@/shared/components/DateRangePicker.vue'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { formatStockQuantity } from '@/shared/formatters'
import {
  useFinanceStore,
  type WorkerProductionEdgeLine,
  type WorkerProductionRow,
} from '@/shared/stores/finance'
import { useWorkshopStore } from '@/shared/stores/workshop'

const { t } = useI18n()
const finance = useFinanceStore()
const workshop = useWorkshopStore()
const permissions = useWorkshopPermissions()
const today = new Date()
const initialRange = presetRange('month', today)
const datePreset = ref<DateRangePreset>('month')
const dateFrom = ref(initialRange.from ?? '')
const dateTo = ref(initialRange.to ?? '')
const financePermissions = [p.manageFinance, p.viewFinanceReports]
const canViewFinance = computed(() => permissions.canAny(financePermissions))

// The topbar picker is the only branch control on the page (QAD-182): the
// duplicate page dropdown is gone, and the report reads the same context every
// other branch-scoped page reads.
const activeBranchId = computed(() => workshop.selectedBranchContext ?? null)

// What this branch produced in the period, under the per-worker rows.
const productionTotals = computed(() => {
  const rows = finance.production?.rows ?? []
  return {
    panelsCut: rows.reduce((sum, row) => sum + row.panels_cut, 0),
    cutCount: rows.reduce((sum, row) => sum + row.cut_count, 0),
    ordersBanded: rows.reduce((sum, row) => sum + row.orders_banded, 0),
  }
})

// One entry per edge material / thickness so the cell can stack them as lines
// (label left, metres right) instead of one unreadable `·`-joined string.
interface EdgeCellLine {
  label: string
  length: string
}

function edgeLengthLines(row: WorkerProductionRow): EdgeCellLine[] {
  if (row.edge_lines.length > 0) {
    return row.edge_lines.map((line) => ({
      label: edgeLabel(line),
      length: formatStockQuantity(line.length_mm, 'm'),
    }))
  }
  return Object.entries(row.edge_length_by_material).map(([key, length]) => ({
    label: t('finance.labour.materialFallback', { id: key.slice(0, 8) }),
    length: formatStockQuantity(length, 'm'),
  }))
}

function thicknessLines(row: WorkerProductionRow): EdgeCellLine[] {
  return row.edge_length_by_thickness.map((line) => ({
    label: line.thickness_mm ? `${line.thickness_mm} mm` : t('finance.labour.unknownThickness'),
    length: formatStockQuantity(line.length_mm, 'm'),
  }))
}

function edgeLabel(line: WorkerProductionEdgeLine) {
  // `material_label` is already the canonical `{manufacturer} {decor}` ·
  // `{color}` · `{thickness}x{width} mm` shape (backend
  // app/core/material_label.py) — thickness_mm/color are separate fields on
  // the line for sorting/filtering, not for re-appending here.
  return line.material_label
}

async function refresh() {
  if (!canViewFinance.value) return
  await finance.loadProduction({
    date_from: dateFrom.value,
    date_to: dateTo.value,
    branch_id: activeBranchId.value,
  })
}

onMounted(async () => {
  await workshop.loadBranchContext().catch(() => undefined)
  if (canViewFinance.value) await refresh()
})

// Switching branch in the topbar reloads the report — the figures must never
// lag behind the picker above them.
watch(activeBranchId, () => void refresh())

// Date range auto-applies now that the explicit "Qo'llash" button is gone.
let dateTimer: number | undefined
watch([dateFrom, dateTo], () => {
  window.clearTimeout(dateTimer)
  dateTimer = window.setTimeout(() => void refresh(), 250)
})
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-display text-3xl font-semibold text-ink">
          {{ $t('finance.labour.title') }}
        </h1>
      </div>
    </div>

    <section v-if="!canViewFinance" class="mp-surface p-5 text-sm font-bold text-warning">
      {{ $t('finance.labour.denied') }}
    </section>

    <!-- Bare filter row on the page background, like every other page — this was
         the only view wrapping its filters in a surface card. -->
    <div v-else class="mp-filters">
      <DateRangePicker
        v-model:preset="datePreset"
        v-model:date-from="dateFrom"
        v-model:date-to="dateTo"
      />
    </div>

    <section
      v-if="canViewFinance && finance.loading"
      class="mp-surface p-5 text-sm font-bold text-ink-soft"
    >
      {{ $t('finance.labour.loading') }}
    </section>
    <section v-else-if="finance.error" class="mp-surface p-5" role="alert">
      <p class="text-sm font-bold text-danger">{{ $t('finance.labour.loadFailed') }}</p>
      <p class="mt-1 text-sm text-ink-soft">{{ $t('finance.error.checkConnection') }}</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        :disabled="finance.loading"
        @click="refresh"
      >
        {{ $t('common.action.retry') }}
      </button>
      <p v-if="finance.traceId" class="mt-3 text-xs text-ink-muted">
        trace_id: {{ finance.traceId }}
      </p>
    </section>
    <section
      v-else-if="!finance.production || finance.production.rows.length === 0"
      class="mp-surface p-5 text-sm text-ink-soft"
    >
      {{ $t('finance.labour.empty') }}
    </section>
    <section v-else class="mp-surface overflow-hidden">
      <div class="overflow-x-auto">
        <table class="min-w-full text-left text-sm">
          <thead class="bg-sunk text-[12.5px] text-ink-muted">
            <tr>
              <th class="px-5 py-3">{{ $t('finance.field.worker') }}</th>
              <th class="px-5 py-3 text-right">{{ $t('finance.labour.colPanelsCut') }}</th>
              <th class="px-5 py-3 text-right">{{ $t('finance.labour.colCuts') }}</th>
              <th class="px-5 py-3 text-right">{{ $t('finance.labour.colOrdersBanded') }}</th>
              <th class="px-5 py-3">{{ $t('finance.labour.colEdgeMetres') }}</th>
              <th class="px-5 py-3">{{ $t('finance.labour.colThickness') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-hairline">
            <tr v-for="row in finance.production.rows" :key="row.user_id">
              <td class="px-5 py-3 font-bold text-ink">{{ row.full_name }}</td>
              <td class="px-5 py-3 text-right text-xs tabular-nums">
                {{ row.panels_cut }}
              </td>
              <td class="px-5 py-3 text-right text-xs tabular-nums">
                {{ row.cut_count }}
              </td>
              <td class="px-5 py-3 text-right text-xs tabular-nums">
                {{ row.orders_banded }}
              </td>
              <td class="px-5 py-3 text-xs">
                <span v-if="edgeLengthLines(row).length === 0" class="text-ink-muted">
                  {{ $t('finance.labour.noEdgeMetres') }}
                </span>
                <ul v-else class="grid min-w-52 gap-1">
                  <li
                    v-for="(line, index) in edgeLengthLines(row)"
                    :key="index"
                    class="flex items-baseline justify-between gap-4"
                  >
                    <span class="text-ink-soft">{{ line.label }}</span>
                    <b class="whitespace-nowrap text-ink">{{ line.length }}</b>
                  </li>
                </ul>
              </td>
              <td class="px-5 py-3 text-xs">
                <span v-if="thicknessLines(row).length === 0" class="text-ink-muted">
                  {{ $t('finance.labour.noThickness') }}
                </span>
                <ul v-else class="grid min-w-32 gap-1">
                  <li
                    v-for="(line, index) in thicknessLines(row)"
                    :key="index"
                    class="flex items-baseline justify-between gap-4"
                  >
                    <span class="text-ink-soft">{{ line.label }}</span>
                    <b class="whitespace-nowrap text-ink">{{ line.length }}</b>
                  </li>
                </ul>
              </td>
            </tr>
          </tbody>
          <tfoot v-if="finance.production.rows.length > 1" class="border-t border-hairline-strong">
            <tr class="bg-sunk">
              <td class="px-5 py-3 font-bold text-ink">{{ $t('common.field.total') }}</td>
              <td class="px-5 py-3 text-right text-xs font-bold tabular-nums">
                {{ productionTotals.panelsCut }}
              </td>
              <td class="px-5 py-3 text-right text-xs font-bold tabular-nums">
                {{ productionTotals.cutCount }}
              </td>
              <td class="px-5 py-3 text-right text-xs font-bold tabular-nums">
                {{ productionTotals.ordersBanded }}
              </td>
              <td class="px-5 py-3"></td>
              <td class="px-5 py-3"></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  </section>
</template>
