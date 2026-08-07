import {
  dekorTurLabel,
  materialOptionLabel,
  snapshotEdgeLabel,
  snapshotMaterialLabel,
  snapshotShortLabel,
} from '@/shared/app/materialLabel'
import { translate } from '@/shared/i18n'
import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'

// Pure presentation helpers shared by the cutting-editor sub-components
// (CuttingPartRow, the edge-banding modal) extracted from the editor view as part
// of the CB-93 decomposition. No Vue/runtime dependencies — testable in isolation.

// Label composition lives in one module (app/materialLabel.ts), the mirror of the
// backend's material_label.py. Re-exported here so the editor's long-standing
// import path keeps working and nobody is tempted to write a second composer.
export {
  dekorTurLabel,
  materialOptionLabel,
  snapshotEdgeLabel,
  snapshotMaterialLabel,
  snapshotShortLabel,
}

// The four bandable sides of a part, in render order, plus their labels.
export const edgeFields = ['edge_top', 'edge_bottom', 'edge_left', 'edge_right'] as const
export type EdgeField = (typeof edgeFields)[number]

// Getters, not literals: a frozen record would keep whichever locale was active
// when this module first evaluated, and `sideLabels[side]` is read from several
// call sites that a plain function would have to change.
export const sideLabels: Record<EdgeField, string> = {
  get edge_top() {
    return translate('cutting.side.top')
  },
  get edge_bottom() {
    return translate('cutting.side.bottom')
  },
  get edge_left() {
    return translate('cutting.side.left')
  },
  get edge_right() {
    return translate('cutting.side.right')
  },
}

// Deterministic swatch colour for a material: a few named-colour shortcuts, then a
// stable hash → pastel HSL so the same material always renders the same chip.
// Callers pass `nomi` where they used to pass `color`.
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
  // Was `material.name`, the server's stored label. That column is gone, so the
  // same string is composed — through the one composer, never inline.
  return materialOptionLabel(material)
}

export function edgeTinyLabel(material: ClientCatalogMaterialOption | null | undefined): string {
  if (!material) return '-'
  return `${material.manufacturer_name.split(' ')[0] ?? material.manufacturer_name} ${material.qalinlik_mm}`
}

// Keyboard-jump filter for the rows already loaded into the open edge-picker
// modal. The catalog list itself is server-searched; this only narrows what is
// on screen, which is why it stays client-side (the cutting editor's behaviour
// is unchanged by the reshape). `name` is gone from the blob; `kod`/`nomi` carry
// the signal now.
export function edgeSearchText(material: ClientCatalogMaterialOption): string {
  return `${material.manufacturer_name} ${material.nomi} ${material.kod ?? ''} ${material.qalinlik_mm} ${material.kromka_eni_mm ?? ''}`.toLowerCase()
}
