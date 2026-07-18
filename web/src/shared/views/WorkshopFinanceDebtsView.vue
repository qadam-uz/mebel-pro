<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { presetRange, type DateRangePreset } from '@/shared/app/dateRange'
import { sanitizeMoneyInput } from '@/shared/app/inputSanitizers'
import { useRolePath } from '@/shared/app/paths'
import { workshopErrorMessage } from '@/shared/app/workshopUi'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import AppModal from '@/shared/components/AppModal.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import DateRangePicker from '@/shared/components/DateRangePicker.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import {
  formatDate,
  formatDateInputValue,
  formatStockQuantity,
  formatTiyin,
  formatTiyinParts,
  parseSomToTiyin,
} from '@/shared/formatters'
import { useFinanceStore, type DebtRow, type DebtStatementRow } from '@/shared/stores/finance'

const router = useRouter()
const rolePath = useRolePath()
const permissions = useWorkshopPermissions()
const finance = useFinanceStore()
const toast = useToast()
const today = formatDateInputValue(new Date())

const canManageFinance = computed(() => permissions.can(p.manageFinance))

// List state. «Faqat qarzdorlar» is the default — the working list is who owes whom.
const search = ref('')
const onlyWithDebt = ref(true)
let searchTimer: number | undefined

// Statement state: a selected supplier switches the page into akt-sverka mode.
const selectedSupplierId = ref<string | null>(null)
const initialRange = presetRange('all')
const datePreset = ref<DateRangePreset>('all')
const dateFrom = ref(initialRange.from ?? '')
const dateTo = ref(initialRange.to ?? '')

// «Qarz tuzatish» modal — direction is asked in words, the sign is derived.
const adjustmentOpen = ref(false)
const adjustmentSaving = ref(false)
const adjustmentError = ref<string | null>(null)
const adjustmentForm = reactive({
  direction: 'we_owe_more' as string | null,
  amount: '',
  adjustedOn: today,
  note: '',
})
const directionOptions: ChoiceOption[] = [
  { value: 'we_owe_more', label: 'Qarzimiz oshadi', meta: "ta'minotchiga qarzimiz ko'payadi" },
  { value: 'we_owe_less', label: 'Qarzimiz kamayadi', meta: 'chegirma, qaytarish, boshqa' },
]

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

const weOweParts = computed(() => formatTiyinParts(finance.supplierDebts?.we_owe_total_tiyin ?? 0))
const theyOweParts = computed(() =>
  formatTiyinParts(finance.supplierDebts?.they_owe_total_tiyin ?? 0),
)

const statementSupplierName = computed(
  () =>
    finance.statement?.name ??
    finance.supplierDebts?.rows.find((row) => row.counterparty_id === selectedSupplierId.value)
      ?.name ??
    '',
)

// Positive balance = they owe us; negative = we owe them. Words, never bare signs.
function balanceChip(balance: number) {
  if (balance > 0) return { cls: 'pill p-ok', text: `Bizga qarzi: ${formatTiyin(balance)}` }
  if (balance < 0) return { cls: 'pill p-bad', text: `Bizning qarzimiz: ${formatTiyin(-balance)}` }
  return { cls: 'pill p-dn', text: 'Qarz yo`q' }
}

function statementRowLabel(row: DebtStatementRow) {
  if (row.kind === 'delivery') {
    const qty =
      row.quantity !== null && row.display_unit
        ? ` · ${formatStockQuantity(row.quantity, row.display_unit)}`
        : ''
    return `Kirim · ${row.material_name ?? 'Material'}${qty}`
  }
  if (row.kind === 'payment') return `Xarajat · ${row.note ?? "to'lov"}`
  if (row.kind === 'order') return `Buyurtma ${row.order_number ?? ''}`.trim()
  return `Qarz tuzatish · ${row.note ?? ''}`.trim()
}

async function refreshList() {
  await finance.loadSupplierDebts({
    search: search.value.trim() || undefined,
    only_with_debt: onlyWithDebt.value,
  })
}

async function refreshStatement() {
  if (!selectedSupplierId.value) return
  await finance.loadSupplierStatement(selectedSupplierId.value, {
    date_from: dateFrom.value || null,
    date_to: dateTo.value || null,
  })
}

function openStatement(row: DebtRow) {
  selectedSupplierId.value = row.counterparty_id
  void refreshStatement()
}

function backToList() {
  selectedSupplierId.value = null
  finance.statement = null
  void refreshList()
}

function paySupplier() {
  if (!selectedSupplierId.value) return
  // Reuses the real expense modal — the expenses page opens it pre-filled.
  void router.push({
    path: rolePath('/workshop/finance/expenses'),
    query: { create: 'expense', supplier_id: selectedSupplierId.value },
  })
}

function openAdjustment() {
  adjustmentForm.direction = 'we_owe_more'
  adjustmentForm.amount = ''
  adjustmentForm.adjustedOn = today
  adjustmentForm.note = ''
  adjustmentError.value = null
  adjustmentOpen.value = true
}

