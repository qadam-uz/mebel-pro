import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api, apiTraceId, captureApiError, withQuery } from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'
import { downloadBlob } from '@/shared/app/downloadBlob'
import type { MaterialKind, PanelMaterialType } from '@/shared/stores/admin'

export type MaterialSource = 'shop' | 'own'
export type CuttingResultStatus = 'candidate' | 'confirmed' | 'invalidated'

export interface CuttingEdgeBand {
  material_id: string
  source: MaterialSource
}

export interface CuttingPart {
  part_ref: string
  material_id: string
  material_source: MaterialSource
  length_mm: number
  width_mm: number
  quantity: number
  edge_top: CuttingEdgeBand | null
  edge_bottom: CuttingEdgeBand | null
  edge_left: CuttingEdgeBand | null
  edge_right: CuttingEdgeBand | null
}

export interface CuttingPlacement {
  id: string
  part_ref: string
  part_quantity_index: number
  x_mm: number
  y_mm: number
  length_mm: number
  width_mm: number
  rotated: boolean
}

export interface CuttingPanel {
  id: string
  material_id: string
  panel_index: number
  waste_area_mm2: number
  placements: CuttingPlacement[]
}

export interface CuttingResult {
  id: string
  draft_id: string | null
  algorithm_name: string
  algorithm_version: string
  status: CuttingResultStatus
  kerf_mm: number
  edge_trim_mm: number
  panels_used_by_material: Record<string, number>
  waste_percentage: string
  total_cut_length_mm: number
  total_edge_length_mm: number
  edge_length_by_material: Record<string, number>
  parts_snapshot: CuttingPart[]
  material_snapshots: Record<string, Record<string, unknown>>
  edge_length_shop_by_material: Record<string, number>
  edge_length_own_by_material: Record<string, number>
  edge_consumed_shop_by_material: Record<string, number>
  edge_consumed_own_by_material: Record<string, number>
  edge_banded_sides_by_material: Record<string, { shop: number; own: number }>
  order_id: string | null
  created_at: string
  confirmed_at: string | null
  invalidated_at: string | null
  panels: CuttingPanel[]
}

export interface CuttingDraft {
  id: string
  client_id: string
  preferred_branch_id: string | null
  parts_snapshot: CuttingPart[]
  chosen_result_id: string | null
  created_at: string
  updated_at: string
  results: CuttingResult[]
}

export interface ClientCatalogMaterialOption {
  id: string
  kind: MaterialKind
  manufacturer_id: string
  manufacturer_name: string
  type: PanelMaterialType | null
  name: string
  thickness_mm: string
  color: string
  decor_code: string | null
  panel_length_mm: number | null
  panel_width_mm: number | null
  grain_direction: boolean | null
  image_file_id: string | null
  branch_carried: boolean
  price_tiyin: number | null
  display_unit: string
}

export interface ClientBranchOption {
  branch_id: string
  workshop_id: string
  workshop_name: string
  branch_name: string
  status: 'active' | 'temporarily_closed'
  closed_reason: string | null
  today_hours: { open: string | null; close: string | null }
}

export interface WorkshopCuttingPlanSummary {
  id: string
  order_id: string
  order_number: string
  client_id: string
  branch_id: string
  algorithm_name: string
  waste_percentage: string
  panels_used_by_material: Record<string, number>
  total_cut_length_mm: number
  total_edge_length_mm: number
  confirmed_at: string | null
}

export interface WorkshopCuttingPlanDetail extends WorkshopCuttingPlanSummary {
  result: CuttingResult
}

export function materialLabel(material: ClientCatalogMaterialOption | null | undefined) {
  if (!material) return "Material yo'q"
  const size =
    material.kind === 'panel'
      ? `${material.panel_length_mm ?? '-'}x${material.panel_width_mm ?? '-'}`
      : `${material.thickness_mm} mm krom`
  return `${material.manufacturer_name} ${material.name} · ${size}`
}

