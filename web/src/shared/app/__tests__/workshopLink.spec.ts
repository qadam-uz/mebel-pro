import { describe, expect, it } from 'vitest'

import { clientAppBase, workshopLinkUrl } from '@/shared/app/workshopLink'

describe('client app base', () => {
  it('swaps the workshop subdomain for the client one in production', () => {
    expect(clientAppBase('https://workshop.mebel-pro.uz', '/branches/1', false)).toBe(
      'https://app.mebel-pro.uz',
    )
  })

  it('keeps the port and scheme of a non-standard deploy', () => {
    expect(clientAppBase('http://workshop.lvh.me:8080', '/settings', false)).toBe(
      'http://app.lvh.me:8080',
    )
  })

  it('mounts the client role base in dev, where one server hosts all three apps', () => {
    expect(clientAppBase('http://localhost:5173', '/workshop/branches/1', true)).toBe(
      'http://localhost:5173/client',
    )
  })

  it('falls back to the current origin when the host is not the documented one', () => {
    expect(clientAppBase('https://mebel-pro.uz', '/branches/1', false)).toBe('https://mebel-pro.uz')
  })
})

describe('workshop link url', () => {
  it('builds the branch link the counter QR carries', () => {
    expect(
      workshopLinkUrl('ABCD2345', 3, 'https://workshop.mebel-pro.uz', '/branches/1', false),
    ).toBe('https://app.mebel-pro.uz/w/ABCD2345/3')
  })

  it('builds the workshop-level link when no branch is named', () => {
    expect(
      workshopLinkUrl('ABCD2345', null, 'https://workshop.mebel-pro.uz', '/settings', false),
    ).toBe('https://app.mebel-pro.uz/w/ABCD2345')
  })

  it('never drops branch 0 — the branch number is data, not a truthiness test', () => {
    expect(workshopLinkUrl('ABCD2345', 0, 'https://workshop.mebel-pro.uz', '/x', false)).toBe(
      'https://app.mebel-pro.uz/w/ABCD2345/0',
    )
  })
})
