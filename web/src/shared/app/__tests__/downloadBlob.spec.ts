import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/shared/api/client'
import { openBlobInNewTab, PopupBlockedError } from '@/shared/app/downloadBlob'

vi.mock('@/shared/api/client', () => ({
  api: { blob: vi.fn() },
}))

function fakeTab() {
  return { location: { href: '' }, opener: {} as unknown, close: vi.fn() }
}

describe('openBlobInNewTab', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.mocked(api.blob).mockReset()
    URL.createObjectURL = vi.fn(() => 'blob:fake')
    URL.revokeObjectURL = vi.fn()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('opens the tab before awaiting the blob, then points it at the object URL', async () => {
    const tab = fakeTab()
    const open = vi.fn(() => tab)
    vi.stubGlobal('open', open)
    let resolveBlob: (blob: Blob) => void = () => {}
    vi.mocked(api.blob).mockReturnValue(
      new Promise<Blob>((resolve) => {
        resolveBlob = resolve
      }),
    )

    const pending = openBlobInNewTab('/client/cutting-results/r-1/pdf')
    // The popup must exist before the fetch settles — a `window.open` after an
    // `await` is treated as unrequested and blocked.
    // `noopener` in the features string would make window.open return null and
    // strand the placeholder tab, so it must not be passed.
    expect(open).toHaveBeenCalledWith('', '_blank')
    expect(tab.opener).toBeNull()
    resolveBlob(new Blob(['%PDF'], { type: 'application/pdf' }))
    await pending

    expect(tab.location.href).toBe('blob:fake')
    expect(tab.close).not.toHaveBeenCalled()
    expect(URL.revokeObjectURL).not.toHaveBeenCalled()
    vi.advanceTimersByTime(60_000)
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:fake')
  })

  it('throws PopupBlockedError when the browser refuses the tab', async () => {
    vi.stubGlobal(
      'open',
      vi.fn(() => null),
    )

    await expect(openBlobInNewTab('/client/cutting-results/r-1/pdf')).rejects.toBeInstanceOf(
      PopupBlockedError,
    )
    expect(api.blob).not.toHaveBeenCalled()
  })

  it('closes the placeholder tab and rethrows when the fetch fails', async () => {
    const tab = fakeTab()
    vi.stubGlobal(
      'open',
      vi.fn(() => tab),
    )
    vi.mocked(api.blob).mockRejectedValue(new Error('401'))

    await expect(openBlobInNewTab('/client/cutting-results/r-1/pdf')).rejects.toThrow('401')
    expect(tab.close).toHaveBeenCalledTimes(1)
  })
})
