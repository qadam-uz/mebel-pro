<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
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

const router = useRouter()
const rolePath = useRolePath()
const permissions = useWorkshopPermissions()
const finance = useFinanceStore()
const workshop = useWorkshopStore()
const toast = useToast()
const today = formatDateInputValue(new Date())

const canManageFinance = computed(() => permissions.can(p.manageFinance))

const activeTab = ref<DebtSide>('suppliers')
const debtTabs: ChoiceOption[] = [
  { value: 'suppliers', label: "Ta'minotchilar" },
  { value: 'clients', label: 'Mijozlar' },
]

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
        { value: 'debt_grows', label: 'Qarzimiz oshadi', meta: "ta'minotchiga qarzimiz ko'payadi" },
        { value: 'debt_shrinks', label: 'Qarzimiz kamayadi', meta: 'chegirma, qaytarish, boshqa' },
      ]
    : [
        { value: 'debt_grows', label: 'Mijozning qarzi oshadi', meta: "daftar qarzi, qo'shimcha" },
        { value: 'debt_shrinks', label: 'Mijozning qarzi kamayadi', meta: 'chegirma, kechirilgan' },
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
    ? `Ro'yxatda ${count} ta ta'minotchi`
    : `Ro'yxatda ${count} ta mijoz`
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
    ? { debit: 'Qarzimiz +', credit: 'Qarzimiz −' }
    : { debit: 'Qarzi +', credit: 'Qarzi −' },
)
const counterpartyRole = computed(() => (activeTab.value === 'suppliers' ? "Ta'minotchi" : 'Mijoz'))

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
  if (statement.date_from) return `${formatDate(statement.date_from)} dan`
  if (statement.date_to) return `${formatDate(statement.date_to)} gacha`
  return 'butun tarix'
})

function balanceWord(balanceTiyin: number) {
  return directionLabel(balanceDirection(balanceTiyin))
}

// Positive balance = they owe us; negative = we owe them. Words, never bare signs.
function balanceChip(balance: number) {
  if (balance > 0) return { cls: 'pill p-ok', text: `Bizga qarzi: ${formatTiyin(balance)}` }
  if (balance < 0) return { cls: 'pill p-bad', text: `Bizning qarzimiz: ${formatTiyin(-balance)}` }
  return { cls: 'pill p-dn', text: "Qarz yo'q" }
}

