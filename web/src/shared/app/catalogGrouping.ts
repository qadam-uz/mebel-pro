/**
 * How the Materiallar table breaks a flat page of branch materials into the two
 * levels a reader actually scans: **manufacturer**, then **decor**.
 *
 * The server already orders rows `Manufacturer.name, Decor.name, thickness`
 * (catalog `service.py`), and the table still read «aralash» (owner,
 * 2026-09-07) — because nothing on screen broke between one brand and the next,
 * and every decor label repeated the manufacturer that was already implied. So
 * the break is drawn here, on the page in hand: the server order stays exactly
 * as it is and this module only decides where the section rows go.
 *
 * **Runs, not buckets.** A section starts whenever the manufacturer changes
 * between two consecutive rows, and a decor group whenever the decor does.
 * Bucketing by id would merge two runs the server deliberately left apart —
 * and, worse, would repeat a manufacturer's header after a "load more" that
 * split its rows across two pages. A run survives the page boundary because the
 * next page continues the order the last one ended on.
 */

import { isTape } from '@/shared/app/materialLabel'
import type { Decor } from '@/shared/stores/admin'

/** The fields this module reads off a row — anything carrying them will do. */
export interface GroupableMaterial {
  id: string
  decor: Decor
  /** The decor is this workshop's own, not a library one. */
  decor_own: boolean
  decor_format: { decor_id: string; type: string; thickness_mm: string }
}

export interface CatalogDecorGroup<T extends GroupableMaterial> {
  decor: Decor
  /** Own decors carry the «Sizniki» chip and the ⋯ «Dekorni tahrirlash» item. */
  own: boolean
  rows: T[]
}

export interface CatalogSection<T extends GroupableMaterial> {
  manufacturerId: string
  manufacturerName: string
  /** Decors under this heading, on this page. */
  decorCount: number
  /** O'lchamlar under this heading, on this page. */
  formatCount: number
  groups: CatalogDecorGroup<T>[]
}

/**
 * Boards before kromka, then by thickness.
 *
 * A decor's tape is the accessory to its boards, so it belongs at the foot of
 * the group rather than sorted into the middle of it by a thickness (0.8 mm)
 * that means something entirely different from a board's.
 */
export function sortDecorFormats<T extends GroupableMaterial>(rows: T[]): T[] {
  return [...rows].sort((left, right) => {
    const leftTape = isTape(left.decor_format.type as never) ? 1 : 0
    const rightTape = isTape(right.decor_format.type as never) ? 1 : 0
    if (leftTape !== rightTape) return leftTape - rightTape
    const leftThickness = Number(left.decor_format.thickness_mm)
    const rightThickness = Number(right.decor_format.thickness_mm)
    if (Number.isFinite(leftThickness) && Number.isFinite(rightThickness)) {
      if (leftThickness !== rightThickness) return leftThickness - rightThickness
    }
    return left.id.localeCompare(right.id)
  })
}

/** The page in hand, cut into manufacturer sections and decor groups. */
export function catalogSections<T extends GroupableMaterial>(rows: T[]): CatalogSection<T>[] {
  const sections: CatalogSection<T>[] = []
  for (const row of rows) {
    let section = sections[sections.length - 1]
    if (!section || section.manufacturerId !== row.decor.manufacturer_id) {
      section = {
        manufacturerId: row.decor.manufacturer_id,
        manufacturerName: row.decor.manufacturer_name,
        decorCount: 0,
        formatCount: 0,
        groups: [],
      }
      sections.push(section)
    }
    let group = section.groups[section.groups.length - 1]
    if (!group || group.decor.id !== row.decor_format.decor_id) {
      group = { decor: row.decor, own: row.decor_own, rows: [] }
      section.groups.push(group)
      section.decorCount += 1
    }
    group.rows.push(row)
    section.formatCount += 1
  }
  for (const section of sections) {
    for (const group of section.groups) group.rows = sortDecorFormats(group.rows)
  }
  return sections
}

export interface ManufacturerChip {
  /** `'all'` for «Barchasi»; otherwise the manufacturer id the filter sends. */
  value: string
  label: string
  /** Distinct decors behind the chip, on the page in hand. */
  count: number
}

/**
 * The chip row under the filter bar: «Barchasi 7 · Egger 3 · Kastamonu 2».
 *
 * Counts are decors, not o'lchamlar — the row answers "whose materials do I
 * carry", and a brand with one decor in four thicknesses is one entry in that
 * answer, not four. Derived from the same page the table draws, so the number
 * beside a chip is always the number of rows pressing it will leave on screen.
 */
export function manufacturerChips<T extends GroupableMaterial>(
  rows: T[],
  allLabel: string,
): ManufacturerChip[] {
  const byManufacturer = new Map<string, { label: string; decors: Set<string> }>()
  const decors = new Set<string>()
  for (const row of rows) {
    decors.add(row.decor.id)
    const existing = byManufacturer.get(row.decor.manufacturer_id)
    if (existing) existing.decors.add(row.decor.id)
    else {
      byManufacturer.set(row.decor.manufacturer_id, {
        label: row.decor.manufacturer_name,
        decors: new Set([row.decor.id]),
      })
    }
  }
  // A single brand makes the row a control that cannot narrow anything — the
  // same rule the manufacturer dropdown already follows.
  if (byManufacturer.size < 2) return []
  return [
    { value: 'all', label: allLabel, count: decors.size },
    ...[...byManufacturer.entries()]
      .map(([value, entry]) => ({ value, label: entry.label, count: entry.decors.size }))
      .sort((left, right) => left.label.localeCompare(right.label)),
  ]
}
