import {
  decorTypeLabel,
  materialOptionLabel,
  snapshotEdgeLabel,
  snapshotMaterialLabel,
  snapshotShortLabel,
  snapshotText,
  type MaterialSnapshot,
} from '@/shared/app/materialLabel'
import { buildSearchKey, fold } from '@/shared/app/searchFold'
import { translate } from '@/shared/i18n'
import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'

// Pure presentation helpers shared by the cutting-editor sub-components
// (CuttingPartRow, the edge-banding modal) extracted from the editor view as part
// of the CB-93 decomposition. No Vue/runtime dependencies — testable in isolation.

// Label composition lives in one module (app/materialLabel.ts), the mirror of the
// backend's material_label.py. Re-exported here so the editor's long-standing
// import path keeps working and nobody is tempted to write a second composer.
export {
  decorTypeLabel,
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
// Callers pass `name` where they used to pass `color`.
export function colorForMaterial(value: string | null | undefined): string {
  const text = (value ?? '').toLowerCase()
  // `yong'oq` (walnut) ends in `oq`, so the compound colours have to be tested
  // before the plain ones or every walnut decor paints near-white.
  if (text.includes('walnut') || text.includes('yong')) return '#805434'
  if (text.includes('white') || text.includes('oq')) return '#f7f4ec'
  if (text.includes('black') || text.includes('qora')) return '#2a2d33'
  if (text.includes('gray') || text.includes('grey') || text.includes('kul')) return '#a7adb5'
  if (text.includes('oak') || text.includes('dub')) return '#c9aa73'
  let hash = 0
  for (const char of text || 'material') hash = (hash * 31 + char.charCodeAt(0)) % 360
  return `hsl(${hash} 34% 72%)`
}

/**
 * The swatch a result screen paints beside a material name — how an operator
 * recognises a row before reading it. A reserved slot painted nothing is worse
 * than no slot: it holds the width and reads as broken.
 *
 * **It takes the frozen snapshot, not a label, and that is the whole point.**
 * `colorForMaterial` hashes whatever string it is handed, so the colour is only
 * stable if every screen hands it the same one. The picker passes the decor's
 * `name`; passing the composed label here instead would paint the same board a
 * different colour one wizard step later, and give one decor two colours in two
 * thicknesses — the exact recognition this swatch exists to create.
 *
 * A customer's own board is hatched rather than coloured. It is not a catalog
 * decor, so hashing the typed name would invent an identity for something nobody
 * picked; the hatch is the handoff's, and it also reads at a glance as "not ours"
 * beside the `Mijoz materiali` chip.
 *
 * One deviation from the prototype: it paints each decor a two-stop gradient,
 * but those gradients are literals hand-authored for its five demo materials.
 * Nothing derives one for an arbitrary catalog row, so the app keeps the flat
 * colour it already shares with the picker.
 */
export function materialSwatchStyle(snapshot: MaterialSnapshot): Record<string, string> {
  if (snapshot?.customer_supplied === true) {
    return {
      backgroundImage:
        'repeating-linear-gradient(135deg, var(--color-hairline-soft) 0 5px, var(--color-sunk) 5px 10px)',
    }
  }
  return { background: colorForMaterial(snapshotText(snapshot, 'nomi', 'color', 'name')) }
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
  return `${material.manufacturer_name.split(' ')[0] ?? material.manufacturer_name} ${material.thickness_mm}`
}

// Keyboard-jump filter for the rows already loaded into the open edge-picker
// modal. The catalog list itself is server-searched; this only narrows what is
// on screen, which is why it stays client-side (the cutting editor's behaviour
// is unchanged by the reshape).
//
// The key is built the way `decors.search_key` is (SPEC_CATALOG_SMART_SEARCH §1),
// not lower-cased: the rows are stored in Latin and half the shop floor types on
// a Cyrillic keyboard, so `.toLowerCase().includes()` found nothing for «сонома»
// while the server's own list found it. Search it with `matchesQuery`, never with
// `includes` — the spaces around the tokens are what makes a word-start test
// possible. The type word (`kromka`) is in the key on purpose, and so are the
// thickness and tape width: «0.4» has always narrowed this list.
export function edgeSearchParts(material: ClientCatalogMaterialOption): string[] {
  return [
    material.manufacturer_name,
    material.name,
    material.code ?? '',
    material.type,
    // `fold`ed rather than passed raw: `0.4` would otherwise tokenise into `0`
    // and `4`, and a query of `4` would then hit every thin tape at a word
    // start. Folded it is the single token `04`, which is what `fold('0.4')`
    // makes of the query too.
    fold(material.thickness_mm),
    material.tape_width_mm == null ? '' : String(material.tape_width_mm),
  ]
}

export function edgeSearchKey(material: ClientCatalogMaterialOption): string {
  return buildSearchKey(edgeSearchParts(material))
}
