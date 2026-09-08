import { describe, expect, it } from 'vitest'

import {
  catalogSections,
  manufacturerChips,
  sortDecorFormats,
  type GroupableMaterial,
} from '@/shared/app/catalogGrouping'
import type { Decor } from '@/shared/stores/admin'

function decor(id: string, manufacturerId: string, manufacturerName: string): Decor {
  return {
    id,
    manufacturer_id: manufacturerId,
    manufacturer_name: manufacturerName,
    code: id.toUpperCase(),
    name: id,
    has_grain: false,
    image_file_id: null,
    status: 'active',
    label: `${manufacturerName} ${id}`,
    branch_usage_count: 0,
    format_count: 1,
    own: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }
}

function row(
  id: string,
  decorRow: Decor,
  format: { type: string; thickness_mm: string },
  own = false,
): GroupableMaterial {
  return {
    id,
    decor: decorRow,
    decor_own: own,
    decor_format: { decor_id: decorRow.id, ...format },
  }
}

const board = (thickness = '18') => ({ type: 'ldsp', thickness_mm: thickness })
const tape = () => ({ type: 'kromka', thickness_mm: '0.8' })

describe('Materiallar sections', () => {
  it('opens a section whenever the manufacturer changes between consecutive rows', () => {
    const egger = decor('h1145', 'm-egger', 'Egger')
    const kastamonu = decor('a101', 'm-kastamonu', 'Kastamonu')
    const sections = catalogSections([
      row('r1', egger, board()),
      row('r2', egger, board('16')),
      row('r3', kastamonu, board()),
    ])

    expect(sections.map((section) => section.manufacturerName)).toEqual(['Egger', 'Kastamonu'])
    expect(sections[0].decorCount).toBe(1)
    expect(sections[0].formatCount).toBe(2)
    expect(sections[1].formatCount).toBe(1)
  })

  it('does not repeat a manufacturer heading when a page boundary falls inside it', () => {
    // "Load more" appends the next page in the same server order, so a brand
    // split across two pages arrives as consecutive rows and must stay ONE
    // section — a bucket-by-id grouping would look identical here, but a
    // change-detected header emitted per page would print «Egger» twice.
    const egger = decor('h1145', 'm-egger', 'Egger')
    const eggerTwo = decor('w980', 'm-egger', 'Egger')
    const pageOne = [row('r1', egger, board())]
    const pageTwo = [row('r2', eggerTwo, board())]

    const sections = catalogSections([...pageOne, ...pageTwo])
    expect(sections).toHaveLength(1)
    expect(sections[0].decorCount).toBe(2)
    expect(sections[0].groups.map((group) => group.decor.id)).toEqual(['h1145', 'w980'])
  })

  it('flags an own decor on its group, so only that header wears «Sizniki»', () => {
    const library = decor('h1145', 'm-egger', 'Egger')
    const mine = decor('oq', 'm-kastamonu', 'Kastamonu')
    const sections = catalogSections([row('r1', library, board()), row('r2', mine, board(), true)])
    expect(sections.map((section) => section.groups[0].own)).toEqual([false, true])
  })

  it('puts a decor’s kromka after its boards, then sorts by thickness', () => {
    const egger = decor('h1145', 'm-egger', 'Egger')
    const sorted = sortDecorFormats([
      row('tape', egger, tape()),
      row('thick', egger, board('18')),
      row('thin', egger, board('16')),
    ])
    // Thickness alone would file 0.8 mm of tape between nothing and 16 mm of
    // board — two numbers that do not measure the same kind of thing.
    expect(sorted.map((entry) => entry.id)).toEqual(['thin', 'thick', 'tape'])
  })
})

describe('manufacturer chips', () => {
  it('counts decors, not o‘lchamlar, and leads with «Barchasi»', () => {
    const egger = decor('h1145', 'm-egger', 'Egger')
    const eggerTwo = decor('w980', 'm-egger', 'Egger')
    const kastamonu = decor('a101', 'm-kastamonu', 'Kastamonu')
    const chips = manufacturerChips(
      [
        row('r1', egger, board()),
        row('r2', egger, board('16')),
        row('r3', eggerTwo, board()),
        row('r4', kastamonu, board()),
      ],
      'Barchasi',
    )

    expect(chips).toEqual([
      { value: 'all', label: 'Barchasi', count: 3 },
      { value: 'm-egger', label: 'Egger', count: 2 },
      { value: 'm-kastamonu', label: 'Kastamonu', count: 1 },
    ])
  })

  it('shows no row at all when the branch carries one brand', () => {
    const egger = decor('h1145', 'm-egger', 'Egger')
    // «Barchasi» plus one chip is a control that cannot narrow anything.
    expect(manufacturerChips([row('r1', egger, board())], 'Barchasi')).toEqual([])
  })
})
