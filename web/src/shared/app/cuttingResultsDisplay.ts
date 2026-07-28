import { snapshotMaterialLabel, snapshotShortLabel } from '@/shared/app/cuttingDisplay'
import {
  deriveEdgeRegistry,
  edgeRegistryKey,
  partDisplayName,
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

export function resultPanelCount(result: Pick<CuttingResult, 'panels_used_by_material'>) {
  return Object.values(result.panels_used_by_material).reduce((sum, count) => sum + count, 0)
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
}

// Placements whose part_ref is missing from parts_snapshot (older results)
// still get a stable D-number continuing after the snapshot, in placement
// order across the whole result — the raw part_ref uuid never renders.
export function orphanPartIndexByRef(result: CuttingResult): Map<string, number> {
  const known = new Set((result.parts_snapshot ?? []).map((part) => part.part_ref))
  const orphans = new Map<string, number>()
  let next = known.size
  for (const panel of result.panels)
    for (const placement of panel.placements)
      if (!known.has(placement.part_ref) && !orphans.has(placement.part_ref))
        orphans.set(placement.part_ref, next++)
  return orphans
}

export function groupPanelPlacements(result: CuttingResult, panel: CuttingPanel): PanelPartGroup[] {
  const partsByRef = new Map<string, { part: CuttingPart; index: number }>(
    (result.parts_snapshot ?? []).map((part, index) => [part.part_ref, { part, index }]),
  )
  const orphanIndex = orphanPartIndexByRef(result)
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
        name: row
          ? partDisplayName(row.part, row.index)
          : `D${(orphanIndex.get(placement.part_ref) ?? 0) + 1}`,
        length_mm: part?.length_mm ?? placement.length_mm,
        width_mm: part?.width_mm ?? placement.width_mm,
        count: 0,
        rotatedCount: 0,
      }
      indexByRef.set(placement.part_ref, groups.length)
      groups.push(group)
    }
    group.count += 1
    if (placement.rotated) group.rotatedCount += 1
  }
  return groups
}

export interface ResultSheetPartGroups {
  panelId: string
  sheetLabel: string
  materialLabel: string
  groups: PanelPartGroup[]
}

// QAD-177: the whole result as text, sheet by sheet. The narrow-viewport parts
// list is the authoritative reading of a result — the drawing shrinks past
// legibility on a phone, so every sheet's parts must be reachable without
// switching the drawing first. Sheet order follows `panelDisplayIndex`, the
// same drawing-wide numbering the thumbnails and the PDF use; within a sheet
// the rows follow `parts_snapshot` order (the editor's and the PDF's `#`
// order) rather than the optimizer's placement order, so D1 precedes D4 and a
// screen reader walks the parts the way the user wrote them.
export function resultSheetPartGroups(result: CuttingResult): ResultSheetPartGroups[] {
  const snapshotOrder = new Map(
    (result.parts_snapshot ?? []).map((part, index) => [part.part_ref, index]),
  )
  const orphanOrder = orphanPartIndexByRef(result)
  const rank = (partRef: string) =>
    snapshotOrder.get(partRef) ?? orphanOrder.get(partRef) ?? Number.MAX_SAFE_INTEGER
  return result.panels.map((panel) => ({
    panelId: panel.id,
    sheetLabel: `List ${panelDisplayIndex(result, panel)}`,
    materialLabel: snapshotMaterialLabel(
      result.material_snapshots[panel.material_id],
      panel.material_id.slice(0, 8),
    ),
    groups: groupPanelPlacements(result, panel).sort(
      (left, right) => rank(left.partRef) - rank(right.partRef),
    ),
  }))
}

export function edgeRegistryEntryByMaterial(
  edgeRegistry: EdgeRegistryEntry[],
  materialId: string,
  source: 'shop' | 'own' = 'shop',
) {
  const key = edgeRegistryKey(materialId, source)
  return edgeRegistry.find((entry) => entry.key === key) ?? null
}
