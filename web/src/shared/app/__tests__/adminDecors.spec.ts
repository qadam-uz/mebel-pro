import { describe, expect, it } from 'vitest'

import {
  buildDecorWriteRequest,
  composeDecorLabel,
  type AdminDecorFormState,
} from '@/shared/app/adminDecors'

function makeForm(overrides: Partial<AdminDecorFormState> = {}): AdminDecorFormState {
  return {
    manufacturerId: 'manufacturer-1',
    code: 'H1334',
    name: 'Dub Sonoma',
    has_grain: true,
    imageFileId: 'file-1',
    ...overrides,
  }
}

describe('buildDecorWriteRequest', () => {
  // One flat payload, no panel/edge union: the admin app owns identity only, so
  // thickness, size, grain and price have no arm to belong to any more.
  it('sends exactly the five identity fields', () => {
    expect(buildDecorWriteRequest(makeForm())).toEqual({
      manufacturer_id: 'manufacturer-1',
      code: 'H1334',
      name: 'Dub Sonoma',
      has_grain: true,
      image_file_id: 'file-1',
    })
  })

  it('nulls an empty kod and keeps kromka on the same shape', () => {
    expect(
      buildDecorWriteRequest(
        makeForm({
          code: '  ',
          name: 'Sonoma eman',
          has_grain: false,
          imageFileId: null,
        }),
      ),
    ).toEqual({
      manufacturer_id: 'manufacturer-1',
      code: null,
      name: 'Sonoma eman',
      has_grain: false,
      image_file_id: null,
    })
  })
})

describe('composeDecorLabel', () => {
  // BEHAVIOUR CHANGE, not a rename: the old `composeMaterialName` ended in
  // ` · 2800×2070×18 mm` / ` · 2×19 mm`. A decor has no thickness and no size, so
  // the preview is the IDENTITY half of material_label() and nothing more. The
  // dimension segment reappears on the branch's own row, where the format lives.
  it('previews the identity prefix for a panel dekor', () => {
    expect(composeDecorLabel(makeForm(), 'Egger')).toBe('Egger H1334 · Dub Sonoma')
  })

  it('previews a code-bearing dekor without any substrate prefix', () => {
    expect(composeDecorLabel(makeForm({ code: 'H1145', name: 'Sonoma eman' }), 'Egger')).toBe(
      'Egger H1145 · Sonoma eman',
    )
  })

  it('does not repeat name when there is no code to put in the base', () => {
    expect(composeDecorLabel(makeForm({ code: '', name: 'Sonoma eman' }), 'Egger')).toBe(
      'Egger Sonoma eman',
    )
  })

  it('shows placeholders while the form is still empty', () => {
    expect(composeDecorLabel(makeForm({ code: '', name: '' }), null)).toBe('... ...')
  })
})
