/**
 * Correlation table for the parlay copula engine.
 *
 * Returns the bundled `PARLAY_CORRELATION_PRIORS` immediately (offline fallback),
 * then overlays `source='empirical'` rows from the `parlay_correlations` table
 * once fetched. Empirical coefficients win where present; the priors stand if the
 * fetch fails — the feature never hard-depends on the network. Keyed exactly like
 * the engine's `classPairKey` (sport|classA|classB|teamRel, classes ordered).
 */

import { useEffect, useState } from 'react';
import { PARLAY_CORRELATION_PRIORS, type RhoTable } from '@/lib/parlayCorrelation';
import { fetchParlayCorrelations, type ParlayCorrelationRow } from '@/lib/queries';

function overlay(base: RhoTable, rows: ParlayCorrelationRow[]): RhoTable {
  const merged: RhoTable = { ...base };
  for (const r of rows) {
    const a = r.market_class_a;
    const b = r.market_class_b;
    const [lo, hi] = a <= b ? [a, b] : [b, a]; // mirror classPairKey ordering
    const rho = typeof r.rho === 'string' ? Number(r.rho) : r.rho;
    if (!Number.isFinite(rho)) continue;
    merged[`${r.sport}|${lo}|${hi}|${r.relationship}`] = rho;
  }
  return merged;
}

export function useParlayCorrelations(): RhoTable {
  const [table, setTable] = useState<RhoTable>(PARLAY_CORRELATION_PRIORS);
  useEffect(() => {
    let alive = true;
    fetchParlayCorrelations()
      .then((rows) => {
        if (alive && rows.length > 0) setTable(overlay(PARLAY_CORRELATION_PRIORS, rows));
      })
      .catch(() => {
        /* keep bundled priors on any error (e.g. offline) */
      });
    return () => {
      alive = false;
    };
  }, []);
  return table;
}
