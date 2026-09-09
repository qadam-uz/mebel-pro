/**
 * The standard thickness / size chips the **platform's** format-create form
 * offers per `type`.
 *
 * These used to be the branch attach sheet's suggestions, back when a format was
 * a branch fact. It is a platform fact now: only a superadmin creates formats,
 * and a branch picks from what exists. So the same lists moved one screen up and
 * became quick-fill for the admin form — they prefill the thickness and size
 * fields of a new `decor_format`, and anything unusual is still typed by hand.
 *
 * Still hard-coded in the web app rather than served: they are a typing
 * shortcut, not data. There is no settings knob and no endpoint for them.
 *
 * Thicknesses are decimal STRINGS, matching `thickness_mm` on the wire (a
 * Decimal). Compare them through `normalizeThickness`, never with `===` on the
 * raw text: `"18"`, `"18.0"` and `"18.00"` are the same format.
 */

import { formatMm } from '@/shared/app/materialLabel'
import type { DecorType } from '@/shared/stores/admin'

/** A panel-shaped size chip. Always normalized so `length_mm >= width_mm`. */
export interface StandardPanelSize {
  length_mm: number
  width_mm: number
}

/** The chips offered for one `type`: thicknesses on one axis, sizes on the other. */
export interface StandardFormatSet {
  /** Decimal strings, ascending. */
  qalinliklar: readonly string[]
  /** Panel-shaped types only — empty for kromka. */
  olchamlar: readonly StandardPanelSize[]
  /** Kromka only — tape widths in mm, empty for panel-shaped types. */
  kromkaEnlar: readonly number[]
}

const EMPTY_SET: StandardFormatSet = { qalinliklar: [], olchamlar: [], kromkaEnlar: [] }

const PANEL_SET = (
  qalinliklar: readonly string[],
  olchamlar: readonly StandardPanelSize[],
): StandardFormatSet => ({ qalinliklar, olchamlar, kromkaEnlar: [] })

const LDSP_SET = PANEL_SET(
  ['10', '16', '18', '25'],
  [
    { length_mm: 2750, width_mm: 1830 },
    { length_mm: 2800, width_mm: 2070 },
    { length_mm: 2440, width_mm: 1830 },
  ],
)

/**
 * Standard format chips per `type`.
 *
 * `yogoch` and `boshqa` deliberately carry no standard set: there is no common
 * sheet size for solid timber or for the "everything else" bucket, and inventing
 * one would offer the operator a number no manufacturer actually makes. Those
 * two are typed in full.
 */
const MDF_SET = PANEL_SET(
  ['3', '8', '16', '18'],
  [
    { length_mm: 2800, width_mm: 2070 },
    { length_mm: 2440, width_mm: 1220 },
  ],
)

export const STANDARD_FORMATS: Readonly<Record<DecorType, StandardFormatSet>> = {
  ldsp: LDSP_SET,
  // DSP is the same sheet geometry as LDSP without the laminate, so the chips
  // are shared even though the two are different products at different prices.
  dsp: LDSP_SET,
  mdf: MDF_SET,
  // Same board, laminated — the press does not change what the mill cut, so
  // LMDF is offered the MDF thicknesses and sheet sizes (2026-09-08).
  lmdf: MDF_SET,
  fanera: PANEL_SET(
    ['4', '6', '9', '12', '18'],
    [
      { length_mm: 2440, width_mm: 1220 },
      { length_mm: 1525, width_mm: 1525 },
    ],
  ),
  yogoch: EMPTY_SET,
  kromka: { qalinliklar: ['0.4', '0.8', '1', '2'], olchamlar: [], kromkaEnlar: [19, 22, 35, 42] },
  boshqa: EMPTY_SET,
}

export function standardFormatSet(type: DecorType): StandardFormatSet {
  return STANDARD_FORMATS[type] ?? EMPTY_SET
}

/**
 * Canonical thickness text for comparison and for the wire: `18.0` → `18`,
 * `0.40` → `0.4`. Two formats are the same only if their normalized
 * thicknesses are equal.
 */
export function normalizeThickness(value: unknown): string {
  return formatMm(value)
}

/** Longer side first, so `1830×2750` and `2750×1830` are one chip, not two. */
export function normalizePanelSize(a: number, b: number): StandardPanelSize {
  return a >= b ? { length_mm: a, width_mm: b } : { length_mm: b, width_mm: a }
}

/**
 * One composed o'lcham on its way to `POST …/catalog/decors[/{id}/formats]`.
 *
 * The same shape the wire takes (`DecorFormatCreateRequest`), spelled out here
 * so the chip block, the pending list and the payload are one object rather
 * than three that can drift.
 */
export interface FormatDraft {
  type: DecorType
  /** Decimal string, already normalized. */
  thickness_mm: string
  length_mm: number | null
  width_mm: number | null
  tape_width_mm: number | null
  finished_sides: number | null
}

/**
 * Identity of a draft — every field that makes it a different product.
 *
 * Both halves of the duplicate rule read it: the pending list refuses a second
 * copy of a shape, and the sheet's «+ Boshqa o'lcham» matches a 409 twin back
 * to the row already on screen.
 */
export function formatDraftKey(draft: FormatDraft): string {
  return [
    draft.type,
    normalizeThickness(draft.thickness_mm),
    draft.length_mm,
    draft.width_mm,
    draft.tape_width_mm,
    draft.finished_sides,
  ]
    .map((part) => String(part ?? ''))
    .join('|')
}

/**
 * `18 mm · 2800×2070`, `0.8 mm · 22 mm`, plus «1 tomonlama» when it applies.
 *
 * Thickness first, unlike the canonical `formatDimensionsLabel` — here the row
 * is being *composed* from a thickness chip and a size chip, so it reads back
 * in the order it was picked. `oneSided` is the caller's translated note; the
 * module stays i18n-free so it can be unit-tested without a locale.
 */
export function formatDraftLabel(draft: FormatDraft, oneSided = ''): string {
  const thickness = `${normalizeThickness(draft.thickness_mm)} mm`
  const size =
    draft.type === 'kromka'
      ? draft.tape_width_mm !== null
        ? `${draft.tape_width_mm} mm`
        : ''
      : draft.length_mm !== null && draft.width_mm !== null
        ? `${draft.length_mm}×${draft.width_mm}`
        : ''
  const note = draft.finished_sides === 1 ? oneSided : ''
  return [thickness, size, note].filter(Boolean).join(' · ')
}

/**
 * Types whose sheets have a finished-face count — the **laminated** boards, and
 * only those two (2026-09-08, owner review).
 *
 * A finished face is the laminate, so counting them on a bare DSP or MDF panel
 * was asking about a surface that does not exist: both faces are raw chipboard.
 * Everything else (dsp, mdf, fanera, yog'och, kromka, boshqa) carries `null`,
 * which `validate_decor_format_shape` and the `ck_decor_formats_shape` CHECK
 * now enforce.
 */
export function hasFinishedSides(type: DecorType): boolean {
  return type === 'ldsp' || type === 'lmdf'
}
