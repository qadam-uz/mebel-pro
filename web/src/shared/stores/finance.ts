import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api, apiTraceId, withQuery } from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'

export type IncomeType = 'order_payment' | 'other'
export type MoneyMethod = 'cash' | 'bank_transfer' | 'other'
export type LedgerStatus = 'recorded' | 'voided'
export type ExpenseCategory =
  | 'rent'
  | 'utilities'
  | 'raw_materials'
  | 'supplies'
  | 'transport'
  | 'equipment'
  | 'marketing'
  | 'taxes_and_fees'
  | 'salary'
  | 'other'

export interface Income {
  id: string
  workshop_id: string
  branch_id: string | null
  type: IncomeType
  order_id: string | null
  amount_tiyin: number
  method: MoneyMethod
  received_on: string
  note: string | null
  receipt_file_id: string | null
  status: LedgerStatus
  voided_reason: string | null
  recorded_by_user_id: string
  voided_by_user_id: string | null
  voided_at: string | null
  created_at: string
  updated_at: string
}

export interface Expense {
  id: string
  workshop_id: string
  branch_id: string | null
  category: ExpenseCategory
  amount_tiyin: number
  incurred_on: string
  description: string
  vendor: string | null
  receipt_file_id: string | null
  status: LedgerStatus
  voided_reason: string | null
  recorded_by_user_id: string
  voided_by_user_id: string | null
  voided_at: string | null
  created_at: string
  updated_at: string
}

export interface FinanceBranchSummary {
  branch_id: string | null
  income_tiyin: number
  expense_tiyin: number
  net_tiyin: number
}

export interface FinanceSummary {
  date_from: string
  date_to: string
  income_tiyin: number
  expense_tiyin: number
  net_tiyin: number
  income_by_type: Record<IncomeType, number>
  expense_by_category: Record<ExpenseCategory, number>
  salary_expense_tiyin: number
  branches: FinanceBranchSummary[]
}

export interface WorkerProductionRow {
  user_id: string
  full_name: string
  panels_cut: number
  cut_count: number
  orders_banded: number
  edge_length_by_material: Record<string, number>
}

export interface WorkerProduction {
  date_from: string
  date_to: string
  rows: WorkerProductionRow[]
}

export const useFinanceStore = defineStore('finance', () => {
  const summary = ref<FinanceSummary | null>(null)
  const incomes = ref<Income[]>([])
  const expenses = ref<Expense[]>([])
  const production = ref<WorkerProduction | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const traceId = ref<string | null>(null)

  function capture(errorValue: unknown, fallback: string) {
    error.value = fallback
    traceId.value = apiTraceId(errorValue)
  }

  async function loadSummary(filters: {
    date_from?: string
    date_to?: string
    branch_id?: string | null
  }) {
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      summary.value = await api.get<FinanceSummary>(
        withQuery('/workshop/finance/summary', filters),
        authInit(),
      )
    } catch (errorValue) {
      capture(errorValue, 'finance_summary_failed')
    } finally {
      loading.value = false
    }
  }

  async function loadIncome(filters: {
    date_from?: string
    date_to?: string
    branch_id?: string | null
    type?: IncomeType | null
    method?: MoneyMethod | null
    status?: LedgerStatus | null
    min_amount_tiyin?: string | null
    max_amount_tiyin?: string | null
  }) {
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      incomes.value = await api.get<Income[]>(
        withQuery('/workshop/finance/income', filters),
        authInit(),
      )
    } catch (errorValue) {
      capture(errorValue, 'income_load_failed')
    } finally {
      loading.value = false
    }
  }

  async function createIncome(payload: unknown) {
    const created = await api.post<Income>('/workshop/finance/income', payload, authInit())
    incomes.value = [created, ...incomes.value]
    return created
  }

  async function voidIncome(id: string, reason: string) {
    const updated = await api.post<Income>(
      `/workshop/finance/income/${id}/void`,
      { reason },
      authInit(),
    )
    incomes.value = incomes.value.map((row) => (row.id === id ? updated : row))
    return updated
  }

  async function loadExpenses(filters: {
    date_from?: string
    date_to?: string
    branch_id?: string | null
    category?: ExpenseCategory | null
    status?: LedgerStatus | null
    min_amount_tiyin?: string | null
    max_amount_tiyin?: string | null
  }) {
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      expenses.value = await api.get<Expense[]>(
        withQuery('/workshop/finance/expenses', filters),
        authInit(),
      )
    } catch (errorValue) {
      capture(errorValue, 'expenses_load_failed')
    } finally {
      loading.value = false
    }
  }

  async function createExpense(payload: unknown) {
    const created = await api.post<Expense>('/workshop/finance/expenses', payload, authInit())
    expenses.value = [created, ...expenses.value]
    return created
  }

  async function voidExpense(id: string, reason: string) {
    const updated = await api.post<Expense>(
      `/workshop/finance/expenses/${id}/void`,
      { reason },
      authInit(),
    )
    expenses.value = expenses.value.map((row) => (row.id === id ? updated : row))
    return updated
  }

  async function loadProduction(filters: {
    date_from?: string
    date_to?: string
    branch_id?: string | null
  }) {
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      production.value = await api.get<WorkerProduction>(
        withQuery('/workshop/finance/production', filters),
        authInit(),
      )
    } catch (errorValue) {
      capture(errorValue, 'production_load_failed')
    } finally {
      loading.value = false
    }
  }

  return {
    summary,
    incomes,
    expenses,
    production,
    loading,
    error,
    traceId,
    loadSummary,
    loadIncome,
    createIncome,
    voidIncome,
    loadExpenses,
    createExpense,
    voidExpense,
    loadProduction,
  }
})
