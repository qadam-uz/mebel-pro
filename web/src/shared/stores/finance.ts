import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api, captureApiError, withQuery } from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'
import { downloadBlob } from '@/shared/app/downloadBlob'
import type { OrderStatus } from '@/shared/stores/orders'

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

/**
 * The order an order-payment income points at, resolved by the server onto the
 * income row itself. Nothing in the finance views reads an order back through
 * the sales API: that read is permission-gated away from the accountant, and a
 * settled order never returns to the payable-orders picker.
 */
export interface IncomeOrderRef {
  order_id: string
  order_number: string
  contact_name: string
  total_tiyin: number
  recorded_tiyin: number
  balance_tiyin: number
}

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
  // Who handled the money — resolved server-side at read time. "Kim qabul
  // qildi?" is the first question asked of a cash row, and an id cannot answer it.
  recorded_by_name: string | null
  voided_by_user_id: string | null
  voided_at: string | null
  created_at: string
  updated_at: string
  order: IncomeOrderRef | null
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
  supplier_id: string | null
  invoice_id: string | null
  invoice_no: string | null
  receipt_file_id: string | null
  status: LedgerStatus
  voided_reason: string | null
  recorded_by_user_id: string
  // Who handled the money — resolved server-side at read time. "Kim qabul
  // qildi?" is the first question asked of a cash row, and an id cannot answer it.
  recorded_by_name: string | null
  voided_by_user_id: string | null
  voided_at: string | null
  created_at: string
  updated_at: string
}

export interface DebtRow {
  counterparty_id: string
  name: string
  phone: string | null
  inactive: boolean
  balance_tiyin: number
}

export interface DebtList {
  rows: DebtRow[]
  we_owe_total_tiyin: number
  they_owe_total_tiyin: number
}

export interface DebtStatementRow {
  kind: 'delivery' | 'payment' | 'adjustment' | 'order'
  on: string
  at: string
  reference_id: string
  amount_tiyin: number
  balance_after_tiyin: number
  note: string | null
  invoice_no: string | null
  line_count: number | null
  discount_tiyin: number | null
  surcharge_tiyin: number | null
  category: ExpenseCategory | null
  method: MoneyMethod | null
  order_number: string | null
}

export interface DebtStatement {
  counterparty_id: string
  name: string
  phone: string | null
  /** Our side of the reconciliation — the document names both parties. */
  workshop_name: string
  workshop_phone: string | null
  date_from: string | null
  date_to: string | null
  opening_balance_tiyin: number
  /** In-period movements that grew their debt / shrank it (stored convention). */
  period_increase_tiyin: number
  period_decrease_tiyin: number
  closing_balance_tiyin: number
  current_balance_tiyin: number
  rows: DebtStatementRow[]
}

export interface CounterpartyAdjustment {
  id: string
  workshop_id: string
  supplier_id: string | null
  client_id: string | null
  amount_tiyin: number
  adjusted_on: string
  note: string
  status: LedgerStatus
  voided_reason: string | null
  recorded_by_user_id: string
  voided_by_user_id: string | null
  voided_at: string | null
  created_at: string
  updated_at: string
}

/** An order that still owes money — a candidate for an order-payment income. */
export interface PayableOrder {
  order_id: string
  order_number: string
  contact_name: string
  contact_phone: string
  status: OrderStatus
  created_at: string
  total_tiyin: number
  recorded_tiyin: number
  balance_tiyin: number
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
  daily_income: Array<{ day: string; income_tiyin: number }>
}

export interface WorkerProductionRow {
  user_id: string
  full_name: string
  panels_cut: number
  cut_count: number
  orders_banded: number
  edge_length_by_material: Record<string, number>
  edge_lines: WorkerProductionEdgeLine[]
  edge_length_by_thickness: WorkerProductionThicknessLine[]
}

export interface WorkerProductionEdgeLine {
  material_id: string
  material_label: string
  thickness_mm: string | null
  color: string | null
  length_mm: number
}

export interface WorkerProductionThicknessLine {
  thickness_mm: string | null
  length_mm: number
}

export interface WorkerProduction {
  date_from: string
  date_to: string
  rows: WorkerProductionRow[]
}

export type InvoicePaymentStatus = 'unpaid' | 'partial' | 'paid'

/** A supplier faktura the workshop still owes on — the expense form's picker. */
export interface PayableInvoice {
  id: string
  invoice_no: string
  invoice_date: string
  supplier_id: string | null
  supplier_name: string | null
  branch_id: string
  branch_name: string | null
  line_count: number
  total_tiyin: number
  paid_tiyin: number
  outstanding_tiyin: number
  payment_status: InvoicePaymentStatus
}

