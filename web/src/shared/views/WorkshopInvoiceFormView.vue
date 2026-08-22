<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'

import { apiErrorCode, apiTraceId } from '@/shared/api/client'
import { traceLine } from '@/shared/app/errorTrace'
import { sanitizeMoneyInput, sanitizeQuantityInput } from '@/shared/app/inputSanitizers'
import { useRolePath } from '@/shared/app/paths'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import DateField from '@/shared/components/DateField.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import {
  formatDate,
  formatDateInputValue,
  formatQuantityInput,
  formatStockQuantity,
  formatStockUnit,
  formatTiyin,
  parseDisplayQuantity,
  parseSomToTiyin,
  tiyinToSomInput,
} from '@/shared/formatters'
import {
  useWorkshopStore,
  type StockItem,
  type StockLastPrice,
  type SupplierInvoice,
  type SupplierInvoiceLineInput,
} from '@/shared/stores/workshop'

/**
 * Record or correct one arrival document — a page, in both modes.
 *
 * Create and edit are the same form with the same arithmetic; only the seed and
 * two affordances differ (inline-add and the finance hand-off are create-only).
 * Two components would be two places for the line maths to drift.
 *
 * The document total is the line sum, full stop: the supplier's document-level
 * skidka left the UI in revision 2, so there is no ladder to show — only
 * **Jami**.
 */
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const rolePath = useRolePath()
const workshop = useWorkshopStore()
const permissions = useWorkshopPermissions()
const toast = useToast()

const today = formatDateInputValue(new Date())
const invoiceId = computed(() =>
  typeof route.params.invoice_id === 'string' ? route.params.invoice_id : null,
)
const isEdit = computed(() => invoiceId.value !== null)

const loading = ref(false)
const loadError = ref<string | null>(null)
const loadTraceId = ref<string | null>(null)
const invoice = ref<SupplierInvoice | null>(null)
const saving = ref(false)
const saveError = ref<string | null>(null)
const supplierError = ref<string | null>(null)
const inlineSupplierError = ref<string | null>(null)
const linesError = ref<string | null>(null)

interface InvoiceLineDraft {
  key: number
  materialId: string | null
  quantity: string
  unitPrice: string
  // A typed (or seeded) price is never overwritten by a later last-price fetch.
  priceEdited: boolean
  lastPrice: StockLastPrice | null
  lastPriceLoaded: boolean
}

let lineKeySeed = 0
function blankLine(): InvoiceLineDraft {
  return {
    key: ++lineKeySeed,
    materialId: null,
    quantity: '',
    unitPrice: '',
    priceEdited: false,
    lastPrice: null,
    lastPriceLoaded: false,
  }
}

const form = reactive({
  supplierId: null as string | null,
  inlineSupplierName: '',
  invoiceDate: today,
})
const lines = ref<InvoiceLineDraft[]>([blankLine()])

const canUseInventory = computed(() => permissions.can(p.manageInventory))
// The finance hand-off is offered only to users who could open the ledger anyway.
const canSeeFinance = computed(() => permissions.isOwner.value || permissions.can(p.manageFinance))
const accessibleBranches = computed(() =>
  permissions.accessibleBranches(workshop.branches, [p.manageInventory]),
)
/**
 * Create takes the branch from the topbar context; edit takes it from the
 * record, because a faktura belongs to the branch it was booked into and a
 * later context switch must not retarget it.
 */
const branchId = computed(() => {
  if (isEdit.value) return invoice.value?.branch_id ?? ''
  const context = workshop.selectedBranchContext
  if (context && accessibleBranches.value.some((branch) => branch.id === context)) return context
  return accessibleBranches.value[0]?.id ?? ''
})

