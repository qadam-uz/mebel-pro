<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, type CSSProperties } from 'vue'
import { useI18n } from 'vue-i18n'

import { firstEnabledIndex as findEnabledIndex, nextStableId } from '@/shared/app/listboxNav'
import { overlayRect, overlayViewport } from '@/shared/app/overlayGeometry'
import { foldIncludes } from '@/shared/app/searchFold'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useDropdownPlacement } from '@/shared/composables/useDropdownPlacement'

const props = withDefaults(
  defineProps<{
    label: string
    modelValue: string | null
    options: ChoiceOption[]
    placeholder?: string
    error?: string | null
    disabled?: boolean
    noResultsText?: string
    // Extra classes on the visible <label> — e.g. `lg:sr-only` to keep the label
    // for a11y while a column header carries it on wide layouts. Default: visible.
    labelClass?: string
    // Dense single-line trigger for grid/table cells (shorter, tighter padding).
    compact?: boolean
    // A colour swatch rendered inside the input's left edge (e.g. the picked
    // material colour) so the cell reads visually, not just by name.
    swatchColor?: string | null
    // Show a trailing ✕ that clears the current selection and reopens the list
    // for a fresh search — opt-in, since most pickers expect a value to stay set.
    clearable?: boolean
    // The parent already filtered `options` server-side (it owns the query).
    // Filtering them again here would hide rows the server matched on a field
    // the option text doesn't carry — a phone number, say.
    serverFiltered?: boolean
    // A fetch is in flight for the current query.
    loading?: boolean
    loadingText?: string
    // Wait this long after the last keystroke before emitting `search`. Default
    // 0 keeps every existing client-filtered call site emitting synchronously;
    // a server-backed picker sets it so typing doesn't become one request per
    // character.
    searchDebounceMs?: number
    // Standing footnote under the list — what the picker offers and what it
    // searches. Not an error and not a result, so it sits outside the options.
    hint?: string
  }>(),
  {
    // The three copy defaults carry no literal: a prop default is evaluated
    // once, at module load, so it would freeze at whatever locale happened to
    // be active then. They fall back to the catalog in a computed instead.
    placeholder: undefined,
    error: null,
    disabled: false,
    noResultsText: undefined,
    labelClass: '',
    compact: false,
    swatchColor: null,
    clearable: false,
    serverFiltered: false,
    loading: false,
    loadingText: undefined,
    searchDebounceMs: 0,
    hint: '',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
  search: [value: string]
}>()

const { t } = useI18n()

const inputRef = ref<HTMLInputElement | null>(null)
// The vertical anchor is the whole FIELD — input plus its error message — not the
// input alone. Anchoring to the input would open the panel straight over the
// error text, which is the defect the old `top-full`-below-the-message layout
// was built to avoid. Horizontal placement still follows the input.
const fieldRef = ref<HTMLElement | null>(null)
const listRef = ref<HTMLUListElement | null>(null)
const query = ref('')
const open = ref(false)
const activeIndex = ref(0)
const id = nextStableId('mp-combobox')
// `useDropdownPlacement` still drives scroll-into-view and the open/close
// lifecycle; its `dropUp` is unused now that `updatePanelPosition` decides the
// flip itself from the measured viewport.
const { start: startPlacement, stop: stopPlacement } = useDropdownPlacement(inputRef, listRef)

// The panel teleports to <body> and is placed from the trigger, like every other
// popover here (ActionMenu, ProjectDropdown, DateField). It has to leave: this
// combobox is used inside `.table-wrap`, which is `overflow-x: auto` and so
// clips on BOTH axes per spec, and its old `z-40` sat under the modal layer —
// so in the Kirim form the list rendered behind the row beneath it. Fixed
// positioning also frees the width: anchored to the cell it was ~200px and
// truncated "Egger H1137 · Kulrang eman" to "Egger H1137 · K...".
const PANEL_GUTTER = 8
const PANEL_MIN_WIDTH = 420
const PANEL_MAX_HEIGHT = 288
const panelStyle = ref<CSSProperties>({})

function updatePanelPosition() {
  const trigger = inputRef.value
  if (!trigger) return
  const inputRect = overlayRect(trigger)
  // `rect` spans the field so the panel clears any error message below the input.
  const rect = fieldRef.value ? overlayRect(fieldRef.value) : inputRect
  const { width: viewportWidth, height: viewportHeight } = overlayViewport()
  // Never narrower than the trigger, never wider than the viewport allows.
  const width = Math.min(
    Math.max(inputRect.width, PANEL_MIN_WIDTH),
    Math.max(160, viewportWidth - PANEL_GUTTER * 2),
  )
  const below = viewportHeight - rect.bottom - PANEL_GUTTER - 4
  const above = rect.top - PANEL_GUTTER - 4
  const openUp = below < PANEL_MAX_HEIGHT && above > below
  const maxHeight = Math.max(120, Math.min(openUp ? above : below, PANEL_MAX_HEIGHT))
  const left = Math.min(
    Math.max(inputRect.left, PANEL_GUTTER),
    Math.max(PANEL_GUTTER, viewportWidth - width - PANEL_GUTTER),
  )
  const top = openUp
    ? Math.max(PANEL_GUTTER, rect.top - maxHeight - 4)
    : Math.min(rect.bottom + 4, viewportHeight - PANEL_GUTTER)
  panelStyle.value = {
    top: `${top}px`,
    left: `${left}px`,
    width: `${width}px`,
    maxHeight: `${maxHeight}px`,
  }
}

watch(open, async (isOpen) => {
  if (!isOpen) return
  await nextTick()
  updatePanelPosition()
})

const selected = computed(() => props.options.find((option) => option.value === props.modelValue))
const showClear = computed(() => props.clearable && !!props.modelValue && !props.disabled)
const filteredOptions = computed(() => {
  if (props.serverFiltered) return props.options
  const value = query.value.trim()
  if (!value) return props.options
  // Folded, not lowercased: the labels are stored in Latin and workshops type on
  // a Cyrillic keyboard. `сонома` has to reach `Sonoma eman` — see searchFold.ts.
  return props.options.filter((option) =>
    foldIncludes(`${option.label} ${option.meta ?? ''}`, value),
  )
})
const activeOptionId = computed(() => {
  const option = filteredOptions.value[activeIndex.value]
  return option ? `${id}-${option.value}` : undefined
})
const errorId = computed(() => (props.error ? `${id}-error` : undefined))
const placeholderText = computed(() => props.placeholder ?? t('forms.combobox.placeholder'))
const noResultsLabel = computed(() => props.noResultsText ?? t('forms.combobox.noResults'))
const loadingLabel = computed(() => props.loadingText ?? t('forms.combobox.loading'))
// While the list is open the input is a search box, so it reads empty even when
// a value is set. Echoing the picked label as the placeholder keeps the current
// selection legible instead of the field claiming nothing is chosen.
const inputPlaceholder = computed(() =>
  open.value && props.modelValue ? selectedLabel() : placeholderText.value,
)

// Remember the chosen option's label so the input keeps showing it even when the
// parent filters that option out of `options` (CB-84 panel filters) — the value
// is still selected, so the display must not blank out.
const rememberedLabel = ref('')
watch(
  selected,
  (option) => {
    if (option) rememberedLabel.value = option.label
  },
  { immediate: true },
)

function selectedLabel() {
  if (selected.value) return selected.value.label
  return props.modelValue ? rememberedLabel.value : ''
}

function syncQueryFromModel() {
  if (!open.value) query.value = selectedLabel()
}

function firstEnabledIndex(start = 0, direction = 1) {
  return findEnabledIndex(filteredOptions.value, start, direction)
}

// Set while choosing closes the list: clicking an option blurs the input, and
// choose() refocuses it — without this guard the input's @focus would reopen the
// list we just closed (the dropdown "lingered" after picking).
let suppressFocusOpen = false

// The index the list should open on: the current selection, so a picker that
// already holds a value opens *at* that value rather than at the top.
function selectedIndex() {
  const index = filteredOptions.value.findIndex((option) => option.value === props.modelValue)
  if (index >= 0 && !filteredOptions.value[index]?.disabled) return index
  return firstEnabledIndex(0)
}

function scrollActiveIntoView() {
  const list = listRef.value
  const row = list?.children[activeIndex.value]
  if (row instanceof HTMLElement) row.scrollIntoView({ block: 'nearest' })
}

// Reaching for the list (focus, click, ArrowDown) starts a fresh search: the
// query holds the whole selected label, so leaving it in place means the client
// filter matches only that one option and the list opens showing the single row
// the user already picked — the value could not be changed without deleting the
// text by hand. Typing does *not* go through here, or it would wipe itself.
function beginFreshSearch() {
  if (open.value || query.value === '') return
  query.value = ''
  if (props.serverFiltered) {
    // The parent owns the filtering, so it has to hear that the query is empty
    // again — immediately, since reaching for the list isn't typing.
    cancelPendingSearch()
    emit('search', '')
  }
}

function onFocus() {
  if (props.disabled || suppressFocusOpen) return
  beginFreshSearch()
  void openList()
}

async function openList() {
  if (props.disabled || suppressFocusOpen) return
  open.value = true
  await nextTick()
  // After the tick: blanking the query recomputes `filteredOptions`, whose watcher
  // resets `activeIndex` to the top. Setting it here means the selection wins.
  activeIndex.value = selectedIndex()
  scrollActiveIntoView()
  // Placement flips the list up when there's no room below and the list scrolls
  // internally, so it stays visible without scrolling the page (which jumped the
  // content "up" when the dropdown opened low in the viewport).
  startPlacement()
}

function closeList(returnFocus = false) {
  open.value = false
  stopPlacement()
  syncQueryFromModel()
  if (!returnFocus) return
  // Handing focus back must not trip @focus into reopening the list we just
  // closed — and now also not into blanking the label syncQueryFromModel just
  // restored, which would leave an Escaped search showing an empty field.
  suppressFocusOpen = true
  inputRef.value?.focus()
  suppressFocusOpen = false
}

function choose(option: ChoiceOption) {
  if (option.disabled) return
  emit('update:modelValue', option.value)
  query.value = option.label
  closeList(true)
}

// One pending `search` emit at a time. A server-backed picker sets
// `searchDebounceMs` so a six-character order number costs one request, not
// six; with the default 0 the emit still goes out synchronously, so existing
// client-filtered call sites are unchanged.
let searchTimer: ReturnType<typeof setTimeout> | undefined

function cancelPendingSearch() {
  if (searchTimer === undefined) return
  clearTimeout(searchTimer)
  searchTimer = undefined
}

function emitSearch(value: string) {
  cancelPendingSearch()
  if (props.searchDebounceMs <= 0) {
    emit('search', value)
    return
  }
  searchTimer = setTimeout(() => {
    searchTimer = undefined
    emit('search', value)
  }, props.searchDebounceMs)
}

async function clearSelection() {
  emit('update:modelValue', null)
  query.value = ''
  // Clearing is a deliberate act, not typing — the fresh list must not wait
  // out a debounce the user can't see.
  cancelPendingSearch()
  emit('search', '')
  await openList()
  inputRef.value?.focus()
}

function onInput(event: Event) {
  const target = event.target
  if (!(target instanceof HTMLInputElement)) return
  query.value = target.value
  emitSearch(query.value)
  // Typing is a search, not an unset: the selection stands until another option
  // is chosen. Clearing it here meant that starting a search and then changing
  // your mind (Esc, click away) silently dropped a good pick.
  void openList()
}

function move(direction: number) {
  if (!open.value) {
    beginFreshSearch()
    void openList()
    return
  }
  const next = firstEnabledIndex(activeIndex.value + direction, direction)
  if (next < 0) return
  activeIndex.value = next
  void nextTick(scrollActiveIntoView)
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    move(1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    move(-1)
  } else if (event.key === 'Enter') {
    if (!open.value) return
    event.preventDefault()
    const option = filteredOptions.value[activeIndex.value]
    if (option) choose(option)
  } else if (event.key === 'Escape') {
    // Only act when open; refocusing a closed list would retrigger @focus → reopen.
    // Two-stage Escape: closing the listbox must not bubble into a host
    // dialog's focus trap and dismiss the whole modal.
    if (open.value) {
      event.stopPropagation()
      closeList(true)
    }
  } else if (event.key === 'Tab') {
    closeList()
  }
}

function onDocumentPointerDown(event: PointerEvent) {
  const target = event.target
  if (!(target instanceof Node)) return
  if (inputRef.value?.contains(target) || listRef.value?.contains(target)) return
  closeList()
}

watch(
  () => props.modelValue,
  () => syncQueryFromModel(),
  { immediate: true },
)

watch(filteredOptions, () => {
  activeIndex.value = firstEnabledIndex(0)
})

// Re-sync the displayed label when the option set changes underneath us (parent
// filtering). selectedLabel() falls back to the remembered label, so this never
// blanks a still-selected value.
watch(
  () => props.options,
  () => syncQueryFromModel(),
)

// A rejected submit has to put the caret on the field it rejected — the host
// form owns that decision, so the trigger is exposed rather than guessed at
// through a generated id.
function focus() {
  inputRef.value?.focus()
}

defineExpose({ focus })

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown)
  window.addEventListener('resize', updatePanelPosition)
  // Capture phase: the trigger's own scroll container is what moves it.
  window.addEventListener('scroll', updatePanelPosition, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
  window.removeEventListener('resize', updatePanelPosition)
  window.removeEventListener('scroll', updatePanelPosition, true)
  cancelPendingSearch()
})
</script>

