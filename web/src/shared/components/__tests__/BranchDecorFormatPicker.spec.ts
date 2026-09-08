import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import BranchDecorFormatPicker from '@/shared/components/BranchDecorFormatPicker.vue'
import type { DecorType } from '@/shared/stores/admin'

function mountPicker(initialType: DecorType = 'ldsp') {
  return mount(BranchDecorFormatPicker, { props: { initialType } })
}

/** The substrate chips — `ClientChipFilter` renders them as radios. */
function typeChip(wrapper: ReturnType<typeof mountPicker>, label: string) {
  return wrapper.findAll('[role="radio"]').find((chip) => chip.text() === label)
}

function thicknessChips(wrapper: ReturnType<typeof mountPicker>) {
  return wrapper
    .findAll('button.mp-chip')
    .filter((chip) => chip.attributes('aria-pressed'))
    .map((chip) => chip.text())
}

describe('BranchDecorFormatPicker — the substrate decides the fields', () => {
  it('offers «1 tomonlama» only for the laminated boards', async () => {
    const wrapper = mountPicker('ldsp')
    expect(wrapper.text()).toContain('1 tomonlama')

    // A finished face is the laminate: LMDF has one to count, bare MDF and DSP
    // do not, and neither does anything else (2026-09-08).
    await typeChip(wrapper, 'LMDF')!.trigger('click')
    expect(wrapper.text()).toContain('1 tomonlama')

    for (const label of ['DSP', 'MDF', 'Fanera', 'Kromka']) {
      await typeChip(wrapper, label)!.trigger('click')
      expect(wrapper.text()).not.toContain('1 tomonlama')
    }
  })

  it('gives LMDF the MDF chip set', async () => {
    const wrapper = mountPicker('mdf')
    const mdf = thicknessChips(wrapper)
    await typeChip(wrapper, 'LMDF')!.trigger('click')
    expect(thicknessChips(wrapper)).toEqual(mdf)
    expect(thicknessChips(wrapper)).toEqual(['3', '8', '16', '18', '2800×2070', '2440×1220'])
  })

  it('composes a one-sided LMDF sheet, and drops the count on a bare panel', async () => {
    const wrapper = mountPicker('lmdf')
    const chip = (label: string) =>
      wrapper.findAll('button.mp-chip').find((node) => node.text() === label)!
    await chip('16').trigger('click')
    await chip('2800×2070').trigger('click')
    await wrapper.find('input[type="checkbox"]').setValue(true)
    await wrapper.find('button.mp-button-outline').trigger('click')

    expect(wrapper.emitted('add')?.[0]).toEqual([
      {
        type: 'lmdf',
        thickness_mm: '16',
        length_mm: 2800,
        width_mm: 2070,
        tape_width_mm: null,
        finished_sides: 1,
      },
    ])

    // The same geometry under MDF carries `null` — the field is not offered, so
    // it cannot be sent.
    await typeChip(wrapper, 'MDF')!.trigger('click')
    await chip('16').trigger('click')
    await chip('2800×2070').trigger('click')
    await wrapper.find('button.mp-button-outline').trigger('click')
    expect(wrapper.emitted('add')?.[1]).toEqual([
      {
        type: 'mdf',
        thickness_mm: '16',
        length_mm: 2800,
        width_mm: 2070,
        tape_width_mm: null,
        finished_sides: null,
      },
    ])
  })
})
