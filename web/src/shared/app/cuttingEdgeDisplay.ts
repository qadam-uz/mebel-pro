import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'

/**
 * Pure edge-banding ranking helpers (CB-130), extracted from the cutting editor so
 * the "Mos" (recommended) badge and default edge are unit-testable without mounting
 * the view. Rank: 0 = decor match with the panel, 1 = colour match, 2 = neither.
 */
export function edgeRank(
  panel: ClientCatalogMaterialOption | null | undefined,
  edge: ClientCatalogMaterialOption,
): number {
  if (!panel) return 2
  if (panel.kod && edge.kod && panel.kod === edge.kod) return 0
  if (panel.nomi && edge.nomi && panel.nomi.toLowerCase() === edge.nomi.toLowerCase()) return 1
  return 2
}

export interface RankedEdge {
  material: ClientCatalogMaterialOption
  rank: number
}

export function widthPenalty(
  panelThickness: number | null | undefined,
  edge: Pick<ClientCatalogMaterialOption, 'kromka_eni_mm'>,
): number {
  if (panelThickness == null || !Number.isFinite(panelThickness)) return 0
  const width = Number(edge.kromka_eni_mm)
  if (!Number.isFinite(width)) return 0
  return width < panelThickness ? 10_000 + (panelThickness - width) : width - panelThickness
}

export function edgeTooNarrow(
  panelThickness: number | null | undefined,
  edge: Pick<ClientCatalogMaterialOption, 'kromka_eni_mm'> | null | undefined,
): boolean {
  if (!edge || panelThickness == null || !Number.isFinite(panelThickness)) return false
  const width = Number(edge.kromka_eni_mm)
  return Number.isFinite(width) && width < panelThickness
}

/**
 * Edges sorted by rank → width fit → thickness → manufacturer + identity,
 * carrying the rank. The last tiebreak used to read the server's stored `name`;
 * `kod || nomi` is that string's identity slot (material_label.py `_identity`),
 * which keeps the ordering the picker has always had.
 */
export function rankedEdges(
  panel: ClientCatalogMaterialOption | null | undefined,
  edges: ClientCatalogMaterialOption[],
): RankedEdge[] {
  const panelThickness = panel ? Number(panel.qalinlik_mm) : null
  return edges
    .map((material) => ({ material, rank: edgeRank(panel, material) }))
    .sort((left, right) => {
      if (left.rank !== right.rank) return left.rank - right.rank
      const leftWidthPenalty = widthPenalty(panelThickness, left.material)
      const rightWidthPenalty = widthPenalty(panelThickness, right.material)
      if (leftWidthPenalty !== rightWidthPenalty) return leftWidthPenalty - rightWidthPenalty
      const leftThickness = Number(left.material.qalinlik_mm)
      const rightThickness = Number(right.material.qalinlik_mm)
      if (leftThickness !== rightThickness) return leftThickness - rightThickness
      const identity = (edge: ClientCatalogMaterialOption) =>
        `${edge.manufacturer_name} ${edge.kod || edge.nomi}`
      return identity(left.material).localeCompare(identity(right.material))
    })
}

/**
 * The draft-scoped edge to arm: the currently-picked one, else the remembered one
 * for the part, then group/document usage. Catalog ranking deliberately does not
 * arm a tape; a fresh drawing must return null until the user selects one.
 * `currentId`/`rememberedId` resolve against the same `edges` list.
 */
export function recommendedEdge(
  panel: ClientCatalogMaterialOption | null | undefined,
  edges: ClientCatalogMaterialOption[],
  currentId: string | null | undefined,
  rememberedId: string | null | undefined,
  groupUsage: string[] = [],
  documentUsage: string[] = [],
): ClientCatalogMaterialOption | null {
  const byId = (id: string | null | undefined) => edges.find((edge) => edge.id === id) ?? null
  if (currentId) return byId(currentId)
  if (rememberedId) return byId(rememberedId)
  for (const id of groupUsage) {
    const edge = byId(id)
    if (edge) return edge
  }
  for (const id of documentUsage) {
    const edge = byId(id)
    if (edge && edgeRank(panel, edge) < 2) return edge
  }
  return null
}
