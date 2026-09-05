/**
 * Debounced writer with a synchronous flush.
 *
 * The cutting editor's `localStorage` recovery snapshot serialises every part
 * in the drawing, so writing it on each keystroke costs a full re-serialisation
 * (~60 kB of JSON at 300 rows) per character. This coalesces those writes the
 * way `autosaveController` coalesces server saves — but without its async/status
 * machinery, because a `localStorage.setItem` is synchronous and cannot fail
 * halfway.
 *
 * It is deliberately *not* `autosaveController` with a shorter delay: that one
 * owns a promise-returning `persist`, a status mirror and a dirty/revision
 * ledger, none of which a synchronous write has any use for — and its `flush()`
 * is `async`, so it cannot run inside a `beforeunload`/`pagehide` handler, which
 * is the one moment this layer exists for.
 *
 * Guarantees:
 * - `schedule()` coalesces rapid calls into a single `write()` after `delayMs`.
 * - `flush()` runs a pending write immediately, synchronously, and clears the
 *   timer; with nothing pending it is a no-op (it never writes on its own).
 * - `cancel()` drops a pending write without running it.
 * - `pending` says whether a write is queued, so a caller that is about to move
 *   or replace the write's target can decide between the queued value and what
 *   is already stored.
 */
export interface DebouncedWriter {
  /** True while a scheduled write has not yet run. */
  readonly pending: boolean
  /** Something changed — debounce a write. */
  schedule(): void
  /** Run a pending write now, synchronously. No-op when nothing is pending. */
  flush(): void
  /** Drop a pending write without running it. */
  cancel(): void
}

export function createDebouncedWriter(write: () => void, delayMs: number): DebouncedWriter {
  let timer: ReturnType<typeof setTimeout> | undefined

  function clearTimer() {
    if (timer !== undefined) {
      clearTimeout(timer)
      timer = undefined
    }
  }

  return {
    get pending() {
      return timer !== undefined
    },
    schedule() {
      clearTimer()
      timer = setTimeout(() => {
        timer = undefined
        write()
      }, delayMs)
    },
    flush() {
      if (timer === undefined) return
      clearTimer()
      write()
    },
    cancel() {
      clearTimer()
    },
  }
}
