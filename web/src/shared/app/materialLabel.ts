/**
 * Canonical material / edge-band display-label formatting — the TypeScript mirror
 * of `backend/app/core/material_label.py`.
 *
 * Most reshaped responses hand the web a server-composed `label`
 * (`DecorResponse.label`, `BranchMaterialResponse.label`, the `material_name` /
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
 * **Three snapshot vocabularies are read, deliberately** — the mirror of the
 * table in `material_label.py`. Snapshots are frozen history and are never
 * rewritten by a migration, so the database holds every vocabulary the app has
 * ever written, forever:
 *
 * | slot         | 1. current      | 2. Uzbek        | 3. pre-reshape    |
 * |--------------|-----------------|-----------------|-------------------|
 * | substrate    | `type`          | `tur`           | `type`            |
 * | decor code   | `code`          | `kod`           | `decor_code`      |
 * | decor name   | `name`          | `nomi`          | `color`           |
 * | thickness    | `thickness_mm`  | `qalinlik_mm`   | `thickness_mm`    |
 * | sheet length | `length_mm`     | `uzunlik_mm`    | `panel_length_mm` |
 * | sheet width  | `width_mm`      | `eni_mm`        | `panel_width_mm`  |
 * | tape width   | `tape_width_mm` | `kromka_eni_mm` | `edge_width_mm`   |
 * | finished     | `finished_sides`| —               | —                 |
 *
 * `name` collides: current snapshots put the DECOR name there, pre-reshape ones
 * put the whole generated material name there. So the decor-name slot reads
 * `nomi` and `color` BEFORE `name` — neither can occur in a current snapshot, so
 * a current one still resolves to `name`, while a pre-reshape one keeps
 * resolving to `color` and leaves its generated `name` to the identity slot,
 * which is where it always rendered. Dropping any of this would silently render
 * old orders as an 8-character id fragment, with no error anywhere.
 *
 * One deliberate divergence from the backend: the type prefix goes through i18n
 * (`cutting.panelType.*`), so a `ru` reader sees `ЛДСП` where the PDF prints
 * `LDSP`. That divergence predates the reshape and is preserved on purpose —
 * these keys render on screen, the Python module renders in print.
 */

import { translate } from '@/shared/i18n'
import type { DecorType } from '@/shared/stores/admin'
import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'

/** Every `type` a decor can have, in the backend enum's order. */
export const DECOR_TYPES = [
  'ldsp',
  'dsp',
  'mdf',
  'fanera',
  'yogoch',
  'kromka',
  'boshqa',
] as const satisfies readonly DecorType[]

/**
 * Legacy `panel_material_type` values that never became a `type`. They only ever
 * appear inside pre-reshape snapshots — which is precisely why they must keep
 * resolving: `cutting.panelType.plywood` and friends are not dead keys.
 */
export const LEGACY_PANEL_TYPES = ['plywood', 'natural_wood', 'other'] as const

const LABELLED_TYPES: readonly string[] = [...DECOR_TYPES, ...LEGACY_PANEL_TYPES]

/** True when the format is a tape (thickness × tape width, no length × width). */
export function isTape(type: DecorType | null | undefined): boolean {
  return type === 'kromka'
}

/**
 * Localized `type` label — `LDSP`, `MDF`, `Fanera`, `Yog'och`, `Kromka`, `List`.
 * A value the catalog does not know is echoed verbatim rather than swallowed, so
 * a future enum member is visible instead of blank.
 */
export function decorTypeLabel(type: string | null | undefined): string {
  const value = (type ?? '').trim()
  if (!value) return ''
  return LABELLED_TYPES.includes(value) ? translate(`cutting.panelType.${value}`) : value
}

/**
 * The Tur pill's classes — the neutral chip plus the dot colour for this
 * substrate's **family**.
 *
 * Grouped, not one hue per enum member: the word beside the dot is the identity,
 * so the dot only has to answer "board, wood, or tape?" at a glance, and a hue
 * per member would be six things to learn instead of four. `ldsp` and `dsp`
 * share a dot because they are the same board with and without its laminate —
 * their *labels* stay distinct, which is what tells them apart; `fanera` and
 * `yog'och` share one because both are literally wood; `boshqa` takes the muted
 * default, the honest colour for "unclassified".
 *
 * Deliberately off the status ramp — see the `--color-tur-*` note in main.css.
 */