export const useFinanceStore = defineStore('finance', () => {
  const summary = ref<FinanceSummary | null>(null)
  const incomes = ref<Income[]>([])
  const expenses = ref<Expense[]>([])
  const production = ref<WorkerProduction | null>(null)
  const supplierDebts = ref<DebtList | null>(null)
  const clientDebts = ref<DebtList | null>(null)
  const statement = ref<DebtStatement | null>(null)
  const statementPdfLoading = ref(false)
  const payableInvoices = ref<PayableInvoice[]>([])
  const payableOrders = ref<PayableOrder[]>([])
  const payableOrdersLoading = ref(false)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const traceId = ref<string | null>(null)
  const actionError = ref<string | null>(null)
  const actionTraceId = ref<string | null>(null)

  function capture(errorValue: unknown, fallback: string) {
    const captured = captureApiError(errorValue, fallback)
    error.value = captured.code
    traceId.value = captured.traceId
  }

  function captureAction(errorValue: unknown, fallback: string) {
    const captured = captureApiError(errorValue, fallback)
    actionError.value = captured.code
    actionTraceId.value = captured.traceId
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
    recorded_by_user_id?: string | null
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
    actionError.value = null
    actionTraceId.value = null
    try {
      const created = await api.post<Income>('/workshop/finance/income', payload, authInit())
      incomes.value = [created, ...incomes.value]
      return created
    } catch (errorValue) {
      captureAction(errorValue, 'income_save_failed')
      throw errorValue
    }
  }

  async function updateIncome(id: string, payload: unknown) {
    actionError.value = null
    actionTraceId.value = null
    try {
      const updated = await api.patch<Income>(`/workshop/finance/income/${id}`, payload, authInit())
      incomes.value = incomes.value.map((row) => (row.id === id ? updated : row))
      return updated
    } catch (errorValue) {
      captureAction(errorValue, 'income_save_failed')
      throw errorValue
    }
  }

  async function voidIncome(id: string, reason: string) {
    actionError.value = null
    actionTraceId.value = null
    try {
      const updated = await api.post<Income>(
        `/workshop/finance/income/${id}/void`,
        { reason },
        authInit(),
      )
      incomes.value = incomes.value.map((row) => (row.id === id ? updated : row))
      return updated
    } catch (errorValue) {
      captureAction(errorValue, 'ledger_void_failed')
      throw errorValue
    }
  }

  async function loadExpenses(filters: {
    date_from?: string
    date_to?: string
    branch_id?: string | null
    category?: ExpenseCategory | null
    status?: LedgerStatus | null
    recorded_by_user_id?: string | null
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
    actionError.value = null
    actionTraceId.value = null
    try {
      const created = await api.post<Expense>('/workshop/finance/expenses', payload, authInit())
      expenses.value = [created, ...expenses.value]
      return created
    } catch (errorValue) {
      captureAction(errorValue, 'expense_save_failed')
      throw errorValue
    }
  }

  async function updateExpense(id: string, payload: unknown) {
    actionError.value = null
    actionTraceId.value = null
    try {
      const updated = await api.patch<Expense>(
        `/workshop/finance/expenses/${id}`,
        payload,
        authInit(),
      )
      expenses.value = expenses.value.map((row) => (row.id === id ? updated : row))
      return updated
    } catch (errorValue) {
      captureAction(errorValue, 'expense_save_failed')
      throw errorValue
    }
  }

  async function voidExpense(id: string, reason: string) {
    actionError.value = null
    actionTraceId.value = null
    try {
      const updated = await api.post<Expense>(
        `/workshop/finance/expenses/${id}/void`,
        { reason },
        authInit(),
      )
      expenses.value = expenses.value.map((row) => (row.id === id ? updated : row))
      return updated
    } catch (errorValue) {
      captureAction(errorValue, 'ledger_void_failed')
      throw errorValue
    }
  }

  async function loadSupplierDebts(
    filters: { search?: string; only_with_debt?: boolean; branch_id?: string | null } = {},
  ) {
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      supplierDebts.value = await api.get<DebtList>(
        withQuery('/workshop/finance/debts/suppliers', {
          search: filters.search || undefined,
          only_with_debt: filters.only_with_debt,
          branch_id: filters.branch_id || undefined,
        }),
        authInit(),
      )
    } catch (errorValue) {
      capture(errorValue, 'debts_load_failed')
    } finally {
      loading.value = false
    }
  }

  // Only unpaid and partially paid invoices come back, newest first — the
  // picker offers what can still be paid, never a settled faktura.
  async function loadPayableInvoices(search?: string | null) {
    actionError.value = null
    actionTraceId.value = null
    try {
      payableInvoices.value = await api.get<PayableInvoice[]>(
        withQuery('/workshop/finance/payable-invoices', { search: search || undefined }),
        authInit(),
      )
    } catch (errorValue) {
      captureAction(errorValue, 'payable_invoices_load_failed')
      payableInvoices.value = []
    }
  }

  async function loadClientDebts(
    filters: { search?: string; only_with_debt?: boolean; branch_id?: string | null } = {},
  ) {
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      clientDebts.value = await api.get<DebtList>(
        withQuery('/workshop/finance/debts/clients', {
          search: filters.search || undefined,
          only_with_debt: filters.only_with_debt,
          branch_id: filters.branch_id || undefined,
        }),
        authInit(),
      )
    } catch (errorValue) {
      capture(errorValue, 'debts_load_failed')
    } finally {
      loading.value = false
    }
  }

  async function loadStatement(
    side: 'suppliers' | 'clients',
    counterpartyId: string,
    filters: { date_from?: string | null; date_to?: string | null; branch_id?: string | null } = {},
  ) {
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      statement.value = await api.get<DebtStatement>(
        withQuery(`/workshop/finance/debts/${side}/${counterpartyId}/statement`, {
          date_from: filters.date_from || undefined,
          date_to: filters.date_to || undefined,
          branch_id: filters.branch_id || undefined,
        }),
        authInit(),
      )
    } catch (errorValue) {
      capture(errorValue, 'statement_load_failed')
    } finally {
      loading.value = false
    }
  }

  // The signed document itself, rendered by the server so the file a
  // counterparty keeps is identical whoever generated it.
  async function downloadStatementPdf(
    side: 'suppliers' | 'clients',
    counterpartyId: string,
    filters: { date_from?: string | null; date_to?: string | null; branch_id?: string | null } = {},
    filename = 'akt-sverka.pdf',
  ) {
    statementPdfLoading.value = true
    actionError.value = null
    actionTraceId.value = null
    try {
      await downloadBlob(
        withQuery(`/workshop/finance/debts/${side}/${counterpartyId}/statement.pdf`, {
          date_from: filters.date_from || undefined,
          date_to: filters.date_to || undefined,
          branch_id: filters.branch_id || undefined,
        }),
        filename,
        authInit(),
      )
    } catch (errorValue) {
      captureAction(errorValue, 'statement_pdf_failed')
      throw errorValue
    } finally {
      statementPdfLoading.value = false
    }
  }

  async function createAdjustment(payload: unknown) {
    actionError.value = null
    actionTraceId.value = null
    try {
      return await api.post<CounterpartyAdjustment>(
        '/workshop/finance/debts/adjustments',
        payload,
        authInit(),
      )
    } catch (errorValue) {
      captureAction(errorValue, 'adjustment_save_failed')
      throw errorValue
    }
  }

  async function voidAdjustment(id: string, reason: string) {
    actionError.value = null
    actionTraceId.value = null
    try {
      return await api.post<CounterpartyAdjustment>(
        `/workshop/finance/debts/adjustments/${id}/void`,
        { reason },
        authInit(),
      )
    } catch (errorValue) {
      captureAction(errorValue, 'ledger_void_failed')
      throw errorValue
    }
  }

  // The order picker searches server-side, so answers can land out of order
  // when a slow early query resolves after a fast later one. Only the newest
  // request may write — a stale list under a newer query is a wrong list.
  let payableRequestId = 0

  async function loadPayableOrders(
    filters: { branch_id?: string | null; search?: string | null; limit?: number } = {},
  ) {
    const requestId = ++payableRequestId
    payableOrdersLoading.value = true
    actionError.value = null
    actionTraceId.value = null
    try {
      const rows = await api.get<PayableOrder[]>(
        withQuery('/workshop/finance/payable-orders', {
          branch_id: filters.branch_id || undefined,
          search: filters.search || undefined,
          limit: filters.limit,
        }),
        authInit(),
      )
      if (requestId !== payableRequestId) return
      payableOrders.value = rows
    } catch (errorValue) {
      if (requestId !== payableRequestId) return
      payableOrders.value = []
      captureAction(errorValue, 'payable_orders_load_failed')
    } finally {
      if (requestId === payableRequestId) payableOrdersLoading.value = false
    }
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

  function reset() {
    summary.value = null
    incomes.value = []
    expenses.value = []
    production.value = null
    supplierDebts.value = null
    clientDebts.value = null
    statement.value = null
    payableInvoices.value = []
    payableOrders.value = []
    payableOrdersLoading.value = false
    statementPdfLoading.value = false
    loading.value = false
    error.value = null
    traceId.value = null
    actionError.value = null
    actionTraceId.value = null
  }

  return {
    summary,
    incomes,
    expenses,
    production,
    supplierDebts,
    clientDebts,
    statement,
    statementPdfLoading,
    payableInvoices,
    payableOrders,
    payableOrdersLoading,
    loading,
    error,
    traceId,
    actionError,
    actionTraceId,
    loadSummary,
    loadIncome,
    createIncome,
    updateIncome,
    voidIncome,
    loadExpenses,
    createExpense,
    updateExpense,
    voidExpense,
    loadSupplierDebts,
    loadPayableInvoices,
    loadClientDebts,
    loadStatement,
    downloadStatementPdf,
    createAdjustment,
    voidAdjustment,
    loadPayableOrders,
    loadProduction,
    reset,
  }
})
