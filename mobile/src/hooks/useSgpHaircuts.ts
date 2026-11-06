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
