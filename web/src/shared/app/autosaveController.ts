/**
 * Framework-agnostic debounced-autosave controller.
 *
 * Encapsulates the timing-sensitive part of the cutting-editor autosave so it
 * can be unit-tested with fake timers instead of mounting the whole SFC (the
 * data-loss bug in CB-15 was a timing bug; CB-108 covers it here). The owning
 * component wires reactive state in via the callbacks and reflects `onStatus`
 * back onto its own `saveState` ref.
 *
 * Guarantees:
 * - `schedule()` coalesces rapid edits into a single `persist()` after `delayMs`.
 * - `flush()` runs a pending save immediately and resolves once it settles, so
 *   callers can `await` it before optimize or on unmount.
 * - `markSaved()` (called after re-hydrating from the server) cancels any
 *   pending timer and clears the dirty flag, so a server snapshot never races a
 *   queued local save.
 * - When `canPersist()` is false (e.g. invalid rows or a read-only draft) a
 *   scheduled run resolves to the `editing` state without hitting the network.
 */
export type AutosaveStatus = 'saved' | 'saving' | 'error' | 'editing'

export interface AutosaveControllerOptions {
  /** Performs the actual save; reads the latest data itself. */
  persist: () => Promise<void>
  /** Gate — only persist when true (e.g. all rows valid and not read-only). */
  canPersist: () => boolean
  /** Reports every status transition back to the component. */
  onStatus?: (status: AutosaveStatus) => void
  /** Debounce window in ms (default 700). */
  delayMs?: number
}

export interface AutosaveController {
  /** Current status (also pushed through `onStatus`). */
  readonly status: AutosaveStatus
  /** User edited — debounce a save. */
  schedule(): void
  /** Run a pending save now; resolves once it settles. No-op when not dirty. */
  flush(): Promise<void>
  /** External save/hydration happened — reset to `saved`, drop the timer. */
  markSaved(): void
  /**
   * Abandon the queued edit: drop the timer *and* the dirty flag, so a later
   * `flush()` has nothing to save either (e.g. the draft was deleted, or a
   * never-created `/new` draft is being torn down).
   */
  cancel(): void
}

export function createAutosaveController(options: AutosaveControllerOptions): AutosaveController {
  const delayMs = options.delayMs ?? 700
  let timer: ReturnType<typeof setTimeout> | undefined
  let dirty = false
  let status: AutosaveStatus = 'saved'
  let revision = 0
  let savedRevision = 0
  let running: Promise<void> | null = null

  function setStatus(next: AutosaveStatus) {
    status = next
    options.onStatus?.(next)
  }

  function clearTimer() {
    if (timer !== undefined) {
      clearTimeout(timer)
      timer = undefined
    }
  }

  async function run(): Promise<void> {
    clearTimer()
    if (running) return running
    if (!options.canPersist()) {
      // Invalid rows / read-only draft surface their own state; never fire a
      // doomed network save, and keep the queued edit so a later valid flush
      // still persists it.
      setStatus('editing')
      return
    }
    const revisionAtStart = revision
    running = (async () => {
      setStatus('saving')
      try {
        await options.persist()
        savedRevision = revisionAtStart
        dirty = revision > savedRevision
        if (dirty) {
          setStatus('editing')
          timer = setTimeout(() => void run(), delayMs)
        } else {
          setStatus('saved')
        }
      } catch {
        setStatus('error')
      }
    })()
    try {
      await running
    } finally {
      running = null
    }
  }

  return {
    get status() {
      return status
    },
    schedule() {
      revision += 1
      dirty = true
      clearTimer()
      setStatus('editing')
      timer = setTimeout(() => void run(), delayMs)
    },
    async flush() {
      while (dirty || running) {
        if (running) await running
        if (!dirty) break
        if (!options.canPersist()) {
          clearTimer()
          setStatus('editing')
          return
        }
        await run()
        if (status === 'error') return
      }
      clearTimer()
    },
    markSaved() {
      clearTimer()
      dirty = false
      savedRevision = revision
      setStatus('saved')
    },
    cancel() {
      clearTimer()
      // Not just the timer: a still-dirty ledger would make the next `flush()`
      // (route leave, unmount) persist the edit this call abandoned.
      dirty = false
      savedRevision = revision
    },
  }
}