const pickerItems = computed(() => workshop.stockPickerItems)
const stockOptions = computed(() =>
  pickerItems.value.map((item) => ({
    value: item.branch_material_id,
    label: item.material.label,
    meta:
      item.on_hand < 0
        ? t('inventory.stock.optionShort', {
            quantity: formatStockQuantity(-item.on_hand, item.display_unit),
          })
        : t('inventory.stock.optionOnHand', {
            quantity: formatStockQuantity(item.on_hand, item.display_unit),
          }),
  })),
)

/**
 * Real suppliers, plus «Yangi ta'minotchi» last behind a divider — on create
 * only. Correcting *which* supplier a document came from is not the moment to
 * mint a counterparty, and an inactive supplier the invoice already names stays
 * selectable or the select would silently drop it.
 */
const supplierOptions = computed<ChoiceOption[]>(() => {
  const options: ChoiceOption[] = workshop.suppliers
    .filter((supplier) => supplier.status === 'active')
    .map((supplier) => ({
      value: supplier.id,
      label: supplier.name,
      meta: supplier.phone ?? t('inventory.supplier.activeMeta'),
    }))
  if (!isEdit.value) {
    options.push({
      value: 'inline',
      label: t('inventory.supplier.inlineOption'),
      meta: t('inventory.supplier.inlineOptionMeta'),
      separator: true,
    })
    return options
  }
  const current = invoice.value
  if (current?.supplier_id && !options.some((option) => option.value === current.supplier_id)) {
    options.unshift({
      value: current.supplier_id,
      label: current.supplier_name ?? current.supplier_id,
      meta: t('inventory.supplier.statusInactive'),
    })
  }
  return options
})

const pageTitle = computed(() =>
  isEdit.value && invoice.value
    ? t('inventory.form.editTitle', { number: invoice.value.invoice_no })
    : t('inventory.form.createTitle'),
)

function stockItemByMaterial(materialId: string | null): StockItem | null {
  return pickerItems.value.find((item) => item.branch_material_id === materialId) ?? null
}

function isMetreUnit(displayUnit: string) {
  return displayUnit === 'metre' || displayUnit === 'm'
}

// The unit a line's price is entered per — one panel for panels, one metre for
// edges. A persistent suffix inside the field, never a placeholder: the
// difference between 18 so'm/m and 1 800 so'm/m is the whole cost base.
function linePriceUnit(line: InvoiceLineDraft) {
  const item = stockItemByMaterial(line.materialId)
  if (!item) return t('inventory.invoice.priceUnitSom')
  return isMetreUnit(item.display_unit)
    ? t('inventory.invoice.priceUnitMetre')
    : t('inventory.invoice.priceUnitSheet')
}

function lineQuantityUnit(line: InvoiceLineDraft) {
  const item = stockItemByMaterial(line.materialId)
  return item ? formatStockUnit(item.display_unit) : ''
}

function lineMaterialLabel(line: InvoiceLineDraft): string {
  return stockOptions.value.find((option) => option.value === line.materialId)?.label ?? ''
}

function lineLastPriceHint(line: InvoiceLineDraft) {
  if (!line.materialId || !line.lastPriceLoaded) return null
  const price = line.lastPrice
  if (!price || price.unit_price_tiyin === null) return t('inventory.invoice.firstArrival')
  const parts = [t('inventory.invoice.lastPrice', { price: formatTiyin(price.unit_price_tiyin) })]
  if (price.recorded_at) parts.push(formatDate(price.recorded_at))
  if (price.supplier_name) parts.push(`«${price.supplier_name}»`)
  return parts.join(' · ')
}

function validLineQuantity(line: InvoiceLineDraft, item: StockItem | null) {
  const quantity = parseDisplayQuantity(line.quantity, item?.display_unit ?? 'piece')
  return Number.isFinite(quantity) && quantity > 0 ? quantity : null
}

// Live line total mirroring the server math exactly: panels multiply, edges take
// millimetres × per-metre price with floor division (the sale-side mirror).
function lineTotalTiyin(line: InvoiceLineDraft) {
  const item = stockItemByMaterial(line.materialId)
  const quantity = validLineQuantity(line, item)
  const price = parseSomToTiyin(line.unitPrice)
  if (!item || quantity === null || price === null) return null
  return isMetreUnit(item.display_unit) ? Math.floor((quantity * price) / 1000) : quantity * price
}

