import {
  snapshotMaterialLabel,
  snapshotSheetSize,
  snapshotShortLabel,
  type SheetSize,
} from '@/shared/app/materialLabel'
import { edgeFields } from '@/shared/app/cuttingDisplay'
import {
  deriveEdgeRegistry,
  edgeRegistryKey,
  partDisplayName,
  syncEdgeAssignments,
  type EdgeRegistryEntry,
} from '@/shared/app/cuttingEditorDerived'
import { translate, translatePlural } from '@/shared/i18n'
import { metres } from '@/shared/stores/cutting'
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

/** Bounding extent of everything laid on a sheet, in sheet mm. */
export function panelExtent(panel: CuttingPanel): SheetSize {
  let length = 0
  let width = 0
  for (const item of panel.placements) {
    length = Math.max(length, item.x_mm + item.length_mm)
    width = Math.max(width, item.y_mm + item.width_mm)
  }
  for (const item of panel.offcuts) {
    length = Math.max(length, item.x_mm + item.length_mm)
    width = Math.max(width, item.y_mm + item.width_mm)
  }
  return { length, width }
}

/** The one place a drawn sheet's millimetres are decided — twin of the
 *  backend's `rendering.sheet_size`, so the on-screen map and the PDF agree.
 *
 *  Never guesses. When the snapshot carries no size in any vocabulary the size
 *  is *derived*: the optimizer fills every square millimetre it does not cut
 *  into a part with an offcut rectangle, so the bounding extent of placements +
 *  offcuts is the sheet, minus at most the edge trim. The old flat 1000x700
 *  fallback drew a real 2800x2070 layout at 2.8x, spilling outside its own
 *  viewBox with nothing to signal it. */
export function panelSheetSize(result: CuttingResult, panel: CuttingPanel): SheetSize {
  const snapshot = snapshotSheetSize(result.material_snapshots[panel.material_id])
  const extent = panelExtent(panel)
  return {
    length: snapshot.length || extent.length,
    width: snapshot.width || extent.width,
  }
}

/** `panelSheetSize` with a floor of 1, for the callers that divide by it: an
 *  empty panel carries neither a snapshot size nor an extent. */
export function drawnSheetSize(result: CuttingResult, panel: CuttingPanel): SheetSize {
  const size = panelSheetSize(result, panel)
  const extent = panelExtent(panel)
  // Widened past the recorded sheet when the placements disagree with it, so a
  // stale or hand-built snapshot cannot push anything outside the frame.
  return {
    length: Math.max(size.length, extent.length) || 1,
    width: Math.max(size.width, extent.width) || 1,
  }
}

export function panelFillPercent(result: CuttingResult, panel: CuttingPanel) {
  const { length, width } = panelSheetSize(result, panel)
  if (length <= 0 || width <= 0) return '-'
  return `${Math.max(0, 100 - (panel.waste_area_mm2 / (length * width)) * 100).toFixed(1)}%`
}

export function panelDisplayIndex(result: CuttingResult, panel: CuttingPanel) {
  const index = result.panels.findIndex((item) => item.id === panel.id)
  return index >= 0 ? index + 1 : panel.panel_index
}

export function resultPanelCount(result: Pick<CuttingResult, 'panels_used_by_material'>) {
  return Object.values(result.panels_used_by_material).reduce((sum, count) => sum + count, 0)
}

/** The order-level figures the result already carries, in raw units — mm and
 *  counts, never formatted. Formatting is the caller's, so the same numbers
 *  feed a screen, a comparison and a test without a round-trip through a
 *  localized string. */
export interface CuttingResultTotals {
  placedParts: number
  requestedParts: number
  sheets: number
  cutLengthMm: number
  edgeConsumedMm: number
  usableOffcutCount: number
  usableOffcutAreaMm2: number
}

function sumValues(record: Record<string, number>) {
  return Object.values(record).reduce((sum, value) => sum + value, 0)
}

/**
 * Every number the result aside shows, derived from the payload the optimizer
 * already returns — there is no API field behind any of them.
 *
 * Two choices worth stating. `edgeConsumedMm` reads the **consumed** dicts, not
 * `edge_length_*`: consumed is what the shop actually pulls off the roll (the
 * visible edge plus the per-side glue-and-trim overhang), which is the number a
 * cutter and an invoice both mean by "kromka lentasi". And offcuts are counted
 * from the panels rather than from `waste_percentage`, because only the panel
 * rows carry the `usable` flag that separates a keepable remnant from scrap —
 * the same flag the drawing colours green.
 */
