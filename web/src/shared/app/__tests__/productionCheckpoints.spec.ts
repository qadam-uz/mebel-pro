import { beforeEach, describe, expect, it } from 'vitest'

import {
  clearPanelMarks,
  loadPanelMarks,
  prunePanelMarks,
  savePanelMarks,
} from '@/shared/app/productionCheckpoints'

const PREFIX = 'mp-prod-marks:v1:'
const DAY_MS = 24 * 60 * 60 * 1000

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

beforeEach(() => {
  // Node's jsdom setup can expose an incomplete localStorage shim. Use a full
  // in-memory Storage implementation so these browser-storage tests are
  // deterministic in every worker.
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: memoryStorage(),
  })
})

describe('production panel checkpoints', () => {
  it('round-trips marks for an order and keeps orders separate', () => {
    savePanelMarks('order-1', new Set(['panel-a', 'panel-b']))
    savePanelMarks('order-2', new Set(['panel-c']))

    expect([...loadPanelMarks('order-1')].sort()).toEqual(['panel-a', 'panel-b'])
    expect([...loadPanelMarks('order-2')]).toEqual(['panel-c'])
    expect(loadPanelMarks('order-3').size).toBe(0)
  })

  it('drops the key when the last mark is removed', () => {
    savePanelMarks('order-1', new Set(['panel-a']))
    savePanelMarks('order-1', new Set())

    expect(window.localStorage.getItem(`${PREFIX}order-1`)).toBeNull()
    expect(loadPanelMarks('order-1').size).toBe(0)
  })

  it('clearPanelMarks wipes a finished order only', () => {
    savePanelMarks('order-1', new Set(['panel-a']))
    savePanelMarks('order-2', new Set(['panel-b']))

    clearPanelMarks('order-1')

    expect(loadPanelMarks('order-1').size).toBe(0)
    expect([...loadPanelMarks('order-2')]).toEqual(['panel-b'])
  })

  it('survives corrupted stored values instead of throwing', () => {
    window.localStorage.setItem(`${PREFIX}order-1`, 'not json')
    window.localStorage.setItem(`${PREFIX}order-2`, JSON.stringify({ marks: 'nope', ts: 1 }))

    expect(loadPanelMarks('order-1').size).toBe(0)
    expect(loadPanelMarks('order-2').size).toBe(0)
  })

  it('prunes stale and unreadable keys but keeps fresh ones', () => {
    const now = Date.now()
    window.localStorage.setItem(
      `${PREFIX}old`,
      JSON.stringify({ marks: ['panel-a'], ts: now - 31 * DAY_MS }),
    )
    window.localStorage.setItem(
      `${PREFIX}fresh`,
      JSON.stringify({ marks: ['panel-b'], ts: now - 2 * DAY_MS }),
    )
    window.localStorage.setItem(`${PREFIX}broken`, '{')
    window.localStorage.setItem('unrelated-key', 'keep me')

    prunePanelMarks(30 * DAY_MS, now)

    expect(window.localStorage.getItem(`${PREFIX}old`)).toBeNull()
    expect(window.localStorage.getItem(`${PREFIX}broken`)).toBeNull()
    expect([...loadPanelMarks('fresh')]).toEqual(['panel-b'])
    expect(window.localStorage.getItem('unrelated-key')).toBe('keep me')
  })
})
