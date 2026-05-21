// Workshop-app API surface — thin wrappers over the /workshop/* endpoints.
// Screens call these; the shared api client handles auth/refresh/errors.

import { api } from '@/shared/api'
import type { Permission } from '@/shared/types'
import type {
  BranchCreate,
  BranchMaterial,
  BranchOut,
  BranchPricing,
  BranchStatusChange,
  BranchSummary,
  CreatedSecret,
  CuttingModel,
  Expense,
  ExpenseCategory,
  FinanceReport,
  Income,
  IncomeType,
  Material,
  MaterialKind,
  OrderListOut,
  PaymentMethod,
  StockItem,
  StockTransaction,
  Supplier,
  TransitionOut,
  WorkerProductionRow,
  WorkshopBoard,
  WorkshopOrderDetail,
  WorkshopProfile,
  WorkshopUser,
  WorkshopUserDetail,
} from './types'

// --- orders ----------------------------------------------------------------

export function listOrders(params: {
  branchId?: string | null
  status?: string
  search?: string
}): Promise<WorkshopBoard> {
  const qs = new URLSearchParams()
  if (params.branchId) qs.set('branch_id', params.branchId)
  if (params.status) qs.set('status', params.status)
  if (params.search) qs.set('search', params.search)
  const q = qs.toString()
  return api.get<WorkshopBoard>(`/workshop/orders${q ? `?${q}` : ''}`)
}

export function getOrder(id: string): Promise<WorkshopOrderDetail> {
  return api.get<WorkshopOrderDetail>(`/workshop/orders/${id}`)
}

export function approveOrder(id: string, expectedVersion: number): Promise<TransitionOut> {
  return api.post<TransitionOut>(`/workshop/orders/${id}/approve`, {
    expected_version: expectedVersion,
  })
}

export function assignOrder(
  id: string,
  body: { cutter_user_id: string; edger_user_id?: string | null; expected_version: number },
): Promise<TransitionOut> {
  return api.post<TransitionOut>(`/workshop/orders/${id}/assign`, body)
}

export function cuttingDone(
  id: string,
  body: { on_behalf_user_id?: string | null; expected_version: number },
): Promise<TransitionOut> {
  return api.post<TransitionOut>(`/workshop/orders/${id}/cutting-done`, body)
}

export function bandingDone(
  id: string,
  body: { on_behalf_user_id?: string | null; expected_version: number },
): Promise<TransitionOut> {
  return api.post<TransitionOut>(`/workshop/orders/${id}/banding-done`, body)
}

export function markCollected(id: string, expectedVersion: number): Promise<TransitionOut> {
  return api.post<TransitionOut>(`/workshop/orders/${id}/mark-collected`, {
    expected_version: expectedVersion,
  })
}

export function revertOrder(
  id: string,
  body: { reason: string; expected_version: number },
): Promise<TransitionOut> {
  return api.post<TransitionOut>(`/workshop/orders/${id}/revert`, body)
}

export function cancelOrder(
  id: string,
  body: { reason: string; expected_version: number },
): Promise<TransitionOut> {
  return api.post<TransitionOut>(`/workshop/orders/${id}/cancel`, body)
}

export function applyDiscount(
  id: string,
  body: { discount_tiyin: number; reason: string; expected_version: number },
): Promise<TransitionOut> {
  return api.post<TransitionOut>(`/workshop/orders/${id}/apply-discount`, body)
}

export function myCutting(): Promise<OrderListOut> {
  return api.get<OrderListOut>('/workshop/cutting')
}

export function myBanding(): Promise<OrderListOut> {
  return api.get<OrderListOut>('/workshop/banding')
}

// --- branches --------------------------------------------------------------

export function listBranches(): Promise<BranchSummary[]> {
  return api.get<BranchSummary[]>('/workshop/branches')
}

export function getBranch(id: string): Promise<BranchSummary> {
  return api.get<BranchSummary>(`/workshop/branches/${id}`)
}

export function createBranch(body: BranchCreate): Promise<BranchOut> {
  return api.post<BranchOut>('/workshop/branches', body)
}

export function editBranch(id: string, body: Partial<BranchCreate>): Promise<BranchOut> {
  return api.patch<BranchOut>(`/workshop/branches/${id}`, body)
}

export function changeBranchStatus(id: string, body: BranchStatusChange): Promise<BranchOut> {
  return api.post<BranchOut>(`/workshop/branches/${id}/status`, body)
}

// --- catalog ---------------------------------------------------------------

export function listMaterials(kind?: MaterialKind): Promise<Material[]> {
  return api.get<Material[]>(`/workshop/materials${kind ? `?kind=${kind}` : ''}`)
}