export function metres(mm: number) {
  return `${(mm / 1000).toFixed(2)} m`
}

// Mirrors the backend cutting optimizer (app/modules/cutting/optimizer.py).
export const EDGE_TRIM_MM = 10

/**
 * Pure check of whether a part fits its chosen panel, mirroring the backend
 * validation (panel usable area = panel − 2×edge-trim; non-grained panels may
 * rotate the part, grained panels may not). Returns the matching backend error
 * code, or null when the part fits (or the panel size is unknown).
 */
export function partFitError(
  lengthMm: number,
  widthMm: number,
  panel: Pick<
    ClientCatalogMaterialOption,
    'panel_length_mm' | 'panel_width_mm' | 'grain_direction'
  >,
  trimMm: number = EDGE_TRIM_MM,
): 'impossible_grain' | 'part_too_large' | null {
  if (panel.panel_length_mm == null || panel.panel_width_mm == null) return null
  const length = Number(lengthMm)
  const width = Number(widthMm)
  if (!Number.isFinite(length) || !Number.isFinite(width)) return null
  const usableLength = panel.panel_length_mm - 2 * trimMm
  const usableWidth = panel.panel_width_mm - 2 * trimMm
  const fitsNormal = length <= usableLength && width <= usableWidth
  const fitsRotated = width <= usableLength && length <= usableWidth
  if (panel.grain_direction) return fitsNormal ? null : 'impossible_grain'
  return fitsNormal || fitsRotated ? null : 'part_too_large'
}

export const EDGE_SIDES = ['edge_top', 'edge_bottom', 'edge_left', 'edge_right'] as const
export type EdgeSide = (typeof EDGE_SIDES)[number]

/**
 * Which of a part's SHOP-sourced materials the chosen branch doesn't carry — the
 * panel (`'panel'`) and/or each banded side. Empty when no branch is chosen or all
 * are carried. Pure: the panel/edge resolvers are passed in, so it's unit-testable
 * without the store (CB-124). Drives the per-row recovery banner (CB-19/CB-86).
 */
export function partNotCarried(
  part: CuttingPart,
  branchId: string | null | undefined,
  resolvePanel: (id: string | null | undefined) => { branch_carried: boolean } | null,
  resolveEdge: (id: string | null | undefined) => { branch_carried: boolean } | null,
): string[] {
  if (!branchId) return []
  const issues: string[] = []
  const panel = resolvePanel(part.material_id)
  if (part.material_source === 'shop' && panel && !panel.branch_carried) issues.push('panel')
  for (const side of EDGE_SIDES) {
    const band = part[side]
    const material = resolveEdge(band?.material_id)
    if (band?.source === 'shop' && material && !material.branch_carried) issues.push(side)
  }
  return issues
}

