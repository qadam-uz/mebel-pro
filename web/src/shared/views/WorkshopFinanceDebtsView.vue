<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { presetRange, type DateRangePreset } from '@/shared/app/dateRange'
import {
  balanceDirection,
  directionLabel,
  periodTurnover,
  statementLines,
  type DebtSide,
} from '@/shared/app/debtStatement'
import { traceLine } from '@/shared/app/errorTrace'
import { sanitizeMoneyInput } from '@/shared/app/inputSanitizers'
import { useRolePath } from '@/shared/app/paths'
import { workshopErrorMessage } from '@/shared/app/workshopUi'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import AppModal from '@/shared/components/AppModal.vue'
import AppTabs from '@/shared/components/AppTabs.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import DateField from '@/shared/components/DateField.vue'
import DateRangePicker from '@/shared/components/DateRangePicker.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import {
  formatDate,
  formatDateInputValue,
  formatSom,
  formatTiyin,
  formatTiyinParts,
  parseSomToTiyin,
} from '@/shared/formatters'
import { useFinanceStore, type DebtRow, type DebtStatementRow } from '@/shared/stores/finance'
import { useWorkshopStore } from '@/shared/stores/workshop'

const { t } = useI18n()
const router = useRouter()
const rolePath = useRolePath()
const permissions = useWorkshopPermissions()
const finance = useFinanceStore()
const workshop = useWorkshopStore()
const toast = useToast()
const today = formatDateInputValue(new Date())

const canManageFinance = computed(() => permissions.can(p.manageFinance))

const activeTab = ref<DebtSide>('suppliers')
const debtTabs = computed<ChoiceOption[]>(() => [
  { value: 'suppliers', label: t('finance.debts.tabSuppliers') },
  { value: 'clients', label: t('finance.debts.tabClients') },
])

// List state. «Faqat qarzdorlar» is the default — the working list is who owes whom.
const search = ref('')
const onlyWithDebt = ref(true)
let searchTimer: number | undefined

// Statement state: a selected counterparty switches the page into akt-sverka mode.
const selectedId = ref<string | null>(null)
const initialRange = presetRange('all')
const datePreset = ref<DateRangePreset>('all')
const dateFrom = ref(initialRange.from ?? '')
const dateTo = ref(initialRange.to ?? '')

// «Qarz tuzatish» modal — direction is asked in words, the sign is derived.
const adjustmentOpen = ref(false)
const adjustmentSaving = ref(false)
const adjustmentError = ref<string | null>(null)
const adjustmentForm = reactive({
  direction: 'debt_grows' as string | null,
  amount: '',
  adjustedOn: today,
  note: '',
})
// Direction words are per side: the supplier statement talks about OUR debt,
// the client statement about THEIRS. The stored sign convention is one and the
// same (positive = they owe us more); only the wording flips.
const directionOptions = computed<ChoiceOption[]>(() =>
  activeTab.value === 'suppliers'
    ? [
        {
          value: 'debt_grows',
          label: t('finance.statement.adjustSupplierGrows'),
          meta: t('finance.statement.adjustSupplierGrowsHint'),
        },
        {
          value: 'debt_shrinks',
          label: t('finance.statement.adjustSupplierShrinks'),
          meta: t('finance.statement.adjustSupplierShrinksHint'),
        },
      ]
    : [
        {
          value: 'debt_grows',
          label: t('finance.statement.adjustClientGrows'),
          meta: t('finance.statement.adjustClientGrowsHint'),
        },
        {
          value: 'debt_shrinks',
          label: t('finance.statement.adjustClientShrinks'),
          meta: t('finance.statement.adjustClientShrinksHint'),
        },
      ],
)

const voidTargetId = ref<string | null>(null)
const voidReason = ref('')
const voidSaving = ref(false)
const voidError = ref<string | null>(null)

