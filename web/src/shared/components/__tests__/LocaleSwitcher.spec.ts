import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import LocaleSwitcher from '@/shared/components/LocaleSwitcher.vue'
import { DEFAULT_LOCALE, i18n, setLocale } from '@/shared/i18n'

afterEach(async () => {
  document.body.innerHTML = ''
  await setLocale(DEFAULT_LOCALE)
})

describe('LocaleSwitcher', () => {
  it('names every language in its own script, so it is legible to the person who needs it', () => {
    const wrapper = mount(LocaleSwitcher, { props: { variant: 'segmented' } })
    const labels = wrapper.findAll('[role="radio"]').map((button) => button.text())

    expect(labels).toEqual(["O'zbekcha", 'Ўзбекча', 'Русский'])
  })

  it('marks the active language as checked', async () => {
    await setLocale('ru')
    const wrapper = mount(LocaleSwitcher, { props: { variant: 'segmented' } })

    const checked = wrapper.findAll('[role="radio"][aria-checked="true"]')
    expect(checked).toHaveLength(1)
    expect(checked[0].text()).toBe('Русский')
  })

  it('switches the app locale when a segment is picked', async () => {
    const wrapper = mount(LocaleSwitcher, { props: { variant: 'segmented' } })

    await wrapper.findAll('[role="radio"]')[2].trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(i18n.global.locale.value).toBe('ru')
    expect(document.documentElement.dataset.locale).toBe('ru')
  })

  it('shows the current language on the collapsed trigger without opening it', async () => {
    await setLocale('uz-Cyrl')
    const wrapper = mount(LocaleSwitcher)

    expect(wrapper.get('button').text()).toBe('ЎЗ')
    expect(wrapper.get('button').attributes('aria-label')).toContain('Ўзбекча')
  })

  it('keeps the current language in the menu and ticks it', async () => {
    const wrapper = mount(LocaleSwitcher, { attachTo: document.body })
    await wrapper.get('button').trigger('click')

    const items = document.querySelectorAll('[role="menuitem"]')
    expect([...items].map((item) => item.textContent?.trim())).toEqual([
      "O'zbekcha",
      'Ўзбекча',
      'Русский',
    ])
    expect(items[0].querySelector('svg')).not.toBeNull()
    expect(items[2].querySelector('svg')).toBeNull()

    wrapper.unmount()
  })
})
