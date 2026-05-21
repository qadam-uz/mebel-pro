// Workshop-app DTOs mirroring backend schemas in
// backend/app/schemas/{orders,workshop,catalog,inventory,finance,identity}.py.
// Kept local to the workshop app.

import type { Permission } from '@/shared/types'

export type OrderStatus =
  | 'new'
  | 'confirmed'
  | 'cutting'
  | 'edge_banding'
  | 'ready'
  | 'completed'
  | 'cancelled'

export type MaterialSource = 'shop' | 'own'
export type BranchStatus = 'active' | 'temporarily_closed' | 'inactive'
export type CatalogStatus = 'active' | 'inactive'
export type SupplierStatus = 'active' | 'inactive'
export type CuttingModel = 'per_sheet' | 'per_cut'
export type MaterialKind = 'sheet' | 'edge'
export type MaterialType = 'dsp' | 'mdf' | 'plywood' | 'natural_wood' | 'other'
export type IncomeType = 'order_payment' | 'other'
export type PaymentMethod = 'cash' | 'bank_transfer' | 'other'
export type LedgerStatus = 'recorded' | 'voided'
export type UserStatus = 'active' | 'blocked'
export type StockTransactionType = 'stock_in' | 'consume' | 'restore' | 'adjust'
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

// --- orders ----------------------------------------------------------------

export interface PriceBreakdown {
  subtotal_cutting_tiyin: number
  subtotal_materials_tiyin: number
  subtotal_edge_banding_tiyin: number
  discount_tiyin: number
  total_tiyin: number
  currency: string
}

export interface Settlement {
  total_tiyin: number
  recorded_tiyin: number
  balance_tiyin: number
}

export interface TimelineEvent {
  from_status: OrderStatus | null
  to_status: OrderStatus
  actor_type: string
  reason: string | null
  metadata: Record<string, unknown> | null
  changed_at: string
}

export interface OrderItem {
  id: string
  material_id: string
  material_source: MaterialSource
  material_snapshot: Record<string, unknown>
  part_ref: string
  length_mm: number
  width_mm: number
  quantity: number
  edge_top_mm: number | null
  edge_bottom_mm: number | null
  edge_left_mm: number | null
  edge_right_mm: number | null
  unit_cutting_price_tiyin: number
  unit_material_price_tiyin: number
  edge_cost_tiyin: number
  line_total_tiyin: number
}

export interface OrderCard {
  id: string
  order_number: string
  branch_id: string
  status: OrderStatus
  total_tiyin: number
  item_count: number
  created_at: string
  contact_name: string | null
  contact_phone: string | null
  assigned_cutter_user_id: string | null
  assigned_edger_user_id: string | null
}

export interface WorkshopBoard {
  counts: Record<string, number>
  orders: OrderCard[]
}

export interface OrderListOut {
  orders: OrderCard[]
}

export interface ProductionStamps {
  assigned_cutter_user_id: string | null
  assigned_edger_user_id: string | null
  cutter_user_id: string | null
  cut_completed_at: string | null
  sheets_used_snapshot: number | null
  cut_count_snapshot: number | null
  edger_user_id: string | null
  edge_completed_at: string | null
  edge_length_snapshot: Record<string, unknown> | null
  picked_up_at: string | null
}

export interface WorkshopOrderDetail {
  id: string
  order_number: string
  branch_id: string
  workshop_id: string
  status: OrderStatus
  version: number
  cutting_result_id: string
  note_client: string | null
  note_workshop: string | null
  contact_name: string
  contact_phone: string
  created_at: string
  confirmed_at: string | null
  completed_at: string | null
  cancelled_at: string | null
  price: PriceBreakdown
  items: OrderItem[]
  timeline: TimelineEvent[]
  stamps: ProductionStamps
  available_actions: string[]
  settlement: Settlement | null
  stock_warnings: Array<Record<string, unknown>>
  cancellation_reason: string | null
}

