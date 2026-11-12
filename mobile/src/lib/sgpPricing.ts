/**
 * Same-game parlay (SGP) price estimate.
 *
 * A book prices legs from ONE game together, as a same-game parlay, and pays
 * less than those legs multiplied out. Legs from different games it simply
 * multiplies. No feed we buy publishes the same-game price, so:
 *
 *   fair     = (legs multiplied at that book) / max(1, lift)
 *   estimate = 1 + (fair - 1) x (1 - cut) ^ extraLegs
 *
 *   lift       how much more often the legs all hit than multiplied out says,
 *              from the leg correlations (parlayCorrelation.sgpCorrelationLift)
 *   extraLegs  legs past the first in each game with 2+ legs
 *   cut        the book's margin per extra same-game leg, taken off the PROFIT
 *              (a cut off the whole payout drives a short-priced slip to -10000)
 *
 * A lift below 1 (legs that pull against each other) is used for the win %
 * but never raises the price above the legs multiplied out: no book has been
 * seen to pay that, so the estimate does not claim it.
 *
 * History. 2026-11-06 (Matt): +5993 / FD +6040 where FanDuel said +4254, two
 * 2-leg NBA games. The first fix cut 15.8% once per GAME. 2026-11-12 (Matt):
 * a 5-leg WAS@NYG slip showed FD +8037 where FanDuel said +3085, because one
 * game with five legs got the same single cut as one with two, and NFL had no
 * correlations at all. The legs multiplied out at FanDuel are +9564; the
 * measured NFL correlations (lib/propCorrelation.ts) lift the joint chance
 * 1.87x, which takes it to +5080; the rest is the book's margin.
 *
 * The cut is fitted per book from prices members enter (`sgp_haircuts()`, the
 * median over 120 days, data/migrations/sgp_per_leg_cut_2026_11_12.sql) once a
 * book has SGP_MIN_OBSERVATIONS of them, and DEFAULT_SGP_HAIRCUT until then.
 *
 * Pure: no React, no network. The hook and the RPCs live in
 * hooks/useSgpHaircuts.ts.
 */
import type { ParlayLeg } from '@/lib/parlay';

/**
 * The cut per EXTRA same-game leg, off the profit, before a book has its own
 * fit. Two FanDuel slips, both screenshots of FanDuel's own price:
 *   2026-11-06  NBA, 2 extra legs, lift 1 (no NBA line-leg correlation),
 *               fair 61.40, paid 43.54:  1 - (42.54 / 60.40) ^ (1/2)   = 0.161
 *   2026-11-12  NFL, 4 extra legs, lift 1.866 (exact bivariate-normal),
 *               fair 96.64 / 1.866 = 51.79, paid 31.85:
 *                                        1 - (30.85 / 50.79) ^ (1/4)   = 0.119
 * The default is their geometric mean, 1 - sqrt(0.839 x 0.881) = 0.140. Two
 * slips, one book, and it is fitted to the very slips it is checked against:
 * a starting point, not a property of any book. Entered prices replace it.
 */
export const DEFAULT_SGP_HAIRCUT = 0.14;

/** DISTINCT devices (one vote each, sgp_haircuts()) a book needs before its
 *  own fitted cut replaces the default. */
export const SGP_MIN_OBSERVATIONS = 5;

/** A fitted cut is used only inside this band; anything outside is a bad fit. */
const HAIRCUT_FLOOR = 0;
const HAIRCUT_CEILING = 0.6;

export interface SgpHaircut {
  haircut: number;
  n: number;
}

/** Fitted cuts by raw bookmaker key, as `sgp_haircuts()` returns them. */
export type SgpHaircuts = Readonly<Record<string, SgpHaircut>>;

export const NO_SGP_FITS: SgpHaircuts = Object.freeze({});

/** A leg's game for same-game purposes, or null when it has none we know
 *  (a hand-typed custom leg carries a synthetic `custom:` id). */
function sameGameKey(leg: ParlayLeg): string | null {
  const id = leg.gameId;
  if (!id || id.startsWith('custom:')) return null;
  return id;
}

/** A slip's same-game shape. `lift` is 1 here; parlayCorrelation.sgpShapeFor
 *  fills it in from the leg correlations. */
