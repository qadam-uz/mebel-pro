import { describe, expect, it } from 'vitest'
import {
  buildActionLogQuery,
  buildStatusChangeQuery,
  errorCountDisplay,
  genTempPassword,
  isErrorHot,
  materialCreatePayload,
  validateMaterialForm,
  type MaterialForm,
} from '../admin'

function sheetForm(overrides: Partial<MaterialForm> = {}): MaterialForm {
  return {
    kind: 'sheet',
    type: 'dsp',
    name: 'LDSP H1334',
    thickness_mm: '18',
    color: 'Dub Sonoma',
    decor_code: 'H1334',
    sheet_length_mm: '2750',
    sheet_width_mm: '1830',
    grain_direction: true,
    ...overrides,
  }
}

describe('genTempPassword', () => {
  it('produces a password with an upper, a lower and a digit, ending with !', () => {
    for (let i = 0; i < 50; i++) {
      const pw = genTempPassword()
      expect(pw.length).toBeGreaterThanOrEqual(11)
      expect(pw.endsWith('!')).toBe(true)
      expect(/[A-Z]/.test(pw)).toBe(true)
      expect(/[a-z]/.test(pw)).toBe(true)
      expect(/\d/.test(pw)).toBe(true)
    }
  })

  it('avoids ambiguous glyphs', () => {
    for (let i = 0; i < 50; i++) {
      const pw = genTempPassword().slice(0, -1) // drop the trailing !
      expect(/[0O1lI]/.test(pw)).toBe(false)
    }
  })
})

describe('validateMaterialForm — sheet', () => {
  it('accepts a complete sheet form with length ≥ width', () => {
    const v = validateMaterialForm(sheetForm())
    expect(v.ok).toBe(true)
    expect(v.dimsBad).toBe(false)
  })

  it('flags length < width as a dimension error', () => {
    const v = validateMaterialForm(sheetForm({ sheet_length_mm: '1830', sheet_width_mm: '2750' }))
    expect(v.dimsBad).toBe(true)
    expect(v.ok).toBe(false)
  })

  it('accepts length === width', () => {
    const v = validateMaterialForm(sheetForm({ sheet_length_mm: '2000', sheet_width_mm: '2000' }))
    expect(v.dimsBad).toBe(false)
    expect(v.ok).toBe(true)
  })

  it('requires sheet dimensions', () => {
    expect(validateMaterialForm(sheetForm({ sheet_length_mm: '' })).ok).toBe(false)
    expect(validateMaterialForm(sheetForm({ sheet_width_mm: '0' })).ok).toBe(false)
  })

  it('does not flag dimsBad until both are positive', () => {
    const v = validateMaterialForm(sheetForm({ sheet_length_mm: '', sheet_width_mm: '2750' }))
    expect(v.dimsBad).toBe(false)
  })
})

describe('validateMaterialForm — edge', () => {
  const edge: MaterialForm = {
    kind: 'edge',
    type: '',
    name: 'Krom PVC 0.4',
    thickness_mm: '0.4',
    color: 'Dub Sonoma',
    decor_code: '',
    sheet_length_mm: '',
    sheet_width_mm: '',
    grain_direction: false,
  }

  it('ignores sheet dimensions entirely', () => {
    const v = validateMaterialForm(edge)
    expect(v.ok).toBe(true)
    expect(v.dimsBad).toBe(false)
  })

  it('still requires name, colour and thickness', () => {
    expect(validateMaterialForm({ ...edge, name: '  ' }).ok).toBe(false)
    expect(validateMaterialForm({ ...edge, thickness_mm: '0' }).ok).toBe(false)
  })
})

describe('materialCreatePayload', () => {
  it('includes sheet-only fields for sheets', () => {
    const p = materialCreatePayload(sheetForm())
    expect(p.kind).toBe('sheet')
    expect(p.type).toBe('dsp')
    expect(p.sheet_length_mm).toBe(2750)
    expect(p.sheet_width_mm).toBe(1830)
    expect(p.grain_direction).toBe(true)
    expect(p.decor_code).toBe('H1334')
  })

  it('drops sheet-only fields for edges', () => {
    const p = materialCreatePayload({
      kind: 'edge',
      type: 'dsp',
      name: 'Krom',
      thickness_mm: '0.4',
      color: 'Oq',
      decor_code: '',
      sheet_length_mm: '2750',
      sheet_width_mm: '1830',
      grain_direction: true,
    })
    expect(p.kind).toBe('edge')
    expect(p.type).toBeUndefined()
    expect(p.sheet_length_mm).toBeUndefined()
    expect(p.sheet_width_mm).toBeUndefined()
    expect(p.grain_direction).toBeUndefined()
    expect(p.decor_code).toBeNull()
  })
})

describe('error count display', () => {
  it('shows 24h · 7d', () => {
    expect(errorCountDisplay(12, 84)).toBe('12 · 84')
    expect(errorCountDisplay(0, 0)).toBe('0 · 0')
  })

  it('flags hot rows above the warn threshold', () => {
    expect(isErrorHot(11)).toBe(true)
    expect(isErrorHot(10)).toBe(false)
    expect(isErrorHot(0)).toBe(false)
  })
})

describe('buildActionLogQuery', () => {
  it('drops empty values and maps camelCase to snake_case', () => {
    const q = buildActionLogQuery({
      action: 'order.approve',
      module: '  ',
      actor: 'hasan',
      entityType: 'order',
      entityId: 'abc',
      dateFrom: '2026-01-01',
      limit: 50,
      offset: 0,
    })
    const params = new URLSearchParams(q)
    expect(params.get('action')).toBe('order.approve')
    expect(params.has('module')).toBe(false)
    expect(params.get('actor')).toBe('hasan')
    expect(params.get('entity_type')).toBe('order')
    expect(params.get('entity_id')).toBe('abc')
    expect(params.get('date_from')).toBe('2026-01-01')
    expect(params.get('limit')).toBe('50')
    expect(params.get('offset')).toBe('0')
  })

  it('returns an empty string when nothing is set', () => {
    expect(buildActionLogQuery({})).toBe('')
  })
})

describe('buildStatusChangeQuery', () => {
  it('maps from/to status and entity filters', () => {
    const q = buildStatusChangeQuery({
      entityType: 'order',
      fromStatus: 'new',
      toStatus: 'confirmed',
      actor: 'aziz',
      limit: 25,
    })
    const params = new URLSearchParams(q)
    expect(params.get('entity_type')).toBe('order')
    expect(params.get('from_status')).toBe('new')
    expect(params.get('to_status')).toBe('confirmed')
    expect(params.get('actor')).toBe('aziz')
    expect(params.get('limit')).toBe('25')
  })
})
