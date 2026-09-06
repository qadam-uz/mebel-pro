import { edgeFields } from '@/shared/app/cuttingDisplay'
import { translate } from '@/shared/i18n'
import type { ClientCatalogMaterialOption, CuttingPart } from '@/shared/stores/cutting'

export interface EdgeRegistryColorStyle {
  bg: string
  fg: string
  soft: string
}

/**
 * Tape colours, and they are *categorical* — their only job is telling one edge
 * tape apart from another on the job sheet, so they deliberately do not mirror
 * the brand tokens. One rule binds them: no entry may be the brand colour
 * (entry 1 was once the ultramarine `#4341c6` — which is now `brand-tile`
 * again, so the ban matters twice over: a chip in it would read as the logo).
 * Entry 1 sits in the largest hue gap the ramp had — between amber and green —
 * so the two most-used tapes never look alike.
 *
 * `fg` is pure white and deliberately NOT the bone `--color-on-accent`
 * (`#f4f2ee`). Bone is specified for text on GRAPHITE, where it takes the glare
 * off a near-black field; on a saturated mid-tone it just costs contrast. The
 * number these fills carry renders at 12px, so it owes the full 4.5:1 — and bone
 * puts `#15803d` at 4.49:1 and `#a16207` at 4.40:1, both under the floor, while
 * white clears it at 5.02:1 and 4.92:1. The one entry light enough to fail with
 * either (`#ca8a04`) pairs with ink instead.
 */
export const EDGE_REGISTRY_COLOR_STYLES = [
  { bg: '#49740e', fg: '#ffffff', soft: '#ecfccb' },
  { bg: '#D85A30', fg: '#ffffff', soft: '#fde2d6' },
  { bg: '#2563eb', fg: '#ffffff', soft: '#dbeafe' },
  { bg: '#7c3aed', fg: '#ffffff', soft: '#ede9fe' },
  { bg: '#ca8a04', fg: '#111827', soft: '#fef3c7' },
  { bg: '#475569', fg: '#ffffff', soft: '#e2e8f0' },
  { bg: '#be185d', fg: '#ffffff', soft: '#fce7f3' },
  { bg: '#15803d', fg: '#ffffff', soft: '#dcfce7' },
  { bg: '#0f766e', fg: '#ffffff', soft: '#d8f3ea' },
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

// Keep this list aligned with backend/app/modules/cutting/service.py.  These
// fields change panel placement; every other editable part field only changes
// presentation or edge pricing/consumption metrics.
const geometryDefaults = {
  quantity: 0,
  length_mm: 0,
  width_mm: 0,
  material_id: null,
  follow_grain: true,
} as const

/**
 * Whether a parts edit leaves every existing layout geometrically valid.
 *
 * Draft snapshots written before a field existed may omit it, so compare a
 * missing value with the same default the backend uses rather than treating a
 * serialization difference as a layout-changing edit.
 */
export function isGeometryNeutralEdit(
  oldParts: readonly Partial<CuttingPart>[],
  newParts: readonly Partial<CuttingPart>[],
): boolean {
  const oldByRef = new Map(oldParts.map((part) => [part.part_ref, part]))
  const newByRef = new Map(newParts.map((part) => [part.part_ref, part]))
  if (oldByRef.size !== newByRef.size) return false

  for (const [partRef, oldPart] of oldByRef) {
    const newPart = newByRef.get(partRef)
    if (!newPart) return false
    if (
      (oldPart.quantity ?? geometryDefaults.quantity) !==
        (newPart.quantity ?? geometryDefaults.quantity) ||
      (oldPart.length_mm ?? geometryDefaults.length_mm) !==
        (newPart.length_mm ?? geometryDefaults.length_mm) ||
      (oldPart.width_mm ?? geometryDefaults.width_mm) !==
        (newPart.width_mm ?? geometryDefaults.width_mm) ||
      (oldPart.material_id ?? geometryDefaults.material_id) !==
        (newPart.material_id ?? geometryDefaults.material_id) ||
      (oldPart.follow_grain ?? geometryDefaults.follow_grain) !==
        (newPart.follow_grain ?? geometryDefaults.follow_grain)
    ) {
      return false
    }
  }
  return true
}

export function registryColorStyle(number: number): EdgeRegistryColorStyle {
  const fixed = EDGE_REGISTRY_COLOR_STYLES[number - 1]
  if (fixed) return fixed
  const hue = (((number - 1) * 137.508) % 360).toFixed(3)
  // Same ramp, same reason for white — see EDGE_REGISTRY_COLOR_STYLES. At 42%
  // lightness the generated fills sit in exactly the band where bone drops under
  // 4.5:1.
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
        label: materialId
          ? resolveMaterialLabel(materialId)
          : translate('cutting.material.unassigned'),
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

/**
 * The **entire** input `syncEdgeAssignments` reads out of `parts`, as one
 * string: the ordered, de-duplicated list of banded tape keys.
 *
 * The editor watches this instead of watching `parts` deeply. Two properties
 * make that safe, and both are load-bearing:
 *
 * - **Complete** — `syncEdgeAssignments` reads nothing but `usedEdgeKeys(parts)`,
 *   so two parts lists with the same signature always produce the same
 *   assignments from the same starting map.
 * - **Cheap to track** — it touches only `part.edge_*`, so a computed built on
 *   it is not a subscriber of `length_mm` / `width_mm` / `quantity` / `name`.
 *   Typing in a geometry field cannot invalidate it, which is the point: a deep
 *   watch re-walked all 300 rows and rebuilt the Map on every keystroke.
 *
 * Keep the two functions together — a field added to the sync must be added here.
 */
export function edgeAssignmentSignature(parts: CuttingPart[]): string {
  return usedEdgeKeys(parts).join(',')
}

export function syncEdgeAssignments(assignments: Map<string, number>, parts: CuttingPart[]): void {
  const liveKeys = usedEdgeKeys(parts)
  const liveKeySet = new Set(liveKeys)
  // A side-pattern edit can make one tape appear on more sides, but that must
  // not reshuffle its number or colour. Only removed tapes disappear; retained
  // tapes compact their sequence and new tapes append in first-use order.
  const retainedKeys = [...assignments.entries()]
    .filter(([key]) => liveKeySet.has(key))
    .sort((left, right) => left[1] - right[1])
    .map(([key]) => key)
  const retainedKeySet = new Set(retainedKeys)
  const orderedKeys = [...retainedKeys, ...liveKeys.filter((key) => !retainedKeySet.has(key))]
  assignments.clear()
  for (const [index, key] of orderedKeys.entries()) assignments.set(key, index + 1)
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
  if (!material) return translate('cutting.material.fallback')
  // Was decor_code → name → color; `name` is gone and `color` became `name`, so
  // the four rungs collapse to three.
  return material.code || material.name || material.id.slice(0, 8)
}
