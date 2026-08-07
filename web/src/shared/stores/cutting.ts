import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api, apiTraceId, captureApiError, withQuery } from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'
import { openBlobInNewTab, PopupBlockedError } from '@/shared/app/downloadBlob'
import { translate } from '@/shared/i18n'
import type { MaterialKind, PanelMaterialType } from '@/shared/stores/admin'
import type { ImportMapLayout } from '@/shared/stores/cuttingImport'

export type MaterialSource = 'shop' | 'own'
export type CuttingResultStatus = 'candidate' | 'confirmed' | 'invalidated'
export type CuttingResultSource = 'optimizer' | 'imported_map'

// Which API surface the store talks to: the client SPA uses `/client/*`, the
// workshop SPA the mirrored `/workshop/*` staff endpoints. Each SPA has its own
// Pinia instance, so the scope is set once at bootstrap and never flips.
export type CuttingScope = 'client' | 'workshop'

// The walk-in client a staffer resolved (phone → find-or-create) before
// entering the workshop editor; drafts are created on this client's behalf.
export interface CuttingWalkInClient {
  id: string
  name: string
  phone: string
}

export interface CuttingEdgeBand {
  material_id: string
  source: MaterialSource
}

export interface CuttingPart {
  part_ref: string
  name: string | null
  material_id: string
  material_source: MaterialSource
  follow_grain: boolean
  // Thickening (utolshenie / obmanka, stamped "УТ"): a strip of the same panel
  // is glued under the part so its banded edge reads twice as thick. A workshop
  // instruction only — it never enters the layout, so nothing is cut, counted
  // or priced for it. It does double the thickness the edge tape must cover.
  thickened: boolean
  length_mm: number
  width_mm: number
  quantity: number
  edge_top: CuttingEdgeBand | null
  edge_bottom: CuttingEdgeBand | null
  edge_left: CuttingEdgeBand | null
  edge_right: CuttingEdgeBand | null
}

export interface CuttingOffcut {
  x_mm: number
  y_mm: number
  length_mm: number
  width_mm: number
  usable: boolean
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
  offcuts: CuttingOffcut[]
  placements: CuttingPlacement[]
}

export interface CuttingResult {
  id: string
  draft_id: string | null
  algorithm_name: string
  algorithm_version: string
  source: CuttingResultSource
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
  name: string | null
  preferred_branch_id: string | null
  // Effective kerf/edge-trim for this draft, resolved server-side from its
  // branch (or the platform defaults for a branch-less draft) on every read.
  kerf_mm: number
  edge_trim_mm: number
  parts_snapshot: CuttingPart[]
  /** Client-supplied material: sheets claimed per catalog material, and the
   *  tapes the client brings on their own roll. The sheet number is a claim,
   *  not a cap — a result applies `min(claim, panels_used)`. */
  own_panel_counts: Record<string, number>
  own_edge_material_ids: string[]
  chosen_result_id: string | null
  // Set only on an order's revision draft — the editor switches to revision
  // mode (orders.md "Revising a placed order") when present.
  revision_of_order_id: string | null
  created_at: string
  updated_at: string
  results: CuttingResult[]
}

// A staff-minted walk-in draft on the workshop's saved-drafts surface. The
// backend denormalizes the walk-in client + branch and derives readiness
// (`has_result`) so the list card needs no per-row fetch.
export interface WorkshopDraftSummary {
  id: string
  client_id: string
  client_name: string
  client_phone: string
  name: string | null
  preferred_branch_id: string | null
  branch_name: string | null
  part_count: number
  panel_count: number
  waste_percentage: number | null
  has_result: boolean
  created_at: string
  updated_at: string
}

export interface CuttingMapImportCommitPayload {
  preferred_branch_id?: string | null
  parts: CuttingPart[]
  map_layout: ImportMapLayout
  panel_picks: Record<string, string>
  // The uploaded file's name (e.g. "AFZAL.map") — the wizard already has it
  // from the file picker. The backend derives the new draft's `name` from it
  // (extension stripped); never persisted verbatim.
  source_filename?: string | null
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
  edge_width_mm: number | null
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
  address: string
  status: 'active' | 'temporarily_closed'
  closed_reason: string | null
  kerf_mm: number
  edge_trim_mm: number
}

