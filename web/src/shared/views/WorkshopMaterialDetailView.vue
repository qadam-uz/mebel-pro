<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { apiErrorCode, apiTraceId } from '@/shared/api/client'
import { traceLine } from '@/shared/app/errorTrace'
import { sanitizeQuantityInput } from '@/shared/app/inputSanitizers'
import { lowStockThresholdColumn } from '@/shared/app/lowStockThreshold'
import { formatMm, isTape } from '@/shared/app/materialLabel'
import { groupMaterialMovements, movementTotal } from '@/shared/app/materialMovements'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import { useRolePath } from '@/shared/app/paths'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import { stockTransactionTypeLabel } from '@/shared/app/workshopUi'
import AppIcon from '@/shared/components/AppIcon.vue'
import AppTabs from '@/shared/components/AppTabs.vue'
import StockAdjustmentDialog from '@/shared/components/StockAdjustmentDialog.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import {
  formatDate,
  formatDateTime,
  formatQuantityInput,
  formatStockQuantity,
  formatStockUnit,
  formatTiyin,
  parseDisplayQuantity,
} from '@/shared/formatters'
import {
  useWorkshopStore,
  type StockItem,
  type StockLastPrice,
  type StockTransaction,
} from '@/shared/stores/workshop'

/**
 * One material, read as a whole — a page with its own URL, so a stock row, a
 * link and a reload all land on the same thing.
 *
 * The page answers the three questions an owner actually asks in front of a
 * shelf, each in its own section rather than in one mixed ledger: what came in
 * (with the faktura it came on), who corrected the count and why, and where it
 * went (with the order that took it). The Tranzaksiyalar tab stays the flat
 * audit journal; this is the story.
 */
const MOVEMENT_WINDOW = 100

const { t } = useI18n()
// One module owns this number's copy — the figure tile, Ombor's column and the
// catalog form all read it from there rather than each naming it themselves.
const thresholdColumn = computed(() => lowStockThresholdColumn())
const route = useRoute()
const router = useRouter()
const rolePath = useRolePath()
const workshop = useWorkshopStore()
const permissions = useWorkshopPermissions()
const toast = useToast()

const branchMaterialId = computed(() =>
  typeof route.params.branch_material_id === 'string' ? route.params.branch_material_id : '',
)
const item = ref<StockItem | null>(null)
const loading = ref(false)
const loadError = ref<string | null>(null)
const loadTraceId = ref<string | null>(null)

const movements = ref<StockTransaction[]>([])
const movementsLoading = ref(false)
const movementsError = ref<string | null>(null)
const lastPrice = ref<StockLastPrice | null>(null)
const lastPriceLoaded = ref(false)

// Three questions, one at a time: the sections became tabs so the page opens on
// the arrivals without three tables' worth of scrolling under it. Tabs hide what
// they are not showing, so each label carries its own row count — otherwise
// "where are the write-offs?" costs a click to answer.
type MovementTab = 'arrivals' | 'consumption' | 'adjustments'
const movementTab = ref<MovementTab>('arrivals')

const adjustOpen = ref(false)
const minEditing = ref(false)
const minInput = ref('')
const minSaving = ref(false)
const minError = ref<string | null>(null)

const canUseInventory = computed(() => permissions.can(p.manageInventory))
const backLink = computed(() => rolePath('/workshop/inventory'))
const groups = computed(() => groupMaterialMovements(movements.value))
const movementTabs = computed<ChoiceOption[]>(() => [
  {
    value: 'arrivals',
    label: t('inventory.material.arrivalsTab', { count: groups.value.arrivals.length }),
  },
  {
    value: 'consumption',
    label: t('inventory.material.consumptionTab', { count: groups.value.consumption.length }),
  },
  {
    value: 'adjustments',
    label: t('inventory.material.adjustmentsTab', { count: groups.value.adjustments.length }),
  },
])
// The window is a cap, not the whole history — say so rather than letting a
// section's total read as an all-time figure.
const movementsCapped = computed(() => movements.value.length >= MOVEMENT_WINDOW)

watch(minInput, (value) => {
  const clean = sanitizeQuantityInput(value)
  if (clean !== value) minInput.value = clean
})

const isNegative = computed(() => (item.value?.on_hand ?? 0) < 0)

