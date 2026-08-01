<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

import { isoDate, monthGrid, monthNames, weekdayShortNames } from '@/shared/app/dateRange'

// The app's one calendar surface: month navigation, a Monday-first day grid and
// APG grid keyboard navigation. It renders inside a host popover
// (DateRangePicker, DateField) and knows nothing about how the host turns
// clicks into a value — it just paints a highlighted [from, to] span (a single
// day is from === to) and emits the day that was clicked.
const props = withDefaults(
  defineProps<{
    // The day whose month is the LAST visible one, and the day the roving tab
    // stop starts on. Both are read once, at creation: hosts mount the calendar
    // fresh every time their popover opens, so the first paint is already
    // positioned — no post-mount correction, no measuring a stale panel.
    anchor: string
    initialFocus?: string
    monthCount?: number
    from?: string | null
    to?: string | null
    hovered?: string | null
    min?: string
    max?: string
    // Range hosts preview the span under the cursor; single-date hosts don't.
    trackHover?: boolean
  }>(),
  {
    initialFocus: '',
    monthCount: 1,
    from: null,
    to: null,
    hovered: null,
    min: '',
    max: '',
    trackHover: false,
  },
)

const emit = defineEmits<{
  select: [day: string]
  'update:hovered': [value: string | null]
}>()

function parseIso(value: string): Date | null {
  if (!value) return null
  const [year, month, day] = value.split('-').map(Number)
  if (!year || !month || !day) return null
  return new Date(year, month - 1, day)
}

// Computed, not module constants: the grid has to repaint in the new language
// when someone switches locale with the picker open.
const months = computed(() => monthNames())
const weekdays = computed(() => weekdayShortNames())

const rootRef = ref<HTMLDivElement | null>(null)

const anchorDate = parseIso(props.anchor) ?? new Date()
// The month index (year * 12 + month) of the first visible month.
const firstTotal = anchorDate.getFullYear() * 12 + anchorDate.getMonth() - (props.monthCount - 1)
const viewYear = ref(Math.floor(firstTotal / 12))
const viewMonth = ref(firstTotal % 12)

// A roving tab stop must land on a RENDERED cell; the preferred focus day can
// sit before the visible window (e.g. "Oxirgi 30 kun" on a one-month view), so
// fall back to the anchor, which is always visible.
const focusDate = parseIso(props.initialFocus)
const focusTotal = focusDate ? focusDate.getFullYear() * 12 + focusDate.getMonth() : Number.NaN
const focusedDay = ref<string | null>(
  focusDate && focusTotal >= firstTotal && focusTotal < firstTotal + props.monthCount
    ? props.initialFocus
    : props.anchor,
)

const today = computed(() => isoDate(new Date()))

const visibleMonths = computed(() => {
  const months: { year: number; month: number; key: string; weeks: (string | null)[][] }[] = []
  for (let index = 0; index < props.monthCount; index += 1) {
    const total = viewYear.value * 12 + viewMonth.value + index
    const year = Math.floor(total / 12)
    const month = total % 12
    months.push({ year, month, key: `${year}-${month}`, weeks: monthGrid(year, month) })
  }
  return months
})

function isDisabled(cell: string): boolean {
  if (props.min && cell < props.min) return true
  if (props.max && cell > props.max) return true
  return false
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
  const lastTotal = firstTotal + props.monthCount - 1
  if (dayTotal < firstTotal) shiftMonths(dayTotal - firstTotal)
  else if (dayTotal > lastTotal) shiftMonths(dayTotal - lastTotal)
  focusedDay.value = day
  void nextTick(() => {
    rootRef.value?.querySelector<HTMLButtonElement>(`[data-day="${day}"]`)?.focus()
  })
}

function moveFocus(deltaDays: number) {
  const date = parseIso(focusedDay.value ?? today.value) ?? new Date()
  date.setDate(date.getDate() + deltaDays)
  focusDay(isoDate(date))
}

/**
 * Grid keyboard navigation. Hosts call this from their popover's keydown so
 * PageUp/PageDown still pages the calendar when focus sits on a sibling
 * control (a preset shortcut, the text field) rather than on a day cell.
 */
function onKeydown(event: KeyboardEvent) {
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
  const isStart = cell === props.from
  const isEnd = cell === props.to
  const inRange = Boolean(props.from && props.to && cell > props.from && cell < props.to)
  const classes = ['grid size-9 place-items-center rounded-md text-[13px] transition']
  if (isDisabled(cell)) {
    classes.push('cursor-not-allowed text-ink-muted opacity-40')
    return classes
  }
  classes.push('cursor-pointer')
  if (isStart || isEnd) classes.push('bg-accent font-semibold text-white')
  else if (inRange) classes.push('bg-accent-soft text-ink')
  else if (cell === today.value) classes.push('font-bold text-accent hover:bg-sunk')
  else classes.push('text-ink hover:bg-sunk')
  return classes
}

function dayAriaLabel(cell: string): string {
  const [year, month, day] = cell.split('-').map(Number)
  return `${day} ${months.value[(month ?? 1) - 1]} ${year}`
}

function onDayClick(cell: string) {
  if (isDisabled(cell)) return
  emit('select', cell)
}

function onDayEnter(cell: string) {
  if (props.trackHover) emit('update:hovered', cell)
}

defineExpose({ shiftMonths, focusDay, onKeydown })
</script>

<template>
  <div
    ref="rootRef"
    class="flex items-start gap-4"
    @mouseleave="trackHover ? emit('update:hovered', null) : undefined"
  >
    <div v-for="(monthView, monthIndex) in visibleMonths" :key="monthView.key">
      <div class="mb-2 flex items-center justify-between">
        <button
          v-if="monthIndex === 0"
          type="button"
          class="grid size-8 place-items-center rounded-md text-ink-soft transition hover:bg-sunk hover:text-ink"
          :aria-label="$t('forms.calendar.previousMonth')"
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
          {{ months[monthView.month] }} {{ monthView.year }}
        </span>
        <button
          v-if="monthIndex === visibleMonths.length - 1"
          type="button"
          class="grid size-8 place-items-center rounded-md text-ink-soft transition hover:bg-sunk hover:text-ink"
          :aria-label="$t('forms.calendar.nextMonth')"
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
          v-for="weekday in weekdays"
          :key="weekday"
          class="grid size-9 place-items-center text-[11px] font-bold text-ink-muted"
        >
          {{ weekday }}
        </span>
      </div>
      <div role="grid" :aria-label="`${months[monthView.month]} ${monthView.year}`">
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
              :aria-selected="cell === from || cell === to"
              :aria-disabled="isDisabled(cell) ? 'true' : undefined"
              :aria-label="dayAriaLabel(cell)"
              :class="dayClass(cell)"
              @click="onDayClick(cell)"
              @mouseenter="onDayEnter(cell)"
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
</template>
