/**
 * Canonical material / edge-band display-label formatting — the TypeScript mirror
 * of `backend/app/core/material_label.py`.
 *
 * Most reshaped responses hand the web a server-composed `label`
 * (`DekorResponse.label`, `BranchMaterialResponse.label`, the `material_name` /
 * `material_label` fields on sales, finance and production lines). **Prefer that
 * label wherever it exists.** This module exists for the two places it does not:
 *
 * 1. `ClientCatalogMaterialOption` — the cutting pickers' payload — carries no
 *    `label` field (backend/app/modules/cutting/schemas.py). Every picker row,
 *    parts-by-material header and edge-registry chip composes its string here.
 * 2. Frozen material snapshots (`cutting_results.material_snapshots`,
 *    `order_items.material_snapshot`) are raw dicts, never labelled by the server
 *    on the read path.
 *
 * **Two snapshot vocabularies are read, deliberately.** The catalog reshape
 * renamed the snapshot keys (`type`→`tur`, `decor_code`→`kod`, `color`→`nomi`,
 * `thickness_mm`→`qalinlik_mm`, `panel_length_mm`→`uzunlik_mm`,
 * `panel_width_mm`→`eni_mm`, `edge_width_mm`→`kromka_eni_mm`, and `name` was
 * dropped), but those two columns are frozen history and are NOT rewritten by the
 * migration — that is exactly what protects old orders. So the database holds both
 * vocabularies forever and every reader here accepts both: new key first, legacy
 * key as fallback. Dropping the legacy reads would silently render every
 * pre-reshape order, production card and result sheet as an 8-character id
 * fragment, with no error anywhere.
 *
 * One deliberate divergence from the backend: the tur prefix goes through i18n
 * (`cutting.panelType.*`), so a `ru` reader sees `ЛДСП` where the PDF prints
 * `LDSP`. That divergence predates the reshape and is preserved on purpose —
 * these keys render on screen, the Python module renders in print.
 */

import { translate } from '@/shared/i18n'
import type { DekorType } from '@/shared/stores/admin'
import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'

/** Every `tur` a dekor can have, in the backend enum's order. */
export const DEKOR_TYPES = [
  'ldsp',
  'dsp',
  'mdf',
  'fanera',
  'yogoch',
  'kromka',
  'boshqa',
] as const satisfies readonly DekorType[]

/**
 * Legacy `panel_material_type` values that never became a `tur`. They only ever
 * appear inside pre-reshape snapshots — which is precisely why they must keep
 * resolving: `cutting.panelType.plywood` and friends are not dead keys.
 */
export const LEGACY_PANEL_TYPES = ['plywood', 'natural_wood', 'other'] as const

const LABELLED_TYPES: readonly string[] = [...DEKOR_TYPES, ...LEGACY_PANEL_TYPES]

/** True when the format is a tape (thickness × tape width, no length × width). */
export function isTape(tur: DekorType | null | undefined): boolean {
  return tur === 'kromka'
}

/**
 * Localized `tur` label — `LDSP`, `MDF`, `Fanera`, `Yog'och`, `Kromka`, `List`.
 * A value the catalog does not know is echoed verbatim rather than swallowed, so
 * a future enum member is visible instead of blank.
 */
export function dekorTurLabel(tur: string | null | undefined): string {
  const value = (tur ?? '').trim()
  if (!value) return ''
  return LABELLED_TYPES.includes(value) ? translate(`cutting.panelType.${value}`) : value
}

/**
 * `18.0` → `18`, `0.40` → `0.4`, `2.00` → `2`. Mirrors `_format_mm`: parse as a
 * number to detect an integer, otherwise strip the *textual* trailing zeros so a
 * value's own precision survives.
 */
export function formatMm(value: unknown): string {
  const text = String(value ?? '').trim()
  if (!text) return ''
  const parsed = Number(text)
  if (!Number.isFinite(parsed)) return text
  if (Number.isInteger(parsed)) return String(parsed)
  return text.replace(/0+$/, '').replace(/\.$/, '')
}

export type MaterialSnapshot = Record<string, unknown> | undefined

/** First non-null value among `keys` — mirrors `_snapshot_value`. */
export function snapshotValue(snapshot: MaterialSnapshot, ...keys: string[]): unknown {
  for (const key of keys) {
    const value = snapshot?.[key]
    if (value !== null && value !== undefined) return value
  }
  return null
}

/** Trimmed string at the first present key, or `''` — mirrors `_snapshot_text`. */
export function snapshotText(snapshot: MaterialSnapshot, ...keys: string[]): string {
  const value = snapshotValue(snapshot, ...keys)
  return typeof value === 'string' ? value.trim() : ''
}

/** Whole-number read with a fallback — mirrors `_int_snapshot`. */
export function snapshotInt(value: unknown, fallback: number): number {
  if (typeof value === 'number' && Number.isInteger(value)) return value
  if (typeof value === 'string' && /^\d+$/.test(value.trim())) return Number(value.trim())
  return fallback
}

