<script setup lang="ts">
import { computed, nextTick } from 'vue'

import { nextStableId } from '@/shared/app/listboxNav'

/**
 * A horizontally scrolling row of filter chips (spec §4, §6.2) — the client's
 * phone-first filter, in place of a dropdown.
 *
 * `SegmentedControl` divides one row between its options and stops fitting past
 * three or four; these are five status filters and a variable-length substrate
 * list, and every one has to stay one tap away. So the row scrolls instead of
 * shrinking, and each chip keeps the 44px touch floor.
 *
 * A radiogroup with a roving tabindex, like `SegmentedControl`: one tab stop for
 * the whole row, arrows to move, which is what a set of mutually exclusive
 * choices owes the keyboard.
 */
const props = defineProps<{
  /** The group's accessible name; never rendered — the chips say what they are. */
  label: string
  modelValue: string
  options: Array<{ value: string; label: string }>
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const id = nextStableId('client-chips')
const currentIndex = computed(() =>
  Math.max(
    0,
    props.options.findIndex((option) => option.value === props.modelValue),
  ),
)

function chipId(value: string) {
  return `${id}-${value}`
}

async function select(value: string, focus = false) {
  emit('update:modelValue', value)
  if (!focus) return
  await nextTick()
  const element = document.getElementById(chipId(value))
  element?.focus()
  // A chip chosen with the arrow keys can be off-screen in the scroller.
  element?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
}

function onKeydown(event: KeyboardEvent) {
  const count = props.options.length
  if (count === 0) return
  let next: number | null = null
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown')
    next = (currentIndex.value + 1) % count
  else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp')
    next = (currentIndex.value - 1 + count) % count
  else if (event.key === 'Home') next = 0
  else if (event.key === 'End') next = count - 1
  if (next === null) return
  event.preventDefault()
  const option = props.options[next]
  if (option) void select(option.value, true)
}
</script>

<template>
  <div
    class="-mx-1 flex gap-1.5 overflow-x-auto px-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    role="radiogroup"
    :aria-label="label"
    @keydown="onKeydown"
  >
    <button
      v-for="(option, index) in options"
      :id="chipId(option.value)"
      :key="option.value"
      type="button"
      role="radio"
      class="inline-flex min-h-11 shrink-0 items-center rounded-[10px] border px-3 text-[13.5px] font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
      :class="
        option.value === modelValue
          ? 'border-accent bg-accent text-on-accent'
          : 'border-hairline bg-elevated text-ink-soft hover:text-ink'
      "
      :aria-checked="option.value === modelValue"
      :tabindex="option.value === modelValue || (modelValue === '' && index === 0) ? 0 : -1"
      @click="select(option.value)"
    >
      {{ option.label }}
    </button>
  </div>
</template>
