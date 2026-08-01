<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  dateRangePresetLabel,
  isoDate,
  presetRange,
  type DateRangePreset,
} from '@/shared/app/dateRange'
import { nextStableId } from '@/shared/app/listboxNav'
import { overlayRect, overlayViewport } from '@/shared/app/overlayGeometry'
import CalendarMonths from '@/shared/components/CalendarMonths.vue'

// Filter-bar date range control: one compact trigger opening a popover with
// preset shortcuts and a real calendar. Preset clicks and completed calendar
// selections both emit from/to immediately (auto-apply); the popover closes.
const props = withDefaults(
  defineProps<{
    preset: DateRangePreset
    dateFrom: string
    dateTo: string
    presets?: DateRangePreset[]
    label?: string
  }>(),
  {
    presets: () => ['all', 'today', 'week', 'month', 'last_month', 'days30'],
    // No literal default: a prop default is evaluated once, at module load, so
    // it would freeze at whatever locale happened to be active then.
    label: undefined,
  },
)

const emit = defineEmits<{
  'update:preset': [value: DateRangePreset]
  'update:dateFrom': [value: string]
  'update:dateTo': [value: string]
}>()

const { t } = useI18n()
const labelText = computed(() => props.label ?? t('forms.dateRange.label'))

const buttonRef = ref<HTMLButtonElement | null>(null)
const panelRef = ref<HTMLDivElement | null>(null)
const calendarRef = ref<InstanceType<typeof CalendarMonths> | null>(null)
const panelId = nextStableId('mp-daterange')
const open = ref(false)
const panelStyle = ref<Record<string, string>>({})
// First visible month; a second month renders beside it on wide viewports.
const monthCount = ref(1)
// In-flight calendar selection: first click anchors, second click completes.
const draftStart = ref<string | null>(null)
const hovered = ref<string | null>(null)
const GUTTER = 8

// A non-custom preset owns its window: whenever the preset changes to one —
// including programmatically (e.g. a page's "Tozalash") — push the derived
// from/to, skipping equal values so mount and no-op reselects emit nothing.
watch(
  () => props.preset,
  (value) => {
    if (value === 'custom') return
    const range = presetRange(value)
    const from = range.from ?? ''
    const to = range.to ?? ''
    if (from !== props.dateFrom) emit('update:dateFrom', from)
    if (to !== props.dateTo) emit('update:dateTo', to)
  },
)

function formatDotted(value: string): string {
  const [year, month, day] = value.split('-')
  return `${day}.${month}.${year}`
}

const triggerText = computed(() => {
  if (props.preset === 'custom') {
    if (props.dateFrom && props.dateTo) {
      return `${formatDotted(props.dateFrom)} – ${formatDotted(props.dateTo)}`
    }
    return t('forms.dateRange.range')
  }
  return dateRangePresetLabel(props.preset)
})

// What the calendar highlights: the in-flight draft while picking, otherwise
// the currently applied window (named presets included, so "Joriy oy" shows
// its span).
const displayRange = computed<{ from: string | null; to: string | null }>(() => {
  if (draftStart.value) {
    if (hovered.value && hovered.value > draftStart.value) {
      return { from: draftStart.value, to: hovered.value }
    }
    return { from: draftStart.value, to: draftStart.value }
  }
  return { from: props.dateFrom || null, to: props.dateTo || null }
})

const today = computed(() => isoDate(new Date()))

function updatePanelPosition() {
  const button = buttonRef.value
  const panel = panelRef.value
  if (!button || !panel) return
  const rect = overlayRect(button)
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

async function openPanel() {
  monthCount.value =
    typeof window.matchMedia === 'function' && window.matchMedia('(min-width: 768px)').matches
      ? 2
      : 1
  draftStart.value = null
  hovered.value = null
  open.value = true
  await nextTick()
  updatePanelPosition()
  panelRef.value?.focus()
}

function closePanel({ returnFocus = false } = {}) {
  open.value = false
  draftStart.value = null
  hovered.value = null
  if (returnFocus) buttonRef.value?.focus()
}

function choosePreset(preset: DateRangePreset) {
  emit('update:preset', preset)
  closePanel({ returnFocus: true })
}

function onTriggerKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && open.value) {
    event.stopPropagation()
    closePanel({ returnFocus: true })
  }
}

