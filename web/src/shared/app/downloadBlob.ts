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