export function resultTotals(result: CuttingResult): CuttingResultTotals {
  let placedParts = 0
  let usableOffcutCount = 0
  let usableOffcutAreaMm2 = 0
  for (const panel of result.panels) {
    placedParts += panel.placements.length
    for (const offcut of panel.offcuts) {
      if (!offcut.usable) continue
      usableOffcutCount += 1
      usableOffcutAreaMm2 += offcut.length_mm * offcut.width_mm
    }
  }
  return {
    placedParts,
    // Pre-snapshot results exist in the DB; `?? []` is what keeps them at 0
    // instead of throwing on the read.
    requestedParts: (result.parts_snapshot ?? []).reduce((sum, part) => sum + part.quantity, 0),
    sheets: resultPanelCount(result),
    cutLengthMm: result.total_cut_length_mm,
    edgeConsumedMm:
      sumValues(result.edge_consumed_shop_by_material) +
      sumValues(result.edge_consumed_own_by_material),
    usableOffcutCount,
    usableOffcutAreaMm2,
  }
}

/**
 * The branch's per-side glue-and-trim overhang, recovered from the result rather
 * than fetched: the optimizer stores both the geometric edge length and the
 * consumed one, and consumed is `geometric + overhang × banded sides`. So the
 * allowance falls straight out of the two dicts, per edge material, with no new
 * API field and no branch read on a screen that is already frozen history — the
 * branch may have re-set its overhang since, and this result must keep billing
 * what it was cut with.
 */
function edgeOverhangMm(result: CuttingResult, edgeMaterialId: string): number {
  const geometric = result.edge_length_by_material[edgeMaterialId] ?? 0
  const consumed =
    (result.edge_consumed_shop_by_material[edgeMaterialId] ?? 0) +
    (result.edge_consumed_own_by_material[edgeMaterialId] ?? 0)
  const sides = result.edge_banded_sides_by_material[edgeMaterialId]
  const sideCount = (sides?.shop ?? 0) + (sides?.own ?? 0)
  if (sideCount <= 0) return 0
  return Math.max(0, Math.round((consumed - geometric) / sideCount))
}

/**
 * Tape consumed on ONE sheet, per edge material — the figure the person holding
 * that sheet card is about to band with, which the result-wide totals cannot
 * answer.
 *
 * The arithmetic is the optimizer's, narrowed from "every part × its quantity"
 * to "every placement on this panel": a banded side eats its own edge plus the
 * overhang, and top/bottom follow the part's length while left/right follow its
 * width. Rotation does not enter it — a turned part bands the same two edges, it
 * just draws them on the sheet's other axis.
 */
export function panelEdgeConsumedByMaterial(
  result: CuttingResult,
  panel: CuttingPanel,
): Map<string, number> {
  const partsByRef = new Map((result.parts_snapshot ?? []).map((part) => [part.part_ref, part]))
  const consumed = new Map<string, number>()
  for (const placement of panel.placements) {
    const part = partsByRef.get(placement.part_ref)
    if (!part) continue
    for (const field of edgeFields) {
      const band = part[field]
      if (!band) continue
      const sideLength =
        field === 'edge_top' || field === 'edge_bottom' ? part.length_mm : part.width_mm
      const key = edgeRegistryKey(band.material_id, band.source)
      const millimetres = sideLength + edgeOverhangMm(result, band.material_id)
      consumed.set(key, (consumed.get(key) ?? 0) + millimetres)
    }
  }
  return consumed
}

/**
 * What this one sheet costs in tape. The aside's per-tape totals and the summary
 * row are both result-wide, and neither answers the question the person holding
 * this card has: they are about to band *this* sheet and need the roll for it.
 *
 * A sheet with no banding shows its size alone — never `0.00 m`, which invites
 * the reader to hunt for a figure that does not exist.
 *
 * Two deviations from the prototype, each forced by something it never had to
 * render:
 *
 * 1. It prints one combined figure per sheet; with several tapes we give each
 *    its own. You cannot pull 17.52 m off two different rolls, so a combined
 *    number is the one thing the operator holding this card cannot act on. They
 *    list in registry-number order, the numbering the editor gave them.
 * 2. The tape is named by its **short** label (the decor code), not the composed
 *    one the aside prints. This app builds a tape label from manufacturer, decor
 *    and size — three `·`-separated fields — and dropping two of those into a
 *    caption that already separates its own fields with `·` leaves a chain whose
 *    only grouping cue is a comma, wrapping three lines deep in a 370px card.
 *    The code is the identity the operator reads off the roll.
 *
 * Metres are the app's `metres()` (two decimals), not the prototype's one: this
 * screen already prints the result-wide tape total with two, and a quantity
 * rounded two ways on one screen reads as two different numbers.
 */
