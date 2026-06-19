import { describe, expect, it } from 'vitest'

import { firstEnabledIndex, nextStableId } from '@/shared/app/listboxNav'
import type { ChoiceOption } from '@/shared/components/controlTypes'

const opt = (value: string, disabled = false): ChoiceOption => ({ value, label: value, disabled })

describe('firstEnabledIndex (CB-96 keyboard nav skips disabled)', () => {
  const options = [opt('a'), opt('b', true), opt('c'), opt('d', true)]

  it('returns the start index when it is enabled', () => {
    expect(firstEnabledIndex(options, 0, 1)).toBe(0)
    expect(firstEnabledIndex(options, 2, 1)).toBe(2)
  })

  it('skips disabled options moving forward, wrapping around', () => {
    expect(firstEnabledIndex(options, 1, 1)).toBe(2) // b disabled → c
    expect(firstEnabledIndex(options, 3, 1)).toBe(0) // d disabled → wrap to a
  })

  it('skips disabled options moving backward', () => {
    expect(firstEnabledIndex(options, 3, -1)).toBe(2) // d disabled → c
    expect(firstEnabledIndex(options, 1, -1)).toBe(0) // b disabled → a
  })

  it('returns -1 when every option is disabled or the list is empty', () => {
    expect(firstEnabledIndex([opt('x', true), opt('y', true)], 0, 1)).toBe(-1)
    expect(firstEnabledIndex([], 0, 1)).toBe(-1)
  })
})

describe('nextStableId (CB-96)', () => {
  it('returns prefixed, unique, collision-free ids', () => {
    const a = nextStableId('mp-x')
    const b = nextStableId('mp-x')
    expect(a).toMatch(/^mp-x-\d+$/)
    expect(a).not.toBe(b)
  })
})