const statusPill = computed(() => {
  const row = item.value
  if (!row) return null
  if (row.on_hand < 0) return { cls: 'pill p-bad', text: t('inventory.stock.pillNegative') }
  if (row.is_low_stock) return { cls: 'pill p-warn', text: t('inventory.stock.pillLow') }
  return { cls: 'pill p-ok', text: t('inventory.stock.pillEnough') }
})

/** `2800×2070×18 mm` for a panel, `0.4×19 mm · kromka (metr)` for a tape. */
const materialMeta = computed(() => {
  const row = item.value
  if (!row) return ''
  const thickness = formatMm(row.material.decor_format.thickness_mm)
  if (isTape(row.type)) {
    return t('inventory.stock.materialMetaTape', {
      thickness,
      width: row.material.decor_format.tape_width_mm ?? 0,
    })
  }
  return t('inventory.stock.materialMetaPanel', {
    thickness,
    length: row.material.decor_format.length_mm ?? 0,
    width: row.material.decor_format.width_mm ?? 0,
  })
})

function isMetreUnit(displayUnit: string) {
  return displayUnit === 'metre' || displayUnit === 'm'
}

/**
 * On-hand valued at the last purchase price — the same arithmetic the server
 * runs for the branch total, including the tape mirror (millimetres × the
 * per-metre price, floor-divided). Shown only when both halves are real: an
 * unpriced material has no value, and a negative balance is a bookkeeping gap,
 * not stock worth money.
 */
const valueTiyin = computed(() => {
  const row = item.value
  const price = lastPrice.value?.unit_price_tiyin ?? null
  if (!row || price === null || price <= 0 || row.on_hand <= 0) return null
  return isMetreUnit(row.display_unit)
    ? Math.floor((row.on_hand * price) / 1000)
    : row.on_hand * price
})

const lastPriceMeta = computed(() => {
  const price = lastPrice.value
  if (!lastPriceLoaded.value) return null
  if (!price || price.unit_price_tiyin === null) return t('inventory.invoice.firstArrival')
  const parts: string[] = []
  if (price.recorded_at) parts.push(formatDate(price.recorded_at))
  if (price.supplier_name) parts.push(`«${price.supplier_name}»`)
  return parts.join(' · ')
})

function quantityWithSign(quantity: number) {
  const row = item.value
  const prefix = quantity > 0 ? '+' : ''
  return `${prefix}${formatStockQuantity(quantity, row?.display_unit ?? 'piece')}`
}

function balanceText(quantity: number) {
  return formatStockQuantity(quantity, item.value?.display_unit ?? 'piece')
}

function sectionTotal(rows: StockTransaction[]) {
  return quantityWithSign(movementTotal(rows))
}

// Not copy: `System` and `User <id>` are operator diagnostics for a row with no
// human actor, and the transliterator would turn either into nonsense Cyrillic.
function actorName(row: StockTransaction) {
  if (row.actor_name) return row.actor_name
  if (row.actor_user_id) return `User ${row.actor_user_id.slice(0, 8)}`
  return 'System'
}

function movementTypePill(type: StockTransaction['type']) {
  if (type === 'stock_in') return 'pill p-ok'
  if (type === 'adjust') return 'pill p-warn'
  if (type === 'restore') return 'pill p-conf'
  return 'pill p-bad'
}

async function load() {
  if (!branchMaterialId.value) return
  loading.value = true
  loadError.value = null
  loadTraceId.value = null
  try {
    item.value = await workshop.fetchMaterialStock(branchMaterialId.value)
  } catch (errorValue) {
    item.value = null
    loadError.value =
      apiErrorCode(errorValue) === 'stock_item_not_found' ? 'material_not_found' : 'material_failed'
    loadTraceId.value = apiTraceId(errorValue)
    return
  } finally {
    loading.value = false
  }
  await Promise.all([loadMovements(), loadLastPrice()])
}

async function loadMovements() {
  const row = item.value
  if (!row) return
  movementsLoading.value = true
  movementsError.value = null
  try {
    movements.value = await workshop.fetchStockTransactions(row.branch_id, {
      branch_material_id: row.branch_material_id,
      limit: MOVEMENT_WINDOW,
    })
  } catch {
    movements.value = []
    movementsError.value = 'movements_load_failed'
  } finally {
    movementsLoading.value = false
  }
}

