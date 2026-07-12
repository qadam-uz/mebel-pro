import { describe, expect, it } from 'vitest'

import {
  buildAdminMaterialWriteRequest,
  composeMaterialName,
  type AdminMaterialFormState,
} from '@/shared/app/adminMaterials'

function makeForm(overrides: Partial<AdminMaterialFormState> = {}): AdminMaterialFormState {
  return {
    kind: 'panel',
    manufacturerId: 'manufacturer-1',
    type: 'dsp',
    thicknessMm: '18',
    color: 'Dub Sonoma',
    decorCode: 'H1334',
    panelLengthMm: '2800',
    panelWidthMm: '2070',
    edgeWidthMm: '19',
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
      makeForm({ kind: 'edge', decorCode: '', edgeWidthMm: '42', imageFileId: null }),
    )

    expect(payload).toEqual({
      kind: 'edge',
      manufacturer_id: 'manufacturer-1',
      thickness_mm: '18',
      color: 'Dub Sonoma',
      decor_code: null,
      edge_width_mm: 42,
      image_file_id: null,
    })
    expect('type' in payload).toBe(false)
    expect('panel_length_mm' in payload).toBe(false)
    expect('panel_width_mm' in payload).toBe(false)
    expect('grain_direction' in payload).toBe(false)
  })
})

describe('composeMaterialName', () => {
  it('mirrors backend examples for panels and edges', () => {
    expect(composeMaterialName(makeForm(), 'Egger')).toBe(
      'LDSP Egger H1334 · Dub Sonoma · 2800×2070×18 mm',
    )
    expect(
      composeMaterialName(
        makeForm({
          kind: 'edge',
          decorCode: 'H1145',
          color: 'Sonoma eman',
          thicknessMm: '2.0',
          edgeWidthMm: '19',
        }),
        'Egger',
      ),
    ).toBe('Kromka Egger H1145 · Sonoma eman · 2×19 mm')
  })
})
