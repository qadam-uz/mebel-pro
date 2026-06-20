import { describe, expect, it } from 'vitest'

import {
  buildAdminMaterialWriteRequest,
  type AdminMaterialFormState,
} from '@/shared/app/adminMaterials'

function makeForm(overrides: Partial<AdminMaterialFormState> = {}): AdminMaterialFormState {
  return {
    kind: 'panel',
    manufacturerId: 'manufacturer-1',
    type: 'dsp',
    name: 'Panel H1334',
    thicknessMm: '18',
    color: 'Dub Sonoma',
    decorCode: 'H1334',
    panelLengthMm: '2800',
    panelWidthMm: '2070',
    grainDirection: true,
    imageFileId: 'file-1',
    ...overrides,
  }
}

describe('buildAdminMaterialWriteRequest', () => {
  it('keeps panel-only fields for panel materials', () => {
    expect(buildAdminMaterialWriteRequest(makeForm())).toEqual({
      kind: 'panel',
      manufacturer_id: 'manufacturer-1',
      type: 'dsp',
      name: 'Panel H1334',
      thickness_mm: '18',
      color: 'Dub Sonoma',
      decor_code: 'H1334',
      panel_length_mm: 2800,
      panel_width_mm: 2070,
      grain_direction: true,
      image_file_id: 'file-1',
    })
  })

  it('omits panel-only keys for edge materials', () => {
    const payload = buildAdminMaterialWriteRequest(
      makeForm({ kind: 'edge', decorCode: '', imageFileId: null }),
    )

    expect(payload).toEqual({
      kind: 'edge',
      manufacturer_id: 'manufacturer-1',
      name: 'Panel H1334',
      thickness_mm: '18',
      color: 'Dub Sonoma',
      decor_code: null,
      image_file_id: null,
    })
    expect('type' in payload).toBe(false)
    expect('panel_length_mm' in payload).toBe(false)
    expect('panel_width_mm' in payload).toBe(false)
    expect('grain_direction' in payload).toBe(false)
  })
})