export function materialLabel(material: ClientCatalogMaterialOption | null | undefined) {
  if (!material) return translate('cutting.material.none')
  return material.name
}

export function metres(mm: number) {
  return `${(mm / 1000).toFixed(2)} ${translate('cutting.unit.metre')}`
}

/**
 * Pure check of whether a part fits its chosen panel, mirroring the backend
 * validation (panel usable area = panel − 2×edge-trim; rotation is locked when
 * this part follows texture). `trimMm` is the branch's own edge trim (no
 * platform-wide default exists client-side — see cutting.md). Returns the
 * matching backend error code, or null when the part fits (or the panel size
 * is unknown).
 */
export function partFitError(
  lengthMm: number,
  widthMm: number,
  panel: Pick<
    ClientCatalogMaterialOption,
    'panel_length_mm' | 'panel_width_mm' | 'grain_direction'
  >,
  followGrain: boolean,
  trimMm: number,
): 'impossible_grain' | 'part_too_large' | null {
  if (panel.panel_length_mm == null || panel.panel_width_mm == null) return null
  const length = Number(lengthMm)
  const width = Number(widthMm)
  if (!Number.isFinite(length) || !Number.isFinite(width)) return null
  const usableLength = panel.panel_length_mm - 2 * trimMm
  const usableWidth = panel.panel_width_mm - 2 * trimMm
  const fitsNormal = length <= usableLength && width <= usableWidth
  const fitsRotated = width <= usableLength && length <= usableWidth
  const locked = followGrain
  if (locked) return fitsNormal ? null : 'impossible_grain'
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
  // Role scope (default 'client' — the client SPA needs zero configuration).
  // The workshop SPA calls configureScope('workshop') once at bootstrap
  // (createRoleApp), before any view runs.
  const scope = ref<CuttingScope>('client')
  // Workshop-only: the resolved walk-in client the current draft belongs to.
  const walkInClient = ref<CuttingWalkInClient | null>(null)

  // Single seam between the client and workshop API surfaces: every request
  // path in this store is built here so the '/client' vs '/workshop' prefix
  // can never drift per-call. Note `/workshop/branch-options` does NOT exist —
  // the workshop editor runs with a fixed branch, so loadBranchOptions guards
  // on scope instead of ever building a workshop path.
  function scopedPath(path: string) {
    return `/${scope.value}${path}`
  }

  function configureScope(next: CuttingScope) {
    scope.value = next
  }

  function setWalkInClient(client: CuttingWalkInClient | null) {
    walkInClient.value = client
  }

  // Workshop-only: resolve a walk-in client by phone (find-or-create). `created`
  // tells the caller whether the name was just registered or is a disclosed
  // existing one (the walk-in view asks the staffer to confirm the latter).
  async function resolveWalkInClient(input: { phone: string; name?: string }) {
    const resolved = await api.post<CuttingWalkInClient & { created: boolean }>(
      '/workshop/clients/resolve',
      { phone: input.phone, name: input.name },
      authInit(),
    )
    walkInClient.value = { id: resolved.id, name: resolved.name, phone: resolved.phone }
    return resolved
  }

  // Workshop-only: rehydrate the walk-in client after a mid-flow reload (the
  // editor/checkout carry only the id in the route).
  async function loadWalkInClient(id: string) {
    const loaded = await api.get<CuttingWalkInClient>(`/workshop/clients/${id}`, authInit())
    walkInClient.value = loaded
    return loaded
  }

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
  const loading = ref(false)
  const saving = ref(false)
  const optimizing = ref(false)
  const materialsLoading = ref(false)
  const error = ref<string | null>(null)
  const traceId = ref<string | null>(null)
  // PDF feedback (CB-17): id of the result whose PDF is being fetched, plus a
  // transient error + trace for the last failed open.
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
      drafts.value = await api.get<CuttingDraft[]>(scopedPath('/cutting-drafts'), authInit())
    } catch (errorValue) {
      captureError(errorValue, 'cutting_drafts_load_failed')
    } finally {
      loading.value = false
    }
  }

  // The workshop's unfinished walk-in drafts (saved but never ordered). Always a
  // workshop endpoint, so it doesn't go through scopedPath; delete reuses the
  // scope-aware deleteDraft below. `branchId` is the topbar branch context —
  // omit it (or pass null) for the whole workshop.
  const workshopDrafts = ref<WorkshopDraftSummary[]>([])
  async function loadWorkshopDrafts(branchId: string | null = null) {
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      workshopDrafts.value = await api.get<WorkshopDraftSummary[]>(
        withQuery('/workshop/cutting-drafts', { branch_id: branchId }),
        authInit(),
      )
    } catch (errorValue) {
      captureError(errorValue, 'cutting_drafts_load_failed')
    } finally {
      loading.value = false
    }
  }

  // Client scope: POST with no body (server binds the draft to the caller).
  // Workshop scope: the draft is created on behalf of the resolved walk-in
  // client at the fixed branch — both are required by the contract; the route
  // guard resolves them before the editor mounts, so a miss here is a
  // programming error, not a user-reachable state.
  async function createDraft(options: { branchId?: string | null } = {}) {
    saving.value = true
    try {
      let payload: { client_id: string; branch_id: string } | undefined
      if (scope.value === 'workshop') {
        if (!walkInClient.value) {
          throw new Error('Workshop draft creation requires a resolved walk-in client')
        }
        if (!options.branchId) {
          throw new Error('Workshop draft creation requires a fixed branch id')
        }
        payload = { client_id: walkInClient.value.id, branch_id: options.branchId }
      }
      const draft = await api.post<CuttingDraft>(scopedPath('/cutting-drafts'), payload, authInit())
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
      currentDraft.value = await api.get<CuttingDraft>(
        scopedPath(`/cutting-drafts/${id}`),
        authInit(),
      )
    } catch (errorValue) {
      captureError(errorValue, 'cutting_draft_load_failed')
    } finally {
      loading.value = false
    }
  }

  async function updateDraft(
    id: string,
    payload: {
      name?: string | null
      preferred_branch_id?: string | null
      parts_snapshot?: CuttingPart[]
      own_panel_counts?: Record<string, number>
      own_edge_material_ids?: string[]
    },
  ) {
    saving.value = true
    try {
      const draft = await api.patch<CuttingDraft>(
        scopedPath(`/cutting-drafts/${id}`),
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

  async function commitMapImport(payload: CuttingMapImportCommitPayload) {
    let request:
      | CuttingMapImportCommitPayload
      | (CuttingMapImportCommitPayload & { client_id: string; branch_id: string }) = payload
    if (scope.value === 'workshop') {
      if (!walkInClient.value) {
        throw new Error('Workshop MAP import requires a resolved walk-in client')
      }
      if (!payload.preferred_branch_id) {
        throw new Error('Workshop MAP import requires a fixed branch')
      }
      request = {
        ...payload,
        client_id: walkInClient.value.id,
        branch_id: payload.preferred_branch_id,
      }
    }
    saving.value = true
    try {
      const draft = await api.post<CuttingDraft>(
        scopedPath('/cutting/import/map/commit'),
        request,
        authInit(),
      )
      drafts.value = [draft, ...drafts.value.filter((item) => item.id !== draft.id)]
      currentDraft.value = draft
      return draft
    } finally {
      saving.value = false
    }
  }

  async function deleteDraft(id: string) {
    await api.del(scopedPath(`/cutting-drafts/${id}`), authInit())
    drafts.value = drafts.value.filter((draft) => draft.id !== id)
    if (currentDraft.value?.id === id) currentDraft.value = null
  }

  async function optimizeDraft(id: string) {
    optimizing.value = true
    error.value = null
    traceId.value = null
    try {
      const draft = await api.post<CuttingDraft>(
        scopedPath(`/cutting-drafts/${id}/optimize`),
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
      scopedPath(`/cutting-drafts/${draftId}/chosen-result`),
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
    // Client-only endpoint — there is no /workshop/branch-options mirror (the
    // workshop editor runs with a fixed branch and never shows the picker).
    // Guarded no-op so a stray call in workshop scope can't hit a 404.
    if (scope.value === 'workshop') return
    if (search) {
      branchOptions.value = await api.get<ClientBranchOption[]>(
        withQuery(scopedPath('/branch-options'), { search }),
        authInit(),
      )
      branchOptionsLoadedAt.value = 0
      return
    }
    const fresh =
      branchOptions.value.length > 0 && Date.now() - branchOptionsLoadedAt.value < 30_000
    if (!options.force && fresh) return
    branchOptions.value = await api.get<ClientBranchOption[]>(
      withQuery(scopedPath('/branch-options'), {}),
      authInit(),
    )
    branchOptionsLoadedAt.value = Date.now()
  }

  async function loadMaterials(params: {
    kind: MaterialKind
    branchId?: string | null
    search?: string
    carriedOnly?: boolean
    limit?: number
    force?: boolean
  }) {
    const carriedOnly = params.carriedOnly ?? false
    const cacheKey = `${params.kind}:${params.branchId ?? 'all'}:${params.search ?? ''}:${carriedOnly}:${params.limit ?? ''}`
    const cached = materialsCache.get(cacheKey)
    if (!params.force && cached && Date.now() - cached.at < 30_000) {
      if (params.kind === 'panel') panelOptions.value = cached.items
      else edgeOptions.value = cached.items
      return cached.items
    }
    materialsLoading.value = true
    try {
      const materials = await api.get<ClientCatalogMaterialOption[]>(
        withQuery(scopedPath('/catalog/materials'), {
          kind: params.kind,
          branch_id: params.branchId,
          search: params.search,
          carried_only: carriedOnly,
          limit: params.limit,
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

  async function openClientPdf(resultId: string) {
    await openPdf(scopedPath(`/cutting-results/${resultId}/pdf`), resultId)
  }

  async function openPdf(path: string, id: string) {
    downloadingId.value = id
    downloadError.value = null
    downloadTraceId.value = null
    try {
      await openBlobInNewTab(path, authInit())
    } catch (errorValue) {
      downloadError.value =
        errorValue instanceof PopupBlockedError
          ? translate('cutting.error.popupBlocked')
          : translate('cutting.error.pdfFailed')
      downloadTraceId.value = apiTraceId(errorValue)
    } finally {
      downloadingId.value = null
    }
  }

  // Drop the loaded panel/edge catalogs without touching drafts or branch options
  // — used when the editor has no branch selected (the catalog is branch-scoped,
  // so there's nothing valid to keep showing).
  function clearMaterials() {
    panelOptions.value = []
    edgeOptions.value = []
  }

  function reset() {
    // `scope` deliberately survives reset: it's app identity fixed at
    // bootstrap, not session state. The walk-in client IS session state.
    walkInClient.value = null
    drafts.value = []
    workshopDrafts.value = []
    currentDraft.value = null
    branchOptions.value = []
    panelOptions.value = []
    edgeOptions.value = []
    materialsCache.clear()
    loading.value = false
    saving.value = false
    optimizing.value = false
    materialsLoading.value = false
    error.value = null
    traceId.value = null
    downloadingId.value = null
    downloadError.value = null
    downloadTraceId.value = null
    branchOptionsLoadedAt.value = 0
  }

  return {
    scope,
    walkInClient,
    configureScope,
    setWalkInClient,
    resolveWalkInClient,
    loadWalkInClient,
    drafts,
    workshopDrafts,
    loadWorkshopDrafts,
    currentDraft,
    branchOptions,
    panelOptions,
    edgeOptions,
    loading,
    saving,
    optimizing,
    materialsLoading,
    error,
    traceId,
    downloadingId,
    downloadError,
    downloadTraceId,
    loadDrafts,
    createDraft,
    loadDraft,
    updateDraft,
    commitMapImport,
    deleteDraft,
    optimizeDraft,
    chooseResult,
    loadBranchOptions,
    loadMaterials,
    clearMaterials,
    openClientPdf,
    reset,
  }
})
