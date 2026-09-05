import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createAutosaveController, type AutosaveStatus } from '@/shared/app/autosaveController'

describe('createAutosaveController', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  function setup(overrides: Partial<Parameters<typeof createAutosaveController>[0]> = {}) {
    const persist = vi.fn().mockResolvedValue(undefined)
    const statuses: AutosaveStatus[] = []
    const controller = createAutosaveController({
      persist,
      canPersist: () => true,
      onStatus: (s) => statuses.push(s),
      delayMs: 700,
      ...overrides,
    })
    return { controller, persist, statuses }
  }

  it('coalesces rapid edits into a single persist after the delay', async () => {
    const { controller, persist } = setup()
    controller.schedule()
    vi.advanceTimersByTime(300)
    controller.schedule()
    vi.advanceTimersByTime(300)
    controller.schedule()
    expect(persist).not.toHaveBeenCalled()
    vi.advanceTimersByTime(700)
    await vi.runAllTimersAsync()
    expect(persist).toHaveBeenCalledTimes(1)
    expect(controller.status).toBe('saved')
  })

  it('does not persist while hydration marks the draft saved', async () => {
    const { controller, persist } = setup()
    controller.schedule() // a queued edit...
    controller.markSaved() // ...is cancelled by an incoming server snapshot
    await vi.runAllTimersAsync()
    expect(persist).not.toHaveBeenCalled()
    expect(controller.status).toBe('saved')
  })

  it('flush() persists a pending edit immediately and resolves', async () => {
    const { controller, persist } = setup()
    controller.schedule()
    await controller.flush()
    expect(persist).toHaveBeenCalledTimes(1)
    expect(controller.status).toBe('saved')
  })

  it('flush() is a no-op when there is nothing pending', async () => {
    const { controller, persist } = setup()
    await controller.flush()
    expect(persist).not.toHaveBeenCalled()
  })

  it('does not double-save when flush() races the debounce timer', async () => {
    const { controller, persist } = setup()
    controller.schedule()
    await controller.flush()
    await vi.runAllTimersAsync()
    expect(persist).toHaveBeenCalledTimes(1)
  })

  it('queues an edit made while the previous save is in flight', async () => {
    let resolveFirst: (() => void) | undefined
    const persist = vi
      .fn<() => Promise<void>>()
      .mockImplementationOnce(
        () =>
          new Promise<void>((resolve) => {
            resolveFirst = resolve
          }),
      )
      .mockResolvedValueOnce(undefined)
    const controller = createAutosaveController({ persist, canPersist: () => true, delayMs: 700 })

    controller.schedule()
    await vi.advanceTimersByTimeAsync(700)
    expect(persist).toHaveBeenCalledTimes(1)

    controller.schedule()
    resolveFirst?.()
    await vi.runAllTimersAsync()

    expect(persist).toHaveBeenCalledTimes(2)
    expect(controller.status).toBe('saved')
  })

  it('stays in editing without a network call when canPersist is false', async () => {
    const canPersist = vi.fn().mockReturnValue(false)
    const { controller, persist, statuses } = setup({ canPersist })
    controller.schedule()
    await controller.flush()
    expect(persist).not.toHaveBeenCalled()
    expect(controller.status).toBe('editing')
    expect(statuses).toContain('editing')
  })

  it('reports error status when persist rejects', async () => {
    const persist = vi.fn().mockRejectedValue(new Error('boom'))
    const { controller, statuses } = setup({ persist })
    controller.schedule()
    await controller.flush()
    expect(controller.status).toBe('error')
    expect(statuses).toContain('error')
  })

  it('cancel() drops a pending save without persisting', async () => {
    const { controller, persist } = setup()
    controller.schedule()
    controller.cancel()
    await vi.runAllTimersAsync()
    expect(persist).not.toHaveBeenCalled()
  })

  it('cancel() leaves nothing for a later flush() to save', async () => {
    // The editor cancels on a deleted draft and then navigates, which runs the
    // route-leave flush: that flush must not resurrect the abandoned edit.
    const { controller, persist } = setup()
    controller.schedule()
    controller.cancel()
    await controller.flush()
    await vi.runAllTimersAsync()
    expect(persist).not.toHaveBeenCalled()
  })
})
