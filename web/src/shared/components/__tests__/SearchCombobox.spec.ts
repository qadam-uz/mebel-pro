import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import SearchCombobox from '@/shared/components/SearchCombobox.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'

const ERROR_MESSAGE = "Buyurtma to'lovi uchun buyurtma tanlang."

const options: ChoiceOption[] = [
  { value: 'order-1', label: 'ORD-2026-000042 · Aziza Karimova', meta: '3 000 000' },
  { value: 'order-2', label: 'ORD-2026-000043 · Bobur Rasulov', meta: '1 200 000' },
]

function mountCombobox(props: Record<string, unknown> = {}) {
  return mount(SearchCombobox, {
    props: { label: 'Buyurtma', modelValue: null, options, ...props },
    attachTo: document.body,
    // The listbox teleports to <body> in production so it escapes `.table-wrap`,
    // which clips on both axes. Stubbing the teleport renders it in place so
    // these assertions keep querying through the wrapper — the behaviour under
    // test is the list's, not the portal's.
    global: { stubs: { teleport: true } },
  })
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('SearchCombobox changing an existing pick', () => {
  it('opens on the whole list, not on the one row matching what is already picked', async () => {
    // The regression this guards: choosing wrote the full option label into the
    // input and the client filter then matched only that label, so reopening a
    // set picker showed exactly one row — the option already chosen — and the
    // value could not be changed without deleting the text by hand.
    const wrapper = mountCombobox({ modelValue: 'order-1' })

    await wrapper.get('input').trigger('focus')
    await nextTick()

    expect(wrapper.findAll('[role="option"]')).toHaveLength(options.length)
    expect(wrapper.get('input').element.value).toBe('')
  })

  it('opens with the picked option marked and active, not the first row', async () => {
    const wrapper = mountCombobox({ modelValue: 'order-2' })

    await wrapper.get('input').trigger('focus')
    await nextTick()

    const picked = wrapper.findAll('[role="option"]')[1]
    expect(picked.attributes('aria-selected')).toBe('true')
    expect(wrapper.get('input').attributes('aria-activedescendant')).toBe(picked.attributes('id'))
  })

  it('shows the picked label as the placeholder while the list is open', async () => {
    const wrapper = mountCombobox({ modelValue: 'order-1' })

    await wrapper.get('input').trigger('focus')
    await nextTick()

    expect(wrapper.get('input').attributes('placeholder')).toBe(options[0].label)
  })

  it('keeps the selection when a search is typed and then abandoned', async () => {
    // Typing used to unset the model on the first keystroke, so starting a search
    // and pressing Escape dropped a perfectly good pick.
    const wrapper = mountCombobox({ modelValue: 'order-1' })

    await wrapper.get('input').trigger('focus')
    await wrapper.get('input').setValue('bobur')
    await wrapper.get('input').trigger('keydown', { key: 'Escape' })

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.get('input').element.value).toBe(options[0].label)
  })

  it('does not blank the query the user is typing', async () => {
    const wrapper = mountCombobox({ modelValue: 'order-1' })

    await wrapper.get('input').setValue('bobur')

    expect(wrapper.get('input').element.value).toBe('bobur')
    expect(wrapper.findAll('[role="option"]')).toHaveLength(1)
  })

  it('tells a server-backed parent the query is empty again when it reopens', async () => {
    const wrapper = mountCombobox({
      serverFiltered: true,
      searchDebounceMs: 250,
      modelValue: 'order-1',
    })

    await wrapper.get('input').trigger('focus')

    expect(wrapper.emitted('search')).toEqual([['']])
  })
})

describe('SearchCombobox client filtering', () => {
  it('narrows the list by label and meta as the user types', async () => {
    const wrapper = mountCombobox()

    await wrapper.get('input').setValue('bobur')

    const rendered = wrapper.findAll('[role="option"]').map((row) => row.text())
    expect(rendered).toHaveLength(1)
    expect(rendered[0]).toContain('Bobur Rasulov')
  })

  it('emits every keystroke synchronously when no debounce is configured', async () => {
    const wrapper = mountCombobox()
    const input = wrapper.get('input')

    await input.setValue('a')
    await input.setValue('az')

    expect(wrapper.emitted('search')).toEqual([['a'], ['az']])
  })
})

