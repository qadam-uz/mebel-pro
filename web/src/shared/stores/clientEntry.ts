import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { api, captureApiError, withQuery } from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'
import {
  clearClientEntry,
  queueEntryToast,
  readClientEntry,
  type StoredClientEntry,
} from '@/shared/app/clientEntry'
import { useAuthStore } from '@/shared/stores/auth'

export type EntryBranchStatus = 'active' | 'temporarily_closed'

/** One visible branch behind a workshop link — pickup information only. */
export interface WorkshopLinkBranch {
  id: string
  branch_no: number
  name: string
  address: string
  phone: string
  status: EntryBranchStatus
  closed_reason: string | null
}

export interface WorkshopLink {
  code: string
  workshop_name: string
  workshop_logo_file_id: string | null
  branches: WorkshopLinkBranch[]
  /** Set when the link named a branch that resolved — no choice step. */
  requested_branch_id: string | null
  /**
   * The link named a branch that is gone or invisible. The printed QR outlives
   * branch reshuffles (spec §8), so the landing falls back to the workshop-level
   * behaviour instead of dying — which means showing the choice it was about to
   * skip.
   */
  branch_no_fallback: boolean
}

export interface ClientEntryResult {
  workshop_id: string
  workshop_name: string
  /** Null when the link named no branch — the workshop is recorded, nothing pinned. */
  branch_id: string | null
  branch_name: string | null
}

export interface ClientWorkshopBranch {
  id: string
  branch_no: number
  name: string
  address: string
  phone: string
  /** The branch's other published numbers, in its own order — every client
   *  surface shows all of them, primary first (decision 24). */
  additional_phones?: string[]
  status: EntryBranchStatus
  closed_reason: string | null
  is_pinned: boolean
  /**
   * The pin behind «Xaritada ko'rish» (spec §6.1). Optional on purpose: the
   * pair is nullable on the branch itself (not every workshop drops a pin), and
   * the field was added to this read after the client shipped — an older
   * backend simply omits it and the link is not rendered.
   */
  latitude?: string | null
  longitude?: string | null
}

/** One workshop on Ustaxonalarim: the pin plus everything the client has history with. */
export interface ClientWorkshop {
  workshop_id: string
  name: string
  logo_file_id: string | null
  /** Carried so "Asosiy qilish" re-pins through the same audited entry endpoint. */
  public_code: string
  is_pinned: boolean
  branches: ClientWorkshopBranch[]
}

