<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { isoDate } from '@/shared/app/dateRange'
import { nextStableId } from '@/shared/app/listboxNav'
import { overlayRect, overlayViewport } from '@/shared/app/overlayGeometry'
import CalendarMonths from '@/shared/components/CalendarMonths.vue'

// Single-date form control. A native `<input type="date">` renders in the
// browser's OS locale (07/19/2026 on en-US, 19.07.2026 on ru-RU), which we
// neither control nor want: every other date in the app is dd.mm.yyyy. This
// types and displays dd.mm.yyyy everywhere while still speaking the API's
// yyyy-mm-dd, and opens the app's one calendar for pointer selection.
//
// Drop it inside the usual `<label class="field"><span>…</span>` wrapper —
// `required` lives on the real input, so the label's `*` and native form
// validation both keep working.
const props = withDefaults(
  defineProps<{
    modelValue: string
    min?: string
    max?: string
    required?: boolean
    disabled?: boolean
    placeholder?: string
    ariaLabel?: string
  }>(),
  {
    min: '',
    max: '',
    required: false,
    disabled: false,
    // No literal default: a prop default is evaluated once, at module load, so
    // it would freeze at whatever locale happened to be active then.
    placeholder: undefined,
    ariaLabel: undefined,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const { t } = useI18n()

const inputRef = ref<HTMLInputElement | null>(null)
const wrapRef = ref<HTMLDivElement | null>(null)
const anchorRef = ref<HTMLDivElement | null>(null)
const panelRef = ref<HTMLDivElement | null>(null)
const panelId = nextStableId('mp-datefield')
const open = ref(false)
const panelStyle = ref<Record<string, string>>({})
const text = ref('')
const GUTTER = 8

const today = computed(() => isoDate(new Date()))
const placeholderText = computed(() => props.placeholder ?? t('forms.date.placeholder'))

function toDotted(iso: string): string {
  const [year, month, day] = iso.split('-')
  return year && month && day ? `${day}.${month}.${year}` : ''
}

/** `dd.mm.yyyy` → `yyyy-mm-dd`, or '' when it isn't a real calendar day. */
function toIso(dotted: string): string {
  const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(dotted)
  if (!match) return ''
  const [, day, month, year] = match
  const date = new Date(Number(year), Number(month) - 1, Number(day))
  // Round-trip guard: 31.02.2026 constructs a Date, it just isn't February.
  if (
    date.getFullYear() !== Number(year) ||
    date.getMonth() !== Number(month) - 1 ||
    date.getDate() !== Number(day)
  ) {
    return ''
  }
  return isoDate(date)
}

const iso = computed(() => toIso(text.value))

const error = computed(() => {
  if (!text.value) return ''
  if (!iso.value) return t('forms.date.errorFormat')
  if (props.min && iso.value < props.min)
    return t('forms.date.errorBefore', { date: toDotted(props.min) })
  if (props.max && iso.value > props.max)
    return t('forms.date.errorAfter', { date: toDotted(props.max) })
  return ''
})

// Mirror onto the input so the browser blocks submit on a bad date the same
// way it does on an empty required field — `max`/`min` can't be native here,
// the visible value is dd.mm.yyyy, not the ISO the constraint speaks.
watch(error, (message) => {
  inputRef.value?.setCustomValidity(message)
})

// The parent owns the value; re-render the text only when the ISO the parent
// holds differs from what's typed, so an in-flight edit isn't reformatted.
watch(
  () => props.modelValue,
  (value) => {
    if (value === iso.value) return
    // An unusable entry is reported as '' so the form can't submit a stale
    // date — but that echo must not erase what the user is still typing.
    if (value === '' && error.value) return
    text.value = toDotted(value)
  },
  { immediate: true },
)

function commit() {
  const next = error.value ? '' : iso.value
  if (next !== props.modelValue) emit('update:modelValue', next)
}

/** Group digits as dd.mm.yyyy, adding each separator as its group fills. */
function mask(raw: string, deleting: boolean): string {
  const digits = raw.replace(/\D/g, '').slice(0, 8)
  let out = digits.slice(0, 2)
  if (digits.length > 2) out += `.${digits.slice(2, 4)}`
  if (digits.length > 4) out += `.${digits.slice(4, 8)}`
  if (!deleting && (digits.length === 2 || digits.length === 4)) out += '.'
  return out
}

function onInput(event: Event) {
  const element = event.target as HTMLInputElement
  const raw = element.value
  const caret = element.selectionStart ?? raw.length
  const deleting = raw.length < text.value.length
  const digitsBeforeCaret = raw.slice(0, caret).replace(/\D/g, '').length
  const masked = mask(raw, deleting)
  text.value = masked
  commit()
  void nextTick(() => {
    if (!inputRef.value) return
    // Restore the caret by digit count, so editing mid-string doesn't jump to
    // the end when the mask shifts separators around.
    let seen = 0
    let position = masked.length
    if (digitsBeforeCaret === 0) position = 0
    else {
      for (let index = 0; index < masked.length; index += 1) {
        if (masked[index] >= '0' && masked[index] <= '9') {
          seen += 1
          if (seen === digitsBeforeCaret) {
            // Step past a separator the mask just appended.
            position = masked[index + 1] === '.' ? index + 2 : index + 1
            break
          }
        }
      }
    }
    inputRef.value.value = masked
    inputRef.value.setSelectionRange(position, position)
  })
}

function onBlur() {
  // Normalize a shorthand day/month ("1.7.2026" can't be typed through the
  // mask, but a paste can land it) and drop a half-typed value's separator.
  if (text.value && !iso.value) {
    const parts = text.value.split('.')
    if (parts.length === 3) {
      const padded = `${parts[0].padStart(2, '0')}.${parts[1].padStart(2, '0')}.${parts[2]}`
      if (toIso(padded)) {
        text.value = padded
        commit()
      }
    }
  }
}

function updatePanelPosition() {
  const anchor = anchorRef.value
  const panel = panelRef.value
  if (!anchor || !panel) return
  const rect = overlayRect(anchor)
  const { width: viewportWidth, height: viewportHeight } = overlayViewport()
  const panelWidth = Math.min(panel.offsetWidth, viewportWidth - GUTTER * 2)
  const panelHeight = panel.offsetHeight
  const spaceBelow = viewportHeight - rect.bottom - GUTTER - 6
  const spaceAbove = rect.top - GUTTER - 6
  const openUp = spaceBelow < panelHeight && spaceAbove > spaceBelow
  const left = Math.min(
    Math.max(rect.left, GUTTER),
    Math.max(GUTTER, viewportWidth - panelWidth - GUTTER),
  )
  const top = openUp
    ? Math.max(GUTTER, rect.top - panelHeight - 6)
    : Math.max(GUTTER, Math.min(rect.bottom + 6, viewportHeight - panelHeight - GUTTER))
  panelStyle.value = { top: `${top}px`, left: `${left}px` }
}

// Where the calendar opens: the current value, else the closest allowed day to
// today — landing on a month whose every cell is disabled helps nobody.
const calendarAnchor = computed(() => {
  if (iso.value) return iso.value
  if (props.max && today.value > props.max) return props.max
  if (props.min && today.value < props.min) return props.min
  return today.value
})

async function openPanel() {
  if (props.disabled) return
  open.value = true
  await nextTick()
  updatePanelPosition()
  panelRef.value?.focus()
}

function closePanel({ returnFocus = false } = {}) {
  open.value = false
  if (returnFocus) inputRef.value?.focus()
}

function onSelect(day: string) {
  text.value = toDotted(day)
  commit()
  closePanel({ returnFocus: true })
}

const calendarRef = ref<InstanceType<typeof CalendarMonths> | null>(null)

function onPanelKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    // Two-stage convention: swallow while open so the host modal isn't
    // dismissed by the same keypress that closes this popover.
    event.stopPropagation()
    closePanel({ returnFocus: true })
    return
  }
  calendarRef.value?.onKeydown(event)
}

function onInputKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && open.value) {
    event.stopPropagation()
    closePanel({ returnFocus: true })
  } else if (event.key === 'ArrowDown' && !open.value && !event.altKey) {
    event.preventDefault()
    void openPanel()
  }
}

function onDocumentPointerDown(event: PointerEvent) {
  const target = event.target
  if (!(target instanceof Node)) return
  if (wrapRef.value?.contains(target)) return
  if (panelRef.value?.contains(target)) return
  closePanel()
}

function onViewportChange() {
  if (open.value) updatePanelPosition()
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown)
  window.addEventListener('resize', onViewportChange)
  window.visualViewport?.addEventListener('resize', onViewportChange)
  window.addEventListener('scroll', onViewportChange, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
  window.removeEventListener('resize', onViewportChange)
  window.visualViewport?.removeEventListener('resize', onViewportChange)
  window.removeEventListener('scroll', onViewportChange, true)
})
</script>

<template>
  <div ref="wrapRef">
    <div ref="anchorRef" class="relative">
      <input
        ref="inputRef"
        :value="text"
        class="mp-input pr-11"
        :class="error ? 'border-danger' : ''"
        type="text"
        inputmode="numeric"
        autocomplete="off"
        maxlength="10"
        :placeholder="placeholderText"
        :required="required"
        :disabled="disabled"
        :aria-label="ariaLabel"
        :aria-invalid="error ? 'true' : undefined"
        :aria-describedby="error ? `${panelId}-error` : undefined"
        @input="onInput"
        @blur="onBlur"
        @keydown="onInputKeydown"
      />
      <button
        type="button"
        class="absolute inset-y-0 right-0 grid w-11 place-items-center rounded-r-md text-ink-muted transition hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="disabled"
        :aria-expanded="open"
        :aria-controls="panelId"
        aria-haspopup="dialog"
        :aria-label="$t('forms.date.openCalendar')"
        @click="open ? closePanel({ returnFocus: true }) : openPanel()"
      >
        <svg class="size-[18px]" viewBox="0 0 20 20" aria-hidden="true">
          <rect
            x="3"
            y="4.5"
            width="14"
            height="12"
            rx="2"
            fill="none"
            stroke="currentColor"
            stroke-width="1.6"
          />
          <path d="M3 8.5h14M7 3v3M13 3v3" fill="none" stroke="currentColor" stroke-width="1.6" />
        </svg>
      </button>
    </div>
    <small v-if="error" :id="`${panelId}-error`" class="mp-field-error mt-1 block">
      {{ error }}
    </small>

    <Teleport to="body">
      <!-- z-[84]: above the app modal layer (z-[80]) these forms live in, below
           ConfirmDialog (z-[85]) and toasts (z-[90]). -->
      <div
        v-if="open"
        :id="panelId"
        ref="panelRef"
        role="dialog"
        :aria-label="$t('forms.date.pickDay')"
        tabindex="-1"
        class="fixed z-[84] max-h-[calc(100dvh-16px)] max-w-[calc(100vw-16px)] overflow-y-auto rounded-lg border border-hairline-strong bg-elevated p-3 shadow-[0_18px_44px_-16px_color-mix(in_srgb,var(--color-ink)_35%,transparent)] outline-none"
        :style="panelStyle"
        @keydown="onPanelKeydown"
      >
        <CalendarMonths
          ref="calendarRef"
          :anchor="calendarAnchor"
          :initial-focus="calendarAnchor"
          :from="iso || null"
          :to="iso || null"
          :min="min"
          :max="max"
          @select="onSelect"
        />
      </div>
    </Teleport>
  </div>
</template>
