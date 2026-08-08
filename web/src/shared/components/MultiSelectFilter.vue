<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { firstEnabledIndex, nextStableId } from '@/shared/app/listboxNav'
import type { ChoiceOption } from '@/shared/components/controlTypes'

const props = withDefaults(
  defineProps<{
    id?: string
    label: string
    modelValue: string[]
    options: ChoiceOption[]
    emptyLabel?: string
    selectedLabel?: string
    error?: string | null
    required?: boolean
  }>(),
  {
    error: null,
    required: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const { t } = useI18n()

const buttonRef = ref<HTMLButtonElement | null>(null)
const listRef = ref<HTMLUListElement | null>(null)
const open = ref(false)
const activeIndex = ref(0)
const internalId = nextStableId('mp-multi-filter')
const controlId = computed(() => props.id ?? internalId)
const errorId = computed(() => (props.error ? `${controlId.value}-error` : undefined))

const selectedOptions = computed(() =>
  props.options.filter((option) => props.modelValue.includes(option.value)),
)
const summary = computed(() => {
  const count = selectedOptions.value.length
  if (count === 0) return props.emptyLabel ?? t('forms.multiSelect.all')
  if (count === 1)
    return selectedOptions.value[0]?.label ?? t('forms.multiSelect.selectedCount', { count })
  if (props.selectedLabel) return `${count} ${props.selectedLabel}`
  return t('forms.multiSelect.selectedCount', { count })
})
const activeOptionId = computed(() => {
  const option = props.options[activeIndex.value]
  return option ? `${internalId}-${option.value}` : undefined
})

async function openList() {
  open.value = true
  await nextTick()
  listRef.value?.focus()
}

function closeList(returnFocus = false) {
  open.value = false
  if (returnFocus) buttonRef.value?.focus()
}

function toggle(option: ChoiceOption) {
  if (option.disabled) return
  const next = props.modelValue.includes(option.value)
    ? props.modelValue.filter((value) => value !== option.value)
    : [...props.modelValue, option.value]
  emit('update:modelValue', next)
}

function move(direction: number) {
  if (!open.value) {
    void openList()
    return
  }
  // Skip disabled options instead of landing on them (CB-96).
  const next = firstEnabledIndex(props.options, activeIndex.value + direction, direction)
  if (next >= 0) activeIndex.value = next
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    move(1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    move(-1)
  } else if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    if (!open.value) {
      void openList()
      return
    }
    const option = props.options[activeIndex.value]
    if (option) toggle(option)
  } else if (event.key === 'Escape') {
    closeList(true)
  } else if (event.key === 'Tab') {
    closeList()
  }
}

function onDocumentPointerDown(event: PointerEvent) {
  const target = event.target
  if (!(target instanceof Node)) return
  if (buttonRef.value?.contains(target) || listRef.value?.contains(target)) return
  closeList()
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
})
</script>

<template>
  <div class="relative min-w-0">
    <span :id="`${internalId}-label`" class="mb-1 block text-sm font-bold text-ink">
      {{ label }}
      <span v-if="required" class="mp-field-required" aria-hidden="true">*</span>
    </span>
    <button
      :id="controlId"
      ref="buttonRef"
      type="button"
      class="grid min-h-11 w-full grid-cols-[1fr_auto] items-center gap-3 rounded-md border bg-elevated px-3 text-left text-sm transition hover:border-hairline-strong"
      :class="error ? 'border-danger' : 'border-hairline-strong'"
      :aria-expanded="open"
      :aria-controls="`${internalId}-listbox`"
      :aria-labelledby="`${internalId}-label`"
      :aria-describedby="errorId"
      :aria-invalid="error ? 'true' : undefined"
      :aria-required="required ? 'true' : undefined"
      aria-haspopup="listbox"
      @click="open ? closeList() : openList()"
      @keydown="onKeydown"
    >
      <span class="truncate text-ink">{{ summary }}</span>
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
    <ul
      v-if="open"
      :id="`${internalId}-listbox`"
      ref="listRef"
      role="listbox"
      aria-multiselectable="true"
      tabindex="0"
      class="absolute z-40 mt-1 max-h-72 w-full overflow-auto rounded-md border border-hairline-strong bg-elevated p-1 shadow-[0_18px_44px_-16px_color-mix(in_srgb,var(--color-ink)_35%,transparent)]"
      :aria-labelledby="`${internalId}-label`"
      :aria-activedescendant="activeOptionId"
      @keydown="onKeydown"
    >
      <li
        v-for="(option, index) in options"
        :id="`${internalId}-${option.value}`"
        :key="option.value"
        role="option"
        :aria-selected="modelValue.includes(option.value)"
        class="grid min-h-11 cursor-pointer grid-cols-[auto_1fr] items-center gap-3 rounded-md px-3 py-2 text-sm"
        :class="[
          option.disabled ? 'cursor-not-allowed text-ink-muted opacity-55' : '',
          index === activeIndex ? 'bg-sunk' : 'bg-elevated',
        ]"
        @mouseenter="activeIndex = index"
        @click="toggle(option)"
      >
        <span
          class="grid size-5 place-items-center rounded border"
          :class="
            modelValue.includes(option.value)
              ? 'border-accent bg-accent text-on-accent'
              : 'border-hairline-strong bg-elevated text-transparent'
          "
          aria-hidden="true"
        >
          <svg class="size-3.5" viewBox="0 0 20 20">
            <path
              d="m4.5 10.5 3.2 3.2L15.5 6"
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
            />
          </svg>
        </span>
        <span class="min-w-0">
          <span class="block truncate font-bold">{{ option.label }}</span>
          <span v-if="option.meta" class="block truncate text-[11px] text-ink-muted">
            {{ option.meta }}
          </span>
        </span>
      </li>
    </ul>
    <p v-if="error" :id="errorId" class="mp-field-error mt-1" role="alert">
      {{ error }}
    </p>
  </div>
</template>
