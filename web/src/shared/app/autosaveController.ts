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
  /** Drop a pending timer without saving (e.g. teardown without flush). */
  cancel(): void
}

export function createAutosaveController(options: AutosaveControllerOptions): AutosaveController {
  const delayMs = options.delayMs ?? 700
  let timer: ReturnType<typeof setTimeout> | undefined
  let dirty = false
  let status: AutosaveStatus = 'saved'

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
    if (!options.canPersist()) {
      // Invalid rows / read-only draft surface their own state; never fire a
      // doomed network save, and keep the queued edit so a later valid flush
      // still persists it.
      setStatus('editing')
      return
    }
    setStatus('saving')
    try {
      await options.persist()
      dirty = false
      setStatus('saved')
    } catch {
      setStatus('error')
    }
  }

  return {
    get status() {
      return status
    },
    schedule() {
      dirty = true
      clearTimer()
      setStatus('editing')
      timer = setTimeout(() => void run(), delayMs)
    },
    async flush() {
      if (!dirty) {
        clearTimer()
        return
      }
      await run()
    },
    markSaved() {
      clearTimer()
      dirty = false
      setStatus('saved')
    },
    cancel() {
      clearTimer()
    },
  }
}