<template>
  <div class="min-w-0">
    <label
      :id="`${id}-label`"
      class="mb-1 block text-sm font-bold text-ink"
      :class="labelClass"
      :for="id"
    >
      {{ label }}
    </label>
    <!-- The listbox anchors to this box, which holds the input *and* the error
         message — so `top-full` opens the list below the message instead of on
         top of it. Focusing the field still opens the list (every call site
         expects that); an absolutely positioned overlay simply has nowhere to
         cover the words from. The inner box keeps the swatch and the clear
         button glued to the input itself, whatever the message does to the
         outer height. -->
    <div ref="fieldRef" data-placement-anchor class="relative">
      <div class="relative">
        <span
          v-if="swatchColor"
          class="pointer-events-none absolute top-1/2 size-4 -translate-y-1/2 rounded border border-hairline"
          :class="compact ? 'left-2' : 'left-2.5'"
          :style="{ background: swatchColor }"
          aria-hidden="true"
        ></span>
        <input
          :id="id"
          ref="inputRef"
          class="w-full rounded-md border bg-elevated text-sm font-semibold text-ink placeholder:font-normal"
          :class="[
            error ? 'border-danger' : 'border-hairline-strong',
            compact ? 'min-h-9' : 'min-h-11',
            swatchColor ? (compact ? 'pl-8' : 'pl-9') : compact ? 'pl-2.5' : 'pl-3',
            showClear ? (compact ? 'pr-8' : 'pr-9') : compact ? 'pr-2.5' : 'pr-3',
          ]"
          :value="query"
          :placeholder="inputPlaceholder"
          :disabled="disabled"
          :aria-expanded="open"
          :aria-controls="`${id}-listbox`"
          :aria-activedescendant="open ? activeOptionId : undefined"
          :aria-describedby="errorId"
          :aria-invalid="error ? 'true' : undefined"
          :aria-busy="loading ? 'true' : undefined"
          role="combobox"
          autocomplete="off"
          aria-autocomplete="list"
          @focus="onFocus"
          @input="onInput"
          @keydown="onKeydown"
        />
        <button
          v-if="showClear"
          type="button"
          class="absolute top-1/2 grid -translate-y-1/2 place-items-center rounded-full text-ink-muted transition hover:bg-sunk hover:text-ink"
          :class="compact ? 'right-1.5 size-6' : 'right-2 size-7'"
          :aria-label="$t('forms.combobox.clearSelection', { label })"
          @click="clearSelection"
        >
          <svg class="size-4" viewBox="0 0 20 20" aria-hidden="true">
            <path
              d="M6 6l8 8M14 6l-8 8"
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-width="1.8"
            />
          </svg>
        </button>
      </div>
      <p v-if="error" :id="errorId" class="mt-1 text-sm font-bold text-danger">
        {{ error }}
      </p>
      <Teleport to="body">
        <!-- Esc is bound here as well as on the wrapper: focus is in the input,
             which is no longer an ancestor of this panel once teleported. -->
        <ul
          v-if="open"
          :id="`${id}-listbox`"
          ref="listRef"
          role="listbox"
          class="fixed z-[90] overflow-auto overscroll-contain rounded-md border border-hairline-strong bg-elevated p-1 shadow-[0_18px_44px_-16px_color-mix(in_srgb,var(--color-ink)_35%,transparent)]"
          :style="panelStyle"
          :aria-labelledby="`${id}-label`"
          @keydown.esc.stop.prevent="closeList(true)"
        >
          <li
            v-for="(option, index) in filteredOptions"
            :id="`${id}-${option.value}`"
            :key="option.value"
            role="option"
            :aria-selected="option.value === modelValue"
            class="grid min-h-11 cursor-pointer grid-cols-[1fr_auto] items-center gap-3 rounded-md px-3 py-2 text-sm"
            :class="[
              option.disabled ? 'cursor-not-allowed text-ink-muted opacity-55' : '',
              index === activeIndex ? 'bg-sunk' : 'bg-elevated',
              option.value === modelValue ? 'text-accent' : 'text-ink',
            ]"
            @mouseenter="activeIndex = index"
            @click="choose(option)"
          >
            <span class="min-w-0">
              <slot name="option" :option="option" :selected="option.value === modelValue">
                <span class="block break-words font-bold">{{ option.label }}</span>
                <span v-if="option.meta" class="block truncate text-[11px] text-ink-muted">
                  {{ option.meta }}
                </span>
              </slot>
            </span>
            <svg
              v-if="option.value === modelValue"
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
          <li
            v-if="loading"
            class="px-3 py-3 text-sm font-bold text-ink-muted"
            role="status"
            aria-live="polite"
          >
            {{ loadingLabel }}
          </li>
          <li
            v-else-if="filteredOptions.length === 0"
            class="px-3 py-3 text-sm font-bold text-ink-muted"
          >
            {{ noResultsLabel }}
          </li>
          <li
            v-if="hint"
            role="presentation"
            class="mt-1 border-t border-hairline px-3 pb-1 pt-2 text-[11px] leading-tight text-ink-muted"
          >
            {{ hint }}
          </li>
        </ul>
      </Teleport>
    </div>
  </div>
</template>