const totalTiyin = computed(() =>
  lines.value.reduce((sum, line) => sum + (lineTotalTiyin(line) ?? 0), 0),
)

// Type-time sanitization (PhoneInput precedent) — invalid characters never stick.
watch(
  lines,
  (value) => {
    for (const line of value) {
      const quantity = sanitizeQuantityInput(line.quantity)
      if (quantity !== line.quantity) line.quantity = quantity
      const price = sanitizeMoneyInput(line.unitPrice)
      if (price !== line.unitPrice) line.unitPrice = price
    }
  },
  { deep: true },
)

// A real (non-inline) selected supplier id, for supplier-specific prefill.
const realSupplierId = computed(() =>
  form.supplierId && form.supplierId !== 'inline' ? form.supplierId : null,
)

const lastPriceFetchTokens = new Map<number, number>()
async function refreshLineLastPrice(line: InvoiceLineDraft) {
  if (!branchId.value || !line.materialId) {
    line.lastPrice = null
    line.lastPriceLoaded = false
    return
  }
  const token = (lastPriceFetchTokens.get(line.key) ?? 0) + 1
  lastPriceFetchTokens.set(line.key, token)
  try {
    const fetched = await workshop.fetchMaterialLastPrice(
      branchId.value,
      line.materialId,
      realSupplierId.value,
    )
    if (lastPriceFetchTokens.get(line.key) !== token) return
    line.lastPrice = fetched
    line.lastPriceLoaded = true
    // Prefill only into a field the user has not touched — a typed value always
    // wins. The emptiness check is what makes that race-proof: the fetch is in
    // flight while the price field is already reachable.
    if (!line.priceEdited && !line.unitPrice) {
      line.unitPrice =
        fetched.unit_price_tiyin !== null ? tiyinToSomInput(fetched.unit_price_tiyin) : ''
    }
  } catch {
    if (lastPriceFetchTokens.get(line.key) !== token) return
    // Prefill is best-effort UX; a failed fetch must never block manual entry.
    line.lastPrice = null
    line.lastPriceLoaded = false
  }
}

function onLineMaterialChange(line: InvoiceLineDraft) {
  // A price belongs to a material — switching materials restarts the prefill.
  line.priceEdited = false
  line.unitPrice = ''
  line.lastPriceLoaded = false
  void refreshLineLastPrice(line)
  focusLineQuantity(line)
}

/**
 * Picking a material replaces the combobox with the resolved label, so the input
 * the combobox would hand focus back to is unmounted in the same tick and focus
 * falls to <body>. Quantity is where the operator is going next anyway.
 */
function focusLineQuantity(line: InvoiceLineDraft) {
  if (!line.materialId) return
  void nextTick(() => {
    document.querySelector<HTMLInputElement>(`[data-qty-for="${line.key}"]`)?.focus()
  })
}

/** Back to the picker. Clearing the material must clear what belonged to it. */
function clearLineMaterial(line: InvoiceLineDraft) {
  line.materialId = ''
  onLineMaterialChange(line)
}

function addLine() {
  lines.value = [...lines.value, blankLine()]
}

function removeLine(key: number) {
  const remaining = lines.value.filter((line) => line.key !== key)
  lines.value = remaining.length > 0 ? remaining : [blankLine()]
}

watch(realSupplierId, () => {
  for (const line of lines.value) {
    if (line.materialId) void refreshLineLastPrice(line)
  }
})

// ── Unsaved-changes guard ────────────────────────────────────────────────
// A whole faktura is a long typing session; losing it to a stray Back is the
// one failure this form cannot recover from. `dirty` flips on the first real
// edit and clears on a successful save (and on the deliberate Bekor).
const dirty = ref(false)
const leaveOpen = ref(false)
let leaveResolve: ((allow: boolean) => void) | null = null

