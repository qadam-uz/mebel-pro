// Pure helpers for the client cutting + order screens. No Vue, no API — just
// the load-bearing transforms (SVG placement scaling, 5-phase mapping, edges
// cycle, draft summarising) so they can be unit-tested in isolation.

import type {
  CuttingResult,
  Draft,
  EdgeThickness,
  Material,
  OrderStatus,
  PartSnapshot,
  Placement,
} from '../api/types'

// --- limits (from docs/ref/features/cutting.md) ---------------------------
export const LIMITS = {
  PART_MIN: 50,
  MAX_PARTS: 100,
  MAX_SHEETS_PER_MATERIAL: 20,
  EDGE_TRIM: 10,
  MAX_DRAFTS: 50,
} as const

// --- edges popover state --------------------------------------------------
// Each side cycles None → 0.4 → 2.0 → None.
const EDGE_CYCLE: EdgeThickness[] = [null, 0.4, 2.0]

export function cycleEdge(current: EdgeThickness): EdgeThickness {
  const i = EDGE_CYCLE.findIndex((x) => x === current)
  return EDGE_CYCLE[(i + 1) % EDGE_CYCLE.length]
}

export interface Edges {
  t: EdgeThickness
  b: EdgeThickness
  l: EdgeThickness
  r: EdgeThickness
}

export function presetEdges(value: EdgeThickness): Edges {
  return { t: value, b: value, l: value, r: value }
}

// --- 5-phase client-facing stepper ----------------------------------------
// cutting + edge_banding collapse into "In production" (index 2).
// Labels: Placed → Confirmed → In production → Ready → Done.
export type Phase = 0 | 1 | 2 | 3 | 4

export function phaseIndex(status: OrderStatus): Phase {
  switch (status) {
    case 'new':
      return 0
    case 'confirmed':
      return 1
    case 'cutting':
    case 'edge_banding':
      return 2
    case 'ready':
      return 3
    case 'completed':
      return 4
    case 'cancelled':
      // cancelled has no phase index; callers special-case it.
      return 0
  }
}

export const ACTIVE_STATUSES: OrderStatus[] = [
  'new',
  'confirmed',
  'cutting',
  'edge_banding',
  'ready',
]

export function isActive(status: OrderStatus): boolean {
  return ACTIVE_STATUSES.includes(status)
}

// Finance figures unlock only at ready/completed (orders.md finance gate).
export function financeOpen(status: OrderStatus): boolean {
  return status === 'ready' || status === 'completed'
}

// --- SVG placement transform ----------------------------------------------
// The optimiser stores placements with a BOTTOM-LEFT origin within the usable
// area (x_mm/y_mm = bottom-left corner of the part). SVG's origin is TOP-LEFT
// with y growing downward, so we flip y. We render the full sheet (W×H mm) at a
// fixed pixel width, keeping aspect ratio, and inset placements by the trim.
export interface SvgRect {
  partRef: string
  qtyIndex: number
  x: number
  y: number
  w: number
  h: number
  rotated: boolean
  lengthMm: number
  widthMm: number
}

export interface SvgLayout {
  viewW: number
  viewH: number
  scale: number
  sheetW: number
  sheetH: number
  trim: number
  usable: { x: number; y: number; w: number; h: number }
  rects: SvgRect[]
}

// sheetWmm/sheetHmm — full sheet dims; trim — edge trim per side; placements in
// usable-area coordinates (bottom-left origin). pxWidth — target render width.
export function buildSvgLayout(
  placements: Placement[],
  sheetWmm: number,
  sheetHmm: number,
  trim: number,
  pxWidth = 800,
): SvgLayout {
  const scale = pxWidth / sheetWmm
  const viewW = Math.round(sheetWmm * scale)
  const viewH = Math.round(sheetHmm * scale)
  const usableWmm = sheetWmm - 2 * trim
  const usableHmm = sheetHmm - 2 * trim

  const rects: SvgRect[] = placements.map((p) => {
    // placement (x_mm,y_mm) is the bottom-left of the part inside the usable
    // area. Convert to sheet coordinates (add trim), then flip y for SVG.
    const sheetX = trim + p.x_mm
    const sheetYBottom = trim + p.y_mm
    // SVG top of the rect = sheetH - (bottom + height)
    const sheetYTop = sheetHmm - (sheetYBottom + p.width_mm)
    return {
      partRef: p.part_ref,
      qtyIndex: p.part_quantity_index,
      x: sheetX * scale,
      y: sheetYTop * scale,
      w: p.length_mm * scale,
      h: p.width_mm * scale,
      rotated: p.rotated,
      lengthMm: p.length_mm,
      widthMm: p.width_mm,
    }
  })

  return {
    viewW,
    viewH,
    scale,
    sheetW: sheetWmm,
    sheetH: sheetHmm,
    trim,
    usable: {
      x: trim * scale,
      y: trim * scale,
      w: usableWmm * scale,
      h: usableHmm * scale,
    },
    rects,
  }
}