watch(
  () => adjustmentForm.amount,
  (value) => {
    const clean = sanitizeMoneyInput(value)
    if (clean !== value) adjustmentForm.amount = clean
  },
)
const adjustmentAmountTiyin = computed(() => parseSomToTiyin(adjustmentForm.amount))

const activeDebts = computed(() =>
  activeTab.value === 'suppliers' ? finance.supplierDebts : finance.clientDebts,
)
const weOweParts = computed(() => formatTiyinParts(activeDebts.value?.we_owe_total_tiyin ?? 0))
const theyOweParts = computed(() => formatTiyinParts(activeDebts.value?.they_owe_total_tiyin ?? 0))
// Where we stand overall: receivables minus payables, in the ledger's own
// convention (positive = they owe us).
const netTiyin = computed(
  () =>
    (activeDebts.value?.they_owe_total_tiyin ?? 0) - (activeDebts.value?.we_owe_total_tiyin ?? 0),
)
const netParts = computed(() => formatTiyinParts(Math.abs(netTiyin.value)))
// Counts the rows actually listed, so it always agrees with the table below it.
const listedCountLabel = computed(() => {
  const count = activeDebts.value?.rows.length ?? 0
  return activeTab.value === 'suppliers'
    ? t('finance.debts.listedSuppliers', { n: count }, count)
    : t('finance.debts.listedClients', { n: count }, count)
})

const statementName = computed(
  () =>
    finance.statement?.name ??
    activeDebts.value?.rows.find((row) => row.counterparty_id === selectedId.value)?.name ??
    '',
)

// ── The statement as a document ────────────────────────────────────────────
// Column wording is per side; the sign convention behind it is derived once in
// shared/app/debtStatement.ts and mirrored by the server's PDF.
const columnHeaders = computed(() =>
  activeTab.value === 'suppliers'
    ? {
        debit: t('finance.statement.colDebitSupplier'),
        credit: t('finance.statement.colCreditSupplier'),
      }
    : {
        debit: t('finance.statement.colDebitClient'),
        credit: t('finance.statement.colCreditClient'),
      },
)
const counterpartyRole = computed(() =>
  activeTab.value === 'suppliers' ? t('finance.field.supplier') : t('finance.field.client'),
)

const lines = computed(() =>
  finance.statement
    ? statementLines<DebtStatementRow>(
        finance.statement.rows,
        activeTab.value,
        finance.statement.opening_balance_tiyin,
      )
    : [],
)
const turnover = computed(() =>
  finance.statement ? periodTurnover(finance.statement, activeTab.value) : { debit: 0, credit: 0 },
)
const periodText = computed(() => {
  const statement = finance.statement
  if (!statement) return ''
  if (statement.date_from && statement.date_to) {
    return `${formatDate(statement.date_from)} — ${formatDate(statement.date_to)}`
  }
  if (statement.date_from) {
    return t('finance.statement.periodFrom', { date: formatDate(statement.date_from) })
  }
  if (statement.date_to) {
    return t('finance.statement.periodTo', { date: formatDate(statement.date_to) })
  }
  return t('finance.statement.periodAll')
})

function balanceWord(balanceTiyin: number) {
  return directionLabel(balanceDirection(balanceTiyin))
}

// Positive balance = they owe us; negative = we owe them. Words, never bare
// signs — but the word goes under the figure, so a column of balances stays a
// column of numbers you can compare down (QAD-182).
function balanceChip(balance: number) {
  if (balance > 0) {
    return {
      cls: 'pill p-ok',
      text: t('finance.debts.chipTheyOwe', { amount: formatTiyin(balance) }),
    }
  }
  if (balance < 0) {
    return {
      cls: 'pill p-bad',
      text: t('finance.debts.chipWeOwe', { amount: formatTiyin(-balance) }),
    }
  }
  return { cls: 'pill p-dn', text: t('finance.debts.chipSettled') }
}

function balanceToneClass(balance: number) {
  if (balance > 0) return 'success-text'
  if (balance < 0) return 'danger-text'
  return 'text-ink-muted'
}

