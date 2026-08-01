import { nextTick, ref, watch, type Ref } from 'vue'

import { createAutosaveController } from '@/shared/app/autosaveController'
import { AUTOSAVE_DEBOUNCE_MS } from '@/shared/app/constants'
import { translate } from '@/shared/i18n'

export type DraftSaveState = 'saved' | 'saving' | 'error' | 'editing'

/**
 * Debounced draft autosave (CB-93 seam). Wraps the framework-agnostic
 * `autosaveController` (the unit-tested debounce/flush core, CB-108) with the
 * editor's status mirror + the don't-persist gate, owns the deep `parts` watch,
 * and exposes `hydrate()` to swap in a freshly-loaded server snapshot without
 * saving it straight back (the CB-15 data-loss guard). Keeping this here means
 * the data-loss-sensitive timing lives in one tested place, not inline in the
 * 1900-line editor view.
 */
export function useDraftAutosave<T>(opts: {
  parts: Ref<T[]>
  persist: () => Promise<void>
  canPersist: () => boolean
  isReadOnly: () => boolean
  // Suspend the whole autosave loop while false — no scheduling, no timers, no
  // status churn. The cutting editor uses this for an unsaved (not-yet-created)
  // draft, where there's no id to PATCH until the first optimise creates one.
  // Defaults to always-enabled.
  enabled?: () => boolean
  // Side effect to run when an edit schedules a save (e.g. clear a now-stale
  // row-attributed optimiser error).
  onSchedule?: () => void
}) {
  const saveState = ref<DraftSaveState>('saved')
  const saveError = ref<string | null>(null)
  let hydrating = false

  const controller = createAutosaveController({
    delayMs: AUTOSAVE_DEBOUNCE_MS,
    persist: opts.persist,
    canPersist: () => opts.canPersist() && !opts.isReadOnly(),
    onStatus: (status) => {
      saveState.value = status
      saveError.value = status === 'error' ? translate('forms.autosave.saveFailed') : null
    },
  })

  function schedule() {
    if (hydrating || opts.isReadOnly() || !(opts.enabled?.() ?? true)) return
    opts.onSchedule?.()
    controller.schedule()
  }

  // Mirror a server snapshot into the editable state without scheduling a save of
  // it back to itself: suppress the deep watch for the mutation + one tick and mark
  // the controller already-saved.
  function hydrate(mutate: () => void) {
    hydrating = true
    mutate()
    controller.markSaved()
    void nextTick(() => {
      hydrating = false
    })
  }

  watch(opts.parts, schedule, { deep: true })

  return {
    saveState,
    saveError,
    schedule,
    hydrate,
    flush: () => controller.flush(),
    markSaved: () => controller.markSaved(),
    cancel: () => controller.cancel(),
  }
}
