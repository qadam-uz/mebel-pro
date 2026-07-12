import { edgeFields, snapshotShortLabel } from '@/shared/app/cuttingDisplay'
import {
  deriveEdgeRegistry,
  edgeRegistryKey,
  partDisplayName,
  registryEntryForBand,
  syncEdgeAssignments,
  type EdgeRegistryEntry,
} from '@/shared/app/cuttingEditorDerived'
import type {
  CuttingOffcut,
  CuttingPanel,
  CuttingPart,
  CuttingResult,
} from '@/shared/stores/cutting'

export type OffcutLabelOrientation = 'horizontal' | 'vertical'

export interface OffcutLabelMode {
  text: string
  orientation: OffcutLabelOrientation
}

const LABEL_MIN_W = 80
const LABEL_MIN_H = 30

export function numberSnapshot(value: unknown, fallback: number) {
  if (typeof value === 'number') return value
  if (typeof value === 'string' && value.trim()) return Number(value)
  return fallback
}

export { snapshotShortLabel }

export function panelFillPercent(result: CuttingResult, panel: CuttingPanel) {
  const snapshot = result.material_snapshots[panel.material_id]
  const length = numberSnapshot(snapshot?.panel_length_mm, 0)
  const width = numberSnapshot(snapshot?.panel_width_mm, 0)
  if (!Number.isFinite(length) || !Number.isFinite(width) || length <= 0 || width <= 0) return '-'
  return `${Math.max(0, 100 - (panel.waste_area_mm2 / (length * width)) * 100).toFixed(1)}%`
}

export function panelDisplayIndex(result: CuttingResult, panel: CuttingPanel) {
  const index = result.panels.findIndex((item) => item.id === panel.id)
  return index >= 0 ? index + 1 : panel.panel_index
}

export function wasteToneClass(pct: number | string | null | undefined): string {
  if (pct == null) return 'text-ink'
  const value = Number(pct)
  if (!Number.isFinite(value)) return 'text-ink'
  const percent = value <= 1 ? value * 100 : value
  if (percent <= 15) return 'text-success'
  if (percent > 30) return 'text-warning'
  return 'text-ink'
}

export function variantLabel(result: Pick<CuttingResult, 'source'>) {
  return result.source === 'imported_map' ? 'Fayldagi joylashuv' : 'Optimizer'
}

export function resultPanelCount(result: Pick<CuttingResult, 'panels_used_by_material'>) {
  return Object.values(result.panels_used_by_material).reduce((sum, count) => sum + count, 0)
}

export function sheetsSavingsBanner(results: CuttingResult[], activeResult: CuttingResult | null) {
  if (!activeResult || results.length <= 1) return null
  const counts = results.map((result) => ({ result, count: resultPanelCount(result) }))
  const minCount = Math.min(...counts.map((entry) => entry.count))
  const maxCount = Math.max(...counts.map((entry) => entry.count))
  if (minCount === maxCount) return null
  const activeCount = resultPanelCount(activeResult)
  if (activeCount !== minCount) return null
  return `«${variantLabel(activeResult)}» varianti ${maxCount - minCount} list kam ishlatadi`
}

function textFits(text: string, lengthMm: number, widthMm: number, normScale: number) {
  return (
    lengthMm * normScale > Math.max(LABEL_MIN_W, text.length * 6) &&
    widthMm * normScale > LABEL_MIN_H
  )
}

export function offcutLabelMode(offcut: CuttingOffcut, normScale: number): OffcutLabelMode | null {
  const dims = `${offcut.length_mm}×${offcut.width_mm}`
  const labels = offcut.usable ? [`Qoldiq ${dims}`] : ['chiqit']
  for (const text of labels) {
    if (textFits(text, offcut.length_mm, offcut.width_mm, normScale)) {
      return { text, orientation: 'horizontal' }
    }
  }
  for (const text of labels) {
    if (textFits(text, offcut.width_mm, offcut.length_mm, normScale)) {
      return { text, orientation: 'vertical' }
    }
  }
  if (offcut.usable) {
    if (textFits(dims, offcut.length_mm, offcut.width_mm, normScale)) {
      return { text: dims, orientation: 'horizontal' }
    }
    if (textFits(dims, offcut.width_mm, offcut.length_mm, normScale)) {
      return { text: dims, orientation: 'vertical' }
    }
  }
  return null
}

export function deriveSnapshotEdgeRegistry(parts: CuttingPart[]): EdgeRegistryEntry[] {
  const assignments = new Map<string, number>()
  syncEdgeAssignments(assignments, parts)
  return deriveEdgeRegistry(parts, assignments)
}

export interface PanelPartGroup {
  partRef: string
  name: string
  length_mm: number
  width_mm: number
  count: number
  rotatedCount: number
  tapeNumbers: number[]
}

export function groupPanelPlacements(
  result: CuttingResult,
  panel: CuttingPanel,
  edgeRegistry: EdgeRegistryEntry[] = deriveSnapshotEdgeRegistry(result.parts_snapshot ?? []),
): PanelPartGroup[] {
  const partsByRef = new Map<string, { part: CuttingPart; index: number }>(
    (result.parts_snapshot ?? []).map((part, index) => [part.part_ref, { part, index }]),
  )
  const groups: PanelPartGroup[] = []
  const indexByRef = new Map<string, number>()
  for (const placement of panel.placements) {
    const row = partsByRef.get(placement.part_ref)
    const index = indexByRef.get(placement.part_ref)
    let group = index == null ? null : groups[index]
    if (!group) {
      const part = row?.part
      group = {
        partRef: placement.part_ref,
        name: row ? partDisplayName(row.part, row.index) : placement.part_ref,
        length_mm: part?.length_mm ?? placement.length_mm,
        width_mm: part?.width_mm ?? placement.width_mm,
        count: 0,
        rotatedCount: 0,
        tapeNumbers: part ? partTapeNumbers(part, edgeRegistry) : [],
      }
      indexByRef.set(placement.part_ref, groups.length)
      groups.push(group)
    }
    group.count += 1
    if (placement.rotated) group.rotatedCount += 1
  }
  return groups
}

export function partTapeNumbers(part: CuttingPart, edgeRegistry: EdgeRegistryEntry[]) {
  const numbers = new Set<number>()
  for (const side of edgeFields) {
    const band = part[side]
    const entry = registryEntryForBand(edgeRegistry, band?.material_id, band?.source)
    if (entry) numbers.add(entry.number)
  }
  return [...numbers].sort((left, right) => left - right)
}

export function edgeRegistryEntryByMaterial(
  edgeRegistry: EdgeRegistryEntry[],
  materialId: string,
  source: 'shop' | 'own' = 'shop',
) {
  const key = edgeRegistryKey(materialId, source)
  return edgeRegistry.find((entry) => entry.key === key) ?? null
}
