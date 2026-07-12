import { edgeFields } from '@/shared/app/cuttingDisplay'
import type { ClientCatalogMaterialOption, CuttingPart } from '@/shared/stores/cutting'

export interface EdgeRegistryColorStyle {
  bg: string
  fg: string
  soft: string
}

export const EDGE_REGISTRY_COLOR_STYLES = [
  { bg: '#0f766e', fg: '#ffffff', soft: '#d8f3ea' },
  { bg: '#D85A30', fg: '#ffffff', soft: '#fde2d6' },
  { bg: '#2563eb', fg: '#ffffff', soft: '#dbeafe' },
  { bg: '#7c3aed', fg: '#ffffff', soft: '#ede9fe' },
  { bg: '#ca8a04', fg: '#111827', soft: '#fef3c7' },
  { bg: '#475569', fg: '#ffffff', soft: '#e2e8f0' },
  { bg: '#be185d', fg: '#ffffff', soft: '#fce7f3' },
  { bg: '#15803d', fg: '#ffffff', soft: '#dcfce7' },
  { bg: '#4338ca', fg: '#ffffff', soft: '#e0e7ff' },
  { bg: '#a16207', fg: '#ffffff', soft: '#fef9c3' },
] as const satisfies readonly EdgeRegistryColorStyle[]

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
  colorStyle: EdgeRegistryColorStyle
}

export function edgeRegistryKey(materialId: string, source: 'shop' | 'own') {
  return `${materialId}:${source}`
}

export function registryColorStyle(number: number): EdgeRegistryColorStyle {
  const fixed = EDGE_REGISTRY_COLOR_STYLES[number - 1]
  if (fixed) return fixed
  const hue = (((number - 1) * 137.508) % 360).toFixed(3)
  return {
    bg: `hsl(${hue} 45% 42%)`,
    fg: '#ffffff',
    soft: `hsl(${hue} 55% 92%)`,
  }
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

function usedEdgeKeys(parts: CuttingPart[]): string[] {
  const keys: string[] = []
  const seen = new Set<string>()
  for (const part of parts) {
    for (const side of edgeFields) {
      const edge = part[side]
      if (!edge?.material_id) continue
      const key = edgeRegistryKey(edge.material_id, edge.source)
      if (seen.has(key)) continue
      seen.add(key)
      keys.push(key)
    }
  }
  return keys
}

export function syncEdgeAssignments(assignments: Map<string, number>, parts: CuttingPart[]): void {
  let nextNumber = Math.max(0, ...assignments.values()) + 1
  for (const key of usedEdgeKeys(parts)) {
    if (assignments.has(key)) continue
    assignments.set(key, nextNumber)
    nextNumber += 1
  }
}

export function previewEdgeAssignments(
  assignments: ReadonlyMap<string, number>,
  keys: string[],
): Map<string, number> {
  const preview = new Map<string, number>()
  let nextNumber = Math.max(0, ...assignments.values()) + 1
  for (const key of keys) {
    if (preview.has(key)) continue
    const existing = assignments.get(key)
    if (existing != null) {
      preview.set(key, existing)
    } else {
      preview.set(key, nextNumber)
      nextNumber += 1
    }
  }
  return preview
}

export function deriveEdgeRegistry(
  parts: CuttingPart[],
  assignments: ReadonlyMap<string, number>,
): EdgeRegistryEntry[] {
  return usedEdgeKeys(parts)
    .map((key) => {
      const [materialId, source] = key.split(':') as [string, 'shop' | 'own']
      const number = assignments.get(key)
      if (number == null) return null
      return {
        key,
        materialId,
        source,
        number,
        colorStyle: registryColorStyle(number),
      }
    })
    .filter((entry): entry is EdgeRegistryEntry => entry !== null)
    .sort((left, right) => left.number - right.number)
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