export function sheetEdgeLine(
  result: CuttingResult,
  panel: CuttingPanel,
  edgeRegistry: EdgeRegistryEntry[],
): string | null {
  const consumed = panelEdgeConsumedByMaterial(result, panel)
  if (consumed.size === 0) return null
  const total = [...consumed.values()].reduce((sum, millimetres) => sum + millimetres, 0)
  if (total <= 0) return null
  return [...consumed.entries()]
    .map(([key, millimetres]) => ({
      entry: edgeRegistry.find((registryEntry) => registryEntry.key === key),
      millimetres,
    }))
    .sort((left, right) => (left.entry?.number ?? 0) - (right.entry?.number ?? 0))
    .map(({ entry, millimetres }) => {
      const label = entry ? snapshotShortLabel(result.material_snapshots[entry.materialId]) : ''
      // `·` between fields, per DESIGN.md: without it the metres run onto the
      // tape's own size and read as one more measurement of the roll.
      return label ? `${label} · ${metres(millimetres)}` : metres(millimetres)
    })
    .join(', ')
}

/** m², two decimals — the unit the editor's group headers and the PDF's
 *  material table both print offcut and part areas in. */
export function squareMetres(areaMm2: number) {
  return (areaMm2 / 1_000_000).toFixed(2)
}

function textFits(text: string, lengthMm: number, widthMm: number, normScale: number) {
  return (
    lengthMm * normScale > Math.max(LABEL_MIN_W, text.length * 6) &&
    widthMm * normScale > LABEL_MIN_H
  )
}

export function offcutLabelMode(offcut: CuttingOffcut, normScale: number): OffcutLabelMode | null {
  const dims = `${offcut.length_mm}×${offcut.width_mm}`
  const labels = offcut.usable
    ? [translate('cutting.result.offcutUsable', { dims })]
    : [translate('cutting.result.offcutWaste')]
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
    sheetLabel: translate('cutting.result.sheetLabel', { n: panelDisplayIndex(result, panel) }),
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

/** One of the client's four result figures (§7.7). */
export interface ClientResultFigure {
  key: 'parts' | 'sheets' | 'edge' | 'offcuts'
  label: string
  value: string
}

/**
 * **Detallar · Listlar · Kromka · Foydali qoldiq** — the four figures the client
 * sees, and the only four, on the result stage, the phone summary card and the
 * order confirmation alike (§7.7).
 *
 * One composer for all three so they cannot drift: a phone card and a desktop
 * tally saying different things about the same layout is the complaint this
 * replaces. «Arra yo'li» and «Chiqim» are absent by construction rather than
 * filtered per call site — they are saw and yield metrics the shop plans
 * around, and a client quoted a fixed price cannot act on either.
 */
export function clientResultFigures(result: CuttingResult): ClientResultFigure[] {
  const totals = resultTotals(result)
  return [
    {
      key: 'parts',
      label: translate('cutting.result.summaryParts'),
      value: `${totals.placedParts} ${translate('cutting.unit.pieceShort')}`,
    },
    {
      key: 'sheets',
      label: translate('cutting.result.summarySheets'),
      value: `${totals.sheets} ${translatePlural('cutting.unit.sheet', totals.sheets)}`,
    },
    {
      key: 'edge',
      label: translate('cutting.result.edgeTitle'),
      // Em-dash, not "0.00 m": a drawing with no banding has no tape figure,
      // and a printed zero invites the reader to look for one.
      value: totals.edgeConsumedMm > 0 ? metres(totals.edgeConsumedMm) : '—',
    },
    {
      key: 'offcuts',
      label: translate('cutting.result.usefulOffcut'),
      value: totals.usableOffcutCount
        ? translate('cutting.result.summaryOffcutsValue', {
            n: totals.usableOffcutCount,
            area: squareMetres(totals.usableOffcutAreaMm2),
          })
        : '—',
    },
  ]
}
