import { nextTick, ref, watch, type Ref } from 'vue'

import { createAutosaveController } from '@/shared/app/autosaveController'
import { AUTOSAVE_DEBOUNCE_MS } from '@/shared/app/constants'

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
      saveError.value =
        status === 'error' ? "Chizmani saqlab bo'lmadi. Qayta urinib ko'ring." : null
    },
  })

  function schedule() {
    if (hydrating || opts.isReadOnly()) return
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
  }
}
