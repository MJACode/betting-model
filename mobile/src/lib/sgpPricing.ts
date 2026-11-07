/**
 * Same-game parlay (SGP) price estimate.
 *
 * A book prices legs from ONE game together, as a same-game parlay, and pays
 * less than those legs multiplied out. Legs from different games it simply
 * multiplies. No feed we buy publishes the same-game price (Matt, 2026-11-06:
 * the slip showed +5993 / FD +6040 where FanDuel's own slip said +4254), so:
 *
 *   estimate = (legs multiplied at that book) x (1 - cut) ^ sameGameGroups
 *
 * where a same-game group is a game with 2+ legs on the slip. The cut is fitted
 * per book from prices members enter (`sgp_haircuts()`, the median over 120
 * days, data/migrations/add_sgp_price_observations_2026_11_06.sql) once a book
 * has SGP_MIN_OBSERVATIONS of them, and DEFAULT_SGP_HAIRCUT until then.
 *
 * Pure: no React, no network. The hook and the RPCs live in
 * hooks/useSgpHaircuts.ts.
 */
import type { ParlayLeg } from '@/lib/parlay';

/**
 * The cut per same-game group before a book has its own fit. Measured once:
 * the app's FanDuel tile read +6040 (61.40) for two 2-leg same-game groups and
 * FanDuel quoted +4254 (43.54), so 1 - (43.54 / 61.40) ^ (1/2) = 0.158.
 * One slip, one book. It is the starting point, not a property of any book;
 * entered prices replace it.
 */
export const DEFAULT_SGP_HAIRCUT = 0.158;

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

/** How many games on the slip carry 2+ legs. */
export function sameGameGroupCount(legs: readonly ParlayLeg[]): number {
  const counts = new Map<string, number>();
  for (const l of legs) {
    const k = sameGameKey(l);
    if (k == null) continue;
    counts.set(k, (counts.get(k) ?? 0) + 1);
  }
  let groups = 0;
  for (const n of counts.values()) if (n >= 2) groups += 1;
  return groups;
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

/** The cut this book applies per same-game group. */
export function haircutFor(book: string, fits: SgpHaircuts = NO_SGP_FITS): number {
  return fittedHaircut(book, fits) ?? DEFAULT_SGP_HAIRCUT;
}

/**
 * Multiply a book's multiplied-out decimal payout down to its estimated
 * same-game price. Returns the input unchanged when no game has 2+ legs.
 * Never returns a payout at or below 1 (a price that cannot win anything).
 */
export function applySgpHaircut(
  multipliedDecimal: number,
  groups: number,
  book: string,
  fits: SgpHaircuts = NO_SGP_FITS,
): number {
  if (groups <= 0 || !(multipliedDecimal > 1)) return multipliedDecimal;
  const est = multipliedDecimal * Math.pow(1 - haircutFor(book, fits), groups);
  return est > 1 ? est : multipliedDecimal;
}

/**
 * The cut implied by one entered price, the same formula `sgp_haircuts()`
 * applies server-side: 1 - (book / multiplied) ^ (1 / groups).
 */
export function impliedHaircut(bookDecimal: number, multipliedDecimal: number, groups: number): number {
  if (groups <= 0 || !(bookDecimal > 1) || !(multipliedDecimal > 1)) return NaN;
  return 1 - Math.pow(bookDecimal / multipliedDecimal, 1 / groups);
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