export function listBranchMaterials(branchId: string): Promise<BranchMaterial[]> {
  return api.get<BranchMaterial[]>(`/workshop/branches/${branchId}/materials`)
}

export function addBranchMaterial(
  branchId: string,
  body: { material_id: string; price_tiyin: number; min_stock: number },
): Promise<BranchMaterial> {
  return api.post<BranchMaterial>(`/workshop/branches/${branchId}/materials`, body)
}

export function editBranchMaterial(
  branchId: string,
  branchMaterialId: string,
  body: { price_tiyin?: number; min_stock?: number },
): Promise<BranchMaterial> {
  return api.patch<BranchMaterial>(
    `/workshop/branches/${branchId}/materials/${branchMaterialId}`,
    body,
  )
}

export function setBranchMaterialStatus(
  branchId: string,
  branchMaterialId: string,
  active: boolean,
): Promise<BranchMaterial> {
  return api.post<BranchMaterial>(
    `/workshop/branches/${branchId}/materials/${branchMaterialId}/${active ? 'activate' : 'deactivate'}`,
  )
}

export function getPricing(branchId: string): Promise<BranchPricing> {
  return api.get<BranchPricing>(`/workshop/branches/${branchId}/pricing`)
}

export function setPricing(
  branchId: string,
  body: {
    cutting_model: CuttingModel
    cutting_rate_tiyin: number
    edge_banding_rates: Record<string, number>
  },
): Promise<BranchPricing> {
  return api.put<BranchPricing>(`/workshop/branches/${branchId}/pricing`, body)
}

// --- inventory -------------------------------------------------------------

export function listStock(branchId: string): Promise<StockItem[]> {
  return api.get<StockItem[]>(`/workshop/branches/${branchId}/stock`)
}

export function listStockTransactions(
  branchId: string,
  params: { stock_item_id?: string; limit?: number; offset?: number } = {},
): Promise<StockTransaction[]> {
  const qs = new URLSearchParams()
  if (params.stock_item_id) qs.set('stock_item_id', params.stock_item_id)
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.offset != null) qs.set('offset', String(params.offset))
  const q = qs.toString()
  return api.get<StockTransaction[]>(
    `/workshop/branches/${branchId}/stock/transactions${q ? `?${q}` : ''}`,
  )
}

export function stockIn(
  branchId: string,
  body: { material_id: string; quantity: number; supplier_id: string; note?: string | null },
): Promise<StockTransaction> {
  return api.post<StockTransaction>(`/workshop/branches/${branchId}/stock/stock-in`, body)
}

export function stockAdjust(
  branchId: string,
  body: { material_id: string; delta: number; note: string },
): Promise<StockTransaction> {
  return api.post<StockTransaction>(`/workshop/branches/${branchId}/stock/adjust`, body)
}

export function setMinStock(
  branchId: string,
  materialId: string,
  minStock: number,
): Promise<StockItem> {
  return api.patch<StockItem>(`/workshop/branches/${branchId}/stock/${materialId}/min-stock`, {
    min_stock: minStock,
  })
}

export function listSuppliers(activeOnly = false): Promise<Supplier[]> {
  return api.get<Supplier[]>(`/workshop/suppliers${activeOnly ? '?active_only=true' : ''}`)
}

export function createSupplier(body: {
  name: string
  phone?: string | null
  note?: string | null
}): Promise<Supplier> {
  return api.post<Supplier>('/workshop/suppliers', body)
}

export function editSupplier(
  id: string,
  body: {
    name?: string
    phone?: string | null
    phone_set?: boolean
    note?: string | null
    note_set?: boolean
  },
): Promise<Supplier> {
  return api.patch<Supplier>(`/workshop/suppliers/${id}`, body)
}

export function setSupplierStatus(id: string, active: boolean): Promise<Supplier> {
  return api.post<Supplier>(`/workshop/suppliers/${id}/${active ? 'activate' : 'deactivate'}`)
}

// --- finance ---------------------------------------------------------------

export function listIncome(params: {
  branchId?: string | null
  type?: IncomeType
  status?: string
}): Promise<Income[]> {
  const qs = new URLSearchParams()
  if (params.branchId) qs.set('branch_id', params.branchId)
  if (params.type) qs.set('type', params.type)
  if (params.status) qs.set('status', params.status)
  const q = qs.toString()
  return api.get<Income[]>(`/workshop/finance/income${q ? `?${q}` : ''}`)
}

export function recordIncome(body: {
  type: IncomeType
  order_id?: string | null
  amount_tiyin: number
  method: PaymentMethod
  received_on: string
  branch_id?: string | null
  note?: string | null
}): Promise<Income> {
  return api.post<Income>('/workshop/finance/income', body)
}

