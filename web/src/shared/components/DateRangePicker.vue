<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  DATE_RANGE_PRESET_LABELS,
  isoDate,
  monthGrid,
  presetRange,
  UZ_MONTHS,
  UZ_WEEKDAYS,
  type DateRangePreset,
} from '@/shared/app/dateRange'
import { nextStableId } from '@/shared/app/listboxNav'

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
    label: 'Sana',
  },
)

const emit = defineEmits<{
  'update:preset': [value: DateRangePreset]
  'update:dateFrom': [value: string]
  'update:dateTo': [value: string]
}>()

const buttonRef = ref<HTMLButtonElement | null>(null)
const panelRef = ref<HTMLDivElement | null>(null)
const panelId = nextStableId('mp-daterange')
const open = ref(false)
const panelStyle = ref<Record<string, string>>({})
// First visible month; a second month renders beside it on wide viewports.
const viewYear = ref(0)
const viewMonth = ref(0)
const monthCount = ref(1)
// In-flight calendar selection: first click anchors, second click completes.
const draftStart = ref<string | null>(null)
const hovered = ref<string | null>(null)
const focusedDay = ref<string | null>(null)
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

function parseIso(value: string): Date | null {
  if (!value) return null
  const [year, month, day] = value.split('-').map(Number)
  if (!year || !month || !day) return null
  return new Date(year, month - 1, day)
}

function formatDotted(value: string): string {
  const [year, month, day] = value.split('-')
  return `${day}.${month}.${year}`
}

const triggerText = computed(() => {
  if (props.preset === 'custom') {
    if (props.dateFrom && props.dateTo) {
      return `${formatDotted(props.dateFrom)} – ${formatDotted(props.dateTo)}`
    }
    return "Sana oralig'i"
  }
  return DATE_RANGE_PRESET_LABELS[props.preset]
})

const visibleMonths = computed(() => {
  const months: { year: number; month: number; key: string; weeks: (string | null)[][] }[] = []
  for (let index = 0; index < monthCount.value; index += 1) {
    const total = viewYear.value * 12 + viewMonth.value + index
    const year = Math.floor(total / 12)
    const month = total % 12
    months.push({ year, month, key: `${year}-${month}`, weeks: monthGrid(year, month) })
  }
  return months
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
  const rect = button.getBoundingClientRect()
  const viewportWidth = window.visualViewport?.width ?? window.innerWidth
  const viewportHeight = window.visualViewport?.height ?? window.innerHeight
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
  // Anchor the LAST visible month on the range end (or today): date filters
  // look backwards, so the extra month should show the past, not the future.
  const base = parseIso(props.dateTo) ?? parseIso(props.dateFrom) ?? new Date()
  monthCount.value =
    typeof window.matchMedia === 'function' && window.matchMedia('(min-width: 768px)').matches
      ? 2
      : 1
  const firstTotal = base.getFullYear() * 12 + base.getMonth() - (monthCount.value - 1)
  viewYear.value = Math.floor(firstTotal / 12)
  viewMonth.value = firstTotal % 12
  draftStart.value = null
  hovered.value = null
  // The roving tab stop must land on a RENDERED cell — prefer the range start,
  // but it can sit before the visible window (e.g. "Oxirgi 30 kun" on a
  // one-month view); fall back to the anchor end, which is always visible.
  const preferredFocus = props.dateFrom || today.value
  const focusDate = parseIso(preferredFocus)
  const focusTotal = focusDate ? focusDate.getFullYear() * 12 + focusDate.getMonth() : Number.NaN
  focusedDay.value =
    focusDate && focusTotal >= firstTotal && focusTotal < firstTotal + monthCount.value
      ? preferredFocus
      : props.dateTo || today.value
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
    focusedDay.value = day
    return
  }
  const from = draftStart.value
  if (props.preset !== 'custom') emit('update:preset', 'custom')
  if (from !== props.dateFrom) emit('update:dateFrom', from)
  if (day !== props.dateTo) emit('update:dateTo', day)
  closePanel({ returnFocus: true })
}

function shiftMonths(delta: number) {
  const total = viewYear.value * 12 + viewMonth.value + delta
  viewYear.value = Math.floor(total / 12)
  viewMonth.value = total % 12
}

function focusDay(day: string) {
  const date = parseIso(day)
  if (!date) return
  const dayTotal = date.getFullYear() * 12 + date.getMonth()
  const firstTotal = viewYear.value * 12 + viewMonth.value
  const lastTotal = firstTotal + monthCount.value - 1
  if (dayTotal < firstTotal) shiftMonths(dayTotal - firstTotal)
  else if (dayTotal > lastTotal) shiftMonths(dayTotal - lastTotal)
  focusedDay.value = day
  void nextTick(() => {
    panelRef.value?.querySelector<HTMLButtonElement>(`[data-day="${day}"]`)?.focus()
  })
}

function moveFocus(deltaDays: number) {
  const date = parseIso(focusedDay.value ?? today.value) ?? new Date()
  date.setDate(date.getDate() + deltaDays)
  focusDay(isoDate(date))
}

function onPanelKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    // Two-stage convention: swallow while open so a host dialog isn't
    // dismissed by the same keypress that closes this popover.
    event.stopPropagation()
    closePanel({ returnFocus: true })
    return
  }
  const inGrid = event.target instanceof HTMLElement && event.target.hasAttribute('data-day')
  if (event.key === 'PageUp' || event.key === 'PageDown') {
    event.preventDefault()
    const delta = event.key === 'PageUp' ? -1 : 1
    if (inGrid) {
      // Clamp to the target month's last day so Jan 31 + PageDown lands on
      // Feb 28/29, not Mar 3 (APG grid convention).
      const date = parseIso(focusedDay.value ?? today.value) ?? new Date()
      const targetTotal = date.getFullYear() * 12 + date.getMonth() + delta
      const targetYear = Math.floor(targetTotal / 12)
      const targetMonth = targetTotal % 12
      const lastDay = new Date(targetYear, targetMonth + 1, 0).getDate()
      focusDay(isoDate(new Date(targetYear, targetMonth, Math.min(date.getDate(), lastDay))))
    } else {
      shiftMonths(delta)
    }
    return
  }
  if (!inGrid) return
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    moveFocus(-1)
  } else if (event.key === 'ArrowRight') {
    event.preventDefault()
    moveFocus(1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    moveFocus(-7)
  } else if (event.key === 'ArrowDown') {
    event.preventDefault()
    moveFocus(7)
  }
}

function dayClass(cell: string): string[] {
  const range = displayRange.value
  const isStart = cell === range.from
  const isEnd = cell === range.to
  const inRange = Boolean(range.from && range.to && cell > range.from && cell < range.to)
  const classes = [
    'grid size-9 cursor-pointer place-items-center rounded-md text-[13px] transition',
  ]
  if (isStart || isEnd) classes.push('bg-accent font-semibold text-white')
  else if (inRange) classes.push('bg-accent-soft text-ink')
  else if (cell === today.value) classes.push('font-bold text-accent hover:bg-sunk')
  else classes.push('text-ink hover:bg-sunk')
  return classes
}

function dayAriaLabel(cell: string): string {
  const [year, month, day] = cell.split('-').map(Number)
  return `${day} ${UZ_MONTHS[(month ?? 1) - 1]} ${year}`
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
    <span class="mp-filter-dd-label" aria-hidden="true">{{ label }}</span>
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
      <span class="sr-only">{{ label }}</span>
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
        aria-label="Sana oralig'i"
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
              {{ DATE_RANGE_PRESET_LABELS[presetOption] }}
            </button>
          </div>

          <div class="flex items-start gap-4" @mouseleave="hovered = null">
            <div v-for="(monthView, monthIndex) in visibleMonths" :key="monthView.key">
              <div class="mb-2 flex items-center justify-between">
                <button
                  v-if="monthIndex === 0"
                  type="button"
                  class="grid size-8 place-items-center rounded-md text-ink-soft transition hover:bg-sunk hover:text-ink"
                  aria-label="Oldingi oy"
                  @click="shiftMonths(-1)"
                >
                  <svg class="size-4" viewBox="0 0 20 20" aria-hidden="true">
                    <path
                      d="M12.5 5 8 10l4.5 5"
                      fill="none"
                      stroke="currentColor"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="1.8"
                    />
                  </svg>
                </button>
                <span v-else class="size-8" aria-hidden="true"></span>
                <span class="text-[13px] font-bold text-ink">
                  {{ UZ_MONTHS[monthView.month] }} {{ monthView.year }}
                </span>
                <button
                  v-if="monthIndex === visibleMonths.length - 1"
                  type="button"
                  class="grid size-8 place-items-center rounded-md text-ink-soft transition hover:bg-sunk hover:text-ink"
                  aria-label="Keyingi oy"
                  @click="shiftMonths(1)"
                >
                  <svg class="size-4" viewBox="0 0 20 20" aria-hidden="true">
                    <path
                      d="m7.5 5 4.5 5-4.5 5"
                      fill="none"
                      stroke="currentColor"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="1.8"
                    />
                  </svg>
                </button>
                <span v-else class="size-8" aria-hidden="true"></span>
              </div>
              <div class="mb-1 grid grid-cols-7">
                <span
                  v-for="weekday in UZ_WEEKDAYS"
                  :key="weekday"
                  class="grid size-9 place-items-center text-[11px] font-bold text-ink-muted"
                >
                  {{ weekday }}
                </span>
              </div>
              <div role="grid" :aria-label="`${UZ_MONTHS[monthView.month]} ${monthView.year}`">
                <div
                  v-for="(week, weekIndex) in monthView.weeks"
                  :key="weekIndex"
                  role="row"
                  class="grid grid-cols-7"
                >
                  <template v-for="(cell, cellIndex) in week">
                    <button
                      v-if="cell"
                      :key="cell"
                      type="button"
                      role="gridcell"
                      :data-day="cell"
                      :tabindex="cell === focusedDay ? 0 : -1"
                      :aria-selected="cell === displayRange.from || cell === displayRange.to"
                      :aria-label="dayAriaLabel(cell)"
                      :class="dayClass(cell)"
                      @click="onDayClick(cell)"
                      @mouseenter="draftStart ? (hovered = cell) : undefined"
                    >
                      {{ Number(cell.slice(8)) }}
                    </button>
                    <span
                      v-else
                      :key="`blank-${weekIndex}-${cellIndex}`"
                      role="gridcell"
                      class="size-9"
                      aria-hidden="true"
                    ></span>
                  </template>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
