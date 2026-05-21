// Client-app DTOs mirroring the backend schemas in backend/app/schemas/{cutting,orders,catalog}.py.
// Kept local to the client app — only the cutting + order flows use them.

export type MaterialSource = 'shop' | 'own'
export type EdgeThickness = 0.4 | 2.0 | null

// GET /c/materials — active platform sheet materials for the picker.
export interface Material {
  id: string
  kind: string
  type: string | null
  name: string
  thickness_mm: number
  color: string
  decor_code: string | null
  sheet_length_mm: number | null
  sheet_width_mm: number | null
  grain_direction: boolean | null
  image_file_id: string | null
  status: string
  created_at: string
  updated_at: string
}

// A part line as the client edits it (PUT /c/cutting/{id} body item).
export interface PartIn {
  part_ref?: string
  material_id: string
  material_source: MaterialSource
  length_mm: number
  width_mm: number
  quantity: number
  edge_top_mm: EdgeThickness
  edge_bottom_mm: EdgeThickness
  edge_left_mm: EdgeThickness
  edge_right_mm: EdgeThickness
}

// One stored snapshot row on a draft (GET /c/cutting/{id}.parts_snapshot).
export interface PartSnapshot {
  part_ref: string
  material_id: string
  material_source: MaterialSource
  length_mm: number
  width_mm: number
  quantity: number
  edge_top_mm: number | null
  edge_bottom_mm: number | null
  edge_left_mm: number | null
  edge_right_mm: number | null
}

export interface Draft {
  id: string
  client_id: string
  parts_snapshot: PartSnapshot[]
  chosen_result_id: string | null
  created_at: string
  updated_at: string
}

export interface Placement {
  part_ref: string
  part_quantity_index: number
  x_mm: number
  y_mm: number
  length_mm: number
  width_mm: number
  rotated: boolean
}

export interface Sheet {
  id: string
  material_id: string
  sheet_index: number
  waste_area_mm2: number
  placements: Placement[]
}

export type CuttingResultStatus = 'candidate' | 'confirmed' | 'invalidated'

export interface CuttingResult {
  id: string
  draft_id: string | null
  algorithm_name: string
  algorithm_version: string
  status: CuttingResultStatus
  kerf_mm: number
  edge_trim_mm: number
  sheets_used_by_material: Record<string, number>
  waste_percentage: number
  total_cut_length_mm: number
  total_edge_length_mm: number
  edge_length_by_thickness: Record<string, number>
  order_id: string | null
  created_at: string
  confirmed_at: string | null
  invalidated_at: string | null
  sheets: Sheet[]
}

export interface OptimiseResult {
  draft_id: string
  chosen_result_id: string | null
  results: CuttingResult[]
}

export interface BranchAvailability {
  branch_id: string
  name: string
}

export interface BranchesIndicator {
  mode: 'branches' | 'any' | 'none'
  branches: BranchAvailability[]
  uncovered_material_ids: string[]
}

// --- orders ---------------------------------------------------------------

export type OrderStatus =
  | 'new'
  | 'confirmed'
  | 'cutting'
  | 'edge_banding'
  | 'ready'
  | 'completed'
  | 'cancelled'

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

export interface OrderList {
  orders: OrderCard[]
}

export interface OrderDetail {
  id: string
  order_number: string
  branch_id: string
  status: OrderStatus
  cutting_result_id: string
  note_client: string | null
  contact_name: string
  contact_phone: string
  created_at: string
  confirmed_at: string | null
  completed_at: string | null
  cancelled_at: string | null
  price: PriceBreakdown
  items: OrderItem[]
  timeline: TimelineEvent[]
  settlement: Settlement | null
  cancellation_reason: string | null
}

export interface PlaceOrderIn {
  draft_id: string
  branch_id: string
  contact_name: string
  contact_phone: string
  note_client?: string | null
}

export type OrderScope = 'all' | 'active' | 'completed' | 'cancelled'