function markDirty() {
  if (!loading.value) dirty.value = true
}

watch(() => ({ ...form }), markDirty, { deep: true })
watch(lines, markDirty, { deep: true })

onBeforeRouteLeave(() => {
  if (!dirty.value || saving.value) return true
  leaveOpen.value = true
  return new Promise<boolean>((resolve) => {
    leaveResolve = resolve
  })
})

function resolveLeave(allow: boolean) {
  leaveOpen.value = false
  leaveResolve?.(allow)
  leaveResolve = null
}

// ── Loading ──────────────────────────────────────────────────────────────
const backLink = computed(() => rolePath('/workshop/inventory?tab=invoices'))

function seedFrom(row: SupplierInvoice) {
  form.supplierId = row.supplier_id
  form.inlineSupplierName = ''
  form.invoiceDate = row.invoice_date.slice(0, 10)
  const seeded = row.lines.map((line) => ({
    key: ++lineKeySeed,
    materialId: line.branch_material_id,
    quantity: formatQuantityInput(line.quantity, line.display_unit),
    // The seeded price is what the document says; a prefill must never land on
    // top of it, so it counts as typed.
    unitPrice: line.unit_price_tiyin !== null ? tiyinToSomInput(line.unit_price_tiyin) : '',
    priceEdited: true,
    lastPrice: null,
    lastPriceLoaded: false,
  }))
  lines.value = seeded.length > 0 ? seeded : [blankLine()]
}

async function load() {
  loading.value = true
  loadError.value = null
  loadTraceId.value = null
  try {
    await workshop.loadBranchContext().catch(() => undefined)
    if (isEdit.value && invoiceId.value) {
      const row = await workshop.fetchSupplierInvoice(invoiceId.value)
      invoice.value = row
      // A cancelled document is frozen server-side; sending the operator into a
      // form that can only 409 is worse than putting them back on the paper.
      if (row.status === 'voided') {
        await router.replace(rolePath(`/workshop/inventory/invoices/${row.id}`))
        return
      }
      seedFrom(row)
    }
    if (!branchId.value) return
    await Promise.all([
      workshop.loadStockPicker(branchId.value).catch(() => undefined),
      workshop.loadSuppliers(branchId.value).catch(() => undefined),
    ])
    // `?material=` is how a stock row and the dashboard's negative-balance
    // work item hand a material over: line 1 arrives already picked, its last
    // price in flight, and the operator's next keystroke is the quantity.
    const seed = route.query.material
    const first = lines.value[0]
    if (!isEdit.value && typeof seed === 'string' && seed && first && !first.materialId) {
      first.materialId = seed
      onLineMaterialChange(first)
    }
  } catch (errorValue) {
    loadError.value =
      apiErrorCode(errorValue) === 'invoice_not_found' ? 'invoice_not_found' : 'invoice_load_failed'
    loadTraceId.value = apiTraceId(errorValue)
  } finally {
    loading.value = false
    // The seed itself is not an edit.
    await nextTick()
    dirty.value = false
  }
}

onMounted(load)

// ── Saving ───────────────────────────────────────────────────────────────
function collectLines(): SupplierInvoiceLineInput[] | null {
  const collected: SupplierInvoiceLineInput[] = []
  for (const line of lines.value) {
    const item = stockItemByMaterial(line.materialId)
    const quantity = validLineQuantity(line, item)
    const unitPriceTiyin = parseSomToTiyin(line.unitPrice)
    if (!item || quantity === null || unitPriceTiyin === null) return null
    collected.push({
      branch_material_id: item.branch_material_id,
      quantity,
      unit_price_tiyin: unitPriceTiyin,
    })
  }
  return collected.length > 0 ? collected : null
}

