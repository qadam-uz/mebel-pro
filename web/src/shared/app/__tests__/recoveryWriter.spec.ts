import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createDebouncedWriter } from '@/shared/app/recoveryWriter'

/**
 * The cutting editor's `localStorage` recovery snapshot rides on this: it must
 * coalesce keystrokes, and it must be flushable *synchronously* from a
 * `beforeunload` / `pagehide` handler, where a promise never resolves.
 */
describe('createDebouncedWriter', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('coalesces rapid schedules into one write after the delay', () => {
    const write = vi.fn()
    const writer = createDebouncedWriter(write, 300)

    for (let stroke = 0; stroke < 10; stroke += 1) {
      writer.schedule()
      vi.advanceTimersByTime(20)
    }

    expect(write).not.toHaveBeenCalled()
    vi.advanceTimersByTime(300)
    expect(write).toHaveBeenCalledTimes(1)
    expect(writer.pending).toBe(false)
  })

  it('writes once on flush and drops the timer', () => {
    const write = vi.fn()
    const writer = createDebouncedWriter(write, 300)

    writer.schedule()
    expect(writer.pending).toBe(true)
    writer.flush()

    expect(write).toHaveBeenCalledTimes(1)
    expect(writer.pending).toBe(false)
    // The pending timer is gone, not merely ignored — the write does not fire
    // a second time once the original delay elapses.
    vi.advanceTimersByTime(1000)
    expect(write).toHaveBeenCalledTimes(1)
  })

  it('is a no-op when flushed with nothing pending', () => {
    const write = vi.fn()
    const writer = createDebouncedWriter(write, 300)

    writer.flush()
    expect(write).not.toHaveBeenCalled()

    writer.schedule()
    writer.flush()
    writer.flush()
    expect(write).toHaveBeenCalledTimes(1)
  })

  it('drops a pending write on cancel', () => {
    const write = vi.fn()
    const writer = createDebouncedWriter(write, 300)

    writer.schedule()
    writer.cancel()

    expect(writer.pending).toBe(false)
    vi.advanceTimersByTime(1000)
    expect(write).not.toHaveBeenCalled()
    // A cancelled writer is still usable — the next edit schedules again.
    writer.schedule()
    vi.advanceTimersByTime(300)
    expect(write).toHaveBeenCalledTimes(1)
  })

  it('starts a fresh window on each schedule rather than firing on the first', () => {
    const write = vi.fn()
    const writer = createDebouncedWriter(write, 300)

    writer.schedule()
    vi.advanceTimersByTime(299)
    writer.schedule()
    vi.advanceTimersByTime(299)

    expect(write).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(write).toHaveBeenCalledTimes(1)
  })
})