async function saveAdjustment() {
  if (!selectedSupplierId.value) return
  if (adjustmentAmountTiyin.value === null) {
    adjustmentError.value = 'Summani tekshiring — masalan: 1 500 000'
    return
  }
  adjustmentSaving.value = true
  adjustmentError.value = null
  try {
    // Supplier side: our debt growing means their balance moves negative.
    const sign = adjustmentForm.direction === 'we_owe_more' ? -1 : 1
    await finance.createAdjustment({
      supplier_id: selectedSupplierId.value,
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

watch([search, onlyWithDebt], () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    if (!selectedSupplierId.value) void refreshList()
  }, 250)
})

watch([dateFrom, dateTo], () => {
  if (selectedSupplierId.value) void refreshStatement()
})

onMounted(() => {
  if (!canManageFinance.value) return
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

    <!-- List mode: every supplier with a live derived balance. -->
    <template v-else-if="!selectedSupplierId">
      <div class="kpis kpis-dash">
        <div class="kpi bad">
          <div class="lbl danger-text">Ta'minotchilarga qarzimiz</div>
          <div class="v num danger-text">
            <span :title="weOweParts.full"
              >{{ weOweParts.amount }} <small>{{ weOweParts.unit }}</small></span
            >
          </div>
          <div class="d"><span>to'lanmagan yetkazmalar</span></div>
        </div>
        <div class="kpi">
          <div class="lbl success-text">Ta'minotchilarning bizga qarzi</div>
          <div class="v num success-text">
            <span :title="theyOweParts.full"
              >{{ theyOweParts.amount }} <small>{{ theyOweParts.unit }}</small></span
            >
          </div>
          <div class="d"><span>avans va qaytimlar</span></div>
        </div>
      </div>

      <div class="mp-filters">
        <label class="mp-filter-input">
          <span>Qidirish</span>
          <input v-model="search" placeholder="Ta'minotchi nomi..." />
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

      <section v-if="finance.loading && !finance.supplierDebts" class="card p-5" aria-live="polite">
        <div class="grid gap-3">
          <span class="sk-line"></span>
          <span class="sk-line"></span>
          <span class="sk-line"></span>
        </div>
      </section>

      <section v-else-if="finance.error" class="st-error">
        <h3>Qarzdorlikni yuklab bo'lmadi</h3>
        <p>trace_id: {{ finance.traceId ?? 'unavailable' }}</p>
      </section>

      <section v-else class="card">
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>Ta'minotchi</th>
                <th>Telefon</th>
                <th class="right">Balans</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in finance.supplierDebts?.rows ?? []" :key="row.counterparty_id">
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
              <tr v-if="(finance.supplierDebts?.rows ?? []).length === 0">
                <td colspan="4">
                  <div class="st-empty !border-0 !py-8">
                    <h3>{{ onlyWithDebt ? "Qarzdor ta'minotchi yo'q" : "Ta'minotchi yo'q" }}</h3>
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
        <button type="button" class="mp-button mp-button-outline" @click="openAdjustment">
          Tuzatish kiritish
        </button>
        <button type="button" class="mp-button mp-button-primary" @click="paySupplier">
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
        <p>trace_id: {{ finance.traceId ?? 'unavailable' }}</p>
      </section>

      <section v-else-if="finance.statement" class="card">
        <div class="flex flex-wrap items-center justify-between gap-2 border-b border-hairline p-4">
          <div class="flex min-w-0 items-center gap-3">
            <b class="truncate">{{ statementSupplierName }} — akt sverka</b>
            <span :class="balanceChip(finance.statement.current_balance_tiyin).cls">
              <span class="pd"></span
              >{{ balanceChip(finance.statement.current_balance_tiyin).text }}
            </span>
          </div>
          <small v-if="finance.statement.phone" class="text-ink-muted">
            {{ finance.statement.phone }}
          </small>
        </div>
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>Sana</th>
                <th>Hujjat</th>
                <th class="right">Qarzimiz +</th>
                <th class="right">Qarzimiz −</th>
                <th class="right">Qoldiq</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="finance.statement.date_from">
                <td class="num text-ink-muted">{{ formatDate(finance.statement.date_from) }}</td>
                <td class="nm">Boshlang'ich qoldiq</td>
                <td class="amt muted">—</td>
                <td class="amt muted">—</td>
                <td class="amt">
                  {{ formatTiyin(Math.abs(finance.statement.opening_balance_tiyin)) }}
                  <small
                    v-if="finance.statement.opening_balance_tiyin > 0"
                    class="block text-[11px] text-ink-muted"
                    >bizga qarzi</small
                  >
                </td>
                <td></td>
              </tr>
              <tr v-for="row in finance.statement.rows" :key="row.reference_id">
                <td class="num text-ink-muted">{{ formatDate(row.on) }}</td>
                <td class="nm">{{ statementRowLabel(row) }}</td>
                <td class="amt" :class="row.amount_tiyin < 0 ? 'danger-text' : 'muted'">
                  {{ row.amount_tiyin < 0 ? formatTiyin(-row.amount_tiyin) : '—' }}
                </td>
                <td class="amt" :class="row.amount_tiyin > 0 ? 'success-text' : 'muted'">
                  {{ row.amount_tiyin > 0 ? formatTiyin(row.amount_tiyin) : '—' }}
                </td>
                <td class="amt">
                  {{ formatTiyin(Math.abs(row.balance_after_tiyin)) }}
                  <small v-if="row.balance_after_tiyin > 0" class="block text-[11px] text-ink-muted"
                    >bizga qarzi</small
                  >
                </td>
                <td class="right">
                  <button
                    v-if="row.kind === 'adjustment'"
                    type="button"
                    class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                    @click="openVoid(row)"
                  >
                    Bekor qilish
                  </button>
                </td>
              </tr>
              <tr v-if="finance.statement.rows.length === 0">
                <td colspan="6">
                  <div class="st-empty !border-0 !py-8"><h3>Bu davrda harakat yo'q</h3></div>
                </td>
              </tr>
            </tbody>
          </table>
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
            <input v-model="adjustmentForm.amount" class="mp-input" inputmode="numeric" required />
            <small v-if="adjustmentAmountTiyin !== null" class="text-ink-muted">
              = {{ formatTiyin(adjustmentAmountTiyin) }}
            </small>
          </label>
          <label class="field">
            <span>Sana</span>
            <input
              v-model="adjustmentForm.adjustedOn"
              type="date"
              class="mp-input"
              :max="today"
              required
            />
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
  </section>
</template>
