import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { api } from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'
import { translate } from '@/shared/i18n'
import { useAuthStore } from '@/shared/stores/auth'

// Guided first-run setup for workshop owners (docs/ref/features/onboarding.md).
// Step completion is DERIVED server-side from live data — the store never marks
// a step done itself; it only refetches. The one client-local piece of state is
// which spotlight hints this principal has already seen (localStorage), so a
// skipped hint doesn't nag on every visit while the checklist stays the way back.

export interface WorkshopOnboardingStatus {
  branch_configured: boolean
  materials_added: boolean
  setup_complete: boolean
  first_branch_id: string | null
}

export type OnboardingHintKey = 'branch-pricing' | 'catalog-add'

export interface OnboardingHint {
  key: OnboardingHintKey
  /** Route name the hint's target screen lives on. */
  routeName: string
  title: string
  body: string
  /** Step counter shown in the callout, e.g. "2/3". */
  step: string
}

// `title` / `body` are getters, not values: the record is module-level, so a
// plain string would freeze at whatever locale was active on first import and
// survive a language switch. Reading them inside a render keeps them reactive.
export const ONBOARDING_HINTS: Record<OnboardingHintKey, OnboardingHint> = {
  'branch-pricing': {
    key: 'branch-pricing',
    routeName: 'workshop-branch-detail',
    get title() {
      return translate('workshopAdmin.onboarding.pricingTitle')
    },
    get body() {
      return translate('workshopAdmin.onboarding.pricingBody')
    },
    step: '2/3',
  },
  'catalog-add': {
    key: 'catalog-add',
    routeName: 'workshop-catalog',
    get title() {
      return translate('workshopAdmin.onboarding.catalogTitle')
    },
    get body() {
      return translate('workshopAdmin.onboarding.catalogBody')
    },
    step: '3/3',
  },
}

const SEEN_KEY_PREFIX = 'mp:onboarding-seen:'

function storage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    return null
  }
}

function readSeenKeys(store: Storage, key: string): string[] {
  try {
    const raw = store.getItem(key)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === 'string')
      : []
  } catch {
    return []
  }
}

export const useOnboardingStore = defineStore('onboarding', () => {
  const auth = useAuthStore()
  const status = ref<WorkshopOnboardingStatus | null>(null)
  const loading = ref(false)
  const loaded = ref(false)
  const activeHintKey = ref<OnboardingHintKey | null>(null)
  // A hint explicitly requested (checklist CTA / continuation toast) that should
  // open on arrival at its screen, bypassing the seen-marker.
  const queuedHintKey = ref<OnboardingHintKey | null>(null)

  // The guided setup is an owner-only surface (docs/ref/features/onboarding.md);
  // staff experience only the password gate.
  const isEligible = computed(
    () =>
      auth.me?.principal_type === 'workshop_user' &&
      auth.me.is_owner &&
      auth.me.password_reset_required === false,
  )
  const showChecklist = computed(
    () => isEligible.value && status.value !== null && !status.value.setup_complete,
  )
  const activeHint = computed(() =>
    activeHintKey.value ? ONBOARDING_HINTS[activeHintKey.value] : null,
  )

  function hintStepPending(key: OnboardingHintKey): boolean {
    if (!status.value) return false
    if (key === 'branch-pricing') return !status.value.branch_configured
    return !status.value.materials_added
  }

  async function refresh(): Promise<WorkshopOnboardingStatus | null> {
    if (!isEligible.value) return null
    loading.value = true
    try {
      status.value = await api.get<WorkshopOnboardingStatus>('/workshop/onboarding', authInit())
      loaded.value = true
    } catch {
      // Helper surface: on a failed read keep whatever we had — a null status
      // simply hides the checklist; the dashboard must never break over it.
    } finally {
      loading.value = false
    }
    return status.value
  }

  async function ensureLoaded() {
    if (loaded.value || loading.value || !isEligible.value) return
    await refresh()
  }

  function seenStorageKey(): string | null {
    const principalId = auth.me?.principal_id
    return principalId ? `${SEEN_KEY_PREFIX}${principalId}` : null
  }

  function hasSeenHint(key: OnboardingHintKey): boolean {
    const store = storage()
    const storageKey = seenStorageKey()
    if (!store || !storageKey) return false
    return readSeenKeys(store, storageKey).includes(key)
  }

  function markHintSeen(key: OnboardingHintKey) {
    const store = storage()
    const storageKey = seenStorageKey()
    if (!store || !storageKey) return
    try {
      const seen = readSeenKeys(store, storageKey)
      if (!seen.includes(key)) store.setItem(storageKey, JSON.stringify([...seen, key]))
    } catch {
      // Best-effort marker — a full/blocked storage just means the hint reshows.
    }
  }

  function queueHint(key: OnboardingHintKey) {
    queuedHintKey.value = key
  }

  /**
   * Ask to show a hint. Auto-triggers (route arrival) pass force=false and are
   * filtered by pending-step + seen-marker; explicit asks (queued from the
   * checklist) pass force=true and only require the step to still be pending.
   */
  function requestHint(key: OnboardingHintKey, options: { force?: boolean } = {}): boolean {
    if (!isEligible.value || !hintStepPending(key)) return false
    if (!options.force && hasSeenHint(key)) return false
    activeHintKey.value = key
    return true
  }

  function dismissHint(options: { markSeen?: boolean } = {}) {
    if (activeHintKey.value && options.markSeen) markHintSeen(activeHintKey.value)
    activeHintKey.value = null
  }

  function consumeQueuedHint(): OnboardingHintKey | null {
    const key = queuedHintKey.value
    queuedHintKey.value = null
    return key
  }

  function reset() {
    status.value = null
    loading.value = false
    loaded.value = false
    activeHintKey.value = null
    queuedHintKey.value = null
  }

  return {
    status,
    loading,
    loaded,
    activeHintKey,
    queuedHintKey,
    isEligible,
    showChecklist,
    activeHint,
    hintStepPending,
    refresh,
    ensureLoaded,
    hasSeenHint,
    markHintSeen,
    queueHint,
    requestHint,
    dismissHint,
    consumeQueuedHint,
    reset,
  }
})
