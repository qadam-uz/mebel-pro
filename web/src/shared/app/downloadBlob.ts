import { api, type ApiRequestInit } from '@/shared/api/client'

/**
 * Fetch a file from an authed endpoint and save it to disk.
 *
 * The blob read is async, so the anchor must be attached to the DOM before the
 * click and the object URL revoked on a later tick — otherwise Firefox/Safari
 * abort the download (a detached `<a download>` click is a no-op in Firefox,
 * and a same-tick `revokeObjectURL` cancels the transfer). Throws `ApiError` on
 * a failed fetch so callers can surface feedback (CB-17/CB-111).
 */
export async function downloadBlob(path: string, filename: string, init?: ApiRequestInit) {
  const blob = await api.blob(path, init)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

/** Thrown when the browser refused the placeholder tab, so callers can say so (QAD-160). */
export class PopupBlockedError extends Error {
  constructor() {
    super('popup-blocked')
    this.name = 'PopupBlockedError'
  }
}

/**
 * Fetch a file from an authed endpoint and show it in a new tab.
 *
 * The endpoints are Bearer-authed, so a bare `window.open('/api/v1/…')` gets a
 * 401 — the blob has to be fetched with the auth header and handed to the tab
 * as an object URL. The tab must be opened *synchronously* in the click
 * handler: a `window.open` after an `await` is an unrequested popup and gets
 * blocked. The URL is revoked on a long timer because revoking while the
 * built-in viewer is still reading blanks the tab (QAD-160).
 *
 * The features string must NOT contain `noopener` — that makes `window.open`
 * return `null` by spec, so we'd lose the handle we need to navigate the tab
 * (and would misreport it as a blocked popup). The back-reference is severed
 * with `tab.opener = null` instead.
 */
export async function openBlobInNewTab(path: string, init?: ApiRequestInit) {
  const tab = window.open('', '_blank')
  if (!tab) throw new PopupBlockedError()
  tab.opener = null
  try {
    const blob = await api.blob(path, init)
    const url = URL.createObjectURL(blob)
    tab.location.href = url
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (error) {
    tab.close()
    throw error
  }
}
