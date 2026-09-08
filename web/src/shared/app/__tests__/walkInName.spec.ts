import { describe, expect, it } from 'vitest'

import { isOperatorTypedName, walkInNameAfterLookup } from '@/shared/app/walkInName'

describe('walkInNameAfterLookup', () => {
  it('keeps what the operator typed while the lookup was in flight when it misses', () => {
    const after = walkInNameAfterLookup({ value: 'Dilshod', fromLookup: null }, null)

    expect(after.value).toBe('Dilshod')
    expect(after.fromLookup).toBeNull()
  })

  it('clears a name a previous lookup filled when the next number is unknown', () => {
    const after = walkInNameAfterLookup({ value: 'Bobur', fromLookup: 'Bobur' }, null)

    expect(after.value).toBe('')
    expect(after.fromLookup).toBeNull()
  })

  it('keeps a name the operator retyped over a previous lookup when the next number is unknown', () => {
    const after = walkInNameAfterLookup({ value: 'Karim', fromLookup: 'Bobur' }, null)

    expect(after.value).toBe('Karim')
    expect(after.fromLookup).toBeNull()
  })

  it('leaves an untouched empty field empty on a miss', () => {
    expect(walkInNameAfterLookup({ value: '', fromLookup: null }, null)).toEqual({
      value: '',
      fromLookup: null,
    })
  })

  it('shows the matched client over anything on screen, because the field then claims to be theirs', () => {
    expect(walkInNameAfterLookup({ value: 'Dilshod', fromLookup: null }, 'Bobur')).toEqual({
      value: 'Bobur',
      fromLookup: 'Bobur',
    })
    expect(walkInNameAfterLookup({ value: 'Aziz', fromLookup: 'Aziz' }, 'Bobur')).toEqual({
      value: 'Bobur',
      fromLookup: 'Bobur',
    })
  })

  it('marks a fresh hit as the lookup’s, so the next miss may clear it', () => {
    const hit = walkInNameAfterLookup({ value: '', fromLookup: null }, 'Bobur')

    expect(isOperatorTypedName(hit)).toBe(false)
    expect(walkInNameAfterLookup(hit, null).value).toBe('')
  })
})

describe('isOperatorTypedName', () => {
  it('reads an empty untouched field as nobody’s', () => {
    expect(isOperatorTypedName({ value: '', fromLookup: null })).toBe(false)
  })

  it('reads a typed name with no lookup behind it as the operator’s', () => {
    expect(isOperatorTypedName({ value: 'Dilshod', fromLookup: null })).toBe(true)
  })
})