export const useClientEntryStore = defineStore('clientEntry', () => {
  const link = ref<WorkshopLink | null>(null)
  const linkLoading = ref(false)
  const linkError = ref<string | null>(null)

  const workshops = ref<ClientWorkshop[]>([])
  const workshopsLoading = ref(false)
  const workshopsError = ref<string | null>(null)
  const workshopsTraceId = ref<string | null>(null)

  /**
   * Resolve a scanned code. Unauthenticated on purpose — the landing works
   * before there is a session, and this is the one client endpoint that does.
   */
  async function resolveLink(code: string, branchNo?: number | null) {
    linkLoading.value = true
    linkError.value = null
    link.value = null
    try {
      link.value = await api.get<WorkshopLink>(
        withQuery(`/public/workshop-links/${encodeURIComponent(code)}`, {
          branch_no: branchNo == null ? undefined : String(branchNo),
        }),
      )
      return link.value
    } catch (error) {
      // One 404 covers unknown / blocked / branchless, and 429 is the transient
      // variant of the same screen — both are the dead-link screen, never a raw
      // error page (spec §8).
      linkError.value = captureApiError(error, 'workshop_link_not_found').code
      return null
    } finally {
      linkLoading.value = false
    }
  }

  /**
   * Record this entry, and pin the branch when the link named one.
   *
   * Every entry — pinned or not — puts the workshop on Ustaxonalarim (§2.2);
   * `branch_id: null` is the multi-branch workshop link, which records the
   * workshop and leaves the pin exactly where it was. A branch the link did
   * name is pinned, last write wins.
   */
  async function applyEntry(code: string, branchId: string | null): Promise<ClientEntryResult> {
    const applied = await api.post<ClientEntryResult>(
      '/client/entry',
      { code, branch_id: branchId },
      authInit(),
    )
    // The header subtitle reads the pinned names off `/auth/me`, so the
    // principal has to catch up before the client lands on home.
    await useAuthStore().refreshMe()
    return applied
  }

  /**
   * Apply the entry a scan parked before the login round-trip, then forget it.
   *
   * Absent storage (cleared, different browser) is a normal un-pinned login, and
   * a refused entry — the workshop went away or was blocked while the client was
   * signing in — degrades the same way rather than blocking the session that was
   * just created.
   */
  async function applyPendingEntry(
    entry: StoredClientEntry | null = readClientEntry(),
  ): Promise<ClientEntryResult | null> {
    if (!entry) return null
    try {
      const applied = await applyEntry(entry.code, entry.branch_id)
      queueEntryToast(applied.workshop_name)
      return applied
    } catch {
      return null
    } finally {
      clearClientEntry()
    }
  }

  async function loadMyWorkshops() {
    workshopsLoading.value = true
    workshopsError.value = null
    workshopsTraceId.value = null
    try {
      workshops.value = await api.get<ClientWorkshop[]>('/client/my-workshops', authInit())
    } catch (error) {
      const captured = captureApiError(error, 'client_workshops_load_failed')
      workshopsError.value = captured.code
      workshopsTraceId.value = captured.traceId
    } finally {
      workshopsLoading.value = false
    }
  }

  /**
   * Move the pin to one branch of a workshop already on Ustaxonalarim.
   *
   * The write goes through `POST /client/entry` — the one audited path that can
   * move the pin — and the answer is applied to the rows in hand rather than
   * refetched: the star has to fill *in place* (§6.1), and a reload would also
   * resort the list under the reader's finger. Exactly one branch across every
   * workshop ends up pinned, which is what the backend now holds.
   */
  async function pinBranch(publicCode: string, branchId: string): Promise<ClientEntryResult> {
    const applied = await applyEntry(publicCode, branchId)
    workshops.value = workshops.value.map((workshop) => ({
      ...workshop,
      is_pinned: workshop.workshop_id === applied.workshop_id,
      branches: workshop.branches.map((branch) => ({
        ...branch,
        is_pinned: branch.id === branchId,
      })),
    }))
    return applied
  }

  /**
   * Load the list once per session unless it is already in hand.
   *
   * The shell needs it on every client page — the "Ustaxona" tab points at the
   * one workshop's profile when there is exactly one (§2) — and so do home, the
   * profile and the catalog. A plain `loadMyWorkshops` on each of them would
   * refetch the same rows four times on one navigation.
   */
  async function ensureMyWorkshops(): Promise<ClientWorkshop[]> {
    if (workshops.value.length > 0 || workshopsLoading.value) return workshops.value
    // A failed attempt does not latch: the shell primes this as soon as it has
    // a token, and a page that needs the rows asks again on mount. Latching on
    // the first failure left the home card without its address forever.
    await loadMyWorkshops()
    return workshops.value
  }

  /**
   * Where "Ustaxona" goes — the one target both nav surfaces read.
   *
   * Exactly one related workshop means there is nothing to choose, so the entry
   * lands on that workshop's profile (§2.1); two or more, or nothing loaded
   * yet, and it opens Ustaxonalarim. It lives on the store rather than in each
   * shell because the phone tab and the desktop nav render the same item and
   * had drifted apart — the tab took the shortcut, the nav always went to the
   * list.
   */
  const workshopPath = computed(() =>
    workshops.value.length === 1 ? `/c/workshops/${workshops.value[0].workshop_id}` : '/c/branches',
  )

  function reset() {
    link.value = null
    linkLoading.value = false
    linkError.value = null
    workshops.value = []
    workshopsLoading.value = false
    workshopsError.value = null
    workshopsTraceId.value = null
  }

  return {
    link,
    linkLoading,
    linkError,
    workshops,
    workshopPath,
    workshopsLoading,
    workshopsError,
    workshopsTraceId,
    resolveLink,
    applyEntry,
    applyPendingEntry,
    loadMyWorkshops,
    ensureMyWorkshops,
    pinBranch,
    reset,
  }
})
