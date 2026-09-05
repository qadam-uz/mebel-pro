import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import CuttingBranchPicker from '@/shared/components/CuttingBranchPicker.vue'
import type { ClientBranchOption } from '@/shared/stores/cutting'

/**
 * Workshop-scope recovery only. The client editor takes its branch from the pin
 * (decision 17) and never raises this picker, so the scoped variant — one
 * workshop's branches under its own header — is gone with it.
 */
function option(overrides: Partial<ClientBranchOption> = {}): ClientBranchOption {
  return {
    branch_id: 'b1',
    workshop_id: 'w1',
    workshop_name: 'Mebel Master',
    branch_name: 'Chilonzor',
    address: 'Chilonzor 12',
    status: 'active',
    closed_reason: null,
    kerf_mm: 4,
    edge_trim_mm: 5,
    ...overrides,
  }
}

const crossWorkshop = [
  option(),
  option({ branch_id: 'b2', branch_name: 'Yunusobod', address: 'Yunusobod 8' }),
  option({
    branch_id: 'b3',
    workshop_id: 'w2',
    workshop_name: 'Yog’och Pro',
    branch_name: 'Sergeli',
    address: 'Sergeli 4',
  }),
]

describe('CuttingBranchPicker', () => {
  it('keeps the search and the per-workshop grouping', () => {
    const view = mount(CuttingBranchPicker, {
      props: { options: crossWorkshop, modelValue: null },
    })

    expect(view.find('input[type="search"]').exists()).toBe(true)
    expect(view.text()).toContain('Mebel Master')
    expect(view.text()).toContain('Yog’och Pro')
  })

  it('filters across workshops', async () => {
    const view = mount(CuttingBranchPicker, {
      props: { options: crossWorkshop, modelValue: null },
    })

    await view.get('input[type="search"]').setValue('Sergeli')

    expect(view.text()).toContain('Sergeli')
    expect(view.text()).not.toContain('Chilonzor')
  })

  it('shows its empty state when there is nothing to offer', () => {
    const view = mount(CuttingBranchPicker, {
      props: { options: [], modelValue: null },
    })

    expect(view.text().length).toBeGreaterThan(0)
    expect(view.find('input[type="search"]').exists()).toBe(false)
  })
})
