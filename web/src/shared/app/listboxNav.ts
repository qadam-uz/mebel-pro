import type { ChoiceOption } from '@/shared/components/controlTypes'

let idCounter = 0

/** A process-stable, collision-free element id (CB-96) — replaces the per-component
 * `Math.random()` ids in the dropdown/dialog components. */
export function nextStableId(prefix: string): string {
  idCounter += 1
  return `${prefix}-${idCounter}`
}

/**
 * First NON-disabled option index from `start`, moving `direction` (+1/-1) and
 * wrapping; -1 if every option is disabled or the list is empty (CB-96). Shared so
 * keyboard nav in every listbox skips disabled options instead of landing on them.
 */
export function firstEnabledIndex(options: ChoiceOption[], start = 0, direction = 1): number {
  if (options.length === 0) return -1
  for (let offset = 0; offset < options.length; offset += 1) {
    const index = (start + offset * direction + options.length) % options.length
    if (!options[index]?.disabled) return index
  }
  return -1
}
