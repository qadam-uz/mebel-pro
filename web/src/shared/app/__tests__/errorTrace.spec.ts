import { describe, expect, it } from 'vitest'

import { traceLine, traceSuffix } from '@/shared/app/errorTrace'

describe('error trace display', () => {
  it('shows the trace when the backend answered', () => {
    expect(traceLine('ab12cd34')).toBe('trace_id: ab12cd34')
    expect(traceSuffix('ab12cd34')).toBe(' · trace_id: ab12cd34')
  })

  it('names the connection cause instead of "unavailable" when the backend never answered', () => {
    expect(traceLine(null)).toBe("Serverga ulanib bo'lmadi")
    expect(traceLine(undefined)).toBe("Serverga ulanib bo'lmadi")
  })

  it('stays silent inline without a trace — the error may be local validation', () => {
    expect(traceSuffix(null)).toBe('')
    expect(traceSuffix(undefined)).toBe('')
  })
})