function resetFieldErrors() {
  saveError.value = null
  supplierError.value = null
  inlineSupplierError.value = null
  linesError.value = null
}

/** `withExpense` is what makes the invoice→expense link actually get used. */
async function save(withExpense = false) {
  resetFieldErrors()
  if (!form.supplierId) {
    supplierError.value = t('inventory.invoice.supplierRequired')
    return
  }
  if (form.supplierId === 'inline' && !form.inlineSupplierName.trim()) {
    inlineSupplierError.value = t('inventory.invoice.inlineSupplierRequired')
    return
  }
  const collected = collectLines()
  if (!collected) {
    linesError.value = t('inventory.invoice.linesInvalid')
    return
  }
  saving.value = true
  try {
    const saved = isEdit.value
      ? await workshop.updateSupplierInvoice(invoiceId.value ?? '', {
          supplier_id: form.supplierId,
          invoice_date: form.invoiceDate || null,
          lines: collected,
        })
      : await workshop.createSupplierInvoice(branchId.value, {
          supplier_id: form.supplierId === 'inline' ? null : form.supplierId,
          supplier: form.supplierId === 'inline' ? { name: form.inlineSupplierName.trim() } : null,
          invoice_date: form.invoiceDate || null,
          lines: collected,
        })
    dirty.value = false
    toast.success(
      isEdit.value
        ? t('inventory.detail.saved', { number: saved.invoice_no })
        : t('inventory.invoice.saved', { number: saved.invoice_no }),
    )
    // Stock and the movement log both moved; the Ombor tabs must refetch.
    workshop.clearInventory()
    if (withExpense) {
      await router.push(
        rolePath(`/workshop/finance/expenses?create=expense&invoice_id=${saved.id}`),
      )
      return
    }
    await router.push(rolePath(`/workshop/inventory/invoices/${saved.id}`))
  } catch (errorValue) {
    const code = apiErrorCode(errorValue)
    if (code === 'supplier_inactive') {
      supplierError.value = t('inventory.error.supplier_inactive')
    } else if (code === 'invoice_discount_too_big') {
      linesError.value = t('inventory.form.legacyDiscountBlocks')
    } else if (code === 'branch_material_not_found') {
      saveError.value = 'branch_material_not_found'
    } else if (code === 'future_date_not_allowed') {
      saveError.value = 'future_date_not_allowed'
    } else if (code === 'invoice_voided') {
      saveError.value = 'invoice_voided'
    } else {
      saveError.value = isEdit.value ? 'invoice_update_failed' : 'invoice_save_failed'
    }
  } finally {
    saving.value = false
  }
}

/**
 * Deliberately a switch of LITERAL keys, not `t(\`inventory.error.${code}\`)`:
 * `pnpm i18n:check` only sees literal keys, so a built-up one lets a renamed
 * message ship as a raw key path through a green gate.
 */
const saveErrorMessage = computed(() => {
  switch (saveError.value) {
    case 'branch_material_not_found':
      return t('inventory.error.branch_material_not_found')
    case 'future_date_not_allowed':
      return t('inventory.error.future_date_not_allowed')
    case 'invoice_voided':
      return t('inventory.error.invoice_voided')
    case 'invoice_update_failed':
      return t('inventory.error.invoice_update_failed')
    case 'invoice_save_failed':
      return t('inventory.error.invoice_save_failed')
    default:
      return null
  }
})

async function cancel() {
  dirty.value = false
  await router.push(
    isEdit.value && invoiceId.value
      ? rolePath(`/workshop/inventory/invoices/${invoiceId.value}`)
      : backLink.value,
  )
}
</script>

