import { describe, expect, it } from 'vitest'

import { safeRedirectPath } from '@/shared/app/redirect'

describe('safeRedirectPath', () => {
  const fallback = '/c'

  it('keeps same-origin absolute paths', () => {
    expect(safeRedirectPath('/c/orders', fallback)).toBe('/c/orders')
    expect(safeRedirectPath('/workshop/finance/expenses', fallback)).toBe(
      '/workshop/finance/expenses',
    )
  })

  it('rejects off-origin, scheme, and non-path targets, falling back', () => {
    expect(safeRedirectPath('//evil.com', fallback)).toBe(fallback)
    expect(safeRedirectPath('/\\evil.com', fallback)).toBe(fallback)
    expect(safeRedirectPath('https://evil.com', fallback)).toBe(fallback)
    expect(safeRedirectPath('javascript:alert(1)', fallback)).toBe(fallback)
    expect(safeRedirectPath('evil.com', fallback)).toBe(fallback)
    expect(safeRedirectPath('', fallback)).toBe(fallback)
    expect(safeRedirectPath(undefined, fallback)).toBe(fallback)
    expect(safeRedirectPath(['/c'], fallback)).toBe(fallback)
  })
})
