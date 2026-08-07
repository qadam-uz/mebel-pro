import { describe, expect, it } from 'vitest'

import {
  buildDekorWriteRequest,
  composeDekorLabel,
  type AdminDekorFormState,
} from '@/shared/app/adminDekorlar'

function makeForm(overrides: Partial<AdminDekorFormState> = {}): AdminDekorFormState {
  return {
    manufacturerId: 'manufacturer-1',
    tur: 'ldsp',
    kod: 'H1334',
    nomi: 'Dub Sonoma',
    tolali: true,
    imageFileId: 'file-1',
    ...overrides,
  }
}

describe('buildDekorWriteRequest', () => {
  // One flat payload, no panel/edge union: the admin app owns identity only, so
  // thickness, size, grain and price have no arm to belong to any more.
  it('sends exactly the six identity fields', () => {
    expect(buildDekorWriteRequest(makeForm())).toEqual({
      manufacturer_id: 'manufacturer-1',
      tur: 'ldsp',
      kod: 'H1334',
      nomi: 'Dub Sonoma',
      tolali: true,
      image_file_id: 'file-1',
    })
  })

  it('nulls an empty kod and keeps kromka on the same shape', () => {
    expect(
      buildDekorWriteRequest(
        makeForm({
          tur: 'kromka',
          kod: '  ',
          nomi: 'Sonoma eman',
          tolali: false,
          imageFileId: null,
        }),
      ),
    ).toEqual({
      manufacturer_id: 'manufacturer-1',
      tur: 'kromka',
      kod: null,
      nomi: 'Sonoma eman',
      tolali: false,
      image_file_id: null,
    })
  })
})

describe('composeDekorLabel', () => {
  // BEHAVIOUR CHANGE, not a rename: the old `composeMaterialName` ended in
  // ` · 2800×2070×18 mm` / ` · 2×19 mm`. A dekor has no thickness and no size, so
  // the preview is the IDENTITY half of material_label() and nothing more. The
  // dimension segment reappears on the branch's own row, where the format lives.
  it('previews the identity prefix for a panel dekor', () => {
    expect(composeDekorLabel(makeForm(), 'Egger')).toBe('LDSP Egger H1334 · Dub Sonoma')
  })

  it('previews a kromka dekor through the same generic path', () => {
    expect(
      composeDekorLabel(makeForm({ tur: 'kromka', kod: 'H1145', nomi: 'Sonoma eman' }), 'Egger'),
    ).toBe('Kromka Egger H1145 · Sonoma eman')
  })

  it('does not repeat nomi when there is no kod to put in the base', () => {
    expect(composeDekorLabel(makeForm({ kod: '', nomi: 'Sonoma eman' }), 'Egger')).toBe(
      'LDSP Egger Sonoma eman',
    )
  })

  it('shows placeholders while the form is still empty', () => {
    expect(composeDekorLabel(makeForm({ kod: '', nomi: '' }), null)).toBe('LDSP ... ...')
  })
})
