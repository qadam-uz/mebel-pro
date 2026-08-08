import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { isoDate } from '@/shared/app/dateRange'
import CalendarMonths from '@/shared/components/CalendarMonths.vue'

function mountCalendar(props: Record<string, unknown> = {}) {
  return mount(CalendarMonths, {
    props: { anchor: '2026-07-15', ...props },
  })
}

function dayClasses(wrapper: ReturnType<typeof mountCalendar>, day: string): string {
  return wrapper.get(`[data-day="${day}"]`).attributes('class') ?? ''
}

describe('CalendarMonths', () => {
  // A day's fill is the whole of what the grid says about it, and every fill here
  // is a token whose VALUE can be remapped without breaking a build — so the
  // states are asserted against each other, not against a hex.
  it('paints the range endpoints, the in-range band and hover as three distinct fills', () => {
    const wrapper = mountCalendar({ from: '2026-07-10', to: '2026-07-14', trackHover: true })

    const start = dayClasses(wrapper, '2026-07-10')
    const inRange = dayClasses(wrapper, '2026-07-12')
    const plain = dayClasses(wrapper, '2026-07-20')

    // Endpoints: the graphite fill with bone text.
    expect(start).toContain('bg-accent')
    expect(start).toContain('text-on-accent')
    expect(dayClasses(wrapper, '2026-07-14')).toContain('bg-accent')

    // The band is the `track` trough — never `sunk`, which is the hover fill and
    // is all but invisible on the white popover.
    expect(inRange).toContain('bg-track')
    expect(inRange).not.toContain('bg-sunk')

    // A day outside the range has no fill of its own, only the hover one.
    expect(plain).toContain('hover:bg-sunk')
    expect(plain).not.toContain('bg-track')

    wrapper.unmount()
  })

  it('keeps an in-range day reading as in-range while the cursor is over it', () => {
    // The host feeds the draft `to` back through `hovered` while picking, so the
    // hovered day is frequently also inside the painted span.
    const wrapper = mountCalendar({
      from: '2026-07-10',
      to: '2026-07-14',
      hovered: '2026-07-12',
      trackHover: true,
    })

    const hoveredInRange = dayClasses(wrapper, '2026-07-12')
    expect(hoveredInRange).toContain('bg-track')
    expect(hoveredInRange).not.toContain('hover:bg-sunk')

    wrapper.unmount()
  })

  it('marks today without a fill, so it cannot be mistaken for a range endpoint', () => {
    const today = isoDate(new Date())
    const wrapper = mountCalendar({ anchor: today })
    const todayClasses = dayClasses(wrapper, today)

    expect(todayClasses).toContain('text-accent-deep')
    expect(todayClasses).not.toContain('bg-accent')
    expect(todayClasses).not.toContain('bg-track')

    wrapper.unmount()
  })
})