export function editIncome(
  id: string,
  body: {
    amount_tiyin?: number
    method?: PaymentMethod
    received_on?: string
    note?: string | null
    note_set?: boolean
  },
): Promise<Income> {
  return api.patch<Income>(`/workshop/finance/income/${id}`, body)
}

export function voidIncome(id: string, reason: string): Promise<Income> {
  return api.post<Income>(`/workshop/finance/income/${id}/void`, { reason })
}

export function listExpenses(params: {
  branchId?: string | null
  category?: ExpenseCategory
  status?: string
}): Promise<Expense[]> {
  const qs = new URLSearchParams()
  if (params.branchId) qs.set('branch_id', params.branchId)
  if (params.category) qs.set('category', params.category)
  if (params.status) qs.set('status', params.status)
  const q = qs.toString()
  return api.get<Expense[]>(`/workshop/finance/expenses${q ? `?${q}` : ''}`)
}

export function recordExpense(body: {
  category: ExpenseCategory
  amount_tiyin: number
  incurred_on: string
  description: string
  branch_id?: string | null
  vendor?: string | null
}): Promise<Expense> {
  return api.post<Expense>('/workshop/finance/expenses', body)
}

export function editExpense(
  id: string,
  body: {
    category?: ExpenseCategory
    amount_tiyin?: number
    incurred_on?: string
    description?: string
    vendor?: string | null
    vendor_set?: boolean
  },
): Promise<Expense> {
  return api.patch<Expense>(`/workshop/finance/expenses/${id}`, body)
}

export function voidExpense(id: string, reason: string): Promise<Expense> {
  return api.post<Expense>(`/workshop/finance/expenses/${id}/void`, { reason })
}

export function workerProduction(params: {
  period_start: string
  period_end: string
  branchIds?: string[]
}): Promise<WorkerProductionRow[]> {
  const qs = new URLSearchParams()
  qs.set('period_start', params.period_start)
  qs.set('period_end', params.period_end)
  for (const id of params.branchIds ?? []) qs.append('branch_id', id)
  return api.get<WorkerProductionRow[]>(`/workshop/finance/production?${qs.toString()}`)
}

export function financeReport(params: {
  period_start: string
  period_end: string
  branchIds?: string[]
}): Promise<FinanceReport> {
  const qs = new URLSearchParams()
  qs.set('period_start', params.period_start)
  qs.set('period_end', params.period_end)
  for (const id of params.branchIds ?? []) qs.append('branch_id', id)
  return api.get<FinanceReport>(`/workshop/finance/report?${qs.toString()}`)
}

// --- users (owner-only) ----------------------------------------------------

export function listUsers(): Promise<WorkshopUser[]> {
  return api.get<WorkshopUser[]>('/workshop/users')
}

export function getUser(id: string): Promise<WorkshopUserDetail> {
  return api.get<WorkshopUserDetail>(`/workshop/users/${id}`)
}

export function createUser(body: {
  full_name: string
  login: string
  phone: string
  home_branch_id?: string | null
  grants: { permission: Permission; branch_id: string }[]
  password?: string | null
}): Promise<CreatedSecret> {
  return api.post<CreatedSecret>('/workshop/users', body)
}

export function editUser(
  id: string,
  body: {
    full_name?: string
    phone?: string
    home_branch_id?: string | null
    home_branch_set?: boolean
  },
): Promise<WorkshopUser> {
  return api.patch<WorkshopUser>(`/workshop/users/${id}`, body)
}

export function setGrants(
  id: string,
  grants: { permission: Permission; branch_id: string }[],
): Promise<WorkshopUserDetail> {
  return api.put<WorkshopUserDetail>(`/workshop/users/${id}/grants`, { grants })
}

export function resetUserPassword(id: string): Promise<CreatedSecret> {
  return api.post<CreatedSecret>(`/workshop/users/${id}/reset-password`)
}

export function blockUser(id: string): Promise<WorkshopUser> {
  return api.post<WorkshopUser>(`/workshop/users/${id}/block`)
}

export function unblockUser(id: string): Promise<WorkshopUser> {
  return api.post<WorkshopUser>(`/workshop/users/${id}/unblock`)
}

// --- settings --------------------------------------------------------------

export function getWorkshopProfile(): Promise<WorkshopProfile> {
  return api.get<WorkshopProfile>('/workshop/settings/profile')
}

export function editWorkshopProfile(body: {
  name?: string
  phone?: string
  address?: string | null
}): Promise<WorkshopProfile> {
  return api.patch<WorkshopProfile>('/workshop/settings/profile', body)
}

export type * from './types'
