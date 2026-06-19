import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'

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
  if (!material) return '-'
  const decor = material.decor_code ? `${material.decor_code} ` : ''
  const thickness = withThickness ? ` · ${material.thickness_mm} mm` : ''
  return `${material.manufacturer_name} · ${decor}${material.color}${thickness}`
}

export function edgeTinyLabel(material: ClientCatalogMaterialOption | null | undefined): string {
  if (!material) return '-'
  return `${material.manufacturer_name.split(' ')[0] ?? material.manufacturer_name} ${material.thickness_mm}`
}

export function edgeSearchText(material: ClientCatalogMaterialOption): string {
  return `${material.manufacturer_name} ${material.name} ${material.color} ${material.decor_code ?? ''} ${material.thickness_mm}`.toLowerCase()
}