async function loadLastPrice() {
  const row = item.value
  if (!row) return
  try {
    // No supplier preference here: the question is what this material last
    // cost, not what one counterparty last charged for it.
    lastPrice.value = await workshop.fetchMaterialLastPrice(row.branch_id, row.branch_material_id)
    lastPriceLoaded.value = true
  } catch {
    lastPrice.value = null
    lastPriceLoaded.value = false
  }
}

/**
 * A correction lands in the Tuzatishlar tab, which is not the one the page opens
 * on — so the tab follows the write. Otherwise the operator saves, sees the
 * balance move, and has to hunt for the row that explains it.
 */
async function onAdjustmentSaved() {
  movementTab.value = 'adjustments'
  await refreshAfterMutation()
}

/** After a correction booked here, both the balance and the story moved. */
async function refreshAfterMutation() {
  if (!branchMaterialId.value) return
  try {
    item.value = await workshop.fetchMaterialStock(branchMaterialId.value)
  } catch {
    // The balance failing to re-read must not blank a page that still shows a
    // valid — if now stale — row; the movement list below is reloaded anyway.
  }
  await Promise.all([loadMovements(), loadLastPrice()])
}

function startMinEdit() {
  const row = item.value
  if (!row) return
  minInput.value = formatQuantityInput(row.min_stock, row.display_unit)
  minError.value = null
  minEditing.value = true
  void nextTick(() => document.querySelector<HTMLInputElement>('[data-min-input]')?.focus())
}

function cancelMinEdit() {
  minEditing.value = false
  minError.value = null
}

async function saveMinStock() {
  const row = item.value
  if (!row) return
  const parsed = parseDisplayQuantity(minInput.value.trim(), row.display_unit)
  if (!Number.isFinite(parsed) || parsed < 0) {
    minError.value = t('inventory.material.minInvalid')
    return
  }
  minSaving.value = true
  minError.value = null
  try {
    // The response is the refreshed row; the store patches it into the table's
    // collections too, so this page and the list re-derive together.
    item.value = await workshop.updateStockMinStock(row.branch_id, row.branch_material_id, parsed)
    minEditing.value = false
    toast.success(t('inventory.material.minSaved'))
  } catch (errorValue) {
    minError.value =
      apiErrorCode(errorValue) === 'min_stock_invalid'
        ? t('inventory.material.minInvalid')
        : t('inventory.material.minFailed')
  } finally {
    minSaving.value = false
  }
}

function goToArrival() {
  const row = item.value
  if (!row) return
  // The arrival form is a document with many lines; it opens with this material
  // on line one rather than the page pretending to be a one-line arrival.
  void router.push(rolePath(`/workshop/inventory/invoices/new?material=${row.branch_material_id}`))
}

/** The page tells the story; the Tranzaksiyalar tab remains the audit journal. */
const allMovementsLink = computed(() =>
  rolePath(`/workshop/inventory?tab=tx&material=${branchMaterialId.value}`),
)

watch(branchMaterialId, load, { immediate: true })
</script>