function balanceTitle(balance: number) {
  return balanceChip(balance).text
}

function statementRowLabel(row: DebtStatementRow) {
  if (row.kind === 'delivery') {
    // A delivery term is one faktura, at the grain the supplier quotes: its
    // number, how many positions it carried, and any chegirma/ustama on it.
    const parts = [
      t('finance.statement.rowDelivery', {
        invoice: row.invoice_no ?? t('finance.statement.rowDeliveryFallback'),
      }),
    ]
    if (row.line_count !== null) {
      parts.push(t('finance.unit.positions', { n: row.line_count }, row.line_count))
    }
    if (row.discount_tiyin) {
      parts.push(t('finance.statement.rowDiscount', { amount: formatTiyin(row.discount_tiyin) }))
    }
    if (row.surcharge_tiyin) {
      parts.push(t('finance.statement.rowSurcharge', { amount: formatTiyin(row.surcharge_tiyin) }))
    }
    return parts.join(' · ')
  }
  if (row.kind === 'payment') {
    if (row.order_number) return t('finance.statement.rowPaymentOrder', { order: row.order_number })
    return t('finance.statement.rowExpense', {
      note: row.note ?? t('finance.statement.rowExpenseFallback'),
    })
  }
  if (row.kind === 'order') {
    return t('finance.statement.rowOrder', { order: row.order_number ?? '' }).trim()
  }
  return t('finance.statement.rowAdjustment', { note: row.note ?? '' }).trim()
}

// Debts follow the topbar picker like the rest of the finance module
// (QAD-182). A null branch is the workshop total, which is exactly the sum of
// its branches — every term in the fold names one.
const activeBranchId = computed(() => workshop.selectedBranchContext ?? null)

async function refreshList() {
  const filters = {
    search: search.value.trim() || undefined,
    only_with_debt: onlyWithDebt.value,
    branch_id: activeBranchId.value,
  }
  if (activeTab.value === 'suppliers') await finance.loadSupplierDebts(filters)
  else await finance.loadClientDebts(filters)
}

async function refreshStatement() {
  if (!selectedId.value) return
  await finance.loadStatement(activeTab.value, selectedId.value, {
    date_from: dateFrom.value || null,
    date_to: dateTo.value || null,
    branch_id: activeBranchId.value,
  })
}

function openStatement(row: DebtRow) {
  selectedId.value = row.counterparty_id
  void refreshStatement()
}

function backToList() {
  selectedId.value = null
  finance.statement = null
  void refreshList()
}

function payCounterparty() {
  if (!selectedId.value) return
  // Reuses the real ledger modals — the expenses page opens them pre-filled.
  if (activeTab.value === 'suppliers') {
    void router.push({
      path: rolePath('/workshop/finance/expenses'),
      query: { create: 'expense', supplier_id: selectedId.value },
    })
    return
  }
  void router.push({
    path: rolePath('/workshop/finance/income'),
    query: { create: 'income' },
  })
}

function printStatement() {
  // The print stylesheet strips the app chrome and lays the card out as a
  // document: title, both parties, period, totals, signature block.
  window.print()
}

async function downloadStatementPdf() {
  if (!selectedId.value || !finance.statement) return
  const stamp = finance.statement.date_to ?? formatDateInputValue(new Date())
  try {
    await finance.downloadStatementPdf(
      activeTab.value,
      selectedId.value,
      {
        date_from: dateFrom.value || null,
        date_to: dateTo.value || null,
        branch_id: activeBranchId.value,
      },
      `akt-sverka-${statementName.value}-${stamp}.pdf`.replace(/\s+/g, '-'),
    )
  } catch {
    toast.danger(workshopErrorMessage(finance.actionError ?? 'statement_pdf_failed'))
  }
}

function openAdjustment() {
  adjustmentForm.direction = 'debt_grows'
  adjustmentForm.amount = ''
  adjustmentForm.adjustedOn = today
  adjustmentForm.note = ''
  adjustmentError.value = null
  adjustmentOpen.value = true
}

