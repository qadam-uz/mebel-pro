/**
 * The pin, client-side.
 *
 * A client enters through a workshop's door: `/w/{code}` resolves, the resolved
 * entry is parked in `localStorage` so it survives the Telegram login
 * round-trip, and `POST /client/entry` turns it into `Client.preferred_branch_id`
 * — the pin. Everything here is storage plumbing and pure derivation; the
 * requests live in `@/shared/stores/clientEntry`.
 */

import { API_PREFIX } from '@/shared/api/client'
import type { ClientBranchOption } from '@/shared/stores/cutting'

/**
 * The workshop's logo, addressed by its code rather than by a file id.
 *
 * The landing runs before there is a session, so it cannot use the
 * authenticated file route. This narrow public route serves exactly one file
 * per code — the workshop's own logo — and answers the link's 404 for every
 * other case, including a workshop that has none, which is why the caller keeps
 * the monogram as its fallback. Signed-in surfaces (Ustaxonalarim) stay on the
 * authenticated path.
 */
export function publicWorkshopLogoUrl(code: string): string {
  return `${API_PREFIX}/public/workshop-links/${encodeURIComponent(code)}/logo`
}

/** The scanned link, waiting for a session to apply it to. */
const ENTRY_KEY = 'client.entry'
/** The connected toast, waiting for the next home render to show it once. */
const TOAST_KEY = 'client.entry.toast'

export interface StoredClientEntry {
  /** Canonical public code, as the resolve endpoint echoed it. */
  code: string
  /** The branch the client chose (or the only one the link had). */
  branch_id: string
}

/**
 * `localStorage` throws outright in a few real browsers (Safari private mode,
 * site data blocked). Losing the entry is harmless by design — the QR can be
 * scanned again — so every accessor here degrades to "no entry" rather than
 * taking a screen down with it.
 */
function defaultStorage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    return null
  }
}

export function storeClientEntry(
  entry: StoredClientEntry,
  storage: Storage | null = defaultStorage(),
): void {
  try {
    storage?.setItem(ENTRY_KEY, JSON.stringify(entry))
  } catch {
    // A full or refusing quota degrades to an un-pinned login (spec §3.1).
  }
}

export function readClientEntry(
  storage: Storage | null = defaultStorage(),
): StoredClientEntry | null {
  let raw: string | null = null
  try {
    raw = storage?.getItem(ENTRY_KEY) ?? null
  } catch {
    return null
  }
  if (!raw) return null
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null
    const { code, branch_id: branchId } = parsed as Partial<StoredClientEntry>
    if (typeof code !== 'string' || typeof branchId !== 'string') return null
    if (!code || !branchId) return null
    return { code, branch_id: branchId }
  } catch {
    // Someone else's key, or a half-written value. Treat it as absent.
    return null
  }
}

export function clearClientEntry(storage: Storage | null = defaultStorage()): void {
  try {
    storage?.removeItem(ENTRY_KEY)
  } catch {
    // Nothing to recover from: the next read simply finds a stale entry and
    // re-applies it, which is idempotent.
  }
}

/**
 * Park the connected toast for the screen the client lands on.
 *
 * The toast belongs to the entry, not to the home route: it must fire once
 * after an entry is applied and never again on a plain home load, so the flag
 * is written where the entry is applied and consumed where it is shown.
 */
export function queueEntryToast(
  workshopName: string,
  storage: Storage | null = defaultStorage(),
): void {
  try {
    storage?.setItem(TOAST_KEY, workshopName)
  } catch {
    // A missed toast is cosmetic; the pin itself is already written.
  }
}

/** Read-and-clear: the toast is one-time by construction. */
export function takeEntryToast(storage: Storage | null = defaultStorage()): string | null {
  try {
    const value = storage?.getItem(TOAST_KEY) ?? null
    if (value !== null) storage?.removeItem(TOAST_KEY)
    return value || null
  } catch {
    return null
  }
}

/**
 * Which workshop the editor's branch picker is scoped to, or `null` for the
 * unpinned (organic) client whose cross-workshop picker stays as it was.
 *
 * `pinnedWorkshopName` from `/auth/me` is the authoritative "is this client
 * pinned" signal — it is null when there is no pin *and* when the pinned
 * workshop is blocked, which is exactly when scoping must not apply. The
 * workshop **id** is then derived from the branch-options payload, which
 * already groups by workshop, so the picker costs no extra request:
 *
 * 1. the option matching `preferredBranchId` names it directly;
 * 2. failing that — the pinned branch went `inactive` and dropped out of the
 *    options — the workshop's *other* visible branches are matched by name,
 *    which §8 requires the picker to keep offering.
 */
export function pinnedWorkshopId(
  options: ClientBranchOption[],
  preferredBranchId: string | null | undefined,
  pinnedWorkshopName: string | null | undefined,
): string | null {
  if (!pinnedWorkshopName) return null
  const pinnedOption = preferredBranchId
    ? options.find((option) => option.branch_id === preferredBranchId)
    : undefined
  if (pinnedOption) return pinnedOption.workshop_id
  const byName = options.find((option) => option.workshop_name === pinnedWorkshopName)
  return byName?.workshop_id ?? null
}

/**
 * The branch list the picker may offer.
 *
 * A pinned client sees one workshop's branches and nothing else — no tab, no
 * cross-workshop search, no "see more" (spec §4). A pin whose workshop has no
 * visible branch left yields an empty list on purpose: the picker's own empty
 * state is the right answer, and falling back to every workshop would reopen
 * the door this spec closed.
 */
export function scopedBranchOptions(
  options: ClientBranchOption[],
  workshopId: string | null,
): ClientBranchOption[] {
  if (!workshopId) return options
  return options.filter((option) => option.workshop_id === workshopId)
}
