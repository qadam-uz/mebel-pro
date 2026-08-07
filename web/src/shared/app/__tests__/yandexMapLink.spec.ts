import { describe, expect, it } from 'vitest'

import { yandexMapUrl } from '@/shared/app/yandexMapLink'

describe('yandexMapUrl', () => {
  // Yandex takes longitude first; the branch record stores latitude first. A
  // swap here opens the map in the wrong hemisphere.
  it('centres and pins the same point, longitude first', () => {
    expect(yandexMapUrl(41.311081, 69.240562)).toBe(
      'https://yandex.uz/maps/?ll=69.240562%2C41.311081&z=17&pt=69.240562%2C41.311081',
    )
  })

  it('accepts the decimal strings the API returns', () => {
    expect(yandexMapUrl('41.31', '69.24')).toContain('ll=69.24%2C41.31')
  })

  it('returns null when the branch has no pin', () => {
    expect(yandexMapUrl(null, null)).toBeNull()
    expect(yandexMapUrl(41.3, null)).toBeNull()
    expect(yandexMapUrl('abc', 'def')).toBeNull()
  })
})