// --- material helpers -----------------------------------------------------
// "DSP 18mm Bel · 2800×2070" → the short label used on chips.
export function materialShortLabel(m: Material | undefined): string {
  if (!m) return ''
  return m.name.split('·')[0].trim()
}

export function materialById(materials: Material[], id: string | null): Material | undefined {
  if (!id) return undefined
  return materials.find((m) => m.id === id)
}

// A deterministic swatch colour from a material id (no colour in the API beyond
// a free-text `color`; we hash for a stable visual).
const PALETTE = [
  '#A6471F',
  '#7e6f53',
  '#2d6045',
  '#664a2d',
  '#b87024',
  '#4a5b3f',
  '#856a48',
  '#5a4438',
]
export function partColor(index: number): string {
  return PALETTE[index % PALETTE.length]
}

export function swatchFor(id: string): string {
  let h = 0
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0
  return PALETTE[h % PALETTE.length]
}

// --- draft summarising (for the drafts list + home cards) -----------------
export interface DraftSummary {
  totalParts: number
  materialIds: string[]
  dominantLabel: string
  sheets: number | null
  wastePct: number | null
}

export function summariseDraft(
  draft: Draft,
  materials: Material[],
  chosen: CuttingResult | null,
): DraftSummary {
  const snapshot = draft.parts_snapshot ?? []
  const totalParts = snapshot.reduce((a, p) => a + (p.quantity || 0), 0)
  const materialIds = [...new Set(snapshot.map((p) => p.material_id).filter(Boolean))]
  const labels = materialIds
    .map((id) => materialShortLabel(materialById(materials, id)))
    .filter(Boolean)
  const dominantLabel =
    labels.slice(0, 2).join(' + ') + (labels.length > 2 ? ` +${labels.length - 2}` : '')
  let sheets: number | null = null
  let wastePct: number | null = null
  if (chosen) {
    sheets = Object.values(chosen.sheets_used_by_material).reduce((a, b) => a + Number(b), 0)
    wastePct = Math.round(chosen.waste_percentage * 1000) / 10
  }
  return { totalParts, materialIds, dominantLabel, sheets, wastePct }
}

export function totalSheets(result: CuttingResult): number {
  return Object.values(result.sheets_used_by_material).reduce((a, b) => a + Number(b), 0)
}

// --- relative time --------------------------------------------------------
export function relativeTime(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const diff = Math.max(0, now - then)
  const min = Math.floor(diff / 60000)
  if (min < 1) return 'hozir'
  if (min < 60) return `${min} daqiqa oldin`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} soat oldin`
  const day = Math.floor(hr / 24)
  if (day < 30) return `${day} kun oldin`
  const mo = Math.floor(day / 30)
  return `${mo} oy oldin`
}

// --- snapshot ↔ editable part ---------------------------------------------
export interface EditablePart {
  ref: string
  materialId: string | null
  source: 'shop' | 'own'
  l: number | null
  w: number | null
  qty: number
  edges: Edges
}

export function snapshotToEditable(p: PartSnapshot): EditablePart {
  return {
    ref: p.part_ref,
    materialId: p.material_id,
    source: p.material_source,
    l: p.length_mm,
    w: p.width_mm,
    qty: p.quantity,
    edges: {
      t: (p.edge_top_mm as EdgeThickness) ?? null,
      b: (p.edge_bottom_mm as EdgeThickness) ?? null,
      l: (p.edge_left_mm as EdgeThickness) ?? null,
      r: (p.edge_right_mm as EdgeThickness) ?? null,
    },
  }
}

export function newPartRef(): string {
  // part_ref is a UUID (docs/ref/entities/cutting.md); the backend validates it
  // as such, so a UUID — not an ad-hoc string — is required.
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  // Fallback (older/test environments without crypto.randomUUID).
  return '10000000-1000-4000-8000-100000000000'.replace(/[018]/g, (c) =>
    (Number(c) ^ (Math.floor(Math.random() * 256) & (15 >> (Number(c) / 4)))).toString(16),
  )
}

export function blankPart(): EditablePart {
  return {
    ref: newPartRef(),
    materialId: null,
    source: 'shop',
    l: null,
    w: null,
    qty: 1,
    edges: { t: null, b: null, l: null, r: null },
  }
}
