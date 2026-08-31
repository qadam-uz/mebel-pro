import { beforeEach, describe, expect, it } from 'vitest'

import {
  clearClientEntry,
  pinnedWorkshopId,
  queueEntryToast,
  readClientEntry,
  scopedBranchOptions,
  storeClientEntry,
  takeEntryToast,
} from '@/shared/app/clientEntry'
import type { ClientBranchOption } from '@/shared/stores/cutting'

function option(overrides: Partial<ClientBranchOption> = {}): ClientBranchOption {
  return {
    branch_id: 'branch-1',
    workshop_id: 'workshop-1',
    workshop_name: 'Mebel Master',
    branch_name: 'Chilonzor',
    address: 'Chilonzor 12',
    status: 'active',
    closed_reason: null,
    kerf_mm: 4,
    edge_trim_mm: 5,
    ...overrides,
  }
}

/** A Storage that throws on every call — Safari private mode, blocked site data. */
function refusingStorage(): Storage {
  const refuse = () => {
    throw new Error('storage refused')
  }
  return {
    get length(): number {
      return refuse()
    },
    clear: refuse,
    getItem: refuse,
    key: refuse,
    removeItem: refuse,
    setItem: refuse,
  } as unknown as Storage
}

describe('stored client entry', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('round-trips the scanned entry through localStorage', () => {
    storeClientEntry({ code: 'ABCD2345', branch_id: 'branch-9' })

    expect(readClientEntry()).toEqual({ code: 'ABCD2345', branch_id: 'branch-9' })
    expect(window.localStorage.getItem('client.entry')).toBeTruthy()
  })

  it('survives a page load — a fresh read sees what a previous page wrote', () => {
    storeClientEntry({ code: 'ABCD2345', branch_id: 'branch-9' })

    // What the login round-trip does: nothing but reload. The value is read back
    // out of the same Storage the next page gets.
    expect(readClientEntry(window.localStorage)).toEqual({
      code: 'ABCD2345',
      branch_id: 'branch-9',
    })
  })

  it('clears the entry once it is applied', () => {
    storeClientEntry({ code: 'ABCD2345', branch_id: 'branch-9' })
    clearClientEntry()

    expect(readClientEntry()).toBeNull()
  })

  it('treats absent, malformed and foreign values as no entry', () => {
    expect(readClientEntry()).toBeNull()

    window.localStorage.setItem('client.entry', 'not json')
    expect(readClientEntry()).toBeNull()

    window.localStorage.setItem('client.entry', JSON.stringify({ code: 'ABCD2345' }))
    expect(readClientEntry()).toBeNull()

    window.localStorage.setItem('client.entry', JSON.stringify({ code: '', branch_id: '' }))
    expect(readClientEntry()).toBeNull()
  })

  it('degrades to an un-pinned login when storage refuses', () => {
    const storage = refusingStorage()

    expect(() => storeClientEntry({ code: 'A', branch_id: 'b' }, storage)).not.toThrow()
    expect(readClientEntry(storage)).toBeNull()
    expect(() => clearClientEntry(storage)).not.toThrow()
  })
})

describe('connected toast', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('is one-time: the second read finds nothing', () => {
    queueEntryToast('Mebel Master')

    expect(takeEntryToast()).toBe('Mebel Master')
    expect(takeEntryToast()).toBeNull()
  })

  it('shows again after a re-scan, because a re-scan queues it again', () => {
    queueEntryToast('Mebel Master')
    expect(takeEntryToast()).toBe('Mebel Master')

    queueEntryToast('Mebel Master')
    expect(takeEntryToast()).toBe('Mebel Master')
  })
})

describe('editor picker scoping', () => {
  const options = [
    option({ branch_id: 'b1', workshop_id: 'w1', workshop_name: 'Mebel Master' }),
    option({ branch_id: 'b2', workshop_id: 'w1', workshop_name: 'Mebel Master' }),
    option({ branch_id: 'b3', workshop_id: 'w2', workshop_name: 'Yog’och Pro' }),
  ]

  it('derives the pinned workshop from the pinned branch', () => {
    expect(pinnedWorkshopId(options, 'b2', 'Mebel Master')).toBe('w1')
  })

  it('falls back to the workshop name when the pinned branch went invisible', () => {
    // §8: the pin is not scope-enforced, and the workshop's other visible
    // branches must stay on offer.
    expect(pinnedWorkshopId(options, 'gone-branch', 'Mebel Master')).toBe('w1')
  })

  it('reports no pin when the principal carries no pinned workshop name', () => {
    // Covers the un-pinned client AND the pinned-but-blocked workshop, which the
    // backend reports the same way.
    expect(pinnedWorkshopId(options, 'b2', null)).toBeNull()
    expect(pinnedWorkshopId(options, null, null)).toBeNull()
  })

  it('offers only the pinned workshop, and everything when unpinned', () => {
    expect(scopedBranchOptions(options, 'w1').map((row) => row.branch_id)).toEqual(['b1', 'b2'])
    expect(scopedBranchOptions(options, null)).toHaveLength(3)
  })

  it('offers nothing rather than every workshop when the pin has no visible branch', () => {
    expect(scopedBranchOptions(options, 'w9')).toEqual([])
  })
})
