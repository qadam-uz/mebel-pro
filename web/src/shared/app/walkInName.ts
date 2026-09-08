/**
 * Who owns the «Ism» field on the walk-in step — the operator, or the phone
 * lookup.
 *
 * The lookup is debounced (350 ms) and the name field is editable the whole
 * time, so the two writers race: a busy counter operator types the name of the
 * person standing in front of them while the answer for the number they just
 * finished is still in flight. The miss branch used to clear the field
 * unconditionally, so a lookup the operator never asked for ate what they had
 * typed — silently, and only for the fast typists.
 *
 * The rule: **a lookup may only write over what a lookup wrote.** `fromLookup`
 * is the exact string the last hit put in the field. While the field still
 * holds it, the value on screen is the base's and a fresh answer may replace or
 * clear it; the moment it differs, the value is the operator's and a miss
 * leaves it alone.
 *
 * A hit is the one thing that always wins, including over operator-typed text.
 * It is not a convenience prefill: the field goes read-only and the caption
 * («Bazadan topildi — boshqa odam bo'lsa, raqamni tekshiring») asks the
 * operator to compare the base's name against the person at the counter. Show
 * their own half-typed text there and that check reads as confirmed when
 * nothing was ever compared.
 */

export interface WalkInNameField {
  /** What the «Ism» input shows. */
  value: string
  /** The exact string the last lookup hit wrote, or `null` when none did. */
  fromLookup: string | null
}

/** True while the value on screen is the operator's own typing, not a lookup's. */
export function isOperatorTypedName(field: WalkInNameField): boolean {
  return field.value !== (field.fromLookup ?? '')
}

/**
 * The field after a settled lookup for the phone currently on screen.
 *
 * @param found the matched client's name, or `null` when the base has no client
 *   for that number.
 */
export function walkInNameAfterLookup(
  field: WalkInNameField,
  found: string | null,
): WalkInNameField {
  if (found !== null) return { value: found, fromLookup: found }
  // A miss says «no client for this number», which is a fact about the base —
  // never a verdict on what the operator typed.
  if (isOperatorTypedName(field)) return { value: field.value, fromLookup: null }
  return { value: '', fromLookup: null }
}