export function decorTypePillClass(type: DecorType | null | undefined): string {
  if (type === 'kromka') return 'pill p-tur tur-tape'
  if (type === 'ldsp' || type === 'dsp') return 'pill p-tur tur-board'
  if (type === 'mdf') return 'pill p-tur tur-mdf'
  if (type === 'fanera' || type === 'yogoch') return 'pill p-tur tur-wood'
  return 'pill p-tur'
}

/**
 * The `type` choices a **filter** offers, one per distinct label.
 *
 * `ldsp` and `dsp` are two enum members with one name — the workshop calls both
 * «LDSP» — so a filter listing every wire value shows the same word twice and
 * makes the reader guess which of the two is theirs. Grouping by label keeps
 * every decor reachable (each option carries all the wire values behind its
 * name, for an `in_` filter) without ever printing a choice twice.
 *
 * A function, not a constant: the labels are translated.
 */
export function decorTypeFilterGroups(): Array<{ label: string; types: DecorType[] }> {
  const groups = new Map<string, DecorType[]>()
  for (const type of DECOR_TYPES) {
    const label = decorTypeLabel(type)
    const existing = groups.get(label)
    if (existing) existing.push(type)
    else groups.set(label, [type])
  }
  return [...groups].map(([label, types]) => ({ label, types }))
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

/** The o'lcham fields of a platform format — what `formatDimensionsLabel` reads. */
export interface FormatDimensions {
  type: DecorType
  thickness_mm: string
  length_mm: number | null
  width_mm: number | null
  tape_width_mm: number | null
}

/**
 * `2800×2070×18 mm` for a panel, `0.4×19 mm` for a tape — the o'lcham alone, with
 * no identity in front of it. For the rows that sit under a decor heading
 * (the branch catalog table, the attach sheet's step two) repeating the decor
 * on every line would bury the one thing that differs between them.
 */
export function formatDimensionsLabel(format: FormatDimensions): string {
  const thickness = formatMm(format.thickness_mm)
  if (isTape(format.type)) {
    return format.tape_width_mm !== null
      ? translate('catalog.meta.tapeFormat', { thickness, width: format.tape_width_mm })
      : `${thickness} mm`
  }
  return format.length_mm !== null && format.width_mm !== null
    ? translate('catalog.meta.panelFormat', {
        length: format.length_mm,
        width: format.width_mm,
        thickness,
      })
    : `${thickness} mm`
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

export interface SheetSize {
  length: number
  width: number
}

/**
 * `{length, width}` of the sheet a snapshot describes, `0` for a slot it does
 * not carry. Mirrors `material_label.snapshot_sheet_size`.
 *
 * The single reader of the sheet-size slots, across every vocabulary in the
 * table above. Callers that *draw* the sheet must not re-implement it: a reader
 * that forgets a column does not fail, it silently returns 0 — or, worse, some
 * constant — and rescales the whole drawing with nothing to signal it.
 */
export function snapshotSheetSize(snapshot: MaterialSnapshot): SheetSize {
  return {
    length: Math.max(
      0,
      snapshotInt(snapshotValue(snapshot, 'length_mm', 'uzunlik_mm', 'panel_length_mm'), 0),
    ),
    width: Math.max(
      0,
      snapshotInt(snapshotValue(snapshot, 'width_mm', 'eni_mm', 'panel_width_mm'), 0),
    ),
  }
}

/**
 * The name slot of the base: decor code first, then whatever names exist. `name`
 * is the legacy server-generated column, gone from new snapshots; it is consulted
 * before `name` so a historical snapshot keeps rendering the string it always did.
 */
function identity(snapshot: MaterialSnapshot, decorName: string): string {
  return (
    snapshotText(snapshot, 'code', 'kod', 'decor_code') ||
    snapshotText(snapshot, 'name') ||
    decorName
  )
}

/**
 * The decor's own name — `Sonoma eman`, never the whole generated string. See
 * the `name` collision note in the module docstring for why `nomi`/`color` are
 * consulted first.
 */
function decorName(snapshot: MaterialSnapshot): string {
  return snapshotText(snapshot, 'nomi', 'color', 'name')
}

/**
 * «1 tomonlama», and only for a one-sided board. Two-sided is the norm; saying
 * so on every row would be noise, while one-sided is the exception a buyer has
 * to see. Mirrors `_ONE_SIDED_LABEL`.
 */
export function finishedSidesLabel(value: unknown): string {
  const sides = snapshotInt(value, 0)
  return sides === 1 || sides === 2 ? translate(`catalog.finishedSides.${sides}`) : ''
}

/**
 * The finished-faces note as a *display label* carries it: `1 tomonlama`, and
 * nothing at all for two.
 *
 * Two finished faces is what a board is unless someone says otherwise — it is on
 * the overwhelming majority of rows, so printing it everywhere costs width on
 * every line to say nothing, and buries the one-sided rows that are the actual
 * exception. This is the rule the canonical label has always followed (mirroring
 * `material_label.py`); it lives here so every screen composing its own string
 * follows it too. The platform's own decor-format table is the deliberate
 * exception — there the field is being *entered*, so it prints both values.
 */
export function finishedSidesNote(value: unknown): string {
  return snapshotInt(value, 0) === 1 ? finishedSidesLabel(1) : ''
}

/** Short chip text: decor code, then colour/name, then a clipped legacy name. */
export function snapshotShortLabel(snapshot: MaterialSnapshot): string {
  const code = snapshotText(snapshot, 'code', 'kod', 'decor_code')
  if (code) return code
  // Clipped: this is chip text with a fixed width. A pre-reshape snapshot puts
  // the whole GENERATED material name in `name` ("LDSP Egger H1334 Sonoma"),
  // which is what the clip was written for; a current snapshot puts the decor
  // name there, and a decor name long enough to hit 18 characters needs the
  // same treatment for the same reason.
  const name = decorName(snapshot) || snapshotText(snapshot, 'name')
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
  const type = decorTypeLabel(snapshotText(snapshot, 'type', 'tur'))
  const manufacturer = snapshotText(snapshot, 'manufacturer_name')
  const name = decorName(snapshot)
  const thickness = snapshotText(snapshot, 'thickness_mm', 'qalinlik_mm')
  const { length, width } = snapshotSheetSize(snapshot)
  const oneSided = finishedSidesNote(snapshotValue(snapshot, 'finished_sides'))

  const base = [type, manufacturer, identity(snapshot, name)].filter(Boolean).join(' ') || fallback
  const dimensions =
    length > 0 && width > 0
      ? `${length}×${width}${thickness ? `×${formatMm(thickness)}` : ''} mm`
      : thickness
        ? `${formatMm(thickness)} mm`
        : ''
  const details = [
    // Suppressed when the base already says it — «Egger Sonoma eman · Sonoma eman».
    name && !base.toLowerCase().includes(name.toLowerCase()) ? name : '',
    dimensions,
    oneSided,
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
  const name = decorName(snapshot)
  const thickness = snapshotText(snapshot, 'thickness_mm', 'qalinlik_mm')
  const width = snapshotInt(
    snapshotValue(snapshot, 'tape_width_mm', 'kromka_eni_mm', 'edge_width_mm'),
    0,
  )

  const base = [manufacturer, identity(snapshot, name)].filter(Boolean).join(' ') || fallback
  // A decor without a `code` puts `name` in the base, so the detail slot must
  // suppress it the same way snapshotMaterialLabel does.
  const detail = name && !base.toLowerCase().includes(name.toLowerCase()) ? name : ''
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
    type: option.type,
    code: option.code,
    name: option.name,
    has_grain: option.has_grain,
    thickness_mm: option.thickness_mm,
    length_mm: option.length_mm,
    width_mm: option.width_mm,
    tape_width_mm: option.tape_width_mm,
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
  return isTape(option.type)
    ? snapshotEdgeLabel(snapshot, base)
    : snapshotMaterialLabel(snapshot, base)
}

/**
 * A panel's identity without its format, e.g. `Egger H1334 ST9 · Sanoma`.
 *
 * The canonical label repeats the size, which is right where it stands alone —
 * a picker row, an order line — and wrong where the size is already on the next
 * line. The cutting editor's group header is that case: it prints
 * `2750×1830×18` right underneath.
 */
export function materialIdentityLabel(
  option: ClientCatalogMaterialOption | null | undefined,
  fallback?: string,
): string {
  if (!option) return fallback ?? translate('cutting.material.none')
  const parts = [option.manufacturer_name, option.code, option.name].filter(
    (part): part is string => Boolean(part && part.trim()),
  )
  // Spaces, not the ` · ` the canonical label uses: with the format stripped out
  // these three read as one name — `Egger H1145 Oq daraxt` — and dots between
  // them would present three separate facts.
  return parts.length > 0 ? parts.join(' ') : (fallback ?? option.id.slice(0, 8))
}