function statementRowLabel(row: DebtStatementRow) {
  if (row.kind === 'delivery') {
    // A delivery term is one faktura, at the grain the supplier quotes: its
    // number, how many positions it carried, and any chegirma/ustama on it.
    const parts = [`Kirim · ${row.invoice_no ?? 'faktura'}`]
    if (row.line_count !== null) parts.push(`${row.line_count} pozitsiya`)
    if (row.discount_tiyin) parts.push(`chegirma ${formatTiyin(row.discount_tiyin)}`)
    if (row.surcharge_tiyin) parts.push(`ustama ${formatTiyin(row.surcharge_tiyin)}`)
    return parts.join(' · ')
  }
  if (row.kind === 'payment') {
    if (row.order_number) return `To'lov · ${row.order_number}`
    return `Xarajat · ${row.note ?? "to'lov"}`
  }
  if (row.kind === 'order') return `Buyurtma ${row.order_number ?? ''}`.trim()
  return `Qarz tuzatish · ${row.note ?? ''}`.trim()
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
    adjustmentError.value = 'Summani tekshiring — masalan: 1 500 000'
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
    toast.success('Qarz tuzatish yozildi.')
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
    toast.success('Tuzatish bekor qilindi.')
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
        <h1>Qarzdorlik</h1>
      </div>
    </div>

    <section v-if="!canManageFinance" class="st-empty">
      <h3>Qarzdorlik bo'limiga ruxsatingiz yo'q</h3>
      <p>Bu bo'lim uchun moliya boshqaruvi ruxsati kerak.</p>
    </section>

    <template v-else>
      <AppTabs
        v-model="activeTab"
        id-prefix="workshop-debts"
        label="Qarzdorlik bo'limlari"
        :tabs="debtTabs"
      />

      <!-- List mode: every counterparty with a live derived balance. -->
      <template v-if="!selectedId">
        <!-- Statistics: figures on hairlines, no card chrome. Colour lands on
             the number only — the label already says which way it points. -->
        <div class="figs">
          <div class="fig">
            <span class="fig-l">Qarzimiz</span>
            <span
              class="fig-v"
              :class="(activeDebts?.we_owe_total_tiyin ?? 0) > 0 ? 'danger-text' : ''"
              :title="weOweParts.full"
              >{{ weOweParts.amount }} <small>{{ weOweParts.unit }}</small></span
            >
          </div>
          <div class="fig">
            <span class="fig-l">Bizga qarz</span>
            <span
              class="fig-v"
              :class="(activeDebts?.they_owe_total_tiyin ?? 0) > 0 ? 'success-text' : ''"
              :title="theyOweParts.full"
              >{{ theyOweParts.amount }} <small>{{ theyOweParts.unit }}</small></span
            >
          </div>
          <div class="fig">
            <span class="fig-l">Sof holat</span>
            <span
              class="fig-v"
              :class="netTiyin > 0 ? 'success-text' : netTiyin < 0 ? 'danger-text' : ''"
              :title="netParts.full"
              ><template v-if="netTiyin < 0">−</template>{{ netParts.amount }}
              <small>{{ netParts.unit }}</small></span
            >
            <span class="fig-note">{{ balanceWord(netTiyin) || 'balans nolda' }}</span>
          </div>
        </div>
        <p class="figs-meta">{{ listedCountLabel }}</p>

        <div class="mp-filters">
          <label class="mp-filter-input">
            <span>Qidirish</span>
            <input
              v-model="search"
              :placeholder="
                activeTab === 'suppliers' ? `Ta'minotchi nomi` : 'Mijoz nomi yoki telefoni'
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
            Faqat qarzdorlar
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
          <h3>Qarzdorlikni yuklab bo'lmadi</h3>
          <p>{{ traceLine(finance.traceId) }}</p>
        </section>

        <section v-else class="card">
          <div class="table-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th>{{ activeTab === 'suppliers' ? "Ta'minotchi" : 'Mijoz' }}</th>
                  <th>Telefon</th>
                  <th class="right">Balans</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in activeDebts?.rows ?? []" :key="row.counterparty_id">
                  <td class="nm">
                    {{ row.name }}
                    <small v-if="row.inactive" class="block text-[11px] text-ink-muted">
                      faol emas
                    </small>
                  </td>
                  <td class="num">{{ row.phone ?? '—' }}</td>
                  <td class="right">
                    <span :class="balanceChip(row.balance_tiyin).cls">
                      <span class="pd"></span>{{ balanceChip(row.balance_tiyin).text }}
                    </span>
                  </td>
                  <td class="right">
                    <button
                      type="button"
                      class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                      @click="openStatement(row)"
                    >
                      Akt sverka
                    </button>
                  </td>
                </tr>
                <tr v-if="(activeDebts?.rows ?? []).length === 0">
                  <td colspan="4">
                    <div class="st-empty !border-0 !py-8">
                      <h3>
                        {{
                          onlyWithDebt
                            ? activeTab === 'suppliers'
                              ? "Qarzdor ta'minotchi yo'q"
                              : "Qarzdor mijoz yo'q"
                            : activeTab === 'suppliers'
                              ? "Ta'minotchi yo'q"
                              : "Mijoz yo'q"
                        }}
                      </h3>
                      <p v-if="onlyWithDebt">Hamma balanslar nolda — bu yaxshi belgi.</p>
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
            ← Ro'yxat
          </button>
          <DateRangePicker
            v-model:preset="datePreset"
            v-model:date-from="dateFrom"
            v-model:date-to="dateTo"
          />
          <button type="button" class="mp-button mp-button-outline" @click="printStatement">
            Chop etish
          </button>
          <button
            type="button"
            class="mp-button mp-button-outline"
            :disabled="finance.statementPdfLoading"
            @click="downloadStatementPdf"
          >
            {{ finance.statementPdfLoading ? 'Tayyorlanmoqda' : 'PDF' }}
          </button>
          <button type="button" class="mp-button mp-button-outline" @click="openAdjustment">
            Tuzatish kiritish
          </button>
          <button type="button" class="mp-button mp-button-primary" @click="payCounterparty">
            To'lov qilish
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
          <h3>Akt sverkani yuklab bo'lmadi</h3>
          <p>{{ traceLine(finance.traceId) }}</p>
          <button type="button" class="mp-button mp-button-outline" @click="refreshStatement">
            Qayta urinish
          </button>
        </section>

        <section v-else-if="finance.statement" class="card akt">
          <!-- Document head: what a signed akt sverka must state up front —
               the title, the period, and both parties by name and number. -->
          <header class="akt-head">
            <div>
              <h2 class="akt-title">Akt sverka</h2>
              <p class="akt-meta">{{ periodText }} · summalar so'mda</p>
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
              <span class="akt-role">Ustaxona</span>
              <b>{{ finance.statement.workshop_name }}</b>
              <small>{{ finance.statement.workshop_phone ?? "telefon ko'rsatilmagan" }}</small>
            </div>
            <div class="akt-party">
              <span class="akt-role">{{ counterpartyRole }}</span>
              <b>{{ finance.statement.name }}</b>
              <small>{{ finance.statement.phone ?? "telefon ko'rsatilmagan" }}</small>
            </div>
          </div>
          <div class="table-wrap">
            <table class="tbl tbl-fluid akt-tbl">
              <thead>
                <tr>
                  <th class="nowrap akt-wide">Sana</th>
                  <th>Hujjat</th>
                  <th class="right nowrap akt-wide">{{ columnHeaders.debit }}</th>
                  <th class="right nowrap akt-wide">{{ columnHeaders.credit }}</th>
                  <th class="right nowrap akt-narrow">Summa</th>
                  <th class="right nowrap">
                    Qoldiq
                    <small>+ bizga qarzi · − qarzimiz</small>
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
                    Boshlang'ich qoldiq
                    <small v-if="!finance.statement.date_from">butun tarix boshida</small>
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
                      Bekor qilish
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
                      <h3>Bu davrda harakat yo'q</h3>
                      <p>Boshlang'ich va yopilish qoldig'i bir xil.</p>
                    </div>
                  </td>
                </tr>
              </tbody>
              <tfoot>
                <tr class="akt-turnover">
                  <td class="akt-wide"></td>
                  <td class="nm">
                    Davr aylanmasi
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
                  <td class="nm">Yopilish qoldig'i</td>
                  <td class="amt akt-wide"></td>
                  <td class="amt akt-wide"></td>
                  <td class="amt akt-narrow"></td>
                  <td class="amt">
                    {{ formatSom(Math.abs(finance.statement.closing_balance_tiyin)) }}
                    <small class="akt-dir">{{
                      balanceWord(finance.statement.closing_balance_tiyin) || "qarz yo'q"
                    }}</small>
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>

          <!-- Print only: the two signatures that make this a document. -->
          <div class="akt-sign">
            <p class="akt-sign-lead">Yuqoridagi hisob-kitob tomonlar tomonidan tasdiqlandi.</p>
            <div class="akt-sign-grid">
              <div>
                <b>Ustaxona nomidan</b>
                <small>{{ finance.statement.workshop_name }}</small>
                <span>F.I.Sh.</span>
                <span>Imzo</span>
                <span>Sana</span>
              </div>
              <div>
                <b>Kontragent nomidan</b>
                <small>{{ finance.statement.name }}</small>
                <span>F.I.Sh.</span>
                <span>Imzo</span>
                <span>Sana</span>
              </div>
            </div>
          </div>
        </section>

        <AppModal :open="adjustmentOpen" title="Qarz tuzatish" @close="adjustmentOpen = false">
          <form class="grid gap-3" @submit.prevent="saveAdjustment">
            <FormSelect
              v-model="adjustmentForm.direction"
              label="Yo'nalish"
              :options="directionOptions"
            />
            <label class="field">
              <span>Summa (so'm)</span>
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
              <span>Sana</span>
              <DateField v-model="adjustmentForm.adjustedOn" :max="today" required />
            </label>
            <label class="field">
              <span>Izoh (majburiy)</span>
              <input
                v-model="adjustmentForm.note"
                class="mp-input"
                placeholder="masalan: boshlang'ich qoldiq"
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
              {{ adjustmentSaving ? 'Saqlanmoqda' : 'Saqlash' }}
            </button>
          </form>
        </AppModal>

        <ConfirmDialog
          :open="voidTargetId !== null"
          title="Tuzatishni bekor qilish"
          message="Bekor qilingan tuzatish balansga ta'sir qilmaydi. Sababni yozing."
          confirm-label="Bekor qilish"
          cancel-label="Yopish"
          busy-label="Bekor qilinmoqda"
          danger
          :busy="voidSaving"
          :confirm-disabled="voidReason.trim().length === 0"
          @cancel="voidTargetId = null"
          @confirm="confirmVoid"
        >
          <label class="field !mb-0">
            <span>Bekor qilish sababi</span>
            <input v-model="voidReason" class="mp-input" required />
          </label>
          <p v-if="voidError" class="mt-2 text-sm font-bold text-danger">{{ voidError }}</p>
        </ConfirmDialog>
      </template>
    </template>
  </section>
</template>