function onDayClick(day: string) {
  if (!draftStart.value || day < draftStart.value) {
    draftStart.value = day
    hovered.value = null
    calendarRef.value?.focusDay(day)
    return
  }
  const from = draftStart.value
  if (props.preset !== 'custom') emit('update:preset', 'custom')
  if (from !== props.dateFrom) emit('update:dateFrom', from)
  if (day !== props.dateTo) emit('update:dateTo', day)
  closePanel({ returnFocus: true })
}

function onPanelKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    // Two-stage convention: swallow while open so a host dialog isn't
    // dismissed by the same keypress that closes this popover.
    event.stopPropagation()
    closePanel({ returnFocus: true })
    return
  }
  calendarRef.value?.onKeydown(event)
}

function onDocumentPointerDown(event: PointerEvent) {
  const target = event.target
  if (!(target instanceof Node)) return
  if (buttonRef.value?.contains(target)) return
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
  <div class="mp-filter-date relative flex flex-col gap-1">
    <span class="mp-filter-dd-label" aria-hidden="true">{{ labelText }}</span>
    <button
      ref="buttonRef"
      type="button"
      class="flex min-h-10 items-center gap-2 rounded-lg border bg-elevated px-3 text-left transition"
      :class="open ? 'border-accent' : 'border-hairline-strong hover:bg-sunk'"
      :aria-expanded="open"
      :aria-controls="panelId"
      aria-haspopup="dialog"
      @click="open ? closePanel() : openPanel()"
      @keydown="onTriggerKeydown"
    >
      <svg class="size-4 shrink-0 text-ink-muted" viewBox="0 0 20 20" aria-hidden="true">
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
      <span class="sr-only">{{ labelText }}</span>
      <span class="min-w-0 flex-1 truncate text-[13px] font-semibold text-ink">
        {{ triggerText }}
      </span>
      <svg class="size-4 shrink-0 text-ink-muted" viewBox="0 0 20 20" aria-hidden="true">
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
      <div
        v-if="open"
        :id="panelId"
        ref="panelRef"
        role="dialog"
        :aria-label="$t('forms.dateRange.range')"
        tabindex="-1"
        class="fixed z-50 max-h-[calc(100dvh-16px)] max-w-[calc(100vw-16px)] overflow-y-auto rounded-lg border border-hairline-strong bg-elevated p-3 shadow-[0_18px_44px_-16px_rgb(15_27_45_/_35%)] outline-none"
        :style="panelStyle"
        @keydown="onPanelKeydown"
      >
        <div :class="monthCount === 2 ? 'flex items-start gap-3' : 'flex flex-col gap-3'">
          <!-- Preset shortcuts: a rail beside the calendar on wide viewports,
               wrapped chips above it on narrow ones. -->
          <div
            :class="
              monthCount === 2
                ? 'flex w-36 shrink-0 flex-col gap-1 border-r border-hairline pr-3'
                : 'flex flex-wrap gap-1.5'
            "
          >
            <button
              v-for="presetOption in presets"
              :key="presetOption"
              type="button"
              class="rounded-md px-2.5 py-1.5 text-left text-[13px] font-semibold transition"
              :class="
                presetOption === preset
                  ? 'bg-accent-soft text-accent'
                  : 'text-ink-soft hover:bg-sunk hover:text-ink'
              "
              @click="choosePreset(presetOption)"
            >
              {{ dateRangePresetLabel(presetOption) }}
            </button>
          </div>

          <!-- Anchor the LAST visible month on the range end (or today): date
               filters look backwards, so the extra month shows the past, not
               the future. The tab stop prefers the range start. -->
          <CalendarMonths
            ref="calendarRef"
            v-model:hovered="hovered"
            :anchor="dateTo || dateFrom || today"
            :initial-focus="dateFrom || today"
            :month-count="monthCount"
            :from="displayRange.from"
            :to="displayRange.to"
            :track-hover="draftStart !== null"
            @select="onDayClick"
          />
        </div>
      </div>
    </Teleport>
  </div>
</template>