export const useCuttingStore = defineStore('cutting', () => {
  const drafts = ref<CuttingDraft[]>([])
  const currentDraft = ref<CuttingDraft | null>(null)
  const branchOptions = ref<ClientBranchOption[]>([])
  const panelOptions = ref<ClientCatalogMaterialOption[]>([])
  const edgeOptions = ref<ClientCatalogMaterialOption[]>([])
  // Per-(kind, branch, …) catalog cache (CB-40): the editor re-requests the same
  // material list on remount and when the branch flips back, and the full list
  // drives client-side filtering — so reuse a recent result instead of re-fetching
  // an identical payload. Keyed by the full query; ~30s freshness like branch-options.
  const materialsCache = new Map<string, { at: number; items: ClientCatalogMaterialOption[] }>()
  const workshopPlans = ref<WorkshopCuttingPlanSummary[]>([])
  const currentWorkshopPlan = ref<WorkshopCuttingPlanDetail | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const optimizing = ref(false)
  const materialsLoading = ref(false)
  const workshopLoading = ref(false)
  const error = ref<string | null>(null)
  const traceId = ref<string | null>(null)
  // PDF download feedback (CB-17): id of the result currently downloading, plus
  // a transient error + trace for the last failed download.
  const downloadingId = ref<string | null>(null)
  const downloadError = ref<string | null>(null)
  const downloadTraceId = ref<string | null>(null)

  function captureError(errorValue: unknown, fallback: string) {
    // Canonical capture (CB-100): 403 → permission_denied, else the backend code
    // is preserved (previously this collapsed every non-403 to the fallback).
    const captured = captureApiError(errorValue, fallback)
    error.value = captured.code
    traceId.value = captured.traceId
  }

  async function loadDrafts() {
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      drafts.value = await api.get<CuttingDraft[]>('/client/cutting-drafts', authInit())
    } catch (errorValue) {
      captureError(errorValue, 'cutting_drafts_load_failed')
    } finally {
      loading.value = false
    }
  }

  async function createDraft() {
    saving.value = true
    try {
      const draft = await api.post<CuttingDraft>('/client/cutting-drafts', undefined, authInit())
      drafts.value = [draft, ...drafts.value]
      currentDraft.value = draft
      return draft
    } finally {
      saving.value = false
    }
  }

  async function loadDraft(id: string) {
    loading.value = true
    error.value = null
    traceId.value = null
    currentDraft.value = null
    try {
      currentDraft.value = await api.get<CuttingDraft>(`/client/cutting-drafts/${id}`, authInit())
    } catch (errorValue) {
      captureError(errorValue, 'cutting_draft_load_failed')
    } finally {
      loading.value = false
    }
  }

  async function updateDraft(
    id: string,
    payload: { preferred_branch_id?: string | null; parts_snapshot?: CuttingPart[] },
  ) {
    saving.value = true
    try {
      const draft = await api.patch<CuttingDraft>(
        `/client/cutting-drafts/${id}`,
        payload,
        authInit(),
      )
      currentDraft.value = draft
      drafts.value = [draft, ...drafts.value.filter((item) => item.id !== draft.id)]
      return draft
    } finally {
      saving.value = false
    }
  }

  async function deleteDraft(id: string) {
    await api.del(`/client/cutting-drafts/${id}`, authInit())
    drafts.value = drafts.value.filter((draft) => draft.id !== id)
    if (currentDraft.value?.id === id) currentDraft.value = null
  }

  async function optimizeDraft(id: string) {
    optimizing.value = true
    error.value = null
    traceId.value = null
    try {
      const draft = await api.post<CuttingDraft>(
        `/client/cutting-drafts/${id}/optimize`,
        undefined,
        authInit(),
      )
      currentDraft.value = draft
      drafts.value = [draft, ...drafts.value.filter((item) => item.id !== draft.id)]
      return draft
    } catch (errorValue) {
      captureError(errorValue, 'cutting_optimize_failed')
      throw errorValue
    } finally {
      optimizing.value = false
    }
  }

  async function chooseResult(draftId: string, resultId: string) {
    const draft = await api.post<CuttingDraft>(
      `/client/cutting-drafts/${draftId}/chosen-result`,
      { result_id: resultId },
      authInit(),
    )
    currentDraft.value = draft
    drafts.value = [draft, ...drafts.value.filter((item) => item.id !== draft.id)]
    return draft
  }

  // Reuse the cached branch-options for ~30s on a plain (no-search) load so the
  // editor→checkout navigation doesn't refetch the identical list twice (CB-52).
  // A search always fetches and invalidates the freshness window.
  const branchOptionsLoadedAt = ref(0)
  async function loadBranchOptions(search?: string, options: { force?: boolean } = {}) {
    if (search) {
      branchOptions.value = await api.get<ClientBranchOption[]>(
        withQuery('/client/branch-options', { search }),
        authInit(),
      )
      branchOptionsLoadedAt.value = 0
      return
    }
    const fresh =
      branchOptions.value.length > 0 && Date.now() - branchOptionsLoadedAt.value < 30_000
    if (!options.force && fresh) return
    branchOptions.value = await api.get<ClientBranchOption[]>(
      withQuery('/client/branch-options', {}),
      authInit(),
    )
    branchOptionsLoadedAt.value = Date.now()
  }

  async function loadMaterials(params: {
    kind: MaterialKind
    branchId?: string | null
    search?: string
    carriedOnly?: boolean
    force?: boolean
  }) {
    const carriedOnly = params.carriedOnly ?? false
    const cacheKey = `${params.kind}:${params.branchId ?? 'all'}:${params.search ?? ''}:${carriedOnly}`
    const cached = materialsCache.get(cacheKey)
    if (!params.force && cached && Date.now() - cached.at < 30_000) {
      if (params.kind === 'panel') panelOptions.value = cached.items
      else edgeOptions.value = cached.items
      return cached.items
    }
    materialsLoading.value = true
    try {
      const materials = await api.get<ClientCatalogMaterialOption[]>(
        withQuery('/client/catalog/materials', {
          kind: params.kind,
          branch_id: params.branchId,
          search: params.search,
          carried_only: carriedOnly,
        }),
        authInit(),
      )
      materialsCache.set(cacheKey, { at: Date.now(), items: materials })
      if (params.kind === 'panel') panelOptions.value = materials
      else edgeOptions.value = materials
      return materials
    } finally {
      materialsLoading.value = false
    }
  }

  async function downloadClientPdf(resultId: string) {
    await downloadPdf(
      `/client/cutting-results/${resultId}/pdf`,
      `cutting-${resultId}.pdf`,
      resultId,
    )
  }

  async function loadWorkshopPlans() {
    workshopLoading.value = true
    error.value = null
    traceId.value = null
    try {
      workshopPlans.value = await api.get<WorkshopCuttingPlanSummary[]>(
        '/workshop/cutting-plans',
        authInit(),
      )
    } catch (errorValue) {
      captureError(errorValue, 'workshop_cutting_plans_load_failed')
    } finally {
      workshopLoading.value = false
    }
  }

  async function loadWorkshopPlan(id: string) {
    workshopLoading.value = true
    error.value = null
    traceId.value = null
    currentWorkshopPlan.value = null
    try {
      currentWorkshopPlan.value = await api.get<WorkshopCuttingPlanDetail>(
        `/workshop/cutting-plans/${id}`,
        authInit(),
      )
    } catch (errorValue) {
      captureError(errorValue, 'workshop_cutting_plan_load_failed')
    } finally {
      workshopLoading.value = false
    }
  }

  async function downloadWorkshopPdf(resultId: string) {
    await downloadPdf(
      `/workshop/cutting-plans/${resultId}/pdf`,
      `cutting-${resultId}.pdf`,
      resultId,
    )
  }

  async function downloadPdf(path: string, filename: string, id: string) {
    downloadingId.value = id
    downloadError.value = null
    downloadTraceId.value = null
    try {
      await downloadBlob(path, filename, authInit())
    } catch (errorValue) {
      downloadError.value = "PDF'ni yuklab bo'lmadi. Qayta urinib ko'ring."
      downloadTraceId.value = apiTraceId(errorValue)
    } finally {
      downloadingId.value = null
    }
  }

  return {
    drafts,
    currentDraft,
    branchOptions,
    panelOptions,
    edgeOptions,
    workshopPlans,
    currentWorkshopPlan,
    loading,
    saving,
    optimizing,
    materialsLoading,
    workshopLoading,
    error,
    traceId,
    downloadingId,
    downloadError,
    downloadTraceId,
    loadDrafts,
    createDraft,
    loadDraft,
    updateDraft,
    deleteDraft,
    optimizeDraft,
    chooseResult,
    loadBranchOptions,
    loadMaterials,
    downloadClientPdf,
    loadWorkshopPlans,
    loadWorkshopPlan,
    downloadWorkshopPdf,
  }
})