// QAD-123: the order picker queries the server. Typing an order number must
// cost one request, not one per character.
describe('SearchCombobox server-backed search', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('collapses a burst of keystrokes into a single debounced search', async () => {
    const wrapper = mountCombobox({ serverFiltered: true, searchDebounceMs: 250 })
    const input = wrapper.get('input')

    for (const value of ['0', '00', '000', '0004', '00042']) {
      await input.setValue(value)
      vi.advanceTimersByTime(50)
    }
    expect(wrapper.emitted('search')).toBeUndefined()

    vi.advanceTimersByTime(250)

    expect(wrapper.emitted('search')).toEqual([['00042']])
  })

  it('emits again once the user pauses a second time', async () => {
    const wrapper = mountCombobox({ serverFiltered: true, searchDebounceMs: 250 })
    const input = wrapper.get('input')

    await input.setValue('aziza')
    vi.advanceTimersByTime(250)
    await input.setValue('bobur')
    vi.advanceTimersByTime(250)

    expect(wrapper.emitted('search')).toEqual([['aziza'], ['bobur']])
  })

  it('keeps every server-supplied option instead of filtering them again', async () => {
    // The server matched on the phone number, which the option text does not
    // carry — filtering locally would drop the row it just found.
    const wrapper = mountCombobox({ serverFiltered: true, searchDebounceMs: 250 })

    await wrapper.get('input').setValue('901112233')

    expect(wrapper.findAll('[role="option"]')).toHaveLength(2)
  })

  it('clears without waiting out the debounce', async () => {
    const wrapper = mountCombobox({
      serverFiltered: true,
      searchDebounceMs: 250,
      clearable: true,
      modelValue: 'order-1',
    })

    await wrapper.get('input').setValue('aziz')
    await wrapper.get('button[type="button"]').trigger('click')

    expect(wrapper.emitted('search')).toEqual([['']])
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([null])
  })

  it('shows the loading row and the standing hint while a query is in flight', () => {
    const wrapper = mountCombobox({
      serverFiltered: true,
      loading: true,
      options: [],
      hint: "Faqat qoldig'i bor buyurtmalar",
    })

    wrapper.get('input').element.focus()

    return wrapper.vm.$nextTick().then(() => {
      expect(wrapper.get('input').attributes('aria-busy')).toBe('true')
      expect(wrapper.text()).toContain('Qidirilmoqda')
      expect(wrapper.text()).toContain("Faqat qoldig'i bor buyurtmalar")
      expect(wrapper.text()).not.toContain("Mos variant yo'q")
    })
  })
})

// QAD-123: submitting with no order picked used to drop the message into a
// banner far below the field. The rejection has to land on the control the
// operator must change — described by it, marked invalid, holding the caret,
// and with the message still readable once focus opens the list.
describe('SearchCombobox rejected input', () => {
  it('describes the input by its error and takes focus on demand', () => {
    const wrapper = mountCombobox({ serverFiltered: true, error: ERROR_MESSAGE })
    const input = wrapper.get('input')
    const describedBy = input.attributes('aria-describedby')

    expect(describedBy).toBeTruthy()
    expect(document.getElementById(describedBy ?? '')?.textContent?.trim()).toBe(ERROR_MESSAGE)

    wrapper.vm.focus()

    expect(document.activeElement).toBe(input.element)
  })

  it('reports the invalid state, not only the message', () => {
    const errored = mountCombobox({ serverFiltered: true, error: ERROR_MESSAGE })
    const clean = mountCombobox({ serverFiltered: true })

    expect(errored.get('input').attributes('aria-invalid')).toBe('true')
    expect(clean.get('input').attributes('aria-invalid')).toBeUndefined()
    expect(clean.get('input').attributes('aria-describedby')).toBeUndefined()
  })

  it('opens its list clear of the error message instead of over it', async () => {
    const wrapper = mountCombobox({ serverFiltered: true, error: ERROR_MESSAGE })

    wrapper.vm.focus()
    await wrapper.vm.$nextTick()

    const list = wrapper.get('[role="listbox"]')
    const describedBy = wrapper.get('input').attributes('aria-describedby') ?? ''
    const message = document.getElementById(describedBy)

    expect(message).not.toBeNull()
    // jsdom has no layout, so occlusion is pinned structurally. The list is now
    // fixed-positioned and teleported (it has to escape `.table-wrap`, which
    // clips on both axes), so "opens below the message" is no longer a DOM
    // relationship — it is whichever element the placement measures. Anchoring
    // to the bare input would put the panel straight over the error text, so the
    // guarantee is that the anchor CONTAINS the message.
    const anchor = wrapper.get('[data-placement-anchor]')
    expect(message).not.toBeNull()
    expect(anchor.element.contains(message)).toBe(true)
    expect(list.attributes('class')).toContain('fixed')
  })
})
