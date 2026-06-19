// Small clipboard helper (AB-03 one-time-secret copy). Returns whether the copy
// succeeded so the caller can toast success/failure rather than assume it worked.
export async function copyText(text: string): Promise<boolean> {
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // Permission denied / insecure context — fall through to the failure path.
  }
  return false
}
