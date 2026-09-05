import { beforeEach, describe, expect, it } from 'vitest'

import {
  clearClientEntry,
  queueEntryToast,
  readClientEntry,
  storeClientEntry,
  takeEntryToast,
} from '@/shared/app/clientEntry'

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

    window.localStorage.setItem('client.entry', JSON.stringify({ code: '', branch_id: '' }))
    expect(readClientEntry()).toBeNull()

    window.localStorage.setItem('client.entry', JSON.stringify({ code: 'ABCD2345', branch_id: 7 }))
    expect(readClientEntry()).toBeNull()
  })

  // A branchless entry is a real one (spec §2.2): a multi-branch workshop link
  // records the workshop and pins nothing, and that has to survive the login
  // round-trip exactly as a branch QR does.
  it('keeps an entry that names no branch', () => {
    storeClientEntry({ code: 'ABCD2345', branch_id: null })
    expect(readClientEntry()).toEqual({ code: 'ABCD2345', branch_id: null })

    window.localStorage.setItem('client.entry', JSON.stringify({ code: 'ABCD2345' }))
    expect(readClientEntry()).toEqual({ code: 'ABCD2345', branch_id: null })
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