async function saveAdjustment() {
  if (!selectedId.value) return
  if (adjustmentAmountTiyin.value === null) {
    adjustmentError.value = t('finance.form.amountHint')
    return
  }
  adjustmentSaving.value = true
  adjustmentError.value = null
  try {
    // One sign convention (positive = they owe us more): on the supplier side
    // "our debt grows" means their balance moves negative; on the client side
    // "their debt grows" moves it positive.
    const grows = adjustmentForm.direction === 'debt_grows'
    const sign = activeTab.value === 'suppliers' ? (grows ? -1 : 1) : grows ? 1 : -1
    await finance.createAdjustment({
      branch_id: activeBranchId.value,
      supplier_id: activeTab.value === 'suppliers' ? selectedId.value : null,
      client_id: activeTab.value === 'clients' ? selectedId.value : null,
      amount_tiyin: sign * adjustmentAmountTiyin.value,
      adjusted_on: adjustmentForm.adjustedOn,
      note: adjustmentForm.note,
    })
    adjustmentOpen.value = false
    toast.success(t('finance.statement.adjustSaved'))
    await refreshStatement()
  } catch {
    adjustmentError.value = workshopErrorMessage(finance.actionError ?? 'adjustment_save_failed')
  } finally {
    adjustmentSaving.value = false
  }
}

function openVoid(row: DebtStatementRow) {
  voidTargetId.value = row.reference_id
  voidReason.value = ''
  voidError.value = null
}

async function confirmVoid() {
  if (!voidTargetId.value || !voidReason.value.trim()) return
  voidSaving.value = true
  voidError.value = null
  try {
    await finance.voidAdjustment(voidTargetId.value, voidReason.value)
    voidTargetId.value = null
    toast.success(t('finance.statement.adjustVoided'))
    await refreshStatement()
  } catch {
    voidError.value = workshopErrorMessage(finance.actionError ?? 'ledger_void_failed')
  } finally {
    voidSaving.value = false
  }
}

watch(activeTab, () => {
  selectedId.value = null
  finance.statement = null
  void refreshList()
})

watch([search, onlyWithDebt], () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    if (!selectedId.value) void refreshList()
  }, 250)
})

watch([dateFrom, dateTo], () => {
  if (selectedId.value) void refreshStatement()
})

// Switching branch in the topbar reloads whichever surface is open — the list
// or the statement — so the figures never lag behind the picker above them.
watch(activeBranchId, () => {
  if (!canManageFinance.value) return
  if (selectedId.value) void refreshStatement()
  else void refreshList()
})

onMounted(async () => {
  if (!canManageFinance.value) return
  await workshop.loadBranchContext().catch(() => undefined)
  void refreshList()
})

