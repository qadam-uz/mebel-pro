import { beforeEach, describe, expect, it } from 'vitest'

import {
  clearStaleChunkMark,
  isStaleChunkError,
  staleChunkRecovery,
} from '@/shared/app/createRoleApp'

function memoryStorage(): Storage {
  const values = new Map<string, string>()
  return {
    get length() {
      return values.size
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, String(value)),
  }
}

let storage: Storage

beforeEach(() => {
  storage = memoryStorage()
})

describe('isStaleChunkError', () => {
  // One failure, three wordings and no error code between them — the whole
  // recovery hangs off matching all three.
  it('recognises the message every engine uses for a dead route chunk', () => {
    expect(
      isStaleChunkError(
        new TypeError(
          'Failed to fetch dynamically imported module: https://x/assets/WorkshopProductionView-CK.js',
        ),
      ),
    ).toBe(true)
    expect(isStaleChunkError(new TypeError('error loading dynamically imported module'))).toBe(true)
    expect(isStaleChunkError(new TypeError('Importing a module script failed.'))).toBe(true)
  })

  it('leaves every other failure alone', () => {
    expect(isStaleChunkError(new Error('Network request failed'))).toBe(false)
    expect(isStaleChunkError(new Error('Route guard called next() without declaring it'))).toBe(
      false,
    )
    expect(isStaleChunkError(undefined)).toBe(false)
  })
})

describe('staleChunkRecovery', () => {
  it('recovers to the route the operator actually clicked, not to where they were', () => {
    const error = new TypeError('Failed to fetch dynamically imported module: /assets/x.js')
    expect(staleChunkRecovery(error, '/workshop/cutting', storage)).toBe('/workshop/cutting')
  })

  it('ignores a failure that is not a dead chunk', () => {
    expect(staleChunkRecovery(new Error('boom'), '/workshop/cutting', storage)).toBeNull()
  })

  it('reloads once per target — a chunk still missing after that is a broken deploy', () => {
    const error = new TypeError('Failed to fetch dynamically imported module: /assets/x.js')
    expect(staleChunkRecovery(error, '/workshop/cutting', storage)).toBe('/workshop/cutting')
    expect(staleChunkRecovery(error, '/workshop/cutting', storage)).toBeNull()
  })

  it('still recovers a different target while one is marked', () => {
    const error = new TypeError('Failed to fetch dynamically imported module: /assets/x.js')
    staleChunkRecovery(error, '/workshop/cutting', storage)
    expect(staleChunkRecovery(error, '/workshop/inventory', storage)).toBe('/workshop/inventory')
  })

  it('arms again once a navigation lands, so the next deploy also recovers', () => {
    const error = new TypeError('Failed to fetch dynamically imported module: /assets/x.js')
    staleChunkRecovery(error, '/workshop/cutting', storage)
    clearStaleChunkMark(storage)
    expect(staleChunkRecovery(error, '/workshop/cutting', storage)).toBe('/workshop/cutting')
  })
})
