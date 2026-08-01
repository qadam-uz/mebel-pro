/**
 * The akt sverka's sign convention, derived once.
 *
 * The ledger stores one convention everywhere: **positive = they owe us**. The
 * two sides of the screen then read that same number in opposite directions —
 * on the supplier tab a delivery (stored negative) grows the debt the document
 * is about, on the client tab an order (stored positive) does. Expressed inline
 * per column, that inversion is a money bug waiting to happen, so it lives here
 * and the template only renders what it returns.
 *
 * Parity: backend/app/modules/finance/statement_pdf.py applies the same mapping
 * to the printable document.
 */

import { translate } from '@/shared/i18n'

export type DebtSide = 'suppliers' | 'clients'

/** Which way a balance leans. `settled` is exactly zero — nobody owes anybody. */
export type BalanceDirection = 'they_owe' | 'we_owe' | 'settled'

/** The minimum a statement row must carry to be placed in a column. */
export interface StatementAmounts {
  amount_tiyin: number
  balance_after_tiyin: number
}

export interface StatementLine<T extends StatementAmounts> {
  row: T
  /** The movement that grew the debt, in tiyin — `null` when this row shrank it. */
  debit: number | null
  /** The movement that shrank the debt, in tiyin — `null` when this row grew it. */
  credit: number | null
  /** Running balance as an unsigned figure; `direction` carries the sign. */
  balance: number
  direction: BalanceDirection
  /**
   * True where the direction differs from the previous line — the only moment
   * the direction word carries information rather than repeating itself.
   */
  directionChanged: boolean
}

export function balanceDirection(balanceTiyin: number): BalanceDirection {
  if (balanceTiyin > 0) return 'they_owe'
  if (balanceTiyin < 0) return 'we_owe'
  return 'settled'
}

/** The direction in words. Settled balances say nothing — the zero is the word. */
export function directionLabel(direction: BalanceDirection): string {
  if (direction === 'they_owe') return translate('finance.debts.directionTheyOwe')
  if (direction === 'we_owe') return translate('finance.debts.directionWeOwe')
  return ''
}

/**
 * Turn the stored amount into this side's debit/credit pair.
 *
 * Multiplying by the side's sign is the whole inversion: on the supplier side a
 * stored −10 000 (we received goods) becomes +10 000 of debit.
 */
function debitSign(side: DebtSide): number {
  return side === 'suppliers' ? -1 : 1
}

export function statementLines<T extends StatementAmounts>(
  rows: readonly T[],
  side: DebtSide,
  openingBalanceTiyin: number,
): StatementLine<T>[] {
  const sign = debitSign(side)
  let previous = balanceDirection(openingBalanceTiyin)
  return rows.map((row) => {
    const signed = row.amount_tiyin * sign
    const direction = balanceDirection(row.balance_after_tiyin)
    const line: StatementLine<T> = {
      row,
      debit: signed > 0 ? signed : null,
      credit: signed < 0 ? -signed : null,
      balance: Math.abs(row.balance_after_tiyin),
      direction,
      directionChanged: direction !== previous,
    }
    previous = direction
    return line
  })
}

/** Period turnover mapped onto this side's two columns, in tiyin. */
export function periodTurnover(
  statement: { period_increase_tiyin: number; period_decrease_tiyin: number },
  side: DebtSide,
): { debit: number; credit: number } {
  if (side === 'suppliers') {
    return { debit: statement.period_decrease_tiyin, credit: statement.period_increase_tiyin }
  }
  return { debit: statement.period_increase_tiyin, credit: statement.period_decrease_tiyin }
}