/**
 * The name slot of the base: decor code first, then whatever names exist. `name`
 * is the legacy server-generated column, gone from new snapshots; it is consulted
 * before `nomi` so a historical snapshot keeps rendering the string it always did.
 */
function identity(snapshot: MaterialSnapshot, nomi: string): string {
  return snapshotText(snapshot, 'kod', 'decor_code') || snapshotText(snapshot, 'name') || nomi
}

/** Short chip text: decor code, then colour/name, then a clipped legacy name. */
export function snapshotShortLabel(snapshot: MaterialSnapshot): string {
  const kod = snapshotText(snapshot, 'kod', 'decor_code')
  if (kod) return kod
  const nomi = snapshotText(snapshot, 'nomi', 'color')
  if (nomi) return nomi
  const name = snapshotText(snapshot, 'name')
  return name ? name.slice(0, 18) : translate('cutting.material.fallback')
}

/**
 * Canonical panel label, e.g. `LDSP Egger H1334 ST9 · Sanoma · 2800×2070×18 mm`.
 * `fallback` stands in for the base when the snapshot carries no identity at all.
 */
export function snapshotMaterialLabel(
  snapshot: MaterialSnapshot,
  fallback = translate('cutting.material.fallback'),
): string {
  const type = dekorTurLabel(snapshotText(snapshot, 'tur', 'type'))
  const manufacturer = snapshotText(snapshot, 'manufacturer_name')
  const nomi = snapshotText(snapshot, 'nomi', 'color')
  const thickness = snapshotText(snapshot, 'qalinlik_mm', 'thickness_mm')
  const length = snapshotInt(snapshotValue(snapshot, 'uzunlik_mm', 'panel_length_mm'), 0)
  const width = snapshotInt(snapshotValue(snapshot, 'eni_mm', 'panel_width_mm'), 0)

  const base = [type, manufacturer, identity(snapshot, nomi)].filter(Boolean).join(' ') || fallback
  const dimensions =
    length > 0 && width > 0
      ? `${length}×${width}${thickness ? `×${formatMm(thickness)}` : ''} mm`
      : thickness
        ? `${formatMm(thickness)} mm`
        : ''
  const details = [
    // Suppressed when the base already says it — «Egger Sonoma eman · Sonoma eman».
    nomi && !base.toLowerCase().includes(nomi.toLowerCase()) ? nomi : '',
    dimensions,
  ].filter(Boolean)
  return [base, ...details].join(' · ')
}

/**
 * Canonical edge-band label, e.g. `Egger H1334 ST9 · Sanoma · 0.4×20 mm`. No
 * length × width — tapes don't have those — and no `Kromka` prefix, matching
 * `edge_label()`.
 */
export function snapshotEdgeLabel(
  snapshot: MaterialSnapshot,
  fallback = translate('cutting.edge.label'),
): string {
  const manufacturer = snapshotText(snapshot, 'manufacturer_name')
  const nomi = snapshotText(snapshot, 'nomi', 'color')
  const thickness = snapshotText(snapshot, 'qalinlik_mm', 'thickness_mm')
  const width = snapshotInt(snapshotValue(snapshot, 'kromka_eni_mm', 'edge_width_mm'), 0)

  const base = [manufacturer, identity(snapshot, nomi)].filter(Boolean).join(' ') || fallback
  // A dekor without a `kod` puts `nomi` in the base, so the detail slot must
  // suppress it the same way snapshotMaterialLabel does.
  const detail = nomi && !base.toLowerCase().includes(nomi.toLowerCase()) ? nomi : ''
  const size =
    thickness && width > 0
      ? `${formatMm(thickness)}×${width} mm`
      : thickness
        ? `${formatMm(thickness)} mm`
        : ''
  return [base, detail, size].filter(Boolean).join(' · ')
}

/**
 * A catalog picker option, viewed as a snapshot. One conversion so there is
 * exactly one label composer instead of a picker copy and a snapshot copy that
 * drift — the defect this whole module exists to prevent.
 */
export function optionSnapshot(option: ClientCatalogMaterialOption): Record<string, unknown> {
  return {
    manufacturer_name: option.manufacturer_name,
    tur: option.tur,
    kod: option.kod,
    nomi: option.nomi,
    tolali: option.tolali,
    qalinlik_mm: option.qalinlik_mm,
    uzunlik_mm: option.uzunlik_mm,
    eni_mm: option.eni_mm,
    kromka_eni_mm: option.kromka_eni_mm,
  }
}

/**
 * The display string for a cutting-picker option. `ClientCatalogMaterialOption`
 * is the one reshaped response with no server `label`, so this composes it —
 * routing tapes through the edge shape and everything else through the panel one.
 */
export function materialOptionLabel(
  option: ClientCatalogMaterialOption | null | undefined,
  fallback?: string,
): string {
  if (!option) return fallback ?? translate('cutting.material.none')
  const snapshot = optionSnapshot(option)
  const base = fallback ?? option.id.slice(0, 8)
  return isTape(option.tur)
    ? snapshotEdgeLabel(snapshot, base)
    : snapshotMaterialLabel(snapshot, base)
}
