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
  if (panel.decor_code && edge.decor_code && panel.decor_code === edge.decor_code) return 0
  if (panel.color && edge.color && panel.color.toLowerCase() === edge.color.toLowerCase()) return 1
  return 2
}

export interface RankedEdge {
  material: ClientCatalogMaterialOption
  rank: number
}

/** Edges sorted by rank → thickness → manufacturer+name, carrying the rank. */
export function rankedEdges(
  panel: ClientCatalogMaterialOption | null | undefined,
  edges: ClientCatalogMaterialOption[],
): RankedEdge[] {
  return edges
    .map((material) => ({ material, rank: edgeRank(panel, material) }))
    .sort((left, right) => {
      if (left.rank !== right.rank) return left.rank - right.rank
      const leftThickness = Number(left.material.thickness_mm)
      const rightThickness = Number(right.material.thickness_mm)
      if (leftThickness !== rightThickness) return leftThickness - rightThickness
      return `${left.material.manufacturer_name} ${left.material.name}`.localeCompare(
        `${right.material.manufacturer_name} ${right.material.name}`,
      )
    })
}

/**
 * The edge to default to: the currently-picked one, else the remembered one for
 * the part, else the top-ranked. `currentId`/`rememberedId` resolve against the
 * same `edges` list.
 */
export function recommendedEdge(
  panel: ClientCatalogMaterialOption | null | undefined,
  edges: ClientCatalogMaterialOption[],
  currentId: string | null | undefined,
  rememberedId: string | null | undefined,
): ClientCatalogMaterialOption | null {
  const byId = (id: string | null | undefined) => edges.find((edge) => edge.id === id) ?? null
  if (currentId) return byId(currentId)
  if (rememberedId) return byId(rememberedId)
  return rankedEdges(panel, edges)[0]?.material ?? null
}
