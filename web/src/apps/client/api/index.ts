// Client-app API surface — thin wrappers over the /c/* endpoints. Screens call
// these; the shared api client handles auth/refresh/errors.

import { api } from '@/shared/api'
import type {
  BranchesIndicator,
  Draft,
  Material,
  OptimiseResult,
  OrderDetail,
  OrderList,
  OrderScope,
  PartIn,
  PlaceOrderIn,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

// --- cutting --------------------------------------------------------------

export function listMaterials(): Promise<Material[]> {
  return api.get<Material[]>('/c/materials')
}

export function createDraft(): Promise<Draft> {
  return api.post<Draft>('/c/cutting')
}

export function listDrafts(): Promise<Draft[]> {
  return api.get<Draft[]>('/c/cutting')
}

export function getDraft(id: string): Promise<Draft> {
  return api.get<Draft>(`/c/cutting/${id}`)
}

export function replaceParts(id: string, parts: PartIn[]): Promise<Draft> {
  return api.put<Draft>(`/c/cutting/${id}`, { parts })
}

export function deleteDraft(id: string): Promise<void> {
  return api.del<void>(`/c/cutting/${id}`)
}

export function optimise(id: string): Promise<OptimiseResult> {
  return api.post<OptimiseResult>(`/c/cutting/${id}/optimise`)
}

export function chooseResult(id: string, resultId: string): Promise<Draft> {
  return api.post<Draft>(`/c/cutting/${id}/choose/${resultId}`)
}

export function draftBranches(id: string): Promise<BranchesIndicator> {
  return api.get<BranchesIndicator>(`/c/cutting/${id}/branches`)
}

// PDF is a binary download — open it in a new tab through the same-origin /api
// path so the bearer cookie/proxy applies. We can't attach the bearer header to
// a window.open, so we fetch with auth and open a blob URL.
export async function openDraftPdf(id: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/v1/c/cutting/${id}/pdf`, {
    headers: authHeader(),
  })
  if (!res.ok) throw new Error('pdf_failed')
  const blob = await res.blob()
  return URL.createObjectURL(blob)
}

export async function openResultPdf(resultId: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/v1/c/cutting/results/${resultId}/pdf`, {
    headers: authHeader(),
  })
  if (!res.ok) throw new Error('pdf_failed')
  const blob = await res.blob()
  return URL.createObjectURL(blob)
}

function authHeader(): Record<string, string> {
  // The shared storage keys per app; client tokens live at mp.client.tokens.
  try {
    const raw = localStorage.getItem('mp.client.tokens')
    if (!raw) return {}
    const tokens = JSON.parse(raw) as { access?: string }
    return tokens.access ? { Authorization: `Bearer ${tokens.access}` } : {}
  } catch {
    return {}
  }
}

// --- orders ---------------------------------------------------------------

export function placeOrder(body: PlaceOrderIn): Promise<OrderDetail> {
  return api.post<OrderDetail>('/c/orders', body)
}

export function listOrders(scope: OrderScope = 'all', search?: string): Promise<OrderList> {
  const qs = new URLSearchParams({ scope })
  if (search) qs.set('search', search)
  return api.get<OrderList>(`/c/orders?${qs.toString()}`)
}

export function getOrder(id: string): Promise<OrderDetail> {
  return api.get<OrderDetail>(`/c/orders/${id}`)
}

export function cancelOrder(id: string, reason: string): Promise<unknown> {
  return api.post(`/c/orders/${id}/cancel`, { reason })
}

export type * from './types'