export interface TransitionOut {
  id: string
  status: OrderStatus
  version: number
  stock_warnings: Array<Record<string, unknown>>
}

// --- branches --------------------------------------------------------------

export interface BranchOut {
  id: string
  workshop_id: string
  name: string
  address: string
  phone: string
  latitude: number | null
  longitude: number | null
  working_hours: Record<string, unknown>
  status: BranchStatus
  closed_reason: string | null
  created_at: string
  updated_at: string
}

export interface BranchSummary extends BranchOut {
  materials_count: number
  low_stock_count: number
  active_orders_count: number
}

export interface BranchCreate {
  name: string
  address: string
  phone: string
  latitude?: number | null
  longitude?: number | null
  working_hours?: Record<string, unknown>
}

export interface BranchStatusChange {
  status: BranchStatus
  closed_reason?: string | null
}

// --- catalog ---------------------------------------------------------------

export interface Material {
  id: string
  kind: MaterialKind
  type: MaterialType | null
  name: string
  thickness_mm: number
  color: string
  decor_code: string | null
  sheet_length_mm: number | null
  sheet_width_mm: number | null
  grain_direction: boolean | null
  image_file_id: string | null
  status: CatalogStatus
  created_at: string
  updated_at: string
}

export interface BranchMaterial {
  id: string
  branch_id: string
  material_id: string
  price_tiyin: number
  min_stock: number
  status: CatalogStatus
  created_at: string
  updated_at: string
}

export interface BranchPricing {
  branch_id: string
  cutting_model: CuttingModel | null
  cutting_rate_tiyin: number
  edge_banding_rates: Record<string, number>
  updated_at: string
  updated_by_user_id: string | null
}

// --- inventory -------------------------------------------------------------

export interface StockItem {
  id: string
  branch_id: string
  material_id: string
  on_hand: number
  min_stock: number
  updated_at: string
}

export interface StockTransaction {
  id: string
  stock_item_id: string
  type: StockTransactionType
  quantity: number
  balance_after: number
  order_id: string | null
  supplier_id: string | null
  actor_user_id: string | null
  note: string | null
  created_at: string
}

export interface Supplier {
  id: string
  workshop_id: string
  name: string
  phone: string | null
  note: string | null
  status: SupplierStatus
  created_by_user_id: string
  created_at: string
  updated_at: string
}

// --- finance ---------------------------------------------------------------

export interface Income {
  id: string
  workshop_id: string
  branch_id: string | null
  type: IncomeType
  order_id: string | null
  amount_tiyin: number
  method: PaymentMethod
  received_on: string
  note: string | null
  receipt_file_id: string | null
  status: LedgerStatus
  voided_reason: string | null
  recorded_by_user_id: string
  created_at: string
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
  created_at: string
}

export interface WorkerProductionRow {
  user_id: string
  sheets_cut: number
  cut_count: number
  orders_banded: number
  metres_by_thickness: Record<string, number>
}

export interface FinanceReport {
  period_start: string
  period_end: string
  income_total_tiyin: number
  income_order_payment_tiyin: number
  income_other_tiyin: number
  expense_total_tiyin: number
  expenses_by_category: Record<string, number>
  net_tiyin: number
  per_branch: Record<string, Record<string, number>>
}

// --- workshop / users / profile --------------------------------------------

export interface WorkshopProfile {
  id: string
  name: string
  phone: string
  address: string | null
  logo_file_id: string | null
  owner_user_id: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface GrantIn {
  permission: Permission
  branch_id: string
}

export interface WorkshopUser {
  id: string
  workshop_id: string
  login: string
  full_name: string
  phone: string
  is_owner: boolean
  home_branch_id: string | null
  status: UserStatus
  force_password_change: boolean
  last_login_at: string | null
  created_at: string
}

export interface WorkshopUserDetail extends WorkshopUser {
  grants: GrantIn[]
}

export interface CreatedSecret {
  id: string
  login: string
  temp_password: string
}
