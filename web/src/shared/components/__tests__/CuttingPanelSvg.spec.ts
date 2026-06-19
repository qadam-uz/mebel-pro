import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import type { CuttingPanel, CuttingResult } from '@/shared/stores/cutting'

const panel: CuttingPanel = {
  id: 'panel-1',
  material_id: 'mat-1',
  panel_index: 1,
  waste_area_mm2: 0,
  placements: [
    {
      id: 'placement-1',
      part_ref: 'A',
      part_quantity_index: 1,
      x_mm: 0,
      y_mm: 0,
      length_mm: 300,
      width_mm: 200,
      rotated: false,
    },
  ],
}

const result = {
  id: 'result-1',
  panels: [panel],
  material_snapshots: {
    'mat-1': {
      name: 'Panel',
      panel_length_mm: 1000,
      panel_width_mm: 700,
    },
  },
  panels_used_by_material: { 'mat-1': 1 },
  total_cut_length_mm: 0,
  total_edge_length_mm: 0,
  waste_percentage: '0',
} as unknown as CuttingResult

describe('CuttingPanelSvg', () => {
  it('keeps placements out of the keyboard tab order while preserving mouse selection', async () => {
    const wrapper = mount(CuttingPanelSvg, {
      props: {
        result,
        panel,
        activePlacementId: null,
      },
    })

    expect(wrapper.find('[role="button"]').exists()).toBe(false)
    const placement = wrapper.get('.placement')
    expect(placement.attributes('tabindex')).toBeUndefined()
    expect(placement.attributes('aria-hidden')).toBe('true')

    await placement.trigger('click')
    expect(wrapper.emitted('select-placement')?.[0]).toEqual([panel.placements[0]])
  })
})
