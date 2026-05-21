<script setup lang="ts">
// Income list + form (type → order picker when order_payment) + void.
// view_finance_reports = read-only (the add/void buttons are gated by canMutate).
import { onMounted, ref, watch } from 'vue'
import { ApiError } from '@/shared/api'
import { AppModal, ErrorState, FormField, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtDate, fmtTiyin, sumToTiyin } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopAuth } from '../../store'
import { useBranchesStore } from '../../stores/branches'
import * as api from '../../api'
import type { Income, IncomeType, OrderCard, PaymentMethod } from '../../api/types'
import ConfirmDialog from '../../components/ConfirmDialog.vue'

defineProps<{ canMutate: boolean }>()
const toast = useToast()
const auth = useWorkshopAuth()
const branchesStore = useBranchesStore()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const rows = ref<Income[]>([])
const orders = ref<OrderCard[]>([])

const formOpen = ref(false)
const saving = ref(false)
const form = ref<{
  type: IncomeType
  order_id: string
  amount: number
  method: PaymentMethod
  received_on: string
  note: string
}>({
  type: 'order_payment',
  order_id: '',
  amount: 0,
  method: 'cash',
  received_on: new Date().toISOString().slice(0, 10),
  note: '',
})

const voidId = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    rows.value = await api.listIncome({ branchId: auth.branchScope })
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

async function openForm() {
  form.value = {
    type: 'order_payment',
    order_id: '',
    amount: 0,
    method: 'cash',
    received_on: new Date().toISOString().slice(0, 10),
    note: '',
  }
  formOpen.value = true
  try {
    orders.value = (await api.listOrders({ branchId: auth.branchScope })).orders
  } catch {
    orders.value = []
  }
}

async function save() {
  saving.value = true
  try {
    await api.recordIncome({
      type: form.value.type,
      order_id: form.value.type === 'order_payment' ? form.value.order_id || null : null,
      amount_tiyin: sumToTiyin(form.value.amount),
      method: form.value.method,
      received_on: form.value.received_on,
      branch_id: auth.branchScope,
      note: form.value.note.trim() || null,
    })
    toast.ok(t('workshop.incomeRecorded'))
    formOpen.value = false
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    saving.value = false
  }
}

async function doVoid(reason: string) {
  if (!voidId.value) return
  try {
    await api.voidIncome(voidId.value, reason)
    toast.ok(t('workshop.voided'))
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  }
}

watch(() => auth.branchScope, load)
onMounted(load)
</script>

<template>
  <div style="margin-top: 16px">
    <div class="page-head" style="margin-bottom: 12px">
      <div />
      <div class="tools">
        <button v-if="canMutate" class="btn btn-acc btn-sm" type="button" @click="openForm">
          {{ t('workshop.addIncome') }}
        </button>
      </div>
    </div>

    <ErrorState v-if="error" :error="error" :retry="load" />
    <div v-else-if="loading" class="card">
      <div class="card-b"><div class="sk sk-line" style="width: 60%" /></div>
    </div>
    <div v-else-if="rows.length === 0" class="st-empty">
      <div class="ic">∅</div>
      <h3>{{ t('workshop.incomeEmpty') }}</h3>
    </div>
    <div v-else class="card">
      <table class="tbl">
        <thead>
          <tr>
            <th>{{ t('workshop.colDate') }}</th>
            <th>{{ t('workshop.typeLabel') }}</th>
            <th>{{ t('workshop.colMethod') }}</th>
            <th class="right">{{ t('workshop.amountLabel') }}</th>
            <th>{{ t('workshop.colStatus') }}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.id">
            <td>{{ fmtDate(r.received_on) }}</td>
            <td>
              {{
                r.type === 'order_payment'
                  ? t('workshop.incomeOrderPayment')
                  : t('workshop.incomeOther')
              }}
            </td>
            <td>{{ t(`paymentMethod.${r.method}`) }}</td>
            <td class="amt">{{ fmtTiyin(r.amount_tiyin) }}</td>
            <td>
              <StatusBadge
                :tone="r.status === 'recorded' ? 'ok' : 'bad'"
                :label="
                  r.status === 'recorded' ? t('workshop.statusActive') : t('workshop.statusVoided')
                "
              />
            </td>
            <td>
              <button
                v-if="canMutate && r.status === 'recorded'"
                class="btn btn-ghost btn-sm"
                type="button"
                @click="voidId = r.id"
              >
                {{ t('workshop.voidAction') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <AppModal v-model:open="formOpen" :title="t('workshop.incomeTitle')">
      <div class="field">
        <label>{{ t('workshop.typeLabel') }}</label>
        <select v-model="form.type">
          <option value="order_payment">{{ t('workshop.incomeOrderPayment') }}</option>
          <option value="other">{{ t('workshop.incomeOther') }}</option>
        </select>
      </div>
      <div v-if="form.type === 'order_payment'" class="field">
        <label>{{ t('workshop.orderLabel') }}</label>
        <select v-model="form.order_id">
          <option value="">{{ t('workshop.pickOrder') }}</option>
          <option v-for="o in orders" :key="o.id" :value="o.id">
            {{ o.order_number }} · {{ o.contact_name }} · {{ fmtTiyin(o.total_tiyin) }}
          </option>
        </select>
      </div>
      <FormField v-model.number="form.amount" type="number" :label="t('workshop.amountLabel')" />
      <div class="field">
        <label>{{ t('workshop.methodLabel') }}</label>
        <select v-model="form.method">
          <option value="cash">{{ t('paymentMethod.cash') }}</option>
          <option value="bank_transfer">{{ t('paymentMethod.bank_transfer') }}</option>
          <option value="other">{{ t('paymentMethod.other') }}</option>
        </select>
      </div>
      <FormField v-model="form.received_on" type="date" :label="t('workshop.dateLabel')" />
      <FormField v-model="form.note" :label="t('workshop.noteLabel')" />
      <p v-if="!branchesStore.byId.has(auth.branchScope ?? '')" class="hint">
        {{ auth.branchScope ? '' : t('workshop.branchScopeAll') }}
      </p>
      <template #footer>
        <button class="btn btn-outline" type="button" @click="formOpen = false">
          {{ t('common.cancel') }}
        </button>
        <button
          class="btn btn-acc"
          type="button"
          :disabled="saving || form.amount <= 0"
          @click="save"
        >
          {{ t('common.save') }}
        </button>
      </template>
    </AppModal>

    <ConfirmDialog
      :open="voidId !== null"
      :title="t('workshop.voidTitle')"
      :message="t('workshop.voidReason')"
      :ok-text="t('workshop.voidAction')"
      :reason-label="t('workshop.voidReason')"
      reason
      danger
      @update:open="(v) => !v && (voidId = null)"
      @confirm="doVoid"
    />
  </div>
</template>
