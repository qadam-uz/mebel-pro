import { nextTick, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useDraftAutosave } from '@/shared/composables/useDraftAutosave'

interface Part {
  id: number
}

describe('useDraftAutosave (CB-93)', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('debounces a save when parts change, then reports saved', async () => {
    const parts = ref<Part[]>([{ id: 1 }])
    const persist = vi.fn().mockResolvedValue(undefined)
    const autosave = useDraftAutosave({
      parts,
      persist,
      canPersist: () => true,
      isReadOnly: () => false,
    })

    parts.value.push({ id: 2 })
    await nextTick()
    expect(autosave.saveState.value).toBe('editing')
    expect(persist).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(700)
    expect(persist).toHaveBeenCalledTimes(1)
    expect(autosave.saveState.value).toBe('saved')
  })

  it('coalesces rapid edits into a single save', async () => {
    const parts = ref<Part[]>([{ id: 1 }])
    const persist = vi.fn().mockResolvedValue(undefined)
    useDraftAutosave({ parts, persist, canPersist: () => true, isReadOnly: () => false })

    parts.value.push({ id: 2 })
    await nextTick()
    parts.value.push({ id: 3 })
    await nextTick()
    await vi.advanceTimersByTimeAsync(700)
    expect(persist).toHaveBeenCalledTimes(1)
  })

  it('never persists a read-only draft', async () => {
    const parts = ref<Part[]>([{ id: 1 }])
    const persist = vi.fn().mockResolvedValue(undefined)
    useDraftAutosave({ parts, persist, canPersist: () => true, isReadOnly: () => true })

    parts.value.push({ id: 2 })
    await nextTick()
    await vi.advanceTimersByTimeAsync(700)
    expect(persist).not.toHaveBeenCalled()
  })

  it('hydrate() swaps parts without saving the server snapshot back (CB-15)', async () => {
    const parts = ref<Part[]>([{ id: 1 }])
    const persist = vi.fn().mockResolvedValue(undefined)
    const autosave = useDraftAutosave({
      parts,
      persist,
      canPersist: () => true,
      isReadOnly: () => false,
    })

    autosave.hydrate(() => {
      parts.value = [{ id: 9 }]
    })
    await nextTick()
    await vi.advanceTimersByTimeAsync(700)
    expect(persist).not.toHaveBeenCalled()
    expect(autosave.saveState.value).toBe('saved')
  })

  it('suspends scheduling entirely while enabled() is false', async () => {
    const parts = ref<Part[]>([{ id: 1 }])
    const persist = vi.fn().mockResolvedValue(undefined)
    const onSchedule = vi.fn()
    const autosave = useDraftAutosave({
      parts,
      persist,
      canPersist: () => true,
      isReadOnly: () => false,
      enabled: () => false,
      onSchedule,
    })

    parts.value.push({ id: 2 })
    await nextTick()
    await vi.advanceTimersByTimeAsync(700)
    expect(onSchedule).not.toHaveBeenCalled()
    expect(persist).not.toHaveBeenCalled()
    expect(autosave.saveState.value).toBe('saved')
  })

  it('runs onSchedule when an edit schedules a save', async () => {
    const parts = ref<Part[]>([{ id: 1 }])
    const onSchedule = vi.fn()
    useDraftAutosave({
      parts,
      persist: vi.fn().mockResolvedValue(undefined),
      canPersist: () => true,
      isReadOnly: () => false,
      onSchedule,
    })

    parts.value.push({ id: 2 })
    await nextTick()
    expect(onSchedule).toHaveBeenCalledTimes(1)
  })
})
