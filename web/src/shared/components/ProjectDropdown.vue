<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import type { DropdownOption } from '@/shared/app/roleConfig'

const props = defineProps<{
  label: string
  modelValue: string
  options: DropdownOption[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const buttonRef = ref<HTMLButtonElement | null>(null)
const listboxRef = ref<HTMLUListElement | null>(null)
const open = ref(false)
const activeIndex = ref(0)
const popoverStyle = ref<Record<string, string>>({})
const listboxId = `mp-listbox-${Math.random().toString(36).slice(2)}`

const selected = computed(
  () => props.options.find((option) => option.value === props.modelValue) ?? props.options[0],
)
const activeOptionId = computed(() => {
  const option = props.options[activeIndex.value]
  return option ? `${listboxId}-${option.value}` : undefined
})

function updatePopoverPosition() {
  const button = buttonRef.value
  if (!button) return
  const rect = button.getBoundingClientRect()
  popoverStyle.value = {
    top: `${rect.bottom + window.scrollY + 6}px`,
    left: `${rect.left + window.scrollX}px`,
    minWidth: `${Math.max(rect.width, 260)}px`,
  }
}

async function openList() {
  activeIndex.value = Math.max(
    0,
    props.options.findIndex((option) => option.value === selected.value.value),
  )
  open.value = true
  await nextTick()
  updatePopoverPosition()
  listboxRef.value?.focus()
}

function closeList({ returnFocus = false } = {}) {
  open.value = false
  if (returnFocus) buttonRef.value?.focus()
}

function choose(option: DropdownOption) {
  emit('update:modelValue', option.value)
  closeList({ returnFocus: true })
}

function move(delta: number) {
  if (!open.value) {
    void openList().then(() => {
      activeIndex.value = (activeIndex.value + delta + props.options.length) % props.options.length
    })
    return
  }
  activeIndex.value = (activeIndex.value + delta + props.options.length) % props.options.length
}

function onButtonKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    if (open.value) {
      choose(props.options[activeIndex.value])
    } else {
      void openList()
    }
  } else if (event.key === 'ArrowDown') {
    event.preventDefault()
    move(1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    move(-1)
  } else if (event.key === 'Escape' && open.value) {
    closeList({ returnFocus: true })
  } else if (event.key === 'Tab') {
    closeList()
  }
}

function onDocumentPointerDown(event: PointerEvent) {
  const target = event.target
  if (!(target instanceof Node)) return
  if (buttonRef.value?.contains(target)) return
  const listbox = document.getElementById(listboxId)
  if (listbox?.contains(target)) return
  closeList()
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown)
  window.addEventListener('resize', updatePopoverPosition)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
  window.removeEventListener('resize', updatePopoverPosition)
})
</script>

<template>
  <div class="relative inline-flex">
    <button
      ref="buttonRef"
      type="button"
      class="mp-surface flex min-h-11 min-w-52 items-center gap-3 px-3 py-2 text-left transition hover:border-hairline-strong"
      :aria-expanded="open"
      :aria-controls="listboxId"
      aria-haspopup="listbox"
      @click="open ? closeList() : openList()"
      @keydown="onButtonKeydown"
    >
      <span
        class="grid size-7 place-items-center rounded-md bg-accent-soft text-accent"
        aria-hidden="true"
      >
        <span class="mp-dot"></span>
      </span>
      <span class="min-w-0 flex-1">
        <span class="block text-[11px] font-bold uppercase tracking-[0.13em] text-ink-muted">
          {{ label }}
        </span>
        <span class="block truncate text-sm font-bold text-ink">{{ selected.label }}</span>
        <span class="block truncate font-mono text-[11px] text-ink-muted">{{ selected.meta }}</span>
      </span>
      <svg class="size-4 text-ink-muted" viewBox="0 0 20 20" aria-hidden="true">
        <path
          d="M5 7.5 10 12l5-4.5"
          fill="none"
          stroke="currentColor"
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="1.8"
        />
      </svg>
    </button>

    <Teleport to="body">
      <ul
        v-if="open"
        :id="listboxId"
        ref="listboxRef"
        role="listbox"
        tabindex="0"
        class="fixed z-50 rounded-lg border border-hairline-strong bg-elevated p-1 shadow-[0_18px_44px_-16px_rgb(15_27_45_/_35%)]"
        :style="popoverStyle"
        :aria-label="label"
        :aria-activedescendant="activeOptionId"
        @keydown="onButtonKeydown"
      >
        <li
          v-for="(option, index) in options"
          :id="`${listboxId}-${option.value}`"
          :key="option.value"
          role="option"
          :aria-selected="option.value === selected.value"
          class="grid cursor-pointer grid-cols-[auto_1fr_auto] items-center gap-3 rounded-md px-3 py-2 text-sm"
          :class="[
            index === activeIndex ? 'bg-sunk' : 'bg-elevated',
            option.value === selected.value ? 'text-accent' : 'text-ink',
          ]"
          @mouseenter="activeIndex = index"
          @click="choose(option)"
        >
          <span
            class="size-2 rounded-full"
            :class="{
              'bg-success': option.status === 'active',
              'bg-warning': option.status === 'pending',
              'bg-ink-muted': option.status === 'blocked',
            }"
            aria-hidden="true"
          ></span>
          <span>
            <span class="block font-bold">{{ option.label }}</span>
            <span class="block font-mono text-[11px] text-ink-muted">{{ option.meta }}</span>
          </span>
          <svg
            v-if="option.value === selected.value"
            class="size-4"
            viewBox="0 0 20 20"
            aria-hidden="true"
          >
            <path
              d="m4.5 10.5 3.2 3.2L15.5 6"
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
            />
          </svg>
        </li>
      </ul>
    </Teleport>
  </div>
</template>
