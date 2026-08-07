/**
 * The standard thickness / size chip sets the attach sheet offers per `tur`, and
 * the helpers that derive a branch's own **non-standard** formats from its rows.
 *
 * Hard-coded in the web app on purpose. A format is a branch fact, not a platform
 * one — the backend deliberately stopped enumerating thicknesses
 * (`BranchCatalogFiltersResponse` is manufacturers-only) because a platform
 * operator cannot know what a given workshop's supplier sells. These lists are
 * *suggestions* that cover the common case; anything else the branch types in with
 * "+ qo'shish" and it simply becomes that branch's row. There is no settings knob
 * and no endpoint for them.
 *
 * Thicknesses are decimal STRINGS, matching `qalinlik_mm` on the wire (a Decimal).
 * Compare them through `normalizeQalinlik`, never with `===` on the raw text:
 * `"18"`, `"18.0"` and `"18.00"` are the same format.
 */

import { formatMm, isTape } from '@/shared/app/materialLabel'
import type { DekorType } from '@/shared/stores/admin'
import type { BranchMaterial } from '@/shared/stores/workshop'

/** A panel-shaped size chip. Always normalized so `uzunlik_mm >= eni_mm`. */
export interface StandardPanelSize {
  uzunlik_mm: number
  eni_mm: number
}

/** The chips offered for one `tur`: thicknesses on one axis, sizes on the other. */
export interface StandardFormatSet {
  /** Decimal strings, ascending. */
  qalinliklar: readonly string[]
  /** Panel-shaped turlar only — empty for kromka. */
  olchamlar: readonly StandardPanelSize[]
  /** Kromka only — tape widths in mm, empty for panel-shaped turlar. */
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
    { uzunlik_mm: 2750, eni_mm: 1830 },
    { uzunlik_mm: 2800, eni_mm: 2070 },
    { uzunlik_mm: 2440, eni_mm: 1830 },
  ],
)

/**
 * Standard format chips per `tur`.
 *
 * `yogoch` and `boshqa` deliberately carry no standard set: there is no common
 * sheet size for solid timber or for the "everything else" bucket, and inventing
 * one would prefill the table with formats no branch actually stocks. Those two
 * are entered through "+ qo'shish" alone.
 */
export const STANDARD_FORMATS: Readonly<Record<DekorType, StandardFormatSet>> = {
  ldsp: LDSP_SET,
  dsp: LDSP_SET,
  mdf: PANEL_SET(
    ['3', '8', '16', '18'],
    [
      { uzunlik_mm: 2800, eni_mm: 2070 },
      { uzunlik_mm: 2440, eni_mm: 1220 },
    ],
  ),
  fanera: PANEL_SET(
    ['4', '6', '9', '12', '18'],
    [
      { uzunlik_mm: 2440, eni_mm: 1220 },
      { uzunlik_mm: 1525, eni_mm: 1525 },
    ],
  ),
  yogoch: EMPTY_SET,
  kromka: { qalinliklar: ['0.4', '0.8', '1', '2'], olchamlar: [], kromkaEnlar: [19, 22, 35, 42] },
  boshqa: EMPTY_SET,
}

export function standardFormatSet(tur: DekorType): StandardFormatSet {
  return STANDARD_FORMATS[tur] ?? EMPTY_SET
}

/**
 * Canonical thickness text for comparison and for the wire: `18.0` → `18`,
 * `0.40` → `0.4`. Two rows are the same format only if their normalized
 * thicknesses are equal.
 */
export function normalizeQalinlik(value: unknown): string {
  return formatMm(value)
}

/** Longer side first, so `1830×2750` and `2750×1830` are one chip, not two. */
export function normalizePanelSize(a: number, b: number): StandardPanelSize {
  return a >= b ? { uzunlik_mm: a, eni_mm: b } : { uzunlik_mm: b, eni_mm: a }
}

/**
 * A stable string key for one (thickness + size) combination, used to dedupe
 * chips, to disable already-carried cells in the cross product, and to match the
 * `skipped` format keys the attach response returns (a `BranchMaterialFormatKey`
 * satisfies this parameter structurally).
 */
export function formatKey(format: {
  qalinlik_mm: unknown
  uzunlik_mm?: number | null
  eni_mm?: number | null
  kromka_eni_mm?: number | null
}): string {
  const size =
    format.uzunlik_mm != null && format.eni_mm != null
      ? (({ uzunlik_mm, eni_mm }) => `${uzunlik_mm}x${eni_mm}`)(
          normalizePanelSize(format.uzunlik_mm, format.eni_mm),
        )
      : ''
  return `${normalizeQalinlik(format.qalinlik_mm)}|${size}|${format.kromka_eni_mm ?? ''}`
}

/** The keys of every format of `dekorId` this branch already carries. */
export function carriedFormatKeys(rows: readonly BranchMaterial[], dekorId: string): Set<string> {
  return new Set(rows.filter((row) => row.dekor_id === dekorId).map((row) => formatKey(row)))
}

/**
 * The distinct facet values a branch already uses for one dekor — the raw input
 * for its "Nostandart · faqat sizda" chips.
 */
export function branchFormatFacets(
  rows: readonly BranchMaterial[],
  dekorId: string,
): StandardFormatSet {
  const mine = rows.filter((row) => row.dekor_id === dekorId)
  const qalinliklar = [...new Set(mine.map((row) => normalizeQalinlik(row.qalinlik_mm)))]
    .filter(Boolean)
    .sort((left, right) => Number(left) - Number(right))
  const olchamlar = new Map<string, StandardPanelSize>()
  for (const row of mine) {
    if (row.uzunlik_mm == null || row.eni_mm == null) continue
    const size = normalizePanelSize(row.uzunlik_mm, row.eni_mm)
    olchamlar.set(`${size.uzunlik_mm}x${size.eni_mm}`, size)
  }
  const kromkaEnlar = [
    ...new Set(
      mine.map((row) => row.kromka_eni_mm).filter((value): value is number => value != null),
    ),
  ].sort((left, right) => left - right)
  return { qalinliklar, olchamlar: [...olchamlar.values()], kromkaEnlar }
}

/**
 * The branch's own facets minus the standard ones — the "Nostandart · faqat
 * sizda" group. Empty when the branch only uses standard formats, which is the
 * common case and the reason the group is rendered separately rather than merged.
 */
export function nonStandardFacets(
  tur: DekorType,
  rows: readonly BranchMaterial[],
  dekorId: string,
): StandardFormatSet {
  const standard = standardFormatSet(tur)
  const mine = branchFormatFacets(rows, dekorId)
  const standardThickness = new Set(standard.qalinliklar.map(normalizeQalinlik))
  const standardSizes = new Set(
    standard.olchamlar.map((size) => `${size.uzunlik_mm}x${size.eni_mm}`),
  )
  const standardWidths = new Set(standard.kromkaEnlar)
  return {
    qalinliklar: mine.qalinliklar.filter((value) => !standardThickness.has(value)),
    olchamlar: isTape(tur)
      ? []
      : mine.olchamlar.filter((size) => !standardSizes.has(`${size.uzunlik_mm}x${size.eni_mm}`)),
    kromkaEnlar: isTape(tur) ? mine.kromkaEnlar.filter((value) => !standardWidths.has(value)) : [],
  }
}
