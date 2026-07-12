import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'
import type { PanelMaterialType } from '@/shared/stores/admin'

// Pure presentation helpers shared by the cutting-editor sub-components
// (CuttingPartRow, the edge-banding modal) extracted from the editor view as part
// of the CB-93 decomposition. No Vue/runtime dependencies — testable in isolation.

// The four bandable sides of a part, in render order, plus their Uzbek labels.
export const edgeFields = ['edge_top', 'edge_bottom', 'edge_left', 'edge_right'] as const
export type EdgeField = (typeof edgeFields)[number]

export const sideLabels: Record<EdgeField, string> = {
  edge_top: 'Yuqori',
  edge_bottom: 'Pastki',
  edge_left: 'Chap',
  edge_right: "O'ng",
}

const PANEL_TYPE_LABELS: Record<PanelMaterialType, string> = {
  dsp: 'LDSP',
  mdf: 'MDF',
  plywood: 'Fanera',
  natural_wood: "Yog'och",
  other: 'Panel',
}

// Deterministic swatch colour for a material: a few named-colour shortcuts, then a
// stable hash → pastel HSL so the same material always renders the same chip.
export function colorForMaterial(value: string | null | undefined): string {
  const text = (value ?? '').toLowerCase()
  if (text.includes('white') || text.includes('oq')) return '#f7f4ec'
  if (text.includes('black') || text.includes('qora')) return '#2a2d33'
  if (text.includes('gray') || text.includes('grey') || text.includes('kul')) return '#a7adb5'
  if (text.includes('walnut') || text.includes('yong')) return '#805434'
  if (text.includes('oak') || text.includes('dub')) return '#c9aa73'
  let hash = 0
  for (const char of text || 'material') hash = (hash * 31 + char.charCodeAt(0)) % 360
  return `hsl(${hash} 34% 72%)`
}

export function edgeShortLabel(
  material: ClientCatalogMaterialOption | null | undefined,
  withThickness = false,
): string {
  void withThickness
  if (!material) return '-'
  return material.name
}

export function edgeTinyLabel(material: ClientCatalogMaterialOption | null | undefined): string {
  if (!material) return '-'
  return `${material.manufacturer_name.split(' ')[0] ?? material.manufacturer_name} ${material.thickness_mm}`
}

export function edgeSearchText(material: ClientCatalogMaterialOption): string {
  return `${material.manufacturer_name} ${material.name} ${material.color} ${material.decor_code ?? ''} ${material.thickness_mm} ${material.edge_width_mm ?? ''}`.toLowerCase()
}

export function snapshotShortLabel(snapshot: Record<string, unknown> | undefined): string {
  const decor = typeof snapshot?.decor_code === 'string' ? snapshot.decor_code.trim() : ''
  if (decor) return decor
  const color = typeof snapshot?.color === 'string' ? snapshot.color.trim() : ''
  if (color) return color
  const name = typeof snapshot?.name === 'string' ? snapshot.name.trim() : ''
  return name ? name.slice(0, 18) : 'Material'
}

function snapshotText(snapshot: Record<string, unknown> | undefined, key: string) {
  const value = snapshot?.[key]
  return typeof value === 'string' ? value.trim() : ''
}

function formatMm(value: unknown) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return String(value ?? '').trim()
  return parsed.toString()
}

export function snapshotMaterialLabel(
  snapshot: Record<string, unknown> | undefined,
  fallback = 'Material',
): string {
  const manufacturer = snapshotText(snapshot, 'manufacturer_name')
  const rawType = snapshotText(snapshot, 'type') as PanelMaterialType | ''
  const type = rawType && rawType in PANEL_TYPE_LABELS ? PANEL_TYPE_LABELS[rawType] : rawType
  const decor = snapshotText(snapshot, 'decor_code')
  const name = snapshotText(snapshot, 'name')
  const color = snapshotText(snapshot, 'color')
  const thickness = snapshotText(snapshot, 'thickness_mm')
  const length = Number(snapshot?.panel_length_mm)
  const width = Number(snapshot?.panel_width_mm)
  const base = [type, manufacturer, decor || name].filter(Boolean).join(' ') || fallback
  const dimensions =
    Number.isFinite(length) && Number.isFinite(width) && length > 0 && width > 0
      ? `${length}×${width}${thickness ? `×${formatMm(thickness)}` : ''} mm`
      : thickness
        ? `${formatMm(thickness)} mm`
        : ''
  const details = [
    color && !base.toLowerCase().includes(color.toLowerCase()) ? color : '',
    dimensions,
  ].filter(Boolean)
  return [base, ...details].join(' · ')
}

export function snapshotEdgeLabel(
  snapshot: Record<string, unknown> | undefined,
  fallback = 'Krom',
): string {
  const manufacturer = snapshotText(snapshot, 'manufacturer_name')
  const decor = snapshotText(snapshot, 'decor_code')
  const name = snapshotText(snapshot, 'name')
  const color = snapshotText(snapshot, 'color')
  const thickness = snapshotText(snapshot, 'thickness_mm')
  const width = Number(snapshot?.edge_width_mm)
  const base = [manufacturer, decor || name].filter(Boolean).join(' ') || fallback
  const size =
    thickness && Number.isFinite(width) && width > 0
      ? `${formatMm(thickness)}×${width} mm`
      : thickness
        ? `${formatMm(thickness)} mm`
        : ''
  return [base, color, size].filter(Boolean).join(' · ')
}
