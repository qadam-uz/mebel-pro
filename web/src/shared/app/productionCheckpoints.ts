// Device-local cut checkpoints for the job sheet: a worker marks panels as
// cut to keep their place in a big order. Marks live only on the station
// tablet (localStorage) — a personal coordination aid, never synced, shared
// naturally across the shifts that use the same tablet.

const KEY_PREFIX = 'mp-prod-marks:v1:'
const DEFAULT_MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000

interface PanelMarksRecord {
  marks: string[]
  ts: number
}

function key(orderId: string) {
  return `${KEY_PREFIX}${orderId}`
}

function storage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    return null
  }
}

function readRecord(store: Storage, key: string): PanelMarksRecord | null {
  try {
    const raw = store.getItem(key)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<PanelMarksRecord>
    if (!Array.isArray(parsed.marks) || typeof parsed.ts !== 'number') return null
    return { marks: parsed.marks.filter((mark) => typeof mark === 'string'), ts: parsed.ts }
  } catch {
    return null
  }
}

export function loadPanelMarks(orderId: string): Set<string> {
  const store = storage()
  if (!store) return new Set()
  return new Set(readRecord(store, key(orderId))?.marks ?? [])
}

export function savePanelMarks(orderId: string, marks: ReadonlySet<string>) {
  const store = storage()
  if (!store) return
  try {
    if (marks.size === 0) store.removeItem(key(orderId))
    else store.setItem(key(orderId), JSON.stringify({ marks: [...marks], ts: Date.now() }))
  } catch {
    // Quota / private-mode failures are non-fatal: marks are a convenience.
  }
}

export function clearPanelMarks(orderId: string) {
  storage()?.removeItem(key(orderId))
}

// Completed orders clear their own key; cancelled or reverted ones don't.
// Bound the residue so a shared tablet doesn't accumulate dead marks forever.
export function prunePanelMarks(maxAgeMs = DEFAULT_MAX_AGE_MS, now = Date.now()) {
  const store = storage()
  if (!store) return
  const doomed: string[] = []
  for (let index = 0; index < store.length; index += 1) {
    const candidate = store.key(index)
    if (!candidate || !candidate.startsWith(KEY_PREFIX)) continue
    const record = readRecord(store, candidate)
    if (!record || now - record.ts > maxAgeMs) doomed.push(candidate)
  }
  for (const candidate of doomed) store.removeItem(candidate)
}