<template>
  <section>
    <RouterLink :to="backLink" class="back">{{ $t('inventory.material.back') }}</RouterLink>

    <div v-if="!canUseInventory" class="st-empty">
      <h3>{{ $t('inventory.page.noPermissionTitle') }}</h3>
      <p>{{ $t('inventory.page.noPermissionBody') }}</p>
    </div>

    <section v-else-if="loading" class="card p-5" aria-live="polite">
      <div class="grid gap-3">
        <span class="sk-line"></span>
        <span class="sk-line"></span>
        <span class="sk-line"></span>
      </div>
    </section>

    <section v-else-if="loadError" class="st-error" role="alert">
      <h3>
        {{
          loadError === 'material_not_found'
            ? $t('inventory.material.notFound')
            : $t('inventory.material.loadFailed')
        }}
      </h3>
      <p>{{ traceLine(loadTraceId) }}</p>
      <button type="button" class="mp-button mp-button-outline mt-3" @click="load">
        {{ $t('inventory.detail.retry') }}
      </button>
    </section>

    <template v-else-if="item">
      <div class="page-head mt-2">
        <div class="min-w-0">
          <h1 class="flex flex-wrap items-center gap-2">
            <span class="sw" :class="materialSwatchClass(item.material.decor)"></span>
            <span class="min-w-0">{{ item.material.label }}</span>
            <span v-if="statusPill" :class="statusPill.cls" class="align-middle">
              <span class="pd"></span>{{ statusPill.text }}
            </span>
          </h1>
          <p class="sub">
            {{ materialMeta }}
            <template v-if="item.material.decor_format.status === 'inactive'">
              · {{ $t('inventory.stock.discontinued') }}
            </template>
          </p>
        </div>
        <div class="tools">
          <button
            type="button"
            class="mp-button mp-button-outline min-h-9 px-3 text-xs"
            @click="adjustOpen = true"
          >
            {{ $t('inventory.stock.adjustAction') }}
          </button>
          <button
            type="button"
            class="mp-button mp-button-primary min-h-9 px-3 text-xs"
            @click="goToArrival"
          >
            {{ $t('inventory.stock.rowArrival') }}
          </button>
        </div>
      </div>

      <div class="figs figs-4 mb-4">
        <div class="fig">
          <span class="fig-l">{{ $t('inventory.stock.columnOnHand') }}</span>
          <span class="fig-v" :class="isNegative ? 'danger-text' : undefined">
            {{ formatStockQuantity(item.on_hand, item.display_unit) }}
          </span>
          <small v-if="isNegative" class="fig-note">
            {{ $t('inventory.stock.noteNegative') }}
          </small>
        </div>
        <div class="fig">
          <span class="fig-l">{{ thresholdColumn }}</span>
          <!-- The threshold is warehouse policy, and the decision "5 emas, 10
               bo'lsin" is made standing in front of the shelf — so it is edited
               here as well as on the catalog form. -->
          <template v-if="minEditing">
            <!-- Stacked, not inline: a figure column is ~170px wide and an input
                 beside two buttons spills over the next figure. -->
            <form class="grid gap-2" @submit.prevent="saveMinStock">
              <span class="mp-unit-field">
                <input
                  v-model="minInput"
                  data-min-input
                  class="mp-input min-h-9 text-right"
                  inputmode="decimal"
                  :aria-label="
                    $t('inventory.material.minAria', {
                      unit: formatStockUnit(item.display_unit),
                    })
                  "
                  :aria-invalid="minError ? 'true' : undefined"
                  aria-describedby="material-min-error"
                />
                <span class="mp-unit-suffix" aria-hidden="true">
                  {{ formatStockUnit(item.display_unit) }}
                </span>
              </span>
              <div class="flex flex-wrap gap-2">
                <button
                  type="submit"
                  class="mp-button mp-button-primary min-h-9 px-2 text-xs"
                  :disabled="minSaving"
                >
                  {{ minSaving ? $t('inventory.action.saving') : $t('inventory.action.save') }}
                </button>
                <button
                  type="button"
                  class="mp-button mp-button-outline min-h-9 px-2 text-xs"
                  :disabled="minSaving"
                  @click="cancelMinEdit"
                >
                  {{ $t('inventory.action.cancel') }}
                </button>
              </div>
            </form>
            <small v-if="minError" id="material-min-error" class="mp-field-error">
              {{ minError }}
            </small>
            <!-- The rule belongs where it is actionable: at the input, not
                 standing under a threshold that is already set. -->
            <small v-else class="fig-note">{{ $t('inventory.material.minHint') }}</small>
          </template>
          <template v-else>
            <span class="flex items-center gap-2">
              <span class="fig-v">
                {{
                  item.min_stock > 0
                    ? formatStockQuantity(item.min_stock, item.display_unit)
                    : $t('inventory.material.minOff')
                }}
              </span>
              <button
                type="button"
                class="mp-row-icon"
                :aria-label="$t('inventory.material.minEditAria')"
                @click="startMinEdit"
              >
                <AppIcon name="pencil" />
              </button>
            </span>
          </template>
        </div>
        <div class="fig">
          <span class="fig-l">{{ $t('inventory.material.lastPrice') }}</span>
          <span class="fig-v">
            {{
              lastPrice && lastPrice.unit_price_tiyin !== null
                ? formatTiyin(lastPrice.unit_price_tiyin)
                : '—'
            }}
          </span>
          <small v-if="lastPriceMeta" class="fig-note">{{ lastPriceMeta }}</small>
        </div>
        <div class="fig">
          <span class="fig-l">{{ $t('inventory.material.value') }}</span>
          <span class="fig-v">{{ valueTiyin !== null ? formatTiyin(valueTiyin) : '—' }}</span>
          <small class="fig-note">{{ $t('inventory.material.valueHint') }}</small>
        </div>
      </div>

      <div v-if="movementsLoading && movements.length === 0" class="card p-5" aria-live="polite">
        <div class="grid gap-3">
          <span class="sk-line"></span>
          <span class="sk-line"></span>
        </div>
      </div>

      <div v-else-if="movementsError" class="banner danger mb-4">
        <div class="grow">{{ $t('inventory.material.movementsFailed') }}</div>
        <button type="button" class="mp-button mp-button-outline" @click="loadMovements">
          {{ $t('inventory.detail.retry') }}
        </button>
      </div>

      <template v-else>
        <AppTabs
          v-model="movementTab"
          id-prefix="material-movements"
          :label="$t('inventory.material.movementsTabsLabel')"
          :tabs="movementTabs"
        />

        <!-- Kirimlar: what came in, and on whose faktura. -->
        <section
          v-if="movementTab === 'arrivals'"
          id="material-movements-arrivals-panel"
          class="card mb-4"
          role="tabpanel"
          aria-labelledby="material-movements-arrivals-tab"
          tabindex="0"
        >
          <!-- The tab names the section and `aria-labelledby` carries that to a
               screen reader, so the panel repeats no title — only the number a
               title could not have told you. -->
          <div
            v-if="groups.arrivals.length > 0"
            class="flex items-center justify-end border-b border-hairline px-4 py-2 text-sm text-ink-muted"
          >
            {{ $t('inventory.material.netTotal', { total: sectionTotal(groups.arrivals) }) }}
          </div>
          <div v-if="groups.arrivals.length > 0" class="table-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th>{{ $t('inventory.tx.columnTime') }}</th>
                  <th>{{ $t('inventory.material.columnInvoice') }}</th>
                  <th>{{ $t('inventory.tx.columnSupplier') }}</th>
                  <th class="right">{{ $t('inventory.tx.columnQuantity') }}</th>
                  <th class="right">{{ $t('inventory.tx.columnPrice') }}</th>
                  <th class="right">{{ $t('inventory.tx.columnBalance') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in groups.arrivals" :key="row.id">
                  <td class="num text-ink-muted">{{ formatDateTime(row.created_at) }}</td>
                  <td>
                    <!-- The faktura is the document this line belongs to: the
                         number is the link, so a wrong quantity is one click
                         from the paper it was typed off. -->
                    <RouterLink
                      v-if="row.invoice_id"
                      :to="rolePath(`/workshop/inventory/invoices/${row.invoice_id}`)"
                      class="nm no-underline hover:underline"
                    >
                      {{ row.invoice_no ?? $t('inventory.material.invoiceUnnamed') }}
                    </RouterLink>
                    <span v-else class="muted">—</span>
                    <small
                      v-if="row.type === 'stock_in_void'"
                      class="block text-[11px] text-danger"
                    >
                      {{ stockTransactionTypeLabel(row.type) }}
                    </small>
                  </td>
                  <td>
                    <small class="text-ink-soft">{{ row.supplier_name ?? '—' }}</small>
                  </td>
                  <td class="amt" :class="row.quantity >= 0 ? 'success-text' : 'danger-text'">
                    {{ quantityWithSign(row.quantity) }}
                  </td>
                  <td class="amt">
                    {{ row.unit_price_tiyin !== null ? formatTiyin(row.unit_price_tiyin) : '—' }}
                  </td>
                  <td class="amt muted">{{ balanceText(row.balance_after) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="p-4 text-sm text-ink-muted">
            {{ $t('inventory.material.arrivalsEmpty') }}
          </p>
        </section>

        <!-- Chiqimlar: where it went — always an order, never a person. -->
        <section
          v-else-if="movementTab === 'consumption'"
          id="material-movements-consumption-panel"
          class="card mb-4"
          role="tabpanel"
          aria-labelledby="material-movements-consumption-tab"
          tabindex="0"
        >
          <!-- The tab names the section and `aria-labelledby` carries that to a
               screen reader, so the panel repeats no title — only the number a
               title could not have told you. -->
          <div
            v-if="groups.consumption.length > 0"
            class="flex items-center justify-end border-b border-hairline px-4 py-2 text-sm text-ink-muted"
          >
            {{ $t('inventory.material.netTotal', { total: sectionTotal(groups.consumption) }) }}
          </div>
          <div v-if="groups.consumption.length > 0" class="table-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th>{{ $t('inventory.tx.columnTime') }}</th>
                  <th>{{ $t('inventory.material.columnOrder') }}</th>
                  <th>{{ $t('inventory.tx.columnType') }}</th>
                  <th class="right">{{ $t('inventory.tx.columnQuantity') }}</th>
                  <th class="right">{{ $t('inventory.tx.columnBalance') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in groups.consumption" :key="row.id">
                  <td class="num text-ink-muted">{{ formatDateTime(row.created_at) }}</td>
                  <td>
                    <RouterLink
                      v-if="row.order_id"
                      :to="rolePath(`/workshop/orders/${row.order_id}`)"
                      class="nm no-underline hover:underline"
                    >
                      {{ row.order_number ?? row.order_id.slice(0, 8) }}
                    </RouterLink>
                    <span v-else class="muted">—</span>
                  </td>
                  <td>
                    <span :class="movementTypePill(row.type)">
                      <span class="pd"></span>{{ stockTransactionTypeLabel(row.type) }}
                    </span>
                  </td>
                  <td class="amt" :class="row.quantity >= 0 ? 'success-text' : 'danger-text'">
                    {{ quantityWithSign(row.quantity) }}
                  </td>
                  <td class="amt muted">{{ balanceText(row.balance_after) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="p-4 text-sm text-ink-muted">
            {{ $t('inventory.material.consumptionEmpty') }}
          </p>
        </section>

        <!-- Tuzatishlar: who corrected the count, and why. -->
        <section
          v-else
          id="material-movements-adjustments-panel"
          class="card mb-4"
          role="tabpanel"
          aria-labelledby="material-movements-adjustments-tab"
          tabindex="0"
        >
          <!-- The tab names the section and `aria-labelledby` carries that to a
               screen reader, so the panel repeats no title — only the number a
               title could not have told you. -->
          <div
            v-if="groups.adjustments.length > 0"
            class="flex items-center justify-end border-b border-hairline px-4 py-2 text-sm text-ink-muted"
          >
            {{ $t('inventory.material.netTotal', { total: sectionTotal(groups.adjustments) }) }}
          </div>
          <div v-if="groups.adjustments.length > 0" class="table-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th>{{ $t('inventory.tx.columnTime') }}</th>
                  <th class="right">{{ $t('inventory.tx.columnQuantity') }}</th>
                  <th class="right">{{ $t('inventory.tx.columnBalance') }}</th>
                  <th>{{ $t('inventory.tx.columnActor') }}</th>
                  <th>{{ $t('inventory.tx.columnNote') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in groups.adjustments" :key="row.id">
                  <td class="num text-ink-muted">{{ formatDateTime(row.created_at) }}</td>
                  <td class="amt" :class="row.quantity >= 0 ? 'success-text' : 'danger-text'">
                    {{ quantityWithSign(row.quantity) }}
                  </td>
                  <td class="amt muted">{{ balanceText(row.balance_after) }}</td>
                  <td>
                    <small class="text-ink-soft">{{ actorName(row) }}</small>
                  </td>
                  <td>
                    <small class="text-ink-soft">{{ row.note ?? '—' }}</small>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="p-4 text-sm text-ink-muted">
            {{ $t('inventory.material.adjustmentsEmpty') }}
          </p>
        </section>

        <p class="mb-4 text-sm text-ink-muted">
          <!-- A cap the reader cannot see is a total that lies: say the window
               out loud and point at the journal that has the rest. -->
          <span v-if="movementsCapped">
            {{ $t('inventory.material.windowCapped', { count: MOVEMENT_WINDOW }) }}
          </span>
          <RouterLink :to="allMovementsLink" class="font-bold text-accent-deep no-underline">
            {{ $t('inventory.material.allMovements') }}
          </RouterLink>
        </p>
      </template>

      <StockAdjustmentDialog
        :open="adjustOpen"
        :material="item"
        @close="adjustOpen = false"
        @saved="onAdjustmentSaved"
      />
    </template>
  </section>
</template>
