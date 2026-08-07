export interface ChoiceOption {
  value: string
  label: string
  meta?: string
  disabled?: boolean
  /**
   * Draw a hairline above this option. For the one entry that is a different
   * *kind* of choice rather than another item of the same kind — "Yangi
   * ta'minotchi" creates a supplier, the rest select one — so the list says so
   * before it is clicked.
   */
  separator?: boolean
}