<template>
  <section>
    <RouterLink :to="backLink" class="back">{{ $t('inventory.form.back') }}</RouterLink>

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

    <section v-else-if="loadError" class="st-error">
      <h3>
        {{
          loadError === 'invoice_not_found'
            ? $t('inventory.detail.notFound')
            : $t('inventory.detail.loadFailed')
        }}
      </h3>
      <p>{{ traceLine(loadTraceId) }}</p>
    </section>

    <div v-else-if="!branchId" class="st-empty">
      <h3>{{ $t('inventory.page.noBranchTitle') }}</h3>
      <p>{{ $t('inventory.page.noBranchBody') }}</p>
    </div>

    <template v-else>
      <div class="page-head mt-2">
        <div>
          <h1>{{ pageTitle }}</h1>
          <p class="sub">{{ $t('inventory.form.sub') }}</p>
        </div>
      </div>

      <!-- `card-b` is a card *body*: its top padding is 0 because a `card-h`
           normally sits above it. This card carries no header — the page title is
           the heading — so it takes the headerless-card padding the rest of the app
           uses (and that this view's own loading skeleton uses). -->
      <form class="card grid gap-4 p-5" @submit.prevent="save(false)">
        <div class="grid gap-3 md:grid-cols-3">
          <FormSelect
            v-model="form.supplierId"
            :label="$t('inventory.invoice.supplier')"
            :options="supplierOptions"
            :error="supplierError"
          />
          <label class="field !mb-0">
            <span>{{ $t('inventory.invoice.date') }}</span>
            <DateField v-model="form.invoiceDate" :max="today" required />
          </label>
        </div>

        <!-- The error belongs on the field that is wrong: "type the new
             supplier's name" against the dropdown, which already has a value,
             is invisible next to the empty input it is actually about. -->
        <label v-if="form.supplierId === 'inline'" class="field !mb-0">
          <span>{{ $t('inventory.invoice.inlineSupplierName') }}</span>
          <input
            v-model="form.inlineSupplierName"
            class="mp-input"
            :aria-invalid="inlineSupplierError ? 'true' : undefined"
            aria-describedby="invoice-inline-supplier-error"
            required
          />
          <small
            v-if="inlineSupplierError"
            id="invoice-inline-supplier-error"
            class="mp-field-error"
          >
            {{ inlineSupplierError }}
          </small>
        </label>

        <div class="grid gap-2">
          <div class="table-wrap">
            <table class="tbl">
              <thead>
                <!-- Explicit widths: `auto` layout gave the material the same
                     share as a two-digit quantity, so a 47-character label was
                     clipped while three numeric columns sat half empty. -->
                <tr>
                  <th class="w-[29%]">{{ $t('inventory.invoice.columnMaterial') }}</th>
                  <th class="right w-[19%]">{{ $t('inventory.invoice.columnQuantity') }}</th>
                  <th class="right w-[24%]">{{ $t('inventory.invoice.columnPrice') }}</th>
                  <th class="right w-[21%]">{{ $t('inventory.invoice.columnAmount') }}</th>
                  <th class="w-[7%]"></th>
                </tr>
              </thead>
              <tbody>
                <template v-for="line in lines" :key="line.key">
                  <tr>
                    <td class="align-top">
                      <!-- Once picked, the material stops being an input and
                           becomes wrapping text: a label runs to ~371px and no
                           single-line input in this column can hold it. The
                           label IS the control — clicking it returns to the
                           picker, so the full width goes to what is read. -->
                      <button
                        v-if="line.materialId"
                        type="button"
                        class="w-full text-left text-sm font-bold leading-snug text-ink hover:underline"
                        :title="$t('inventory.invoice.changeMaterial')"
                        @click="clearLineMaterial(line)"
                      >
                        {{ lineMaterialLabel(line) }}
                      </button>
                      <SearchCombobox
                        v-else
                        v-model="line.materialId"
                        :label="$t('inventory.invoice.columnMaterial')"
                        label-class="sr-only"
                        :options="stockOptions"
                        compact
                        @update:model-value="onLineMaterialChange(line)"
                      />
                    </td>
                    <td class="align-top">
                      <span class="mp-unit-field">
                        <!-- No `placeholder="0"`: an untouched row read as a real
                             `0 × 0` line rather than an empty one. -->
                        <input
                          v-model="line.quantity"
                          :data-qty-for="line.key"
                          class="mp-input text-right"
                          inputmode="decimal"
                          :aria-label="
                            $t('inventory.invoice.quantityAria', { unit: lineQuantityUnit(line) })
                          "
                        />
                        <span class="mp-unit-suffix" aria-hidden="true">
                          {{ lineQuantityUnit(line) }}
                        </span>
                      </span>
                    </td>
                    <td class="align-top">
                      <span class="mp-unit-field">
                        <input
                          v-model="line.unitPrice"
                          class="mp-input text-right"
                          inputmode="decimal"
                          :aria-label="
                            $t('inventory.invoice.priceAria', { unit: linePriceUnit(line) })
                          "
                          @input="line.priceEdited = true"
                        />
                        <span class="mp-unit-suffix" aria-hidden="true">
                          {{ linePriceUnit(line) }}
                        </span>
                      </span>
                    </td>
                    <td class="amt whitespace-nowrap align-top">
                      {{
                        lineTotalTiyin(line) !== null ? formatTiyin(lineTotalTiyin(line) ?? 0) : '—'
                      }}
                    </td>
                    <td class="right align-top">
                      <button
                        type="button"
                        class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                        :aria-label="$t('inventory.invoice.removeLineAria')"
                        @click="removeLine(line.key)"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                  <!-- The last-price provenance sits UNDER the line, not inside
                       the price cell: in the cell it wrapped to three lines and
                       pushed the three inputs onto three baselines. -->
                  <tr v-if="lineLastPriceHint(line)" class="hint-row">
                    <td colspan="5" class="pt-0 text-[11px] text-ink-muted">
                      {{ lineLastPriceHint(line) }}
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
          <div>
            <button
              type="button"
              class="mp-button mp-button-outline min-h-9 px-3 text-sm"
              @click="addLine"
            >
              {{ $t('inventory.invoice.addLine') }}
            </button>
          </div>
          <small v-if="linesError" class="mp-field-error">{{ linesError }}</small>
        </div>

        <!-- With no document-level discount there is no ladder: the line sum IS
             the total, and a two-row block would only restate it. -->
        <div class="ml-auto w-full max-w-xs">
          <div
            class="flex items-center justify-between rounded-md border border-hairline bg-sunk p-3 text-base font-bold"
          >
            <span>{{ $t('inventory.invoice.total') }}</span>
            <span class="num">{{ formatTiyin(totalTiyin) }}</span>
          </div>
        </div>

        <p
          v-if="saveErrorMessage"
          class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          role="alert"
        >
          {{ saveErrorMessage }}
        </p>

        <!-- The save actions group right; Bekor is pushed to the far left so it
             stops competing with them — one primary action per screen. -->
        <div class="flex flex-wrap items-center justify-end gap-2">
          <button type="button" class="mp-button mp-button-outline mr-auto" @click="cancel">
            {{ $t('inventory.action.cancel') }}
          </button>
          <button
            v-if="!isEdit && canSeeFinance"
            type="button"
            class="mp-button mp-button-outline"
            :disabled="saving"
            @click="save(true)"
          >
            {{ $t('inventory.invoice.saveWithExpense') }}
          </button>
          <button type="submit" class="mp-button mp-button-primary" :disabled="saving">
            {{ saving ? $t('inventory.action.saving') : $t('inventory.action.save') }}
          </button>
        </div>
      </form>
    </template>

    <ConfirmDialog
      :open="leaveOpen"
      :title="$t('inventory.form.leaveTitle')"
      :message="$t('inventory.form.leaveMessage')"
      :confirm-label="$t('inventory.form.leaveConfirm')"
      :cancel-label="$t('inventory.form.leaveCancel')"
      danger
      @cancel="resolveLeave(false)"
      @confirm="resolveLeave(true)"
    />
  </section>
</template>
