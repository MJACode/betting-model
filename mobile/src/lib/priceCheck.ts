/**
 * "Price check" — usability audit H4 (PR 3). DISPLAY HEURISTICS ONLY.
 *
 * A +3300 moneyline on a 57.8% side (NYY ML, 2026-09-25) is a bad price in the
 * feed, not an edge. It took the top slot of the Edge-sorted board. The root
 * cause was the doubleheader game-id collapse (draft #832). This band only
 * stops a price like that from headlining the board: the card shows "Price
 * check", "—" for edge and EV, and the Edge sort puts it last.
 *
 * Nothing here feeds scoring, thresholds, stakes, `_requalify_at_best`,
 * MAX_EDGE_CAP or any backend. It reads numbers the card already has. Tune
 * the two constants here only; nothing else hard-codes them.
 */

/** Edge above this (a fraction: 0.25 = 25pp) is implausible on the board. */
export const PRICE_CHECK_MAX_EDGE = 0.25;

/**
 * Locked vs current price at the same book, in American-odds cents, above
 * which the lock is implausible. −110 → +110 is 20 cents; +3300 vs −110 is 3,210.
 */
export const PRICE_CHECK_MAX_CENTS = 500;

/**
 * American odds on one continuous "cents" scale: +100 and −100 both sit at 0,
 * so −110 → −10 and +3300 → +3200. The gap between two prices is then a plain
 * subtraction across the even-money gap.
 */
export function americanCents(odds: number): number {
  return odds >= 0 ? odds - 100 : odds + 100;
}

export function centsApart(a: number, b: number): number {
  return Math.abs(americanCents(a) - americanCents(b));
}

export interface PriceCheckInput {
  /** decisionEdge(pick), a fraction. */
  edge: number | null | undefined;
  /** The locked (decision) price. */
  locked: number | null | undefined;
  /** The current price at the same book, when the card has one. */
  current: number | null | undefined;
}

export interface PriceCheck {
  flagged: boolean;
  /** Which rule tripped, for the accessibility label and the tests. */
  reasons: Array<'edge' | 'moved'>;
}

const finite = (n: unknown): n is number => typeof n === 'number' && Number.isFinite(n);

/** Strictly greater than either bound flags; the bound itself does not. */
export function priceCheck({ edge, locked, current }: PriceCheckInput): PriceCheck {
  const reasons: PriceCheck['reasons'] = [];
  if (finite(edge) && edge > PRICE_CHECK_MAX_EDGE) reasons.push('edge');
  if (finite(locked) && finite(current) && centsApart(locked, current) > PRICE_CHECK_MAX_CENTS) {
    reasons.push('moved');
  }
  return { flagged: reasons.length > 0, reasons };
}

/**
 * Stable partition: rows the band flags go to the end, both halves keep their
 * order. The Edge sort applies it so a bad price never headlines the board.
 */
export function flaggedLast<T>(items: T[], isFlagged: (it: T) => boolean): T[] {
  const ok: T[] = [];
  const flagged: T[] = [];
  for (const it of items) (isFlagged(it) ? flagged : ok).push(it);
  return ok.concat(flagged);
}
