import { edgeFields } from '@/shared/app/cuttingDisplay'
import type { ClientCatalogMaterialOption, CuttingPart } from '@/shared/stores/cutting'

export const EDGE_REGISTRY_COLORS = [
  'bg-accent-soft text-accent',
  'bg-info-soft text-info',
  'bg-success-soft text-success',
  'bg-warning-soft text-warning',
  'bg-danger-soft text-danger',
  'bg-sunk text-ink-soft',
] as const

export interface CuttingPartGroup {
  key: string
  materialId: string | null
  label: string
  parts: Array<{ part: CuttingPart; index: number }>
  quantity: number
  areaM2: number
}

export interface EdgeRegistryEntry {
  key: string
  materialId: string
  source: 'shop' | 'own'
  number: number
  colorClass: string
}

export function partDisplayName(part: Pick<CuttingPart, 'name'>, index: number): string {
  return part.name?.trim() || `D${index + 1}`
}

export function groupCuttingParts(
  parts: CuttingPart[],
  resolveMaterialLabel: (materialId: string | null) => string,
): CuttingPartGroup[] {
  const groups: CuttingPartGroup[] = []
  const indexByKey = new Map<string, number>()
  for (const [index, part] of parts.entries()) {
    const materialId = part.material_id || null
    const key = materialId ?? '__unassigned__'
    let group = groups[indexByKey.get(key) ?? -1]
    if (!group) {
      group = {
        key,
        materialId,
        label: materialId ? resolveMaterialLabel(materialId) : 'Material tanlanmagan',
        parts: [],
        quantity: 0,
        areaM2: 0,
      }
      indexByKey.set(key, groups.length)
      groups.push(group)
    }
    group.parts.push({ part, index })
    group.quantity += Math.max(0, Number(part.quantity) || 0)
    group.areaM2 +=
      (Math.max(0, Number(part.length_mm) || 0) *
        Math.max(0, Number(part.width_mm) || 0) *
        Math.max(0, Number(part.quantity) || 0)) /
      1_000_000
  }
  return groups
}

export function deriveEdgeRegistry(parts: CuttingPart[]): EdgeRegistryEntry[] {
  const entries: EdgeRegistryEntry[] = []
  const seen = new Set<string>()
  for (const part of parts) {
    for (const side of edgeFields) {
      const edge = part[side]
      if (!edge?.material_id) continue
      const key = `${edge.material_id}:${edge.source}`
      if (seen.has(key)) continue
      seen.add(key)
      entries.push({
        key,
        materialId: edge.material_id,
        source: edge.source,
        number: entries.length + 1,
        colorClass: EDGE_REGISTRY_COLORS[entries.length % EDGE_REGISTRY_COLORS.length],
      })
    }
  }
  return entries
}

export function registryEntryForBand(
  entries: EdgeRegistryEntry[],
  materialId: string | null | undefined,
  source: 'shop' | 'own' | null | undefined,
): EdgeRegistryEntry | null {
  if (!materialId || !source) return null
  return entries.find((entry) => entry.materialId === materialId && entry.source === source) ?? null
}

export function shortMaterialName(material: ClientCatalogMaterialOption | null | undefined) {
  if (!material) return 'Material'
  return material.decor_code || material.name || material.color || material.id.slice(0, 8)
}
