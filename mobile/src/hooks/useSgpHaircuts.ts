/**
 * Each book's fitted same-game parlay cut (lib/sgpPricing.ts).
 *
 * One fetch per app session, shared by every caller: the betslip bar and the
 * Betslip screen must show the same price, so they read the same table. Until
 * it lands — or if it fails — callers get NO_SGP_FITS and the default cut.
 *
 * Plain useEffect, never useFocusEffect: BetslipBar is mounted outside the
 * NavigationContainer (.claude/rules/frontend.md).
 */
import { useEffect, useState } from 'react';

import { fetchSgpHaircuts } from '@/lib/queries';
import { NO_SGP_FITS, type SgpHaircuts } from '@/lib/sgpPricing';

let cached: SgpHaircuts | null = null;
let inflight: Promise<SgpHaircuts> | null = null;
const listeners = new Set<(f: SgpHaircuts) => void>();

function load(): Promise<SgpHaircuts> {
  if (inflight) return inflight;
  inflight = fetchSgpHaircuts()
    .then((rows) => {
      const out: Record<string, { haircut: number; n: number }> = {};
      for (const r of rows) {
        const haircut = Number(r.haircut);
        const n = Number(r.n);
        if (r.book && Number.isFinite(haircut) && Number.isFinite(n)) out[r.book] = { haircut, n };
      }
      cached = Object.freeze(out);
      listeners.forEach((fn) => fn(cached!));
      return cached;
    })
    .catch(() => {
      inflight = null; // a later mount may retry
      return NO_SGP_FITS;
    });
  return inflight;
}

/** Re-read the fits — after a member enters a price. */
export function refreshSgpHaircuts(): void {
  inflight = null;
  void load();
}

export function useSgpHaircuts(): SgpHaircuts {
  const [fits, setFits] = useState<SgpHaircuts>(cached ?? NO_SGP_FITS);
  useEffect(() => {
    listeners.add(setFits);
    if (cached) setFits(cached);
    else void load();
    return () => {
      listeners.delete(setFits);
    };
  }, []);
  return fits;
}

// ── Prices a member typed in from a book's own slip ─────────────────────────
//
// Shared, not screen state: the betslip bar and the Betslip screen must show
// the same number, and the bar is mounted outside the screen. Keyed by the
// slip's signature (its priced legs' slip keys): a price belongs to the slip it
// was read off, so a different slip reads as nothing entered.

let enteredSig = '';
let enteredPrices: Readonly<Record<string, number>> = Object.freeze({});
const enteredListeners = new Set<() => void>();
const EMPTY: Readonly<Record<string, number>> = Object.freeze({});

function setEntered(sig: string, next: Record<string, number>) {
  enteredSig = sig;
  enteredPrices = Object.freeze(next);
  enteredListeners.forEach((fn) => fn());
}

export function useEnteredSgpPrices(sig: string): {
  prices: Readonly<Record<string, number>>;
  enter: (book: string, american: number) => void;
  clear: (book: string) => void;
} {
  const [, bump] = useState(0);
  useEffect(() => {
    const fn = () => bump((n) => n + 1);
    enteredListeners.add(fn);
    return () => {
      enteredListeners.delete(fn);
    };
  }, []);
  const prices = sig !== '' && sig === enteredSig ? enteredPrices : EMPTY;
  return {
    prices,
    enter: (book, american) =>
      setEntered(sig, { ...(sig === enteredSig ? enteredPrices : {}), [book]: american }),
    clear: (book) => {
      if (sig !== enteredSig) return;
      const next = { ...enteredPrices };
      delete next[book];
      setEntered(sig, next);
    },
  };
}