export interface SgpShape {
  /** Games with 2+ legs. */
  groups: number;
  /** Legs past the first in each of those games. */
  extraLegs: number;
  /** P(all legs hit) / (legs multiplied out), at the book's leg prices. */
  lift: number;
}

export function sgpShape(legs: readonly ParlayLeg[]): SgpShape {
  const counts = new Map<string, number>();
  for (const l of legs) {
    const k = sameGameKey(l);
    if (k == null) continue;
    counts.set(k, (counts.get(k) ?? 0) + 1);
  }
  let groups = 0;
  let extraLegs = 0;
  for (const n of counts.values()) {
    if (n >= 2) {
      groups += 1;
      extraLegs += n - 1;
    }
  }
  return { groups, extraLegs, lift: 1 };
}

/** How many games on the slip carry 2+ legs. */
export function sameGameGroupCount(legs: readonly ParlayLeg[]): number {
  return sgpShape(legs).groups;
}

/** This book's own fitted cut, or null when it has too few entries or the
 *  fit is out of band. */
export function fittedHaircut(book: string, fits: SgpHaircuts = NO_SGP_FITS): number | null {
  const fit = fits[book];
  if (
    fit &&
    fit.n >= SGP_MIN_OBSERVATIONS &&
    Number.isFinite(fit.haircut) &&
    fit.haircut >= HAIRCUT_FLOOR &&
    fit.haircut <= HAIRCUT_CEILING
  ) {
    return fit.haircut;
  }
  return null;
}

/** The cut this book applies per extra same-game leg. */
export function haircutFor(book: string, fits: SgpHaircuts = NO_SGP_FITS): number {
  return fittedHaircut(book, fits) ?? DEFAULT_SGP_HAIRCUT;
}

/**
 * Take a book's multiplied-out decimal payout down to its estimated same-game
 * price. Returns the input unchanged when no game has 2+ legs. Never returns a
 * payout at or below 1 (a price that cannot win anything).
 */
export function applySgpHaircut(
  multipliedDecimal: number,
  shape: SgpShape,
  book: string,
  fits: SgpHaircuts = NO_SGP_FITS,
): number {
  if (shape.groups <= 0 || !(multipliedDecimal > 1)) return multipliedDecimal;
  const fair = multipliedDecimal / priceLift(shape.lift);
  return 1 + (fair - 1) * Math.pow(1 - haircutFor(book, fits), shape.extraLegs);
}

/** The lift the PRICE uses: never below 1 (see the header). */
export function priceLift(lift: number): number {
  return lift > 1 && Number.isFinite(lift) ? lift : 1;
}

/**
 * The cut implied by one entered price, the same formula `sgp_haircuts()`
 * applies server-side: 1 - ((book - 1) / (fair - 1)) ^ (1 / extraLegs), with
 * fair = multiplied / max(1, lift).
 */
export function impliedHaircut(bookDecimal: number, multipliedDecimal: number, shape: SgpShape): number {
  if (shape.extraLegs <= 0 || !(bookDecimal > 1) || !(multipliedDecimal > 1)) return NaN;
  const fair = multipliedDecimal / priceLift(shape.lift);
  if (!(fair > 1)) return NaN;
  return 1 - Math.pow((bookDecimal - 1) / (fair - 1), 1 / shape.extraLegs);
}

/** The ratio the server accepts (log_sgp_price), so the app can say "check
 *  that number" instead of sending one the server will refuse. */
export function enteredPriceIsPlausible(bookDecimal: number, multipliedDecimal: number): boolean {
  if (!(bookDecimal > 1) || !(multipliedDecimal > 1)) return false;
  const r = bookDecimal / multipliedDecimal;
  return r >= 0.2 && r <= 1.2;
}

/** American odds typed by a member ("+4254", "4254", "-120"), or null. */
export function parseEnteredAmerican(text: string): number | null {
  const t = text.trim().replace(/,/g, '');
  if (!/^[+-]?\d+$/.test(t)) return null;
  const n = Number(t.replace(/^\+/, ''));
  if (!Number.isFinite(n) || Math.abs(n) < 100) return null;
  return n;
}
