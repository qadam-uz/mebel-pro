import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import CuttingBranchPicker from '@/shared/components/CuttingBranchPicker.vue'
import type { ClientBranchOption } from '@/shared/stores/cutting'

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

const pinnedWorkshopBranches = [
  option(),
  option({ branch_id: 'b2', branch_name: 'Yunusobod', address: 'Yunusobod 8' }),
]

const crossWorkshop = [
  ...pinnedWorkshopBranches,
  option({
    branch_id: 'b3',
    workshop_id: 'w2',
    workshop_name: 'Yog’och Pro',
    branch_name: 'Sergeli',
    address: 'Sergeli 4',
  }),
]

describe('CuttingBranchPicker — pinned (scoped)', () => {
  it('names the workshop once and lists only its branches', () => {
    const view = mount(CuttingBranchPicker, {
      props: {
        options: pinnedWorkshopBranches,
        modelValue: null,
        pinnedWorkshopName: 'Mebel Master',
      },
    })

    expect(view.get('[data-testid="branch-picker-scope"]').text()).toBe('Mebel Master filiallari')
    expect(view.text()).toContain('Chilonzor')
    expect(view.text()).toContain('Yunusobod')
    // The header is the ONE place the workshop is named — the per-group header
    // would be a second label for the same thing.
    expect(view.text().match(/Mebel Master/g)).toHaveLength(1)
  })

  it('offers no way to reach another workshop — no tab, no search, no see-more', () => {
    const view = mount(CuttingBranchPicker, {
      props: {
        options: pinnedWorkshopBranches,
        modelValue: null,
        pinnedWorkshopName: 'Mebel Master',
      },
    })

    expect(view.find('input[type="search"]').exists()).toBe(false)
    expect(view.findAll('input')).toHaveLength(0)
    expect(view.text()).not.toContain('Yog’och Pro')
  })

  it('still selects a branch on tap', async () => {
    const view = mount(CuttingBranchPicker, {
      props: {
        options: pinnedWorkshopBranches,
        modelValue: null,
        pinnedWorkshopName: 'Mebel Master',
      },
    })

    await view
      .findAll('button')
      .find((node) => node.text().includes('Yunusobod'))
      ?.trigger('click')

    expect(view.emitted('update:modelValue')?.[0]).toEqual(['b2'])
  })
})

describe('CuttingBranchPicker — unpinned (unchanged)', () => {
  it('keeps the cross-workshop search and the per-workshop grouping', () => {
    const view = mount(CuttingBranchPicker, {
      props: { options: crossWorkshop, modelValue: null },
    })

    expect(view.find('[data-testid="branch-picker-scope"]').exists()).toBe(false)
    expect(view.find('input[type="search"]').exists()).toBe(true)
    expect(view.text()).toContain('Mebel Master')
    expect(view.text()).toContain('Yog’och Pro')
  })

  it('filters across workshops as it always did', async () => {
    const view = mount(CuttingBranchPicker, {
      props: { options: crossWorkshop, modelValue: null },
    })

    await view.get('input[type="search"]').setValue('Sergeli')

    expect(view.text()).toContain('Sergeli')
    expect(view.text()).not.toContain('Chilonzor')
  })
})

describe('CuttingBranchPicker — a pin with nothing visible', () => {
  it('shows the empty state rather than falling back to every workshop', () => {
    // §4/§8: the door to another workshop is that workshop's link, even when the
    // pinned workshop has no visible branch left.
    const view = mount(CuttingBranchPicker, {
      props: { options: [], modelValue: null, pinnedWorkshopName: 'Mebel Master' },
    })

    expect(view.text()).not.toContain('Yog’och Pro')
    expect(view.text().length).toBeGreaterThan(0)
  })
})
