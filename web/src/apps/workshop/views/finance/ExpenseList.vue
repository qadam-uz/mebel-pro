<script setup lang="ts">
// Expense list + form + void. Supports a salary prefill (?expense=salary) sent
// from the production report's "record salary expense" shortcut.
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { AppModal, ErrorState, FormField, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtDate, fmtTiyin, sumToTiyin } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopAuth } from '../../store'
import * as api from '../../api'
import type { Expense, ExpenseCategory } from '../../api/types'
import ConfirmDialog from '../../components/ConfirmDialog.vue'

defineProps<{ canMutate: boolean }>()
const route = useRoute()
const router = useRouter()
const toast = useToast()
const auth = useWorkshopAuth()

const CATEGORIES: ExpenseCategory[] = [
  'rent',
  'utilities',
  'raw_materials',
  'supplies',
  'transport',
  'equipment',
  'marketing',
  'taxes_and_fees',
  'salary',
  'other',
]

const loading = ref(true)
const error = ref<ApiError | null>(null)
const rows = ref<Expense[]>([])

const formOpen = ref(false)
const saving = ref(false)
const form = ref<{
  category: ExpenseCategory
  amount: number
  incurred_on: string
  description: string
  vendor: string
}>({
  category: 'rent',
  amount: 0,
  incurred_on: new Date().toISOString().slice(0, 10),
  description: '',
  vendor: '',
})

const voidId = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    rows.value = await api.listExpenses({ branchId: auth.branchScope })
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

function openForm(prefill?: { category?: ExpenseCategory; description?: string }) {
  form.value = {
    category: prefill?.category ?? 'rent',
    amount: 0,
    incurred_on: new Date().toISOString().slice(0, 10),
    description: prefill?.description ?? '',
    vendor: '',
  }
  formOpen.value = true
}

async function save() {
  saving.value = true
  try {
    await api.recordExpense({
      category: form.value.category,
      amount_tiyin: sumToTiyin(form.value.amount),
      incurred_on: form.value.incurred_on,
      description: form.value.description.trim(),
      branch_id: auth.branchScope,
      vendor: form.value.vendor.trim() || null,
    })
    toast.ok(t('workshop.expenseRecorded'))
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
    await api.voidExpense(voidId.value, reason)
    toast.ok(t('workshop.voided'))
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  }
}

function maybePrefill() {
  if (route.query.expense === 'salary') {
    openForm({ category: 'salary', description: String(route.query.worker ?? '') })
    router.replace({ query: {} })
  }
}

watch(() => auth.branchScope, load)
onMounted(async () => {
  await load()
  maybePrefill()
})
</script>

<template>
  <div style="margin-top: 16px">
    <div class="page-head" style="margin-bottom: 12px">
      <div />
      <div class="tools">
        <button v-if="canMutate" class="btn btn-acc btn-sm" type="button" @click="openForm()">
          {{ t('workshop.addExpense') }}
        </button>
      </div>
    </div>

    <ErrorState v-if="error" :error="error" :retry="load" />
    <div v-else-if="loading" class="card">
      <div class="card-b"><div class="sk sk-line" style="width: 60%" /></div>
    </div>
    <div v-else-if="rows.length === 0" class="st-empty">
      <div class="ic">∅</div>
      <h3>{{ t('workshop.expenseEmpty') }}</h3>
    </div>
    <div v-else class="card">
      <table class="tbl">
        <thead>
          <tr>
            <th>{{ t('workshop.colDate') }}</th>
            <th>{{ t('workshop.colCategory') }}</th>
            <th>{{ t('workshop.descriptionLabel') }}</th>
            <th class="right">{{ t('workshop.amountLabel') }}</th>
            <th>{{ t('workshop.colStatus') }}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.id">
            <td>{{ fmtDate(r.incurred_on) }}</td>
            <td>{{ t(`expenseCategory.${r.category}`) }}</td>
            <td class="nm">{{ r.description }}</td>
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

    <AppModal v-model:open="formOpen" :title="t('workshop.expenseTitle')">
      <div class="field">
        <label>{{ t('workshop.categoryLabel') }}</label>
        <select v-model="form.category">
          <option v-for="c in CATEGORIES" :key="c" :value="c">
            {{ t(`expenseCategory.${c}`) }}
          </option>
        </select>
      </div>
      <FormField v-model.number="form.amount" type="number" :label="t('workshop.amountLabel')" />
      <FormField v-model="form.incurred_on" type="date" :label="t('workshop.dateLabel')" />
      <FormField v-model="form.description" :label="t('workshop.descriptionLabel')" required />
      <FormField v-model="form.vendor" :label="t('workshop.vendorLabel')" />
      <template #footer>
        <button class="btn btn-outline" type="button" @click="formOpen = false">
          {{ t('common.cancel') }}
        </button>
        <button
          class="btn btn-acc"
          type="button"
          :disabled="saving || form.amount <= 0 || !form.description.trim()"
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