onBeforeUnmount(() => {
  window.clearTimeout(searchTimer)
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>{{ $t('finance.debts.title') }}</h1>
      </div>
    </div>

    <section v-if="!canManageFinance" class="st-empty">
      <h3>{{ $t('finance.debts.deniedTitle') }}</h3>
      <p>{{ $t('finance.debts.deniedBody') }}</p>
    </section>

    <template v-else>
      <AppTabs
        v-model="activeTab"
        id-prefix="workshop-debts"
        :label="$t('finance.debts.tabsLabel')"
        :tabs="debtTabs"
      />

      <!-- List mode: every counterparty with a live derived balance. -->
      <template v-if="!selectedId">
        <!-- Statistics: figures on hairlines, no card chrome. Colour lands on
             the number only — the label already says which way it points. -->
        <div class="figs">
          <div class="fig">
            <span class="fig-l">{{ $t('finance.debts.figWeOwe') }}</span>
            <span
              class="fig-v"
              :class="(activeDebts?.we_owe_total_tiyin ?? 0) > 0 ? 'danger-text' : ''"
              :title="weOweParts.full"
              >{{ weOweParts.amount }} <small>{{ weOweParts.unit }}</small></span
            >
          </div>
          <div class="fig">
            <span class="fig-l">{{ $t('finance.debts.figTheyOwe') }}</span>
            <span
              class="fig-v"
              :class="(activeDebts?.they_owe_total_tiyin ?? 0) > 0 ? 'success-text' : ''"
              :title="theyOweParts.full"
              >{{ theyOweParts.amount }} <small>{{ theyOweParts.unit }}</small></span
            >
          </div>
          <div class="fig">
            <span class="fig-l">{{ $t('finance.debts.figNet') }}</span>
            <span
              class="fig-v"
              :class="netTiyin > 0 ? 'success-text' : netTiyin < 0 ? 'danger-text' : ''"
              :title="netParts.full"
              ><template v-if="netTiyin < 0">−</template>{{ netParts.amount }}
              <small>{{ netParts.unit }}</small></span
            >
            <span class="fig-note">{{ balanceWord(netTiyin) || $t('finance.debts.figZero') }}</span>
          </div>
        </div>
        <p class="figs-meta">{{ listedCountLabel }}</p>

        <div class="mp-filters">
          <label class="mp-filter-input">
            <span>{{ $t('common.action.search') }}</span>
            <input
              v-model="search"
              :placeholder="
                activeTab === 'suppliers'
                  ? $t('finance.debts.searchSupplier')
                  : $t('finance.debts.searchClient')
              "
            />
          </label>
          <button
            type="button"
            class="mp-filter-chip"
            :aria-pressed="onlyWithDebt"
            @click="onlyWithDebt = !onlyWithDebt"
          >
            <span class="mp-filter-chip-dot" aria-hidden="true"></span>
            {{ $t('finance.debts.onlyDebtors') }}
          </button>
        </div>

        <section v-if="finance.loading && !activeDebts" class="card p-5" aria-live="polite">
          <div class="grid gap-3">
            <span class="sk-line"></span>
            <span class="sk-line"></span>
            <span class="sk-line"></span>
          </div>
        </section>

        <section v-else-if="finance.error" class="st-error">
          <h3>{{ $t('finance.debts.loadFailed') }}</h3>
          <p>{{ traceLine(finance.traceId) }}</p>
        </section>

        <section v-else class="card">
          <div class="table-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th>{{ counterpartyRole }}</th>
                  <th>{{ $t('common.field.phone') }}</th>
                  <th class="right">
                    {{ $t('finance.debts.balanceColumn', { unit: $t('formats.currency.som') }) }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in activeDebts?.rows ?? []"
                  :key="row.counterparty_id"
                  class="row-clickable"
                >
                  <td class="nm">
                    <!-- The name opens the akt sverka, stretched over the row
                         (QAD-184) — the row no longer ends in a button column. -->
                    <button
                      type="button"
                      class="row-open row-open-text"
                      :aria-label="$t('finance.debts.statementAction', { name: row.name })"
                      @click="openStatement(row)"
                    >
                      {{ row.name }}
                    </button>
                    <small v-if="row.inactive" class="block text-[11px] text-ink-muted">
                      {{ $t('finance.status.inactive') }}
                    </small>
                  </td>
                  <td class="num">{{ row.phone ?? '—' }}</td>
                  <td class="amt" :title="balanceTitle(row.balance_tiyin)">
                    <b :class="balanceToneClass(row.balance_tiyin)">
                      {{ formatSom(Math.abs(row.balance_tiyin)) }}
                    </b>
                    <small class="block text-[11px] text-ink-muted">
                      {{ balanceWord(row.balance_tiyin) || $t('finance.debts.noDebt') }}
                    </small>
                  </td>
                </tr>
                <tr v-if="(activeDebts?.rows ?? []).length === 0">
                  <td colspan="3">
                    <div class="st-empty !border-0 !py-8">
                      <h3>
                        {{
                          onlyWithDebt
                            ? activeTab === 'suppliers'
                              ? $t('finance.debts.emptySuppliersWithDebt')
                              : $t('finance.debts.emptyClientsWithDebt')
                            : activeTab === 'suppliers'
                              ? $t('finance.debts.emptySuppliers')
                              : $t('finance.debts.emptyClients')
                        }}
                      </h3>
                      <p v-if="onlyWithDebt">{{ $t('finance.debts.emptyAllSettled') }}</p>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>

      <!-- Statement mode: the akt sverka — chronological rows with a running balance. -->
      <template v-else>
        <div class="mp-filters">
          <button type="button" class="mp-button mp-button-outline" @click="backToList">
            {{ $t('finance.statement.backToList') }}
          </button>
          <DateRangePicker
            v-model:preset="datePreset"
            v-model:date-from="dateFrom"
            v-model:date-to="dateTo"
          />
          <button type="button" class="mp-button mp-button-outline" @click="printStatement">
            {{ $t('finance.action.print') }}
          </button>
          <button
            type="button"
            class="mp-button mp-button-outline"
            :disabled="finance.statementPdfLoading"
            @click="downloadStatementPdf"
          >
            {{ finance.statementPdfLoading ? $t('finance.action.preparing') : 'PDF' }}
          </button>
          <button type="button" class="mp-button mp-button-outline" @click="openAdjustment">
            {{ $t('finance.statement.addAdjustment') }}
          </button>
          <button type="button" class="mp-button mp-button-primary" @click="payCounterparty">
            {{ $t('finance.statement.pay') }}
          </button>
        </div>

        <section v-if="finance.loading && !finance.statement" class="card p-5" aria-live="polite">
          <div class="grid gap-3">
            <span class="sk-line"></span>
            <span class="sk-line"></span>
            <span class="sk-line"></span>
          </div>
        </section>

        <section v-else-if="finance.error" class="st-error">
          <h3>{{ $t('finance.statement.loadFailed') }}</h3>
          <p>{{ traceLine(finance.traceId) }}</p>
          <button type="button" class="mp-button mp-button-outline" @click="refreshStatement">
            {{ $t('common.action.retry') }}
          </button>
        </section>

        <section v-else-if="finance.statement" class="card akt">
          <!-- Document head: what a signed akt sverka must state up front —
               the title, the period, and both parties by name and number. -->
          <header class="akt-head">
            <div>
              <h2 class="akt-title">{{ $t('finance.statement.title') }}</h2>
              <p class="akt-meta">{{ periodText }} · {{ $t('finance.statement.amountsInSom') }}</p>
            </div>
            <span
              class="akt-live"
              :class="balanceChip(finance.statement.current_balance_tiyin).cls"
            >
              <span class="pd"></span
              >{{ balanceChip(finance.statement.current_balance_tiyin).text }}
            </span>
          </header>
          <div class="akt-parties">
            <div class="akt-party">
              <span class="akt-role">{{ $t('finance.statement.partyWorkshop') }}</span>
              <b>{{ finance.statement.workshop_name }}</b>
              <small>{{
                finance.statement.workshop_phone ?? $t('finance.statement.partyNoPhone')
              }}</small>
            </div>
            <div class="akt-party">
              <span class="akt-role">{{ counterpartyRole }}</span>
              <b>{{ finance.statement.name }}</b>
              <small>{{ finance.statement.phone ?? $t('finance.statement.partyNoPhone') }}</small>
            </div>
          </div>
          <div class="table-wrap">
            <table class="tbl tbl-fluid akt-tbl">
              <thead>
                <tr>
                  <th class="nowrap akt-wide">{{ $t('finance.field.date') }}</th>
                  <th>{{ $t('finance.field.document') }}</th>
                  <th class="right nowrap akt-wide">{{ columnHeaders.debit }}</th>
                  <th class="right nowrap akt-wide">{{ columnHeaders.credit }}</th>
                  <th class="right nowrap akt-narrow">{{ $t('common.field.amount') }}</th>
                  <th class="right nowrap">
                    {{ $t('finance.statement.colBalance') }}
                    <small>{{ $t('finance.statement.colBalanceHint') }}</small>
                  </th>
                </tr>
              </thead>
              <tbody>
                <!-- The opening balance opens the document with or without a
                     period: without one it is the all-time opening. -->
                <tr class="akt-opening">
                  <td class="num akt-wide text-ink-muted">
                    {{
                      finance.statement.date_from ? formatDate(finance.statement.date_from) : '—'
                    }}
                  </td>
                  <td class="nm break-words">
                    {{ $t('finance.statement.opening') }}
                    <small v-if="!finance.statement.date_from">{{
                      $t('finance.statement.openingAllTime')
                    }}</small>
                  </td>
                  <td class="amt akt-wide"></td>
                  <td class="amt akt-wide"></td>
                  <td class="amt akt-narrow"></td>
                  <td class="amt">
                    {{ formatSom(Math.abs(finance.statement.opening_balance_tiyin)) }}
                    <small
                      v-if="balanceWord(finance.statement.opening_balance_tiyin)"
                      class="akt-dir"
                      >{{ balanceWord(finance.statement.opening_balance_tiyin) }}</small
                    >
                  </td>
                </tr>
                <tr v-for="line in lines" :key="line.row.reference_id">
                  <td class="num akt-wide text-ink-muted">{{ formatDate(line.row.on) }}</td>
                  <td class="nm break-words">
                    {{ statementRowLabel(line.row) }}
                    <small class="akt-narrow-date">{{ formatDate(line.row.on) }}</small>
                    <button
                      v-if="line.row.kind === 'adjustment'"
                      type="button"
                      class="mp-button mp-button-outline mt-1 min-h-8 px-2 text-xs"
                      @click="openVoid(line.row)"
                    >
                      {{ $t('finance.action.void') }}
                    </button>
                  </td>
                  <td class="amt akt-wide" :class="line.debit !== null ? 'danger-text' : ''">
                    {{ line.debit !== null ? formatSom(line.debit) : '' }}
                  </td>
                  <td class="amt akt-wide" :class="line.credit !== null ? 'success-text' : ''">
                    {{ line.credit !== null ? formatSom(line.credit) : '' }}
                  </td>
                  <td
                    class="amt akt-narrow"
                    :class="line.debit !== null ? 'danger-text' : 'success-text'"
                  >
                    {{
                      line.debit !== null
                        ? `+${formatSom(line.debit)}`
                        : `−${formatSom(line.credit ?? 0)}`
                    }}
                  </td>
                  <td class="amt">
                    {{ formatSom(line.balance) }}
                    <small v-if="line.directionChanged && line.balance" class="akt-dir">{{
                      directionLabel(line.direction)
                    }}</small>
                  </td>
                </tr>
                <tr v-if="finance.statement.rows.length === 0">
                  <td colspan="6">
                    <div class="st-empty !border-0 !py-8">
                      <h3>{{ $t('finance.statement.emptyTitle') }}</h3>
                      <p>{{ $t('finance.statement.emptyBody') }}</p>
                    </div>
                  </td>
                </tr>
              </tbody>
              <tfoot>
                <tr class="akt-turnover">
                  <td class="akt-wide"></td>
                  <td class="nm">
                    {{ $t('finance.statement.turnover') }}
                    <small class="akt-narrow-date"
                      >+{{ formatSom(turnover.debit) }} · −{{ formatSom(turnover.credit) }}</small
                    >
                  </td>
                  <td class="amt akt-wide">{{ formatSom(turnover.debit) }}</td>
                  <td class="amt akt-wide">{{ formatSom(turnover.credit) }}</td>
                  <td class="amt akt-narrow"></td>
                  <td class="amt"></td>
                </tr>
                <tr class="akt-closing">
                  <td class="akt-wide"></td>
                  <td class="nm">{{ $t('finance.statement.closing') }}</td>
                  <td class="amt akt-wide"></td>
                  <td class="amt akt-wide"></td>
                  <td class="amt akt-narrow"></td>
                  <td class="amt">
                    {{ formatSom(Math.abs(finance.statement.closing_balance_tiyin)) }}
                    <small class="akt-dir">{{
                      balanceWord(finance.statement.closing_balance_tiyin) ||
                      $t('finance.debts.noDebt')
                    }}</small>
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>

          <!-- Print only: the two signatures that make this a document. -->
          <div class="akt-sign">
            <p class="akt-sign-lead">{{ $t('finance.statement.signLead') }}</p>
            <div class="akt-sign-grid">
              <div>
                <b>{{ $t('finance.statement.signWorkshop') }}</b>
                <small>{{ finance.statement.workshop_name }}</small>
                <span>{{ $t('finance.statement.signFullName') }}</span>
                <span>{{ $t('finance.statement.signSignature') }}</span>
                <span>{{ $t('finance.field.date') }}</span>
              </div>
              <div>
                <b>{{ $t('finance.statement.signCounterparty') }}</b>
                <small>{{ finance.statement.name }}</small>
                <span>{{ $t('finance.statement.signFullName') }}</span>
                <span>{{ $t('finance.statement.signSignature') }}</span>
                <span>{{ $t('finance.field.date') }}</span>
              </div>
            </div>
          </div>
        </section>

        <AppModal
          :open="adjustmentOpen"
          :title="$t('finance.statement.adjustTitle')"
          @close="adjustmentOpen = false"
        >
          <form class="grid gap-3" @submit.prevent="saveAdjustment">
            <FormSelect
              v-model="adjustmentForm.direction"
              :label="$t('finance.field.direction')"
              :options="directionOptions"
            />
            <label class="field">
              <span>{{
                $t('finance.field.amountInSom', { unit: $t('formats.currency.som') })
              }}</span>
              <input
                v-model="adjustmentForm.amount"
                class="mp-input"
                inputmode="numeric"
                required
              />
              <small v-if="adjustmentAmountTiyin !== null" class="text-ink-muted">
                = {{ formatTiyin(adjustmentAmountTiyin) }}
              </small>
            </label>
            <label class="field">
              <span>{{ $t('finance.field.date') }}</span>
              <DateField v-model="adjustmentForm.adjustedOn" :max="today" required />
            </label>
            <label class="field">
              <span>{{ $t('finance.statement.adjustNote') }}</span>
              <input
                v-model="adjustmentForm.note"
                class="mp-input"
                :placeholder="$t('finance.statement.adjustNotePlaceholder')"
                required
              />
            </label>
            <p
              v-if="adjustmentError"
              class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
            >
              {{ adjustmentError }}
            </p>
            <button type="submit" class="mp-button mp-button-primary" :disabled="adjustmentSaving">
              {{ adjustmentSaving ? $t('finance.action.saving') : $t('common.action.save') }}
            </button>
          </form>
        </AppModal>

        <ConfirmDialog
          :open="voidTargetId !== null"
          :title="$t('finance.void.adjustmentTitle')"
          :message="$t('finance.void.adjustmentMessage')"
          :confirm-label="$t('finance.action.void')"
          :cancel-label="$t('common.action.close')"
          :busy-label="$t('finance.action.voiding')"
          danger
          :busy="voidSaving"
          :confirm-disabled="voidReason.trim().length === 0"
          @cancel="voidTargetId = null"
          @confirm="confirmVoid"
        >
          <label class="field !mb-0">
            <span>{{ $t('finance.void.reason') }}</span>
            <input v-model="voidReason" class="mp-input" required />
          </label>
          <p v-if="voidError" class="mt-2 text-sm font-bold text-danger">{{ voidError }}</p>
        </ConfirmDialog>
      </template>
    </template>
  </section>
</template>
